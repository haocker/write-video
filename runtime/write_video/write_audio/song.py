# -*- coding: utf-8 -*-
"""write_audio.song — 乐谱与渲染引擎（核心）。

设计：引擎只做“渲染”。曲式、和弦、旋律、织体全部由调用者在乐谱里显式给出；
本模块不做任何自动作曲、任何随机决策（同一乐谱 → 逐样本可复现）。

    import write_audio as ca

    s = ca.Song(bpm=124)

    kick = s.track("kick", gain_db=0)
    kick.grid("x|x|x|x", step=1.0)          # 每拍一击

    bass = s.track("bass", gain_db=-4)
    bass.notes([(0, "A1", 1.0), (1, "A1", 0.5), (1.5, "C2", 0.5)])

    s.sidechain("kick", "bass", depth_db=-7)
    s.length(bars=4)
    rep = s.render("out.mp3")

时间坐标一律为“拍”（beat，float）：第 n 小节第 k 拍的拍位置 = (n-1)*每小节拍数 + k。
音符 dur（时值）单位也是拍；perc（鼓）忽略 dur。
"""
import math
import os
import tempfile
import time

import numpy as np

from . import mix as _mix
from .audio import INST, SR, synth_sfx, _norm, _place
from .theory import midi_to_freq, parse_note


# ================================================================ Track

class Track(object):
    """一条轨道（一个乐器 + 一串显式音符事件）。

    音符写法（note / notes / 直接列表均可）：
        (at)                    打击乐：在 at 拍击发一次
        (at, pitch)             音高乐器：pitch = 'A3' / MIDI；poly 可给音名列表
        (at, pitch, dur)        dur = 时值（拍）
        (at, pitch, dur, vel)   vel = 力度 0~1（默认 1.0）
        {"at":..., "pitch":..., "dur":..., "vel":...}  dict 写法
    """

    __slots__ = ("song", "inst", "name", "gain_db", "pan", "seed", "events")

    def __init__(self, song, inst, name, gain_db=0.0, pan=0.0, seed=1):
        self.song = song
        self.inst = inst
        self.name = name
        self.gain_db = float(gain_db)
        self.pan = float(pan)
        self.seed = int(seed)
        self.events = []          # [(at_beats, pitch, dur_beats_or_None, vel)]

    # ---------------- 写音符

    def note(self, at, pitch=None, dur=None, vel=1.0):
        """追加一个音符。"""
        at = float(at)
        if at != at or at < 0:
            raise ValueError("音符位置（拍）必须 >= 0：%r" % (at,))
        if dur is not None:
            dur = float(dur)
            if dur <= 0:
                raise ValueError("音符时值 dur（拍）必须 > 0：%r" % (dur,))
        self.events.append((at, pitch, dur, float(vel)))
        return self

    def notes(self, events):
        """批量追加音符（元组 / dict / 数字写法混合均可）。"""
        for ev in events:
            if isinstance(ev, dict):
                at = ev.get("at")
                if at is None:
                    raise ValueError("音符 dict 缺少 'at'：%r" % (ev,))
                self.note(at, ev.get("pitch"), ev.get("dur"), ev.get("vel", 1.0))
            elif isinstance(ev, (list, tuple)):
                n = len(ev)
                if n == 0 or n > 4:
                    raise ValueError("音符应为 (at[, pitch[, dur[, vel]]])：%r" % (ev,))
                self.note(ev[0],
                          ev[1] if n >= 2 else None,
                          ev[2] if n >= 3 else None,
                          ev[3] if n >= 4 else 1.0)
            elif isinstance(ev, (int, float)) and not isinstance(ev, bool):
                self.note(ev)
            else:
                raise ValueError("无法解析的音符写法：%r（应为数字 / (at,pitch,...) / dict）" % (ev,))
        return self

    def hit(self, at, vel=1.0):
        """击发一次（打击乐/无音高）。"""
        return self.note(at, None, None, vel)

    def hits(self, times, vel=1.0):
        """批量击发（时间列表）。"""
        for t in times:
            self.note(t, None, None, vel)
        return self

    def grid(self, spec, step=0.25, at=0.0, pitch=None, vel=1.0):
        """文本网格谱：每字符一步（step 拍），'x'/'X'/'1'/'*' = 击发，'|' 只分隔不推进。

            例如 kick.grid("x...x...x...x...", step=0.25)  # 四拍，16 分网格
            hat.grid("x|x|x.|x.", step=0.5)              # 八分网格，'|' 为拍线
        """
        t = float(at)
        for ch in str(spec):
            if ch == "|":
                continue
            if ch in "xX1*":
                self.note(t, pitch, None, vel)
            t += float(step)
        return self

    def count(self):
        return len(self.events)

    def last_beat(self):
        """最后一个音符的结束拍（用于估算曲长）。"""
        end = 0.0
        for (at, pitch, dur, vel) in self.events:
            d = dur if dur is not None else _default_dur_beats(self.inst)
            end = max(end, at + d)
        return end


# ================================================================ Song

class Song(object):
    """一支曲子（一叠轨道 + 混音设置 + 渲染）。

    参数：
        bpm           速度（每拍 60/bpm 秒）
        beats_per_bar 每小节拍数（默认 4）
        tail          渲染时在音乐实长之后附加的缓冲秒数（乐尾释放，默认 1.5）
    """

    def __init__(self, bpm=120.0, beats_per_bar=4, tail=1.5):
        self.bpm = float(bpm)
        if self.bpm <= 0:
            raise ValueError("bpm 必须 > 0：%r" % (bpm,))
        self.beats_per_bar = int(beats_per_bar)
        self.tail = float(tail)
        self.tracks = []
        self._length_beats = None
        self._sidechains = []      # [(src, dst, depth_db, release)]
        self._fade_in = None
        self._fade_out = None
        self._rendered = False
        self._report = None

    @property
    def spb(self):
        """每拍秒数。"""
        return 60.0 / self.bpm

    # ---------------- 乐谱构建

    def track(self, inst, name=None, gain_db=0.0, pan=0.0, seed=1):
        """新建并添加一条轨道。

        inst 可用：kick/hat/clap/snare/crash（打击乐）、bass/pluck/bell/rhodes（音高）、
        pad（和弦）、riser/vinyl（过渡/纹理）、以及 19 种音效名（impact/ding/whoosh...）。
        """
        if inst not in INST:
            main = [k for k, v in INST.items() if v["kind"] != "sfx"]
            raise ValueError("未知乐器 %r。\n乐器：%s\n音效：%s"
                             % (inst, "/".join(sorted(main)), "/".join(sorted(set(INST) - set(main)))))
        if name is None:
            name = inst
        base = name
        k = 2
        while any(t.name == name for t in self.tracks):
            name = "%s_%d" % (base, k)
            k += 1
        track = Track(self, inst, name, gain_db=gain_db, pan=pan, seed=seed)
        self.tracks.append(track)
        return track

    def length(self, bars=None, seconds=None, beats=None):
        """显式设定音乐长度（渲染输出 = 此长度 + tail）。三者只能选一。"""
        if sum(x is not None for x in (bars, seconds, beats)) > 1:
            raise ValueError("length 只接受 bars / seconds / beats 之一")
        if bars is not None:
            self._length_beats = float(bars) * self.beats_per_bar
        elif seconds is not None:
            self._length_beats = float(seconds) / self.spb
        elif beats is not None:
            self._length_beats = float(beats)
        return self

    def sidechain(self, source, target, depth_db=-7.0, release=0.18):
        """侧链：source 轨的每个音符触发 target 轨的闪避。depth_db 负值（越负压越深）。

        source / target 可给 Track 对象或轨名字。重复调用叠加（多个源取更深）。
        """
        if depth_db > 0:
            raise ValueError("depth_db 应为负值（如 -7 = 压 7 dB）")
        if release <= 0:
            raise ValueError("release（秒）必须 > 0")
        self._sidechains.append((source, target, float(depth_db), float(release)))
        return self

    def fade(self, in_seconds=None, out_seconds=None):
        """整曲渐入/渐出（秒）。也可在 render 时用同名参数。"""
        if in_seconds is not None:
            self._fade_in = float(in_seconds)
        if out_seconds is not None:
            self._fade_out = float(out_seconds)
        return self

    # ---------------- 查询

    def _find_track(self, ref):
        if isinstance(ref, Track):
            return ref
        for t in self.tracks:
            if t.name == ref:
                return t
        raise ValueError("找不到轨道 %r（已定义：%s）" % (ref, "/".join(t.name for t in self.tracks)))

    def music_beats(self):
        """音乐实长（拍）：最后一个音符结束点与 length 下限的较大值。"""
        end = 0.0
        for trk in self.tracks:
            end = max(end, trk.last_beat())
        if self._length_beats is not None:
            end = max(end, self._length_beats)
        return end

    def stats(self):
        """乐谱摘要（不渲染）。"""
        beats = self.music_beats()
        tracks = []
        for trk in self.tracks:
            events = trk.events
            tracks.append({
                "name": trk.name, "inst": trk.inst, "notes": len(events),
                "first": events[0][0] if events else None,
                "last": trk.last_beat() if events else None,
                "gain_db": trk.gain_db, "pan": trk.pan,
            })
        return {
            "bpm": self.bpm, "beats_per_bar": self.beats_per_bar,
            "beats": round(beats, 3),
            "bars": round(beats / self.beats_per_bar, 2),
            "seconds": round(beats * self.spb, 3),
            "tail": self.tail,
            "sidechains": [(_name(x), _name(y), d, r) for (x, y, d, r) in self._sidechains],
            "tracks": tracks,
        }

    # ---------------- 渲染

    def render(self, out=None, wav=None, stems=None, lufs=-14.0, ceiling=0.72,
               bitrate=192, keep_wav=False, gain_db=0.0, fade_in=None, fade_out=None,
               tail=None, title=None):
        """渲染并输出。

        out     输出路径（.mp3 或 .wav；默认 track.mp3）
        wav     额外/指定 wav 输出路径
        stems   分轨目录（每轨一个 <轨名>.wav，未经母带，不含增益/声像/侧链）
        lufs    响度目标（默认 -14，流媒体标准）
        bitrate mp3 码率（kbps，默认 192）
        fade_in / fade_out  整曲渐入/渐出（秒）
        tail    乐尾缓冲秒数（默认 = Song.tail）
        返回报告 dict。
        """
        t_start = time.time()
        if out is None and wav is None and stems is None:
            out = "track.mp3"
        if not self.tracks:
            raise ValueError("乐谱尚未添加任何轨道（用 song.track(...) 添加）")
        total_notes = sum(len(t.events) for t in self.tracks)
        if total_notes == 0:
            raise ValueError("乐谱里没有任何音符，无法渲染")

        spb = self.spb
        music_beats = self.music_beats()
        dur_s = music_beats * spb
        tail_s = self.tail if tail is None else float(tail)
        n = int(round((dur_s + tail_s) * SR))

        # 1) 逐轨渲染
        bufs = {}
        track_reps = []
        for trk in self.tracks:
            buf = self._render_track(trk, n, n / float(SR))
            bufs[trk.name] = buf
            peak = float(np.max(np.abs(buf))) if len(buf) else 0.0
            track_reps.append({
                "name": trk.name, "inst": trk.inst, "notes": len(trk.events),
                "gain_db": trk.gain_db, "pan": trk.pan,
                "peak_db": round(20.0 * math.log10(peak), 1) if peak > 1e-9 else None,
            })

        # 2) 侧链闪避包络
        ducks = self._build_ducks(n)

        # 3) 立体声混音（等功率声像）
        mix_l = np.zeros(n, dtype=np.float32)
        mix_r = np.zeros(n, dtype=np.float32)
        for trk in self.tracks:
            buf = bufs[trk.name]
            if not len(trk.events):
                continue
            env = ducks.get(trk.name)
            if env is not None:
                buf = buf * env
            g = 10.0 ** (trk.gain_db / 20.0)
            gl, gr = _pan_gains(trk.pan)
            mix_l += buf * (g * gl)
            mix_r += buf * (g * gr)
        mixx = np.stack([mix_l, mix_r], axis=1)

        # 4) 整曲淡化
        fin = self._fade_in if fade_in is None else fade_in
        fout = self._fade_out if fade_out is None else fade_out
        if fin:
            mixx = _mix._fade_in(mixx, float(fin))
        if fout:
            mixx = _mix._fade_out(mixx, float(fout))
        mixx = _mix._fade_tail(mixx, 120.0)

        # 5) 母带 + 输出
        ff = None
        try:
            ff = _mix.find_ffmpeg()
        except Exception:
            ff = None

        tmp_wav = None
        if wav:
            wav_path = wav
        elif out and out.lower().endswith(".wav"):
            wav_path = out
        else:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="write_audio_")
            os.close(fd)
            wav_path = tmp_wav
        d = os.path.dirname(os.path.abspath(wav_path))
        if d:
            os.makedirs(d, exist_ok=True)

        rep = {"bpm": self.bpm, "beats": round(music_beats, 3),
               "bars": round(music_beats / self.beats_per_bar, 2),
               "seconds": round(n / float(SR), 2),
               "tracks": track_reps,
               "sidechains": [(_name(x), _name(y), dd, rr) for (x, y, dd, rr) in self._sidechains]}
        rep.update(_mix.master(mixx, wav_path, ffmpeg=ff, target_lufs=lufs,
                               gain_db=gain_db, ceiling=ceiling))
        if not tmp_wav:
            rep["wav"] = os.path.abspath(wav_path)

        if out and out.lower().endswith(".mp3"):
            if ff:
                d = os.path.dirname(os.path.abspath(out))
                if d:
                    os.makedirs(d, exist_ok=True)
                if _mix.write_mp3(wav_path, out, ff, bitrate=bitrate, title=title):
                    rep["mp3"] = os.path.abspath(out)
                    rep["mp3_bytes"] = os.path.getsize(out)
                else:
                    rep["mp3_error"] = "mp3 编码失败（ffmpeg 缺少 mp3 编码器？）"
            else:
                rep["mp3_error"] = "找不到 ffmpeg，未输出 mp3"

        # 6) 分轨
        if stems:
            os.makedirs(stems, exist_ok=True)
            names = []
            for trk in self.tracks:
                if not len(trk.events):
                    continue
                buf = bufs[trk.name]
                if float(np.max(np.abs(buf))) < 1e-5:
                    continue
                p = os.path.join(stems, _safe_filename(trk.name) + ".wav")
                _mix.write_wav(p, _norm(buf, 0.9))
                names.append(p)
            rep["stems"] = names

        if tmp_wav and keep_wav:
            rep["wav"] = os.path.abspath(tmp_wav)
        elif tmp_wav:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass
        rep["render_seconds"] = round(time.time() - t_start, 1)
        self._rendered = True
        self._report = rep
        return rep

    # ---------------- 内部

    def _render_track(self, trk, n, total_s):
        buf = np.zeros(n, dtype=np.float32)
        if not trk.events:
            return buf
        spec = INST[trk.inst]
        kind = spec["kind"]
        fn = spec.get("fn")
        default_dur_s = spec.get("dur", 0.0) * self.spb
        for (at, pitch, dur, vel) in trk.events:
            t0 = at * self.spb
            seed = trk.seed + int(round(at * 331.0))
            dur_s = (dur * self.spb) if dur is not None else None
            if kind == "perc":
                sig = fn(seed=seed)
            elif kind == "tone":
                f = _tone_freq(trk, at, pitch)
                sig = fn(f, dur_s if dur_s is not None else default_dur_s, seed)
            elif kind == "poly":
                freqs = _poly_freqs(trk, at, pitch)
                sig = fn(freqs, dur_s if dur_s is not None else default_dur_s, seed)
            elif kind == "riser":
                sig = fn(dur_s if dur_s is not None else default_dur_s, seed)
            elif kind == "texture":
                d = dur_s if dur_s is not None else max(0.0, total_s - t0)
                m = int(d * SR)
                if m <= 0:
                    continue
                sig = fn(m, seed)
            elif kind == "sfx":
                sig = synth_sfx(trk.inst, gain=0.0, dur=dur_s, pitch=_sfx_shift(trk, at, pitch), seed=seed)
            else:
                raise ValueError("未知乐器类型 kind=%r（乐器 %r）" % (kind, trk.inst))
            _place(buf, t0, sig, vel)
        return buf

    def _build_ducks(self, n):
        envs = {}
        for (src, dst, depth_db, release) in self._sidechains:
            src_track = self._find_track(src)
            dst_name = self._find_track(dst).name
            amount = 1.0 - 10.0 ** (float(depth_db) / 20.0)
            rel_n = max(1, int(float(release) * SR))
            env = envs.get(dst_name)
            if env is None:
                env = np.ones(n, dtype=np.float32)
                envs[dst_name] = env
            base = np.exp(-np.arange(rel_n, dtype=np.float32) / (float(release) * SR))
            for ev in src_track.events:
                i0 = int(round(ev[0] * self.spb * SR))
                if i0 >= n:
                    continue
                m = min(rel_n, n - i0)
                if m > 0:
                    env[i0:i0 + m] = np.minimum(env[i0:i0 + m], 1.0 - amount * base[:m])
        return envs


# ================================================================ 工具

def _default_dur_beats(inst):
    spec = INST.get(inst, {})
    if spec.get("kind") == "texture":
        return 0.0
    if "dur" in spec:
        return spec["dur"]
    # perc / sfx：按各自典型长度估（仅用于曲长估算）
    return 0.5


def _pan_gains(pan):
    """等功率声像：pan -1(左)..1(右) → (gL, gR)。居中 = (0.707, 0.707)。"""
    p = max(-1.0, min(1.0, float(pan)))
    a = (p + 1.0) * 0.25 * math.pi
    return math.cos(a), math.sin(a)


def _name(ref):
    return ref.name if isinstance(ref, Track) else str(ref)


def _safe_filename(name):
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "track"


def _tone_freq(trk, at, pitch):
    if pitch is None:
        raise ValueError("轨道 %r 在拍 %s 的音符缺少音高（该乐器需要音名或 MIDI，如 'A3' / 57）"
                         % (trk.name, round(float(at), 3)))
    return midi_to_freq(parse_note(pitch))


def _poly_freqs(trk, at, pitch):
    if pitch is None:
        raise ValueError("轨道 %r 在拍 %s 的音符缺少音高（pad 需要音名或音名列表，如 ca.chord('Am7', 3)）"
                         % (trk.name, round(float(at), 3)))
    ps = pitch if isinstance(pitch, (list, tuple)) else [pitch]
    return [midi_to_freq(parse_note(x)) for x in ps]


def _sfx_shift(trk, at, pitch):
    if pitch is None:
        return 0.0
    if isinstance(pitch, bool) or isinstance(pitch, str):
        raise ValueError("轨道 %r（音效）在拍 %s 的 pitch 应为半音移调数值（如 0 / 12 / -5）：%r"
                         % (trk.name, round(float(at), 3), pitch))
    return float(pitch)
