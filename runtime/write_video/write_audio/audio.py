# -*- coding: utf-8 -*-
"""write_audio.audio — 音源层：合成工具 / 19 种音效 / 乐器。

全部为确定性合成（噪声用固定 seed，同参数 → 逐样本可复现）。
乐谱渲染见 song.py；乐理工具见 theory.py。

乐器注册表 INST：
    kind="perc"    打击乐（无音高；dur 忽略，音频长度固定）
    kind="tone"    单音音高乐器（pitch 必填；dur = 音符时值，拍）
    kind="poly"    和弦音色（pitch 可给音名列表）
    kind="riser"   扫频过渡（dur = 扫频长度）
    kind="texture" 整轨纹理（音符 dur 缺省 = 到曲终）
    kind="sfx"     19 种音效单发（pitch = 半音移调）
"""
import math

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


# ================================================================ 音效（19 种）

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
    """合成一个音效，返回 float32 单声道数组（含 gain，单位 dB）。"""
    fn = SFX.get(name)
    if fn is None:
        raise ValueError("未知音效 %r（可用：%s）" % (name, ", ".join(sorted(set(SFX)))))
    x = fn(gain=gain, pitch=pitch, dur=dur, seed=seed)
    return (x * (10.0 ** (float(gain) / 20.0))).astype(np.float32)


# ================================================================ 乐器

def _i_kick(dur=0.4, seed=1):
    n = int(dur * SR)
    x = _sweep(150.0, 45.0, n) * _exp_decay(n, 7.5)
    click = _hp(_noise(n, seed), 3000) * _exp_decay(n, 140) * 0.35
    return _norm(x + click, 0.9)


def _i_hat(seed=1, dur=0.07):
    n = int(dur * SR)
    x = _hp(_noise(n, seed), 7000) * _exp_decay(n, 90)
    return _norm(x, 0.28)


def _i_clap(seed=1):
    n = int(0.22 * SR)
    out = np.zeros(n, dtype=np.float32)
    for k in range(3):
        off = int(k * 0.011 * SR)
        m = n - off
        seg = _hp(_noise(m, seed + k), 1000) * _exp_decay(m, 38) * (1.0 - k * 0.22)
        out[off:] += seg.astype(np.float32)
    return _norm(out, 0.4)


def _i_snare(seed=1):
    n = int(0.2 * SR)
    tone = _sine(196.0, n) * _exp_decay(n, 28) * 0.35
    noise = _hp(_noise(n, seed), 1400) * _exp_decay(n, 20) * 0.9
    return _norm(tone + noise, 0.55)


def _i_bass(f, dur, seed=1):
    n = int(dur * SR)
    t = _t(n)
    x = (2.0 * ((f * t) % 1.0) - 1.0) * 0.6 + (2.0 * ((f * 1.008 * t) % 1.0) - 1.0) * 0.4
    x = _lp(x, 880) * _exp_decay(n, 4.5) * _ad(n, 0.005, 0.03)
    return (x * 0.5).astype(np.float32)


def _i_pluck(f, dur, seed=1):
    n = int(dur * SR)
    x = _sine(f, n) * 0.6 + _sine(f * 2.0, n) * 0.22 + _sine(f * 3.01, n) * 0.08
    x = x * _exp_decay(n, 9.0) * _ad(n, 0.002, 0.05)
    return (x * 0.42).astype(np.float32)


def _i_bell(f, dur, seed=1):
    n = int(dur * SR)
    x = _sine(f, n) + _sine(f * 2.76, n) * 0.4 + _sine(f * 5.4, n) * 0.15
    x = x * _exp_decay(n, 3.2) * _ad(n, 0.002, 0.15)
    return (x * 0.4).astype(np.float32)


def _i_pad(freqs, dur, seed=1, bright=1600.0):
    n = int(dur * SR)
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    x = np.zeros(n, dtype=np.float32)
    for f in freqs:
        for det in (0.9965, 1.0, 1.0035):
            ph = rng.uniform(0.0, math.pi * 2)
            x += _sine(f * det, n, ph) * 0.3
    x = _lp(x, bright)
    x = x * _ad(n, min(0.8, dur * 0.2), min(0.8, dur * 0.3)) * 0.22
    return x.astype(np.float32)


def _i_rhodes(f, dur, seed=1):
    n = int(dur * SR)
    t = _t(n)
    x = _sine(f, n) + _sine(f * 2.0, n) * 0.42 + _sine(f * 3.0, n) * 0.12
    x = x * np.exp(-1.6 * t) * _ad(n, 0.008, 0.3)
    x = x * (1.0 + 0.16 * np.sin(2.0 * math.pi * 4.6 * t))
    return (x * 0.4).astype(np.float32)


def _i_vinyl(n, seed=1):
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    base = _lp(_noise(n, seed), 5200) * 0.06
    for _ in range(int(n / SR * 6)):
        i0 = rng.randint(0, max(1, n - 400))
        seg = min(300, n - i0)
        base[i0:i0 + seg] += _sine(rng.uniform(900.0, 4000.0), seg) * _exp_decay(seg, 260) * rng.uniform(0.1, 0.35)
    return base.astype(np.float32)


def _i_crash(seed=1, dur=1.7):
    """镲片 / 段落撞击：高频噪声 + 金属分音，长衰减。"""
    n = int(dur * SR)
    x = _hp(_noise(n, seed), 3200) * _exp_decay(n, 2.6)
    pal = (4186.0, 5274.0, 6317.0, 7840.0, 10465.0)
    for i, f in enumerate(pal):
        x = x + _sine(f, n) * _exp_decay(n, 2.0 + 0.3 * i) * (0.30 - 0.045 * i)
    x = x * _ad(n, 0.002, 0.45)
    return _norm(x, 0.5)


def _i_riser(dur, seed=1, f0=160.0, f1=1500.0):
    """过渡上升音：扫频 + 逐步打开的高频噪声 + 加速颤音。"""
    n = int(dur * SR)
    if n < 2:
        return np.zeros(max(0, n), dtype=np.float32)
    w = (_t(n) / max(1e-3, float(dur))) ** 2.2
    tone = _sweep(f0, f1, n) * w * 0.5
    noise = _hp(_lp(_noise(n, seed), 9000), 500) * w * 0.6
    trem = 0.72 + 0.28 * np.sin(2.0 * math.pi * (5.0 + 16.0 * _t(n) / max(1e-3, float(dur))) * _t(n))
    x = (tone + noise) * trem * _ad(n, 0.1, 0.05)
    return _norm(x, 0.75)


# ================================================================ 乐器注册表

INST = {
    # 打击乐（无音高；dur 忽略，音频长度固定）
    "kick":  {"kind": "perc", "fn": _i_kick},
    "hat":   {"kind": "perc", "fn": _i_hat},
    "clap":  {"kind": "perc", "fn": _i_clap},
    "snare": {"kind": "perc", "fn": _i_snare},
    "crash": {"kind": "perc", "fn": _i_crash},

    # 音高乐器（pitch 必填；dur = 音符时值/拍，默认见 dur 字段）
    "bass":   {"kind": "tone", "fn": _i_bass,   "dur": 1.0},
    "pluck":  {"kind": "tone", "fn": _i_pluck,  "dur": 0.5},
    "bell":   {"kind": "tone", "fn": _i_bell,   "dur": 1.5},
    "rhodes": {"kind": "tone", "fn": _i_rhodes, "dur": 1.5},

    # 和弦垫（pitch 可给音名列表，如 ca.chord("Am7", 3)）
    "pad": {"kind": "poly", "fn": _i_pad, "dur": 4.0},

    # 过渡 / 纹理
    "riser": {"kind": "riser", "fn": _i_riser, "dur": 1.5},
    "vinyl": {"kind": "texture", "fn": _i_vinyl},
}

# 19 种音效也作为单发音源可用（kind="sfx"）：pitch = 半音移调（默认 0）
for _k in sorted(set(SFX)):
    INST.setdefault(_k, {"kind": "sfx"})
