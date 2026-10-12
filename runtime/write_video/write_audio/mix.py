# -*- coding: utf-8 -*-
"""write_audio — 输出链：ffmpeg 定位 / 响度测量 / 软限幅 / wav / mp3 / 母带（master）。

支持单声道 (n,) 与立体声 (n,2)：write_wav / master / fade 工具均兼容两种形状。
decode_audio 为峰值安全下混（0.5L+0.5R，避免 ffmpeg -ac 1 对双单声道放大 √2）。
"""
import json
import os
import shutil
import subprocess
import wave

import numpy as np

SR = 48000


def find_ffmpeg():
    p = os.environ.get("CA_FFMPEG") or os.environ.get("CF_FFMPEG")
    if p and os.path.exists(p):
        return p
    p = shutil.which("ffmpeg")
    if p:
        return p
    cands = []
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        cands.append(os.path.join(la, "Microsoft", "WinGet", "Links", "ffmpeg.exe"))
        cands.append("C:/ffmpeg/bin/ffmpeg.exe")
        try:
            import glob
            cands += glob.glob(os.path.join(la, "aardio", "ffmpeg-static", "**", "ffmpeg.exe"), recursive=True)
        except Exception:
            pass
    else:
        cands += ["/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise RuntimeError("找不到 ffmpeg。安装：Windows `winget install ffmpeg`；macOS `brew install ffmpeg`；Linux `apt install ffmpeg`；"
                       "或用环境变量 CA_FFMPEG 指定完整路径。")


def _ffmpeg():
    return find_ffmpeg()



def decode_audio(path, ffmpeg=None):
    """把任意音频文件解码成 48kHz 单声道 float32。

    下混策略：先统一为立体声（单声道会自动复制为双声道），再按 0.5L+0.5R 平均——
    对双声道一致的素材不会虚增峰值（ffmpeg 的 `-ac 1` 会把双单声道信号放大 √2）。
    """
    ff = ffmpeg or _ffmpeg()
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0 or not r.stdout:
        return None
    x = np.frombuffer(r.stdout, dtype=np.float32).copy()
    if len(x) % 2 == 0:
        x = x.reshape(-1, 2).mean(axis=1)
    return np.asarray(x, dtype=np.float32)



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
    """写 16bit PCM wav。x 支持单声道 (n,) 或立体声 (n,2)。"""
    x = np.clip(np.asarray(x, dtype=np.float32), -1.0, 1.0)
    pcm = (x * 32767.0).astype(np.int16)
    if pcm.ndim == 1:
        stereo = np.repeat(pcm[:, None], 2, axis=1).ravel()
    else:
        stereo = np.ascontiguousarray(pcm).ravel()
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


def _fade_edges(x, ms=10.0):
    """首尾微淡化，避免咔哒声（支持单声道/立体声）。"""
    n = int(ms / 1000.0 * SR)
    if n <= 0 or n * 2 >= len(x):
        return x
    y = x.copy()
    w = np.linspace(0.0, 1.0, n, dtype=np.float32)
    if y.ndim == 2:
        w = w[:, None]
    y[:n] *= w
    y[-n:] *= w[::-1]
    return y


def _fade_tail(x, ms=260.0):
    """尾部渐隐（支持单声道/立体声）。"""
    n = int(ms / 1000.0 * SR)
    if n <= 0 or n >= len(x):
        return x
    y = x.copy()
    w = (np.linspace(0.0, 1.0, n, dtype=np.float32) ** 1.5)[::-1]
    if y.ndim == 2:
        w = w[:, None]
    y[-n:] *= w
    return y


def _fade_in(x, seconds):
    """开头渐入（支持单声道/立体声）。"""
    n = min(int(float(seconds) * SR), len(x))
    if n <= 0:
        return x
    y = x.copy()
    w = np.linspace(0.0, 1.0, n, dtype=np.float32) ** 1.5
    if y.ndim == 2:
        w = w[:, None]
    y[:n] *= w
    return y


def _fade_out(x, seconds):
    """结尾渐出（支持单声道/立体声）。"""
    n = min(int(float(seconds) * SR), len(x))
    if n <= 0:
        return x
    y = x.copy()
    w = (np.linspace(0.0, 1.0, n, dtype=np.float32) ** 1.5)[::-1]
    if y.ndim == 2:
        w = w[:, None]
    y[-n:] *= w
    return y


def master(x, out_wav, ffmpeg=None, target_lufs=-14.0, gain_db=0.0, ceiling=0.76):
    """响度归一（目标 LUFS）+ 软限幅，写出最终 wav，返回报告 dict。"""
    x = np.asarray(x, dtype=np.float32)
    info = None
    if ffmpeg:
        write_wav(out_wav, x)
        info = measure_loudness(out_wav, ffmpeg)
    g = float(gain_db)
    if info and info["i"] is not None and info["i"] > -70:
        g += float(target_lufs) - float(info["i"])
        y = _soft_peak(x * (10.0 ** (g / 20.0)), ceiling=ceiling)
    else:
        m = float(np.max(np.abs(x))) if len(x) else 0.0
        y = x * (0.9 / m) if m > 1e-9 else x
    y = _fade_edges(y, 10.0)
    write_wav(out_wav, y)
    rep = {"gain_db": round(float(g), 2), "lufs": None, "tp": None}
    if ffmpeg:
        final = measure_loudness(out_wav, ffmpeg)
        if final:
            rep["lufs"] = round(float(final["i"]), 1)
            rep["tp"] = round(float(final["tp"]), 1)
    return rep


def write_mp3(wav_path, mp3_path, ffmpeg, bitrate=192, title=None):
    """把 wav 编码为 mp3（libmp3lame，失败回退内置 mp3 编码器）。"""
    for enc in ("libmp3lame", "mp3"):
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", wav_path, "-vn",
               "-c:a", enc, "-b:a", "%dk" % int(bitrate)]
        if title:
            cmd += ["-metadata", "title=%s" % title]
        cmd += [mp3_path]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode == 0 and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1024:
            return True
    return False
