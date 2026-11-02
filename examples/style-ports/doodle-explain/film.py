# -*- coding: utf-8 -*-
"""《简笔画蒙娜丽莎》 — doodle-explain · 5 页图解 / 46s
框架：先画后说 / 一页一论点 / 停顿是参数 / 换页显式（整页上滑）
  页1 画她 + 名字
  页2 材质与尺寸（标注 + 尺寸线）
  页3 三个谜（圈 + 引线）
  页4 1911 被盗（时间线 + 带走画的小人）
  页5 现在的展柜（玻璃 + 人流）
运行: python3 film.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           os.path.abspath(os.path.join(HERE, "..", "..", "runtime")),
           os.path.abspath(os.path.join(HERE, "..", "..", "..", "runtime"))):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import write_video as wv

W, H = 1920, 1080
SS = 2
OUT = os.path.join(HERE, "artifacts")

INK = (42, 36, 30)
INK_SOFT = (108, 99, 88)
ACCENT = (188, 82, 62)
PAPER = (247, 244, 236)

OFFSET = (0.0, 0.0)
BOIL = 0

# 画框（世界=屏幕坐标）
FX0, FY0, FW, FH = 560.0, 140.0, 560.0, 800.0
FX1, FY1 = FX0 + FW, FY0 + FH
HCX, HCY = 840.0, 430.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def noise1(x, seed):
    i = math.floor(x)
    f = x - i
    a = hash1(i * 1.7 + seed * 13.13)
    b = hash1((i + 1) * 1.7 + seed * 13.13)
    return a + (b - a) * (f * f * (3 - 2 * f))


def seg(t, t0, d, ease=True):
    """局部进程 0..1。"""
    u = clamp((t - t0) / d, 0.0, 1.0)
    return smooth(u) if ease else u


def blend(c, a, bg=PAPER):
    if a >= 0.999:
        return c
    a = max(0.0, min(1.0, a))
    return tuple(int(round(bg[i] * (1.0 - a) + c[i] * a)) for i in range(3))


# ---------------------------------------------------------------- 手绘线
def _truncate(pts, p):
    if p >= 0.999:
        return pts
    if p <= 0.001:
        return []
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = L[-1] * p
    out = [pts[0]]
    for i in range(1, len(pts)):
        if L[i] <= total:
            out.append(pts[i])
        else:
            d = L[i] - L[i - 1]
            u = (total - L[i - 1]) / (d or 1.0)
            out.append((lerp(pts[i - 1][0], pts[i][0], u), lerp(pts[i - 1][1], pts[i][1], u)))
            break
    return out


def stroke(d, pts, width=6.0, color=INK, prog=1.0, seed=0.0, alpha=1.0, jit=1.0):
    pts = _truncate(list(pts), prog)
    if len(pts) < 2:
        return
    ox, oy = OFFSET
    sp = [(x + ox, y + oy) for x, y in pts]
    out = []
    for i in range(1, len(sp)):
        x0, y0 = sp[i - 1]
        x1, y1 = sp[i]
        ln = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(ln / (4.5 / SS)))
        for q in range(n + (1 if i == len(sp) - 1 else 0)):
            u = q / n
            out.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u))
    if len(out) < 2:
        return
    amp = (width * 0.05 + jit * 0.85) * 0.62
    sd = seed * 7.31 + BOIL * 1.77
    dev = []
    for i, (x, y) in enumerate(out):
        j1 = (noise1(i * 0.09 + seed * 3.3, sd) - 0.5) * 2.0
        j2 = (noise1(i * 0.021 + seed * 1.7, sd + 41.0) - 0.5) * 2.0
        dev.append(((x + (j1 + j2 * 1.5) * amp) * SS, (y + (j1 * 0.9 + j2 * 1.2) * amp) * SS))
    col = blend(color, alpha)
    w = max(1, int(round(width * SS)))
    d.line(dev, fill=col, width=w, joint="curve")
    r = w * 0.5
    for (cx, cy) in (dev[0], dev[-1]):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def head_of(pts, prog):
    p = _truncate(list(pts), prog)
    return p[-1] if p else None


def circle_pts(cx, cy, r, n=28, a0=-2.2, ry=None):
    ry = r if ry is None else ry
    return [(cx + math.cos(a0 + i / n * math.tau) * r,
             cy + math.sin(a0 + i / n * math.tau) * ry) for i in range(n + 1)]


def arc_pts(cx, cy, r, a0, a1, n=16, ry=None):
    ry = r if ry is None else ry
    return [(cx + math.cos(lerp(a0, a1, i / n)) * r,
             cy + math.sin(lerp(a0, a1, i / n)) * ry) for i in range(n + 1)]


# ---------------------------------------------------------------- 手写字
_FONTS = {}


def _font(px):
    k = max(8, int(round(px)))
    if k not in _FONTS:
        _FONTS[k] = wv.fonts.load("sans_bold", k)
    return _FONTS[k]


def hand_text(im, s, x, y, size, prog=1.0, seed=0.0, color=INK, align="center",
              alpha=1.0, wob=1.0):
    """y 视为文字底部锚。"""
    ox, oy = OFFSET
    px = max(8.0, size * SS)
    f = _font(px)
    widths = [f.getlength(ch) for ch in s]
    total = sum(widths)
    sx = (x + ox) * SS
    sy = (y + oy) * SS
    cx = sx - total / 2.0 if align == "center" else (sx - total if align == "right" else sx)
    n_show = int(math.ceil(prog * len(s) - 1e-6))
    for i, ch in enumerate(s[:max(0, n_show)]):
        adv = widths[i]
        a = clamp(prog * len(s) - i, 0.0, 1.0)
        if ch.strip():
            jx = (noise1(i * 3.1 + seed, seed + BOIL) - 0.5) * px * 0.09 * wob
            jy = (noise1(i * 5.7 + seed + 9, seed + BOIL) - 0.5) * px * 0.14 * wob
            rot = (noise1(i * 7.3 + seed, seed + 4 + BOIL) - 0.5) * 9.0 * wob
            g = Image.new("RGBA", (int(adv) + 14, int(px * 1.55) + 14), (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            gd.text((7, 7), ch, font=f, fill=color + (int(255 * alpha * a),))
            g = g.rotate(rot, resample=Image.BICUBIC, expand=False)
            im.alpha_composite(g, (int(cx + jx) - 7, int(sy - px * 1.12 + jy) - 7))
        cx += adv


def pencil(d, x, y, ang, ln=44.0, alpha=1.0):
    dx, dy = math.cos(ang), math.sin(ang)
    stroke(d, [(x - dx * ln, y - dy * ln), (x, y)], 3.2, (64, 55, 46), 1, 71, alpha, 0.4)
    stroke(d, [(x - dx * ln, y - dy * ln), (x - dx * (ln + 7), y - dy * (ln + 7))],
           4.8, (216, 158, 108), 1, 73, alpha, 0.3)
    stroke(d, [(x - dx * 8, y - dy * 8), (x, y)], 2.8, (28, 24, 20), 1, 77, alpha, 0.25)


# ---------------------------------------------------------------- 纸
_PAPER = None


def paper_img():
    global _PAPER
    if _PAPER is not None:
        return _PAPER
    rng = np.random.default_rng(5)
    hh, ww = H * SS // 4, W * SS // 4
    fib = rng.normal(0, 1.0, (hh, ww))
    fib = (fib - fib.min()) / float(np.ptp(fib) + 1e-6)
    fib = np.array(Image.fromarray((fib * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.1)), np.float32) / 255.0
    base = np.array(PAPER, np.float32)
    a = np.empty((hh, ww, 3), np.float32)
    for c in range(3):
        a[..., c] = base[c] - 6 + fib * 12
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((W * SS, H * SS), Image.BICUBIC)
    d = ImageDraw.Draw(img, "RGBA")
    r2 = np.random.default_rng(9)
    for _ in range(240):
        x, y = r2.uniform(0, W * SS), r2.uniform(0, H * SS)
        d.ellipse([x, y, x + 3, y + 3], fill=(200, 190, 172, 22))
    _PAPER = img.convert("RGBA")
    return _PAPER


# ---------------------------------------------------------------- 蒙娜丽莎（简笔）
def draw_mona(d, t, s=1.0, cx=HCX, cy=HCY, detail=1.0, alpha=1.0, bg=True, hands=True):
    """t 为本地时间；s 缩放；返回当前笔尖。"""
    tip = None

    def A(pts):
        return [(cx + (x - HCX) * s, cy + (y - HCY) * s) for x, y in pts]

    def put(pts, w, t0, dur, seed, color=INK, a=alpha):
        nonlocal tip
        p = seg(t, t0, dur)
        if p > 0:
            stroke(d, A(pts), w, color, p, seed, a, 1.0)
        if 0 < p < 1:
            tip = head_of(A(pts), p)

    # 背景：两条不在同一高度的地平线 + 水边短笔
    if bg:
        put([(586, 646), (668, 640), (762, 648)], 4.2, 0.20, 0.5, 11, INK_SOFT, alpha * 0.7)
        put([(912, 610), (1000, 604), (1094, 612)], 4.2, 0.38, 0.5, 13, INK_SOFT, alpha * 0.7)
        put([(700, 684), (760, 678), (818, 686)], 3.0, 0.55, 0.4, 15, INK_SOFT, alpha * 0.4)
        put([(884, 682), (942, 676), (1000, 684)], 3.0, 0.65, 0.4, 17, INK_SOFT, alpha * 0.4)

    # 头
    put(circle_pts(840, 420, 96, 26, ry=122), 6.0, 0.85, 0.7, 21)
    # 头发（外轮廓两束 + 头顶）
    put([(752, 330), (726, 402), (726, 520), (744, 642)], 6.2, 1.40, 0.5, 23)
    put([(928, 330), (954, 402), (954, 520), (936, 642)], 6.2, 1.52, 0.5, 25)
    put([(752, 330), (790, 292), (840, 284), (890, 292), (928, 330)], 6.2, 1.62, 0.5, 27)
    # 面纱
    put([(772, 352), (840, 342), (908, 352)], 3.2, 2.05, 0.35, 29, INK_SOFT, alpha * 0.75)
    # 颈
    put([(808, 546), (804, 606)], 5.2, 2.05, 0.28, 31)
    put([(872, 546), (876, 606)], 5.2, 2.12, 0.28, 33)
    # 肩与衣
    put([(804, 606), (742, 646), (676, 706), (640, 776)], 5.8, 2.25, 0.42, 35)
    put([(876, 606), (938, 646), (1004, 706), (1040, 776)], 5.8, 2.36, 0.42, 37)
    put(arc_pts(840, 664, 66, 0.30, math.pi - 0.30, 14, 52), 4.2, 2.62, 0.36, 39, INK_SOFT, alpha * 0.85)
    # 手臂（袖子）
    if hands:
        put([(640, 776), (688, 836), (760, 872)], 5.2, 2.85, 0.42, 41)
        put([(1040, 776), (992, 836), (920, 872)], 5.2, 2.94, 0.42, 43)
    # 脸
    if detail > 0.3:
        put(circle_pts(812, 411, 4.0, 10), 3.4, 3.28, 0.16, 45)
        put(circle_pts(866, 411, 4.0, 10), 3.4, 3.35, 0.16, 47)
        put([(840, 418), (834, 462), (847, 468)], 3.6, 3.44, 0.28, 49)
        # 嘴：全片最重要的一笔，慢
        put(arc_pts(840, 496, 27, 0.25, math.pi - 0.25, 14, 11), 5.2, 3.70, 0.55, 51)
    # 交叠的手
    if hands:
        put([(752, 872), (806, 892), (862, 880), (906, 892)], 5.0, 4.05, 0.42, 53)
        put([(790, 898), (840, 878), (890, 896)], 4.4, 4.22, 0.32, 55)
    return tip


def draw_frame(d, t, t0=0.3, dur=0.6, seed=61, w=6.4, alpha=1.0, gap=None):
    pts = [(FX0, FY0), (FX1, FY0), (FX1, FY1), (FX0, FY1), (FX0, FY0)]
    p = seg(t, t0, dur)
    if p > 0:
        stroke(d, pts, w, INK, p, seed, alpha, 0.7)


# ---------------------------------------------------------------- 页 1：她是谁
def page1(t):
    im = Image.new("RGBA", (W * SS, H * SS), PAPER + (255,))
    d = ImageDraw.Draw(im, "RGBA")
    draw_frame(d, t, 0.35, 0.55)
    tip = draw_mona(d, t)
    if tip:
        pencil(d, tip[0], tip[1], -2.2, 44)
    # 先画后说
    hand_text(im, "蒙娜丽莎", 1480, 300, 92, seg(t, 4.55, 1.0), 3.1)
    hand_text(im, "MONA LISA", 1480, 372, 30, seg(t, 5.3, 0.7), 7.3, INK_SOFT, "center", 0.95)
    hand_text(im, "列奥纳多·达·芬奇", 1480, 452, 44, seg(t, 5.9, 0.9), 11.7)
    hand_text(im, "约 1503 — 1519 年", 1480, 508, 34, seg(t, 6.7, 0.7), 13.1, INK_SOFT, "center", 0.95)
    # 强调：圈住她的脸 + 引线
    u = seg(t, 7.55, 0.55)
    if u > 0:
        stroke(d, [(1312, 330), (1420, 326), (1560, 332), (1648, 328)], 5.0, ACCENT, u, 91, 0.9, 1.4)
    return im


# ---------------------------------------------------------------- 页 2：材质与尺寸
def page2(t):
    im = Image.new("RGBA", (W * SS, H * SS), PAPER + (255,))
    d = ImageDraw.Draw(im, "RGBA")
    draw_frame(d, t, 0.0, 0.05)
    draw_mona(d, 9.0, alpha=0.92)
    # 尺寸线（下方 77，右侧 53）
    u1 = seg(t, 0.5, 0.7)
    stroke(d, [(FX0, 986), (FX1, 986)], 3.6, INK_SOFT, u1, 101, 0.95, 0.7)
    for x in (FX0, FX1):
        stroke(d, [(x, 974), (x, 998)], 3.6, INK_SOFT, u1, 103 + int(x), 0.95, 0.5)
    u2 = seg(t, 1.0, 0.7)
    stroke(d, [(1192, FY0), (1192, FY1)], 3.6, INK_SOFT, u2, 105, 0.95, 0.7)
    for y in (FY0, FY1):
        stroke(d, [(1180, y), (1204, y)], 3.6, INK_SOFT, u2, 107 + int(y), 0.95, 0.5)
    hand_text(im, "77 厘米", 840, 1028, 40, seg(t, 1.6, 0.6), 17.3, INK, "center", 1.0)
    hand_text(im, "53 厘米", 1192, 128, 34, seg(t, 1.9, 0.6), 19.7, INK, "center", 1.0)
    # 右侧说明
    items = [
        ("木板油画", 52, 300, 2.6, 0.8, 23.1),
        ("颜料混油，画在杨木板上", 30, 352, 3.0, 0.7, 27.3),
        ("达·芬奇 1503 年动笔", 32, 470, 3.7, 0.8, 29.9),
        ("前后画了十几年", 32, 516, 4.0, 0.7, 30.7),
        ("今天挂在卢浮宫", 44, 600, 4.7, 0.8, 31.7),
    ]
    for (s2, size, y, t0, du, sd) in items:
        hand_text(im, s2, 1310, y, size, seg(t, t0, du), sd, INK, "left", 1.0)
    # 引线
    u3 = seg(t, 2.2, 0.5)
    stroke(d, [(1130, 300), (1250, 300)], 3.0, INK_SOFT, u3, 111, 0.8, 0.6)
    u4 = seg(t, 4.3, 0.5)
    stroke(d, [(1130, 600), (1250, 600)], 3.0, INK_SOFT, u4, 113, 0.8, 0.6)
    return im


# ---------------------------------------------------------------- 页 3：三个谜
def page3(t):
    im = Image.new("RGBA", (W * SS, H * SS), PAPER + (255,))
    d = ImageDraw.Draw(im, "RGBA")
    draw_frame(d, t, 0.0, 0.05)
    draw_mona(d, 9.0, alpha=0.9)

    # ① 眉毛（额头上方，文字在最上，引线不下穿）
    u = seg(t, 0.6, 0.7)
    stroke(d, circle_pts(840, 386, 84, 22, a0=-2.9, ry=17), 3.0, ACCENT, u, 125, 0.9, 1.1)
    stroke(d, [(922, 378), (1020, 330), (1110, 306)], 2.8, ACCENT, seg(t, 0.9, 0.5), 127, 0.9, 0.7)
    hand_text(im, "一、没有眉毛和睫毛", 1130, 302, 38, seg(t, 1.1, 0.8), 37.7, INK, "left")
    hand_text(im, "也许原本有，被时间洗掉了", 1130, 344, 25, seg(t, 1.6, 0.7), 39.3, INK_SOFT, "left", 0.95)

    # ② 微笑
    u = seg(t, 2.3, 0.7)
    stroke(d, circle_pts(840, 496, 62, 24, a0=-2.4, ry=34), 3.2, ACCENT, u, 121, 0.95, 1.2)
    stroke(d, [(902, 486), (1010, 440), (1110, 432)], 2.8, ACCENT, seg(t, 2.6, 0.5), 123, 0.9, 0.7)
    hand_text(im, "二、微笑没有轮廓线", 1130, 428, 38, seg(t, 2.8, 0.8), 33.3, INK, "left")
    hand_text(im, "晕涂法：用烟一样柔和的过渡", 1130, 470, 25, seg(t, 3.3, 0.7), 35.1, INK_SOFT, "left", 0.95)

    # ③ 地平线
    u = seg(t, 4.5, 0.7)
    stroke(d, circle_pts(676, 644, 52, 18, a0=-2.5, ry=26), 2.8, ACCENT, u, 129, 0.9, 1.0)
    stroke(d, circle_pts(1002, 608, 52, 18, a0=-2.5, ry=26), 2.8, ACCENT, u, 131, 0.9, 1.0)
    stroke(d, [(1054, 616), (1120, 586), (1190, 574)], 2.8, ACCENT, seg(t, 4.9, 0.5), 133, 0.9, 0.7)
    hand_text(im, "三、背景地平线不齐", 1210, 570, 38, seg(t, 5.1, 0.8), 41.9, INK, "left")
    hand_text(im, "左边比右边低一点", 1210, 612, 25, seg(t, 5.6, 0.7), 43.7, INK_SOFT, "left", 0.95)
    return im


# ---------------------------------------------------------------- 页 4：1911 被盗
def page4(t):
    im = Image.new("RGBA", (W * SS, H * SS), PAPER + (255,))
    d = ImageDraw.Draw(im, "RGBA")
    # 时间线
    y = 760.0
    stroke(d, [(300, y), (1620, y)], 4.0, INK_SOFT, seg(t, 0.2, 0.9), 141, 0.9, 0.7)
    for x, s2, sd in ((520, "1911", 43.1), (1420, "1913", 47.3)):
        p = seg(t, 0.8, 0.5)
        stroke(d, [(x, y - 22), (x, y + 22)], 5.0, INK, p, 143 + int(x), 1.0, 0.7)
        hand_text(im, s2, x, y + 92, 56, seg(t, 1.0, 0.7), sd, INK)
    # 小人：扛着画跑
    run0 = 1.9
    u = seg(t, run0, 3.0, ease=False)
    rx = lerp(600, 1330, u)
    ry = y - 96
    ph = (t - run0) * 12.0 if t > run0 else 0.0
    if t > run0 - 0.3:
        a = 1.0
        # 腿
        stroke(d, [(rx, ry + 40), (rx + math.sin(ph) * 26, y)], 4.6, INK, 1, 151, a, 1.0)
        stroke(d, [(rx, ry + 40), (rx - math.sin(ph) * 26, y)], 4.6, INK, 1, 153, a, 1.0)
        # 身
        stroke(d, [(rx, ry + 40), (rx + 2, ry - 4)], 4.8, INK, 1, 155, a, 1.0)
        # 头
        stroke(d, circle_pts(rx + 4, ry - 22, 17, 18), 4.6, INK, 1, 157, a, 1.0)
        # 手臂抱着画
        stroke(d, [(rx + 2, ry - 2), (rx + 26, ry + 8)], 4.4, INK, 1, 159, a, 1.0)
        # 怀里的画（小框）
        stroke(d, [(rx + 22, ry - 34), (rx + 62, ry - 30), (rx + 58, ry + 24), (rx + 20, ry + 20), (rx + 22, ry - 34)],
               3.8, INK, 1, 161, a, 0.8)
    # 说明
    hand_text(im, "1911 年，一个馆内工人把它拆下来", 300, 300, 44, seg(t, 2.4, 0.9), 49.1, INK, "left")
    hand_text(im, "夹在大衣里，走出了卢浮宫", 300, 366, 44, seg(t, 3.2, 0.9), 51.7, INK, "left")
    hand_text(im, "两年后在佛罗伦萨找回", 300, 470, 44, seg(t, 4.9, 0.9), 53.3, INK, "left")
    hand_text(im, "报纸连着登了两年，她从此人尽皆知", 300, 536, 32, seg(t, 5.7, 0.9), 55.9, INK_SOFT, "left", 0.95)
    # 强调：画框上的红圈
    u2 = seg(t, 6.6, 0.6)
    stroke(d, circle_pts(520, y, 46, 18, a0=-2.2, ry=42), 3.4, ACCENT, u2, 165, 0.9, 1.1)
    return im


# ---------------------------------------------------------------- 页 5：现在的展柜
def page5(t):
    im = Image.new("RGBA", (W * SS, H * SS), PAPER + (255,))
    d = ImageDraw.Draw(im, "RGBA")
    # 展柜
    stroke(d, [(520, 190), (1400, 190), (1400, 880), (520, 880), (520, 190)], 5.2, INK_SOFT,
           seg(t, 0.2, 0.9), 171, 0.85, 0.8)
    draw_mona(d, 9.0, s=0.66, cx=900, cy=528, alpha=0.9)
    # 玻璃反光
    u = seg(t, 0.9, 0.6)
    for i in range(3):
        stroke(d, [(600 + i * 34, 800), (760 + i * 34, 250)], 3.0, INK_SOFT,
               u, 173 + i, 0.22, 0.5)
    # 人流
    walk0 = 2.0
    for k in range(5):
        px = 210 + k * 130 + (t - walk0) * 34
        py = 1058
        ph = (t - walk0) * 7.0 + k * 1.3
        a = seg(t, walk0 + k * 0.15, 0.4)
        if a <= 0:
            continue
        stroke(d, [(px, py - 68), (px + math.sin(ph) * 19, py - 28)], 3.8, INK_SOFT, 1, 181 + k, a * 0.85, 0.8)
        stroke(d, [(px, py - 68), (px - math.sin(ph) * 19, py - 28)], 3.8, INK_SOFT, 1, 185 + k, a * 0.85, 0.8)
        stroke(d, [(px, py - 68), (px + 1, py - 116)], 4.0, INK_SOFT, 1, 189 + k, a * 0.85, 0.8)
        stroke(d, circle_pts(px + 2, py - 136, 16, 16), 3.8, INK_SOFT, 1, 193 + k, a * 0.85, 0.8)
        stroke(d, [(px, py - 108), (px + 22, py - 92)], 3.4, INK_SOFT, 1, 197 + k, a * 0.7, 0.7)
    # 说明
    hand_text(im, "现在：防弹玻璃", 1440, 300, 40, seg(t, 2.6, 0.9), 57.1, INK, "left")
    hand_text(im, "恒温、恒湿、日均两万人排队", 1440, 352, 26, seg(t, 3.0, 0.8), 57.9, INK_SOFT, "left", 0.95)
    hand_text(im, "每年约九百万人来看她", 1432, 440, 34, seg(t, 3.6, 0.9), 59.3, INK, "left")
    hand_text(im, "她只是坐在那儿笑", 1440, 516, 38, seg(t, 4.7, 0.9), 61.7, INK, "left")
    # 落版
    hand_text(im, "五百年", 1440, 680, 72, seg(t, 6.0, 1.0), 63.9, ACCENT, "left")
    return im


# ---------------------------------------------------------------- 页表与帧
PAGES = [
    (0.0, 9.2, page1),
    (9.2, 17.6, page2),
    (17.6, 27.4, page3),
    (27.4, 36.2, page4),
    (36.2, 46.0, page5),
]
TR = 0.42


def frame(t):
    global BOIL, OFFSET
    BOIL = int(t * 12)
    total = PAGES[-1][1]
    t = clamp(t, 0.0, total - 0.001)
    idx = 0
    for i, (a, b, fn) in enumerate(PAGES):
        if a <= t < b:
            idx = i
            break
    a, b, fn = PAGES[idx]
    local = t - a
    im = paper_img().copy()
    if t > b - TR and idx + 1 < len(PAGES):
        u = smooth((t - (b - TR)) / TR)
        OFFSET = (0.0, -1080.0 * u)
        im = Image.alpha_composite(im, fn(local))
        OFFSET = (0.0, 1080.0 * (1.0 - u))
        im = Image.alpha_composite(im, PAGES[idx + 1][2](0.0))
    else:
        OFFSET = (0.0, 0.0)
        im = Image.alpha_composite(im, fn(local))
    # 页进度点
    OFFSET = (0.0, 0.0)
    d = ImageDraw.Draw(im, "RGBA")
    for i in range(len(PAGES)):
        cx = 960 + (i - 2) * 30
        r = 6 if i == idx else 4
        col = INK if i == idx else blend(INK, 0.2)
        d.ellipse([(cx - r) * SS, (1064 - r) * SS, (cx + r) * SS, (1064 + r) * SS],
                  fill=col + (255,))
    return im.convert("RGB").resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- 配乐
def make_score(duration, bpm):
    wa = wv.wa
    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.8)
    spb = 60.0 / bpm
    bars = int(math.ceil(duration / (spb * 4.0))) + 1
    pad = s.track("pad", name="pad", gain_db=-22.0, seed=1)
    pl = s.track("pluck", name="pluck", gain_db=-13.0, pan=0.1, seed=2)
    bs = s.track("bass", name="bass", gain_db=-13.5, seed=3)
    CH = [[60, 64, 67], [60, 64, 67], [59, 62, 67], [57, 60, 64],
          [60, 64, 67], [57, 60, 64], [59, 62, 65], [60, 64, 67]]
    ROOT = [48, 48, 47, 45, 48, 45, 47, 48]
    NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def nm(m):
        return NAMES[int(m) % 12] + str(int(m) // 12 - 1)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = CH[bi % 8]
        for m in ch:
            pad.note(b0, nm(m), 3.9, 0.30)
        # 轻快的讲解动机：跳进 + 邻音
        mel = [(0.0, ch[2] + 12, 0.45, 0.42), (0.75, ch[1] + 12, 0.3, 0.32),
               (1.5, ch[0] + 12, 0.3, 0.34), (2.25, ch[1] + 12, 0.3, 0.30),
               (2.75, ch[2] + 12, 0.55, 0.36)]
        if bi % 4 == 3:
            mel.append((3.5, ch[0] + 19, 0.45, 0.28))
        for (o, m, dd, g) in mel:
            pl.note(b0 + o, nm(m), dd, g)
        bs.note(b0, nm(ROOT[bi % 8]), 1.8, 0.42)
        bs.note(b0 + 2.0, nm(ROOT[bi % 8] + 7), 1.6, 0.30)
    # 收尾
    end = max(0.0, duration / spb - 3.0)
    for i, m in enumerate((60, 64, 67)):
        pl.note(end + i * 0.5, nm(m), 0.5, 0.45)
    pl.note(end + 1.6, nm(72), 1.6, 0.4)
    bs.note(end, nm(36), 4.0, 0.5)
    s.length(beats=duration / spb)
    s.fade(out_seconds=1.2)
    return s


# ---------------------------------------------------------------- 装配
film = wv.Film(W, H, duration=46.0, fps=24, ss=1, grain=False,
               theme="paper", bpm=92, name="mona-lisa-doodle")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 46.0, transition="cut")
s1.draw(lambda c, t: c.paste_full(frame(t)), at=0, enter="none")

# 笔触声（分组，不逐笔）
for tt, g in ((0.35, -24), (1.7, -25), (2.6, -25), (3.3, -24), (3.7, -22), (4.2, -24)):
    film.sfx("swish", at=tt, gain=g, pitch=5)
film.sfx("tick", at=4.7, gain=-20)
film.sfx("tick", at=6.0, gain=-20)
# 页 2
film.sfx("swipe", at=9.2, gain=-17)
film.sfx("swish", at=10.1, gain=-22)
film.sfx("tick", at=11.3, gain=-21)
film.sfx("tick", at=12.7, gain=-21)
film.sfx("tick", at=15.1, gain=-20)
# 页 3
film.sfx("swipe", at=17.6, gain=-17)
film.sfx("ding", at=18.4, gain=-20)
film.sfx("ding", at=20.6, gain=-20)
film.sfx("ding", at=22.9, gain=-20)
# 页 4
film.sfx("swipe", at=27.4, gain=-17)
film.sfx("tick", at=28.0, gain=-21)
film.sfx("tick", at=28.7, gain=-21)
for k in range(6):
    film.sfx("tick", at=29.4 + k * 0.42, gain=-23, pitch=7)
film.sfx("pop", at=33.9, gain=-18)
# 页 5
film.sfx("swipe", at=36.2, gain=-17)
film.sfx("sparkle", at=37.6, gain=-20)
film.sfx("chime", at=42.2, gain=-16)
film.flicker_exclude(0.0, 46.0)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "mona-lisa-doodle.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
