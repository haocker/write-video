# -*- coding: utf-8 -*-
"""MO · 动效时间库（移植自 huashu-art-motion lib/motion.js，8 支解说示范片的统一缓动/节奏层）。

全部为 t/p → 数值的纯函数：确定性、不读时钟，帧种子可复现。
p 是 0..1 进度；t/lt 是秒；节拍/时长单位秒。
配套镜头库见 syntax.py 的 Cam/cam_track；8 种解说语法 scaffold 见 syntax.py。
"""
import math

PULSE = {"punch": 0.28, "pan": 0.30, "slam": 0.17, "k": 0.25, "kMin": 0.18,
         "kMax": 0.32, "push": 0.9, "glide": 0.7, "pull": 1.1}


def clamp(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def lerp(a, b, u):
    return a + (b - a) * u


# ---------- 时间片 ----------


def seg(t, a, b):
    """[a,b] 区间映射 0..1。"""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def at(t, t0, dur):
    """t0 起 dur 秒内 0..1。"""
    if dur <= 0:
        return 1.0 if t >= t0 else 0.0
    return clamp((t - t0) / dur)


def step(t, fps=12):
    """一拍二步进：拼贴纸片/打字/荧光笔 12fps，故事角色 24fps，相机保持平滑。"""
    return math.floor(t * fps + 1e-6) / fps


def beat(n, bpm=120):
    """第 n 个四分拍 → 秒。"""
    return n * 60.0 / bpm


def on_beat(bar_time, reveal_p, tr_dur):
    """对位公式：段起点 = 小节线 − 揭开点 × 转场时长（揭开帧落在拍上）。
    zoom 揭开点 .55、色带 .6、push 90% 位移 .58。"""
    return bar_time - reveal_p * tr_dur


# ---------- 解析缓动 ----------


def linear(p):
    return clamp(p)


def smooth(p):
    """manim 默认：6t⁵−15t⁴+10t³，两端速度加速度都为 0。"""
    t = clamp(p)
    return t * t * t * (10.0 - 15.0 * t + 6.0 * t * t)


def sine_in_out(p):
    return -(math.cos(math.pi * clamp(p)) - 1.0) / 2.0


def cubic_in(p):
    t = clamp(p)
    return t * t * t


def cubic_out(p):
    t = clamp(p)
    return 1.0 - (1.0 - t) ** 3


def cubic_in_out(p):
    t = clamp(p)
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def quart_out(p):
    t = clamp(p)
    return 1.0 - (1.0 - t) ** 4


def quint_out(p):
    t = clamp(p)
    return 1.0 - (1.0 - t) ** 5


def quint_in_out(p):
    t = clamp(p)
    if t < 0.5:
        return 16.0 * t ** 5
    return 1.0 - ((-2.0 * t + 2.0) ** 5) / 2.0


def expo_in(p):
    t = clamp(p)
    if t <= 0:
        return 0.0
    return 2.0 ** (10.0 * t - 10.0)


def expo_out(p):
    t = clamp(p)
    if t >= 1:
        return 1.0
    return 1.0 - 2.0 ** (-10.0 * t)


def expo_in_out(p):
    t = clamp(p)
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    if t < 0.5:
        return 2.0 ** (20.0 * t - 10.0) / 2.0
    return (2.0 - 2.0 ** (-20.0 * t + 10.0)) / 2.0


def back_out(p, s=1.70158):
    """过冲回弹：s=1.70158≈10%、2.2≈13%、2.6≈17%、3.5≈23%。"""
    q = clamp(p) - 1.0
    return 1.0 + (s + 1.0) * q * q * q + s * q * q


def elastic_out(p):
    t = clamp(p)
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 2.0 ** (-10.0 * t) * math.sin((t * 10.0 - 0.75) * (2.0 * math.pi / 3.0)) + 1.0


def there_and_back(p):
    t = clamp(p)
    return smooth(2.0 * t if t < 0.5 else 2.0 * (1.0 - t))


def rush_into(p):
    return 2.0 * smooth(clamp(p) / 2.0)


def rush_from(p):
    return 2.0 * smooth(clamp(p) / 2.0 + 0.5) - 1.0


def double_smooth(p):
    t = clamp(p)
    if t < 0.5:
        return 0.5 * smooth(2.0 * t)
    return 0.5 * (1.0 + smooth(2.0 * t - 1.0))


def wiggle(p, wiggles=2.0):
    return there_and_back(p) * math.sin(wiggles * math.pi * clamp(p))


def lagged(i, n, p, r=0.05):
    """LaggedStart：第 i 个（0 基）占 [i·r, i·r+1]，总长 1+(n-1)·r。"""
    return clamp(p * (1.0 + (n - 1) * r) - i * r)


# ---------- cubic-bezier（牛顿迭代） ----------


def _bez_coeffs(x1, y1, x2, y2):
    cx = 3.0 * x1
    bx = 3.0 * (x2 - x1) - cx
    ax = 1.0 - cx - bx
    cy = 3.0 * y1
    by = 3.0 * (y2 - y1) - cy
    ay = 1.0 - cy - by
    return ax, bx, cx, ay, by, cy


def bezier(x1, y1, x2, y2):
    """cubic-bezier 缓动工厂（8 次牛顿迭代，容差 1e-6）。"""
    ax, bx, cx, ay, by, cy = _bez_coeffs(x1, y1, x2, y2)

    def f(p):
        if p <= 0:
            return 0.0
        if p >= 1:
            return 1.0
        s = p
        for _ in range(8):
            x = ((ax * s + bx) * s + cx) * s - p
            if abs(x) < 1e-6:
                break
            d = (3.0 * ax * s + 2.0 * bx) * s + cx
            if abs(d) < 1e-6:
                break
            s -= x / d
        s = clamp(s)
        return ((ay * s + by) * s + cy) * s
    return f


apple_out = bezier(0.25, 0.1, 0.25, 1.0)
emphasized = bezier(0.2, 0.0, 0.0, 1.0)
k75 = bezier(0.75, 0.0, 0.25, 1.0)
easy_ease = bezier(0.333, 0.0, 0.667, 1.0)
long_tail = bezier(0.33, 0.0, 0.2, 1.0)


# ---------- 弹簧与微动 ----------


def spring(t, duration=0.5, bounce=0.0, v0=0.0):
    """SwiftUI 参数化弹簧（0→1 位移，可 >1 过冲）。bounce 0 临界 / 0.15 利落 / 0.3 明显。"""
    if t <= 0:
        return 0.0
    w = 2.0 * math.pi / max(1e-4, duration)
    z = 1.0 - clamp(bounce)
    if abs(z - 1.0) < 1e-4:
        x = math.exp(-w * t) * (1.0 + (w - v0) * t)
    elif z < 1.0:
        wd = w * math.sqrt(1.0 - z * z)
        x = math.exp(-z * w * t) * (math.cos(wd * t) + ((z * w - v0) / wd) * math.sin(wd * t))
    else:
        r = z * math.sqrt(z * z - 1.0) + z * z - 1.0
        r = math.sqrt(max(0.0, z * z - 1.0))
        a = -w * (z - r)
        b = -w * (z + r)
        A = (-v0 - b) / (a - b)
        x = A * math.exp(a * t) + (1.0 - A) * math.exp(b * t)
    return 1.0 - x


def spring_hz(t, freq=2.5, decay=9.0):
    """欠阻尼弹簧（频率/衰减参数化）：freq 3/decay 6 ≈37% 过冲、2.5/9 ≈16%、2.2/10 ≈8%。"""
    if t <= 0:
        return 0.0
    return 1.0 - math.exp(-decay * t) * math.cos(2.0 * math.pi * freq * t)


def settle(t, amp, freq=3.0, decay=5.0):
    """到位后的余振（惯性回弹）：amp·sin(2πft)/e^(decay·t)。身体挤压、屏幕震动。"""
    if t <= 0:
        return 0.0
    return amp * math.sin(2.0 * math.pi * freq * t) / math.exp(decay * t)


def pulse(t, t0, dur=None, ease=None):
    """t0 起 dur 秒内按 ease 0→1，之后停在 1。"""
    dur = PULSE["punch"] if dur is None else dur
    ease = cubic_in_out if ease is None else ease
    return ease(at(t, t0, dur))


def float_(t, amp=6.0, period=4.0, ph=0.0):
    """两频正弦叠加漂浮；周期避开 5s 左右（HIG ~0.2Hz 让人不适）。"""
    return amp * (0.75 * math.sin(2.0 * math.pi * t / period + ph)
                  + 0.25 * math.sin(2.0 * math.pi * t / (period * 0.53) + ph * 1.7))


def invert(ease, y, iters=30):
    """缓动反查：二分求 ease(m)=y 的 m。用途：折线按 smooth 画，求画到某 x 的时刻。"""
    y = clamp(y)
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if ease(mid) < y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ---------- 砸入 ----------


def slam_k(k, frm=1.55, under=0.94):
    """砸入曲线：k≤0 在 from，前 60% from→under 线性砸下，后 40% under→1 回弹。
    t2 进屏轻砸用 (1.06, 0.985)，大数字用 (1.35, 0.96)。"""
    if k <= 0:
        return frm
    if k < 0.6:
        return frm - (frm - under) * (k / 0.6)
    if k < 1.0:
        return under + (1.0 - under) * ((k - 0.6) / 0.4)
    return 1.0


def slam(t, t0, dur=None, frm=1.55, under=0.94):
    """t0 时刻砸入：t<t0 返回 0（未触发），t≥t0 返回缩放倍率。"""
    dur = PULSE["slam"] if dur is None else dur
    if t < t0:
        return 0.0
    return slam_k((t - t0) / dur, frm, under)
