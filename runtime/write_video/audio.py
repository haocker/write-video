# -*- coding: utf-8 -*-
"""write-video — 声音：音效合成、配乐渲染、混音与响度归一。

- 音效：numpy 现场合成（19 种，48kHz 单声道），不依赖音频素材；
- 配乐：由可替换的渲染模块（`write_audio/`）渲染——该模块只做渲染，
  曲式/和弦/旋律/配器/音量全部由影片脚本显式写出，无风格模板、无随机预设；
- 混音 / 闪避 / 响度：本模块，把三条来源（配乐、配音、音效）合成一条 48kHz 单声道。
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

SR = 48000

# ================================================================ 基础工具

def _t(n):
    return np.arange(n, dtype=np.float32) / float(SR)


def _exp_decay(n, k):
    return np.exp(-float(k) * np.arange(n, dtype=np.float32) / float(SR))


def _ad(n, attack, release):
    e = np.ones(n, dtype=np.float32)
    a = max(1, min(n, int(attack * SR)))
    e[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32) ** 1.5
    r = max(1, min(n, int(release * SR)))
    e[n - r:] *= (np.linspace(0.0, 1.0, r, dtype=np.float32) ** 1.5)[::-1]
    return e


def _noise(n, seed=1):
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    return rng.uniform(-1.0, 1.0, n).astype(np.float32)


def _sine(freq, n, phase=0.0):
    return np.sin(2.0 * math.pi * float(freq) * _t(n) + float(phase)).astype(np.float32)


def _sweep(f0, f1, n):
    """指数扫频。"""
    if n < 2:
        return np.zeros(max(0, n), dtype=np.float32)
    T = n / float(SR)
    if abs(f1 - f0) < 1e-6 or f0 <= 0:
        return _sine(max(f0, 1e-3), n)
    r = float(f1) / float(f0)
    t = _t(n)
    ph = 2.0 * math.pi * f0 * T / math.log(r) * (np.exp(t / T * math.log(r)) - 1.0)
    return np.sin(ph).astype(np.float32)


def _lp(x, fc):
    fc = min(float(fc), SR * 0.49)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    H = 1.0 / np.sqrt(1.0 + (f / max(1.0, fc)) ** 2)
    return np.fft.irfft(X * H, len(x)).astype(np.float32)


def _hp(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    r = f / max(1.0, float(fc))
    H = r / np.sqrt(1.0 + r * r)
    return np.fft.irfft(X * H, len(x)).astype(np.float32)


def _norm(x, peak=0.9):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    if m < 1e-9:
        return np.asarray(x, dtype=np.float32)
    return (x * (float(peak) / m)).astype(np.float32)


def _place(buf, t, sig, gain=1.0):
    i0 = int(round(t * SR))
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    if i0 >= len(buf) or len(sig) == 0:
        return
    m = min(len(buf) - i0, len(sig))
    buf[i0:i0 + m] += sig[:m] * float(gain)


# ================================================================ 音效

def _s_impact(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.8
    n = int(dur * SR)
    k = 2.0 ** (pitch / 12.0)
    thump = _sweep(140 * k, 46 * k, n) * _exp_decay(n, 6.5)
    sub = _sine(46 * k, n) * _exp_decay(n, 3.0) * 0.6
    click = _hp(_noise(n, seed), 2500) * _exp_decay(n, 90) * 0.5
    rumble = _lp(_noise(n, seed + 1), 220) * _exp_decay(n, 2.6) * 0.18
    return _norm(thump + sub + click + rumble, 0.95)


def _s_punch(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.4
    n = int(dur * SR)
    k = 2.0 ** (pitch / 12.0)
    body = _sweep(190 * k, 60 * k, n) * _exp_decay(n, 10.0)
    click = _hp(_noise(n, seed), 3000) * _exp_decay(n, 130) * 0.4
    return _norm(body + click, 0.9)


def _s_pop(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.16
    n = int(dur * SR)
    k = 2.0 ** (pitch / 12.0)
    body = _sweep(320 * k, 780 * k, n) * _exp_decay(n, 34)
    click = _hp(_noise(n, seed), 4000) * _exp_decay(n, 200) * 0.25
    return _norm(body + click, 0.85)


def _s_swish(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.28
    n = int(dur * SR)
    x = _lp(_hp(_noise(n, seed), 700), 4200) * (_ad(n, 0.05, 0.16) ** 1.2)
    return _norm(x, 0.5)


def _s_whoosh(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.5
    n = int(dur * SR)
    x_lo = _lp(_noise(n, seed), 600)
    x_hi = _hp(_lp(_noise(n, seed + 1), 5000), 1200)
    w = np.linspace(0.0, 1.0, n, dtype=np.float32)
    x = x_lo * (1.0 - w) * _ad(n, 0.12, 0.25) + x_hi * w * _ad(n, 0.2, 0.15)
    return _norm(x, 0.6)


def _s_click(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.05
    n = int(dur * SR)
    k = 2.0 ** (pitch / 12.0)
    x = _sine(1500 * k, n) * _exp_decay(n, 120) * 0.7 + _hp(_noise(n, seed), 3000) * _exp_decay(n, 180) * 0.3
    return _norm(x, 0.55)


def _s_tick(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.04
    n = int(dur * SR)
    x = _sine(2600, n) * _exp_decay(n, 150)
    return _norm(x, 0.35)


def _s_ding(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.9
    n = int(dur * SR)
    k = 2.0 ** (pitch / 12.0)
    x = _sine(880 * k, n) + _sine(1320 * k, n) * 0.4 + _sine(2640 * k, n) * 0.12
    x = x * _exp_decay(n, 4.0) * _ad(n, 0.004, 0.1)
    return _norm(x, 0.6)


def _s_chime(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 1.2
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    for i, f in enumerate((659.25, 830.61, 987.77)):
        off = int(i * 0.11 * SR)
        m = n - off
        sig = (_sine(f, m) + _sine(f * 2, m) * 0.3) * _exp_decay(m, 3.4) * _ad(m, 0.004, 0.2)
        out[off:] += sig * (1.0 - i * 0.18)
    return _norm(out, 0.65)


def _s_success(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.5
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    for i, f in enumerate((659.25, 987.77)):
        off = int(i * 0.12 * SR)
        m = n - off
        out[off:] += _sine(f, m) * _exp_decay(m, 5.0) * _ad(m, 0.003, 0.15)
    return _norm(out, 0.65)


def _s_error(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.4
    n = int(dur * SR)
    x = (_sine(220, n) + _sine(233, n)) * 0.5 * _exp_decay(n, 7.0) * _ad(n, 0.004, 0.12)
    return _norm(x, 0.5)


def _s_riser(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 1.2
    n = int(dur * SR)
    w = (_t(n) / dur) ** 2.0
    tone = _sweep(180, 900, n) * w
    noise = _hp(_lp(_noise(n, seed), 8000), 400) * w * 0.9
    x = (tone * 0.5 + noise * 0.5) * _ad(n, 0.05, 0.02)
    return _norm(x, 0.7)


def _s_glitch(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.3
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    pos = 0
    while pos < n - 240:
        seg = min(int(rng.uniform(0.008, 0.03) * SR), n - pos)
        blip = _noise(seg, seed + pos) * rng.uniform(0.3, 1.0)
        if rng.uniform() < 0.5:
            blip = blip * _sine(rng.uniform(300.0, 2400.0), seg)
        out[pos:pos + seg] += blip.astype(np.float32)
        pos += seg + int(rng.uniform(0.004, 0.03) * SR)
    out = _hp(out, 300) * _ad(n, 0.004, 0.06)
    return _norm(out, 0.5)


def _s_sparkle(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.8
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    for _ in range(7):
        f = rng.uniform(1400.0, 4200.0)
        off = int(rng.uniform(0.0, 0.25) * SR)
        m = n - off
        sig = _sine(f, m) * _exp_decay(m, rng.uniform(5.0, 10.0)) * _ad(m, 0.002, 0.1)
        out[off:] += sig * rng.uniform(0.3, 1.0)
    return _norm(out, 0.5)


def _s_notification(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.7
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    for i, f in enumerate((880.0, 1174.66)):
        off = int(i * 0.14 * SR)
        m = n - off
        sig = (_sine(f, m) + _sine(f * 2, m) * 0.2) * _exp_decay(m, 4.5) * _ad(m, 0.003, 0.15)
        out[off:] += sig
    return _norm(out, 0.6)


def _s_typing(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 1.0
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    t = 0.0
    while t < dur:
        i0 = int(t * SR)
        m = min(int(0.03 * SR), n - i0)
        if m <= 0:
            break
        click = _sine(rng.uniform(1700.0, 2400.0), m) * _exp_decay(m, 160)
        thunk = _sine(rng.uniform(180.0, 260.0), m) * _exp_decay(m, 90) * 0.3
        out[i0:i0 + m] += (click * 0.5 + thunk).astype(np.float32) * rng.uniform(0.5, 1.0)
        t += rng.uniform(0.055, 0.1)
    return _norm(out, 0.45)


def _s_bassdrop(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 1.0
    n = int(dur * SR)
    x = _sweep(220, 38, n) * _exp_decay(n, 1.6) * _ad(n, 0.01, 0.2)
    return _norm(x, 0.8)


def _s_shutter(gain=0.0, pitch=0.0, dur=None, seed=1):
    dur = dur or 0.18
    n = int(dur * SR)
    x = _hp(_noise(n, seed), 1800) * _exp_decay(n, 45) + _sine(1200, n) * _exp_decay(n, 120) * 0.3
    return _norm(x, 0.6)


SFX = {
    "impact": _s_impact, "punch": _s_punch, "pop": _s_pop, "swish": _s_swish, "swipe": _s_swish,
    "whoosh": _s_whoosh, "click": _s_click, "tick": _s_tick, "ding": _s_ding, "chime": _s_chime,
    "success": _s_success, "error": _s_error, "riser": _s_riser, "glitch": _s_glitch,
    "sparkle": _s_sparkle, "notification": _s_notification, "typing": _s_typing,
    "bassdrop": _s_bassdrop, "shutter": _s_shutter,
}


def synth_sfx(name, gain=0.0, dur=None, pitch=0.0, seed=1):
    """合成一个音效，返回float32单声道数组（含gain）。"""
    fn = SFX.get(name)
    if fn is None:
        raise ValueError("未知音效 %r（可用：%s）" % (name, ", ".join(sorted(set(SFX)))))
    x = fn(gain=gain, pitch=pitch, dur=dur, seed=seed)
    return (x * (10.0 ** (float(gain) / 20.0))).astype(np.float32)


# ================================================================ 配乐（只渲染，不含模板）
# 配乐渲染由可替换的模块负责（当前实现以源码形式放在 runtime/write_video/write_audio/）。
# 该模块只做渲染：曲式、和弦、旋律、配器、音量全部由乐谱显式给出，没有风格模板、没有随机预设。
# 乐谱由影片脚本（film.py）用 wa.Song / wa.Track 直接写，见 knowledge/compose.md。


def render_score(score, duration, gain_db=0.0, lufs=-14.0):
    """渲染一份乐谱，返回 float32 单声道数组（48kHz，长度 >= duration）。

    score   Song 对象（由调用方显式写好音符）
    其余参数：整轨额外增益（dB）与响度目标。

    只做"渲染 → 读回 → 补齐/截断到片长"这件事，不做任何编曲决策。
    """
    import tempfile
    from . import write_audio as wa
    if not isinstance(score, wa.Song):
        raise TypeError("render_score 需要 Song 对象，收到 %r" % (type(score),))
    if not score.tracks:
        raise ValueError("乐谱里没有任何声部（用 song.track(...) 添加）")

    tmpdir = tempfile.mkdtemp(prefix="write_video_score_")
    wav_path = os.path.join(tmpdir, "score.wav")
    try:
        score.render(wav=wav_path, lufs=lufs)
        x = _read_wav_mono(wav_path)
    finally:
        try:
            os.remove(wav_path)
            os.rmdir(tmpdir)
        except OSError:
            pass

    n = int((duration + 1.0) * SR)
    if x is None or len(x) == 0:
        return np.zeros(n, dtype=np.float32)
    if len(x) < n:
        x = np.concatenate([x, np.zeros(n - len(x), dtype=np.float32)])
    else:
        x = x[:n]
    if gain_db:
        x = x * (10.0 ** (float(gain_db) / 20.0))
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 1e-3:
        x = x * (0.85 / peak)
    return np.asarray(x, dtype=np.float32)



def _read_wav_mono(path):
    """读 wav → 48kHz 单声道 float32（0.5L+0.5R 峰值安全下混）。"""
    try:
        w = wave.open(path, "rb")
    except Exception:
        return None
    try:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    finally:
        w.close()
    if sw != 2:
        return None
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if nch >= 2:
        x = x.reshape(-1, nch).mean(axis=1)
    if sr != SR and len(x) > 1:
        idx = np.linspace(0.0, len(x) - 1.0, int(round(len(x) * SR / float(sr))))
        x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return x


# ================================================================ 混音 / 输出

def _ffmpeg():
    from .render import find_ffmpeg
    return find_ffmpeg()


def decode_audio(path, ffmpeg=None):
    """把任意音频文件解码成 48kHz 单声道 float32。"""
    ff = ffmpeg or _ffmpeg()
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0 or not r.stdout:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


# ================================================================ 配音（外部声音）

DUCK_DB = -8.0        # 配音时配乐压低约 8dB
DUCK_LEAD = 0.15      # 开口前开始压
DUCK_TAIL = 0.25      # 说完保持
DUCK_RELEASE = 0.6    # 回升时间
DUCK_MERGE = 1.0      # 两段间隔不足 1 秒时不回升

_VOICE_CACHE = {}


def trim_silence(x, thresh_db=-50.0, pad=0.03):
    """去掉首尾静音。

    返回 (裁剪后数组, 头部裁掉的秒数)；整段静音返回 (None, 0)。
    头部秒数用于补偿词时间（词时间以文件开头为参照）。
    """
    if x is None or len(x) == 0:
        return None, 0.0
    thr = 10.0 ** (float(thresh_db) / 20.0)
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return None, 0.0
    n_pad = int(pad * SR)
    i0 = max(0, int(idx[0]) - n_pad)
    i1 = min(len(x), int(idx[-1]) + 1 + n_pad)
    return x[i0:i1], i0 / float(SR)


def _fade_edges(x, ms=12.0):
    n = int(ms / 1000.0 * SR)
    if n <= 0 or n * 2 >= len(x):
        return x
    w = np.linspace(0.0, 1.0, n, dtype=np.float32) ** 1.4
    y = x.copy()
    y[:n] *= w
    y[-n:] *= w[::-1]
    return y


def prepare_voice(path, gain_db=0.0, target_lufs=-16.0, ffmpeg=None):
    """解码外部声音 → 去首尾静音 → 响度对齐（-16 LUFS）→ 边缘淡化。

    返回 (float32 数组, 头部裁掉的秒数)；失败抛异常（调用方转成 lint error）。
    结果按 (路径, mtime, gain) 缓存在进程内。
    """
    key = None
    try:
        key = (os.path.abspath(path), os.path.getmtime(path), round(float(gain_db), 3))
        hit = _VOICE_CACHE.get(key)
        if hit is not None:
            return hit
    except OSError:
        key = None
    x = decode_audio(path, ffmpeg=ffmpeg)
    if x is None or not len(x):
        raise RuntimeError("ffmpeg 解码失败（文件损坏或不是音频）")
    x, lead = trim_silence(x)
    if x is None:
        raise RuntimeError("整段静音")
    x = _fade_edges(x)
    ff = ffmpeg or _ffmpeg()
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="write_video_voice_")
        os.close(fd)
        write_wav(tmp, x)
        info = measure_loudness(tmp, ff)
        g = float(gain_db)
        if info and info["i"] is not None and info["i"] > -70:
            g += float(target_lufs) - info["i"]
        y = x * (10.0 ** (g / 20.0))
        y = np.asarray(_soft_peak(y), dtype=np.float32)
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    out = (y, lead)
    if key is not None:
        if len(_VOICE_CACHE) > 16:
            _VOICE_CACHE.clear()
        _VOICE_CACHE[key] = out
    return out


def _build_duck(n, voices):
    """配音时间线 → 配乐闪避包络（正常 1.0，压低时 DUCK_DB 电平）。"""
    lvl = 10.0 ** (DUCK_DB / 20.0)
    ivs = sorted([[max(0.0, v.at), max(0.0, v.done)] for v in voices])
    merged = []
    for iv in ivs:
        if merged and iv[0] - merged[-1][1] < DUCK_MERGE:
            merged[-1][1] = max(merged[-1][1], iv[1])
        else:
            merged.append(list(iv))
    env = np.ones(n, dtype=np.float32)
    for t0, t1 in merged:
        i_a = max(0, int((t0 - DUCK_LEAD) * SR))
        i_b = min(n, max(0, int(t0 * SR)))
        i_c = min(n, max(0, int((t1 + DUCK_TAIL) * SR)))
        i_d = min(n, max(0, int((t1 + DUCK_TAIL + DUCK_RELEASE) * SR)))
        if i_b > i_a:
            env[i_a:i_b] = np.minimum(env[i_a:i_b],
                                      np.linspace(1.0, lvl, i_b - i_a, dtype=np.float32))
        if i_c > i_b:
            env[i_b:i_c] = np.minimum(env[i_b:i_c], np.float32(lvl))
        if i_d > i_c:
            env[i_c:i_d] = np.minimum(env[i_c:i_d],
                                      np.linspace(lvl, 1.0, i_d - i_c, dtype=np.float32))
    return env


def mix_tracks(film):
    """把配乐、配音与全部音效混成一个 float32 单声道数组。

    配音段只看配乐（自动闪避），音效不受影响。
    """
    dur = film.duration + 0.9
    n = int(dur * SR)
    mix = np.zeros(n, dtype=np.float32)
    voices = [v for v in getattr(film, "_voices", []) if getattr(v, "buf", None) is not None]
    m = film.music
    if m:
        # 配乐来源二选一：
        #   ① 乐谱（wa.Song 对象）—— 乐谱由影片脚本自己写；
        #   ② 现成音频文件路径（循环铺满全片）。
        gain = 0.0
        if isinstance(m, dict):
            gain = float(m.get("gain", 0.0))
            m = m.get("score", m.get("file"))
        from . import write_audio as wa
        is_score = isinstance(m, wa.Song)
        if is_score:
            music = render_score(m, film.duration, gain_db=gain)
            mix += music[:n]
        elif isinstance(m, str) and os.path.exists(m):
            data = decode_audio(m)
            if data is not None and len(data):
                reps = int(math.ceil(n / float(len(data))))
                mix += np.tile(data, reps)[:n] * (10.0 ** (gain / 20.0))
        else:
            print("[write-video] film.music 未被识别（%s）——配乐已跳过；"
                  "score 需传 wa.Song 对象（勿传 sc.render() 的报告 dict）或音频文件路径"
                  % (type(m).__name__,))
    if voices:
        mix *= _build_duck(n, voices)
        for v in voices:
            _place(mix, v.at, v.buf)
    for item in film._sfx_all:
        t, name, g, mdur, pitch = item
        sig = synth_sfx(name, gain=g, dur=mdur, pitch=pitch, seed=int(t * 977) + 1)
        _place(mix, t, sig)
    return mix


def _soft_peak(x, ceiling=0.82, knee=0.62):
    """软限幅：超过 knee 的部分用 tanh 压向 ceiling（保住响度、防止削波）。"""
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    if m <= ceiling:
        return x
    mag = np.abs(x)
    over = mag > knee
    if not bool(over.any()):
        return (x * (ceiling / m)).astype(np.float32)
    head = ceiling - knee
    y = np.where(over, knee + head * np.tanh((mag - knee) / head), mag)
    ymax = float(np.max(y))
    if ymax > ceiling:
        y = y * (ceiling / ymax)
    return (np.sign(x) * y).astype(np.float32)


def write_wav(path, x, sr=SR):
    x = np.clip(np.asarray(x, dtype=np.float32), -1.0, 1.0)
    pcm = (x * 32767.0).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1).ravel()
    w = wave.open(path, "wb")
    try:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())
    finally:
        w.close()


def measure_loudness(wav_path, ffmpeg):
    cmd = [ffmpeg, "-hide_banner", "-i", wav_path, "-af", "loudnorm=I=-16:TP=-1.5:print_format=json", "-f", "null", "-"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    txt = r.stderr.decode("utf-8", "ignore")
    i, j = txt.rfind("{"), txt.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        data = json.loads(txt[i:j + 1])
        return {"i": float(data.get("input_i")), "tp": float(data.get("input_tp"))}
    except Exception:
        return None


def build_audio_track(film, wav_path, ffmpeg, target_lufs=-16.0):
    """合成、归一（响度对齐 -16 LUFS）并写出 wav，返回统计。"""
    mix = mix_tracks(film)
    write_wav(wav_path, mix)
    if len(mix) == 0:
        return {"lufs": -200.0, "tp": -200.0, "count": 0, "gain": 0.0}
    info = measure_loudness(wav_path, ffmpeg)
    gain_db = 0.0
    if info and info["i"] is not None and info["i"] > -70:
        gain_db = target_lufs - info["i"]
        mix = mix * (10.0 ** (gain_db / 20.0))
        mix = _soft_peak(mix)
        write_wav(wav_path, mix)
    final = measure_loudness(wav_path, ffmpeg)
    lufs = final["i"] if final else (info["i"] + gain_db if info and info["i"] is not None else -200.0)
    tp = final["tp"] if final else -200.0
    return {"lufs": round(lufs, 1), "tp": round(tp, 1), "count": len(film._sfx_all),
            "voices": len(getattr(film, "_voices", [])), "gain": round(gain_db, 1)}
