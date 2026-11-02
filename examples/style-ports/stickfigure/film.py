# -*- coding: utf-8 -*-
"""《最后一格》 — 简笔画 · 30s 三幕
画纸＝世界，格子＝边界，橡皮＝删除。他每天把自己重描一遍。
第一幕 日常／第二幕 发现／第三幕 逃生＋拉远（整页、巨型橡皮、最后一格）
手法：1/12s 手抖（boil）/ 逐笔生长 / 两段式肢体 / 擦拭残影 / 相机缩放
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

INK = (40, 34, 29)
INK_SOFT = (104, 95, 84)
PAPER = (246, 242, 231)
PINK = (240, 166, 158)
PINK_D = (203, 122, 116)
SLEEVE = (248, 246, 241)
SMUDGE = (152, 146, 136)
DESK = (33, 30, 26, 255)

# ---------------------------------------------------------------- 世界 / 相机
PAGE_W, PAGE_H = 2400.0, 1500.0
MX, MY, GUT = 90.0, 90.0, 130.0
CW = 457.5
CH = 303.333
GROUND_OFF = 14.0
K = 0.8                      # 角色体型系数


def cell_rect(col, row):
    return (MX + col * (CW + GUT), MY + row * (CH + GUT), CW, CH)


HERO = cell_rect(1, 1)
HX, HY, HW, HH = HERO
GROUND = HY + HH - GROUND_OFF
LEFT_B, RIGHT_B = HX, HX + HW
TOP_B, BOT_B = HY, HY + HH


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


CAM = (2.55, 906.0, 675.0)
BOIL = 0
CAM_KEYS = [
    (0.0, 2.55, 906, 675),
    (6.9, 2.55, 906, 675),
    (7.9, 2.30, 1012, 672),
    (11.2, 2.30, 1012, 672),
    (12.3, 2.38, 1022, 668),
    (15.55, 2.38, 1010, 670),
    (16.35, 2.34, 812, 676),
    (19.9, 2.26, 874, 676),
    (20.9, 2.26, 874, 676),
    (24.9, 0.58, 1200, 742),
    (27.2, 0.57, 1200, 730),
    (30.2, 0.57, 1200, 722),
]


def cam_at(t):
    for i in range(len(CAM_KEYS) - 1):
        t0, s0, x0, y0 = CAM_KEYS[i]
        t1, s1, x1, y1 = CAM_KEYS[i + 1]
        if t0 <= t <= t1:
            u = smooth((t - t0) / (t1 - t0))
            return (lerp(s0, s1, u), lerp(x0, x1, u), lerp(y0, y1, u))
    return CAM_KEYS[-1][1:]


def W2S(x, y):
    s, cx, cy = CAM
    return ((x - cx) * s + W * 0.5, (y - cy) * s + H * 0.5)


# ---------------------------------------------------------------- 手绘线条
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
            seg = L[i] - L[i - 1]
            u = (total - L[i - 1]) / (seg or 1.0)
            out.append((lerp(pts[i - 1][0], pts[i][0], u), lerp(pts[i - 1][1], pts[i][1], u)))
            break
    return out


def blend(c, a, bg=None):
    """按背景色预混合成不透明色（PIL 的 RGBA 画笔是覆盖而非混合）。"""
    if a >= 0.999:
        return c
    bg = PAPER if bg is None else bg
    a = max(0.0, min(1.0, a))
    return tuple(int(round(bg[i] * (1.0 - a) + c[i] * a)) for i in range(3))


def stroke(d, pts, width=6.0, color=INK, prog=1.0, seed=0.0, alpha=1.0, jit=1.0):
    pts = _truncate(list(pts), prog)
    if len(pts) < 2:
        return
    s = CAM[0]
    sp = [W2S(x, y) for x, y in pts]
    out = []
    for i in range(1, len(sp)):
        x0, y0 = sp[i - 1]
        x1, y1 = sp[i]
        seg = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(seg / (4.5 / SS)))
        for q in range(n + (1 if i == len(sp) - 1 else 0)):
            u = q / n
            out.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u))
    if len(out) < 2:
        return
    amp = (width * 0.05 + jit * 0.85) * s * 0.62
    sd = seed * 7.31 + BOIL * 1.77
    dev = []
    for i, (x, y) in enumerate(out):
        j1 = (noise1(i * 0.09 + seed * 3.3, sd) - 0.5) * 2.0
        j2 = (noise1(i * 0.021 + seed * 1.7, sd + 41.0) - 0.5) * 2.0
        dev.append(((x + (j1 + j2 * 1.5) * amp) * SS, (y + (j1 * 0.9 + j2 * 1.2) * amp) * SS))
    col = blend(color, alpha)
    w = max(1, int(round(width * s * SS)))
    d.line(dev, fill=col, width=w, joint="curve")
    r = w * 0.5
    for (cx, cy) in (dev[0], dev[-1]):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def stroke_head(pts, prog):
    """取生长中折线的笔尖位置（世界坐标）。"""
    p = _truncate(list(pts), prog)
    return p[-1] if p else None


def circle_pts(cx, cy, r, n=30, a0=-2.2, ry=None):
    ry = r if ry is None else ry
    return [(cx + math.cos(a0 + i / n * math.tau) * r,
             cy + math.sin(a0 + i / n * math.tau) * ry) for i in range(n + 1)]


def arc_pts(cx, cy, r, a0, a1, n=18, ry=None):
    ry = r if ry is None else ry
    return [(cx + math.cos(lerp(a0, a1, i / n)) * r,
             cy + math.sin(lerp(a0, a1, i / n)) * ry) for i in range(n + 1)]


# ---------------------------------------------------------------- 手写文字
_FONT_CACHE = {}


def _font(size_px):
    key = max(8, int(round(size_px)))
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = wv.fonts.load("sans_bold", key)
    return _FONT_CACHE[key]


def hand_text(im, s, x, y, size, prog=1.0, seed=0.0, color=INK, align="center",
              alpha=1.0, wob=1.0):
    px = max(8.0, size * CAM[0] * SS)
    f = _font(px)
    widths = [f.getlength(ch) for ch in s]
    total = sum(widths)
    sx, sy = W2S(x, y)
    sx *= SS
    sy *= SS
    cx = sx - total / 2.0 if align == "center" else (sx - total if align == "right" else sx)
    n_show = int(math.ceil(prog * len(s) - 1e-6))
    for i, ch in enumerate(s[:max(0, n_show)]):
        adv = widths[i]
        a = clamp(prog * len(s) - i, 0.0, 1.0)
        if ch.strip():
            jx = (noise1(i * 3.1 + seed, seed + BOIL) - 0.5) * px * 0.10 * wob
            jy = (noise1(i * 5.7 + seed + 9, seed + BOIL) - 0.5) * px * 0.16 * wob
            rot = (noise1(i * 7.3 + seed, seed + 4 + BOIL) - 0.5) * 10.0 * wob
            glyph = Image.new("RGBA", (int(adv) + 14, int(px * 1.55) + 14), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glyph)
            gd.text((7, 7), ch, font=f, fill=color + (int(255 * alpha * a),))
            glyph = glyph.rotate(rot, resample=Image.BICUBIC, expand=False)
            im.alpha_composite(glyph, (int(cx + jx) - 7, int(sy - px * 1.12 + jy) - 7))
        cx += adv


# ---------------------------------------------------------------- 纸
_PAPER = None


def paper_img():
    global _PAPER
    if _PAPER is not None:
        return _PAPER
    rng = np.random.default_rng(7)
    hh, ww = H * SS // 4, W * SS // 4
    fib = rng.normal(0, 1.0, (hh, ww))
    fib = (fib - fib.min()) / float(np.ptp(fib) + 1e-6)
    fib = np.array(Image.fromarray((fib * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.1)), np.float32) / 255.0
    base = np.array(PAPER, np.float32)
    a = np.empty((hh, ww, 3), np.float32)
    for c in range(3):
        a[..., c] = base[c] - 7 + fib * 14
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((W * SS, H * SS), Image.BICUBIC)
    d = ImageDraw.Draw(img, "RGBA")
    r2 = np.random.default_rng(11)
    for _ in range(300):
        x, y = r2.uniform(0, W * SS), r2.uniform(0, H * SS)
        d.ellipse([x, y, x + 3, y + 3], fill=(198, 188, 170, 24))
    _PAPER = img.convert("RGBA")
    return _PAPER


def sheet_mask():
    a = W2S(0, 0)
    b = W2S(PAGE_W, PAGE_H)
    m = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(m).rectangle([int(a[0] * SS), int(a[1] * SS),
                                 int(b[0] * SS), int(b[1] * SS)], fill=255)
    return m


def sheet_shadow(im):
    a = W2S(0, 0)
    b = W2S(PAGE_W, PAGE_H)
    w = max(4, int((b[0] - a[0]) * SS))
    h = max(4, int((b[1] - a[1]) * SS))
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).rectangle([0, 0, w - 1, h - 1], fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(max(3, int(13 * CAM[0] * SS))))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.putalpha(sh)
    im.alpha_composite(layer, (int(a[0] * SS) + int(14 * SS), int(a[1] * SS) + int(18 * SS)))


# ---------------------------------------------------------------- 角色
def pose_default():
    return dict(lean=0.0, legA=7.0, legB=-5.0, kneeA=5.0, kneeB=5.0,
                armA=8.0, armB=-9.0, elbowA=7.0, elbowB=7.0,
                headTilt=0.0, look=0.0, mouth="smile", eye="dot")


def figure_parts(x, ground, k, p):
    hip = (x + p["lean"] * 26 * k, ground - 100 * k)
    sh = (hip[0] + p["lean"] * 14 * k, hip[1] - 88 * k)
    hr = 27.0 * k
    hx = sh[0] + math.sin(p["headTilt"]) * 34 * k
    hy = sh[1] - math.cos(p["headTilt"]) * 50 * k
    head = circle_pts(hx, hy, hr, 26)

    def limb(root, a1, l1, a2, l2):
        t1 = math.radians(a1)
        j = (root[0] + math.sin(t1) * l1, root[1] + math.cos(t1) * l1)
        t2 = math.radians(a1 + a2)
        return j, (j[0] + math.sin(t2) * l2, j[1] + math.cos(t2) * l2)

    kA, fA = limb(hip, p["legA"], 52 * k, -p["kneeA"], 50 * k)
    kB, fB = limb(hip, p["legB"], 52 * k, -p["kneeB"], 50 * k)
    eA, hA = limb(sh, p["armA"], 46 * k, p["elbowA"], 40 * k)
    eB, hB = limb(sh, p["armB"], 46 * k, p["elbowB"], 40 * k)

    return dict(head=head, body=[(hx, hy + hr * 0.92), sh, hip],
                legA=[hip, kA, fA], legB=[hip, kB, fB],
                armA=[sh, eA, hA], armB=[sh, eB, hB],
                eye=(hx + 7 * k + p["look"] * 4 * k, hy - 5 * k),
                mouth=(hx - 1 * k + p["look"] * 3 * k, hy + 13 * k),
                hip=hip, sh=sh, headc=(hx, hy), hr=hr, handF=hA)


def draw_figure(d, x, ground, k, p, prog=1.0, seed0=0.0, alpha=1.0,
                skip=(), w=5.4, ghost=0.0, arm_fade=1.0):
    P = figure_parts(x, ground, k, p)
    seq = ["head", "body", "legB", "legA", "armB", "armA"]
    for i, name in enumerate(seq):
        if name in skip and name != "armB":
            continue
        a_here = alpha * (arm_fade if name == "armB" else 1.0)
        if a_here <= 0.01:
            continue
        stroke(d, P[name], w * k ** 0.25, INK, prog, seed0 + i * 3.7, a_here, 1.0)
        if ghost > 0:
            stroke(d, [(px + 5 * k + 0 * py, py - 4 * k) for px, py in P[name]],
                   w * k ** 0.25, INK, prog, seed0 + i * 3.7, alpha * ghost, 1.0)
    if prog > 0.92 and not skip and "armA" not in skip:
        ex, ey = P["eye"]
        if p["eye"] == "wide":
            stroke(d, circle_pts(ex, ey, 4.6 * k, 14), w * 0.62, INK, 1, seed0 + 21, alpha)
        else:
            stroke(d, [(ex - 2.8 * k, ey), (ex + 2.8 * k, ey)], w * 0.72, INK, 1, seed0 + 21, alpha)
        mx, my = P["mouth"]
        if p["mouth"] == "o":
            stroke(d, circle_pts(mx, my, 5.2 * k, 16, ry=6.0 * k), w * 0.58, INK, 1, seed0 + 23, alpha)
        else:
            stroke(d, arc_pts(mx, my - 5 * k, 7.4 * k, 0.35, math.pi - 0.35, 12, 4.8 * k),
                   w * 0.62, INK, 1, seed0 + 23, alpha)
    return P


# ---------------------------------------------------------------- 道具
def draw_eraser(d, x, y, w, h, alpha=1.0, sleeve=0.5, crumbs=0.0):
    s = CAM[0]
    if alpha <= 0.01:
        return
    a = W2S(x, y)
    b = W2S(x + w, y + h)
    # 影子
    p0, p1 = W2S(x + 12, y + h - 6), W2S(x + w + 2, y + h + 7 * (h / 74.0))
    d.ellipse([p0[0] * SS, p0[1] * SS, p1[0] * SS, p1[1] * SS],
              fill=blend((92, 82, 70), 0.22 * alpha))
    d.rounded_rectangle([a[0] * SS, a[1] * SS, b[0] * SS, b[1] * SS],
                        radius=max(1, 9 * s * SS), fill=blend(PINK, alpha),
                        outline=blend(PINK_D, alpha), width=max(1, int(2.4 * s * SS)))
    if sleeve > 0:
        sx0 = x + w * (1.0 - sleeve)
        a2, b2 = W2S(sx0, y), W2S(x + w - 5, y + h - 5)
        d.rounded_rectangle([a2[0] * SS, a2[1] * SS, b2[0] * SS, b2[1] * SS],
                            radius=max(1, 6 * s * SS), fill=blend(SLEEVE, alpha),
                            outline=blend(PINK_D, alpha), width=max(1, int(1.8 * s * SS)))
        stroke(d, [(sx0 + 5, y + h * 0.30), (x + w - 11, y + h * 0.30)], 1.5, INK_SOFT,
               1, 55, alpha * 0.5, 0.25)
    if crumbs > 0:
        for i in range(8):
            ax = x + w * (0.15 + 0.85 * hash1(i * 3.1 + 5))
            ay = y + h + 6 + hash1(i * 7.7) * 20 * (h / 74.0)
            rr = (1.0 + hash1(i * 2.3) * 2.0) * (h / 74.0)
            px = W2S(ax, ay)
            d.ellipse([(px[0] - rr) * SS, (px[1] - rr) * SS,
                       (px[0] + rr) * SS, (px[1] + rr) * SS],
                      fill=blend((118, 102, 86), 0.55 * crumbs * alpha))


def draw_pencil(d, x, y, ang, ln=42.0, alpha=1.0):
    dx, dy = math.cos(ang), math.sin(ang)
    stroke(d, [(x - dx * ln, y - dy * ln), (x, y)], 3.0, (62, 53, 44), 1, 71, alpha, 0.4)
    stroke(d, [(x - dx * ln, y - dy * ln), (x - dx * (ln + 7), y - dy * (ln + 7))],
           4.6, (216, 158, 108), 1, 73, alpha, 0.3)
    stroke(d, [(x - dx * 8, y - dy * 8), (x, y)], 2.6, (28, 24, 20), 1, 77, alpha, 0.2)


_SMUDGE = None


def smudge(im, x, y, w, h, alpha=0.3):
    global _SMUDGE
    if _SMUDGE is None:
        m = Image.new("L", (160, 110), 0)
        md = ImageDraw.Draw(m)
        md.ellipse([8, 16, 152, 94], fill=150)
        md.ellipse([28, 6, 122, 102], fill=110)
        _SMUDGE = m.filter(ImageFilter.GaussianBlur(9))
    a, b = W2S(x, y), W2S(x + w, y + h)
    box = (int(a[0] * SS), int(a[1] * SS), int(b[0] * SS), int(b[1] * SS))
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        return
    sp = _SMUDGE.resize((box[2] - box[0], box[3] - box[1]), Image.BILINEAR)
    sp = sp.point(lambda v: int(v * alpha))
    layer = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), SMUDGE + (0,))
    layer.putalpha(sp)
    im.alpha_composite(layer, (box[0], box[1]))


# ---------------------------------------------------------------- 格子边框
def cell_border(d, rect, prog=1.0, gap_l=None, gap_r=None, w=6.0, alpha=1.0, seed=100):
    x, y, cw, ch = rect
    parts = [
        ([(x, y), (x + cw, y)], 0),
        ([(x + cw, y), (x + cw, y + ch)], 1),
        ([(x + cw, y + ch), (x, y + ch)], 2),
        ([(x, y + ch), (x, y)], 3),
    ]
    for sg, si in parts:
        p = clamp((prog - si * 0.24) / 0.40, 0.0, 1.0)
        if p <= 0:
            continue
        gap = None
        if sg[0][0] == sg[1][0]:
            gap = gap_l if si == 3 else gap_r
        if gap is None:
            stroke(d, sg, w, INK, p, seed + si, alpha, 0.6)
            continue
        g0, g1 = gap
        a, b = sorted([sg[0][1], sg[1][1]])
        for pa, pb in ((a, min(g0, b)), (max(g1, a), b)):
            if pb - pa > 1.0:
                stroke(d, [(sg[0][0], pa), (sg[0][0], pb)], w, INK, p, seed + si, alpha, 0.6)


# ---------------------------------------------------------------- 时间线
def eraser_at(t):
    """追击橡皮的左上角与透明度；返回 (x, y, alpha, crumbs)。"""
    y = 636.0
    if t < 8.55:
        return (LEFT_B + HW + 8, y, 1.0, 0.0)
    if t < 9.95:
        u = smooth((t - 8.55) / 1.4)
        return (lerp(RIGHT_B + 8, RIGHT_B - 40, u), y, 1.0, 0.0)
    if t < 10.65:
        u = smooth((t - 9.95) / 0.7)
        return (lerp(RIGHT_B - 40, RIGHT_B - 70, u), y, 1.0, 0.4)
    if t < 11.45:
        u = smooth((t - 10.65) / 0.8)
        return (lerp(RIGHT_B - 70, RIGHT_B - 118, u), y, 1.0, 0.7)
    if t < 13.15:
        u = smooth((t - 11.45) / 1.7)
        return (lerp(RIGHT_B - 118, RIGHT_B - 250, u), y, 1.0, 0.8)
    if t < 15.65:
        u = smooth((t - 13.15) / 2.5)
        return (lerp(RIGHT_B - 250, RIGHT_B - 300, u), y, 1.0, 0.6)
    if t < 17.25:
        u = smooth((t - 15.65) / 1.6)
        return (lerp(RIGHT_B - 300, LEFT_B + 12, u), y, 1.0, 0.9)
    if t < 18.6:
        u = (t - 17.25) / 1.35
        return (LEFT_B + 12, y - 320 * smooth(u), 1.0 - smooth(u) ** 1.6, 0.0)
    return (LEFT_B + 12, y, 0.0, 0.0)


def figure_state(t):
    x = 800.0
    p = pose_default()
    skip = ()
    walk = 0.0

    if t < 5.55:
        x = 800.0
    elif t < 7.0:
        x = lerp(800, 1002, smooth((t - 5.55) / 1.45))
        walk = t - 5.55
    elif t < 11.7:
        x = 1002.0
    elif t < 13.2:
        x = lerp(1002, 745, smooth((t - 11.7) / 1.5))
        walk = t - 11.7
    elif t < 15.1:
        x = 745.0
    elif t < 15.72:
        x = lerp(745, 520, smooth((t - 15.1) / 0.62))
        walk = t - 15.1
    elif t < 18.6:
        x = 520.0
    elif t < 19.8:
        x = lerp(520, 880, smooth((t - 18.6) / 1.2))
        walk = t - 18.6
    else:
        x = 880.0

    if walk > 0:
        ph = walk * (10.6 if t > 11.6 else 9.4)
        amp = 38 if t > 11.6 else 30
        p["legA"] = math.sin(ph) * amp
        p["legB"] = -math.sin(ph) * amp
        p["kneeA"] = max(0.0, -math.sin(ph)) * 32 + 6
        p["kneeB"] = max(0.0, math.sin(ph)) * 32 + 6
        p["armA"] = -math.sin(ph) * 27
        p["armB"] = math.sin(ph) * 27
        p["elbowA"] = 11
        p["elbowB"] = 11
        p["lean"] = 0.26 if t > 11.6 else 0.10

    if 5.0 < t < 5.55:
        u = smooth((t - 5.0) / 0.4)
        p["headTilt"] = 0.36 * u
        p["look"] = u
        p["mouth"] = "o"

    if 7.0 <= t < 7.95:
        u = smooth((t - 7.0) / 0.3)
        p["armA"] = lerp(8, 88, u)
        p["elbowA"] = lerp(7, -6, u)
        p["lean"] = 0.2 * u
        p["headTilt"] = 0.28

    if 10.45 <= t < 11.7:
        u = smooth(clamp((t - 10.45) / 0.8, 0, 1))
        p["headTilt"] = lerp(0.28, 0.46, u)
        p["look"] = 1.0
        p["mouth"] = "o"
        p["armB"] = lerp(-9, -118, u)
        p["elbowB"] = 12
        p["lean"] = lerp(0.2, -0.24, u)
    if t >= 11.2:
        skip = ("armB",)

    if 13.2 <= t < 14.6:
        u = smooth((t - 13.2) / 0.5)
        p["armA"] = lerp(8, -54, u)
        p["elbowA"] = 8
        p["headTilt"] = 0.3
        p["look"] = -0.7

    if 14.95 <= t < 15.72:
        p["lean"] = 0.42
        p["kneeA"] = 30
        p["kneeB"] = 26

    if 18.3 <= t < 18.62:
        br = math.sin((t - 18.3) * 2.6) * 0.5 + 0.5
        p["lean"] = -0.14
        p["headTilt"] = -0.14 + 0.06 * br
        p["armA"] = 16
        p["armB"] = -16
        p["elbowA"] = 28
        p["elbowB"] = 26
        p["mouth"] = "o"

    if 19.9 <= t < 20.9:
        p["armA"] = -66
        p["elbowA"] = 16
        p["headTilt"] = -0.22

    if t >= 25.0:
        u = smooth(clamp((t - 25.0) / 0.7, 0, 1))
        p["headTilt"] = lerp(-0.22, -0.66, u)
        p["eye"] = "wide" if u > 0.35 else "dot"
        p["mouth"] = "o" if u > 0.25 else "smile"
        p["armA"] = lerp(16, -126, u)
        p["armB"] = lerp(-16, -138, u)
        p["elbowA"] = 22
        p["elbowB"] = 24
        p["look"] = 0.5

    return x, p, skip


def door_state(t):
    """返回 (prog, open, alpha)。"""
    if t < 13.3:
        return (0.0, 0.0, 1.0)
    if t < 14.55:
        return (smooth((t - 13.3) / 1.05), 0.0, 1.0)
    if t < 14.95:
        return (1.0, smooth((t - 14.55) / 0.4), 1.0)
    return (1.0, 1.0, 1.0)


def small_cell_state(t):
    """他给自己画的小格子。"""
    if t < 19.9:
        return 0.0
    return smooth((t - 19.9) / 0.75)


def title_prog(t):
    if t < 27.05:
        return 0.0
    return smooth((t - 27.05) / 1.55)


# ---------------------------------------------------------------- 帧
def frame(t):
    global CAM, BOIL
    CAM = cam_at(t)
    BOIL = int(t * 12)

    im = Image.new("RGBA", (W * SS, H * SS), DESK)
    if CAM[0] < 1.4:
        sheet_shadow(im)
    im.paste(paper_img(), (0, 0), sheet_mask())
    d = ImageDraw.Draw(im, "RGBA")

    # ---- 背景网格（除主角格）----
    zoom_out = CAM[0] < 1.2
    for row in range(3):
        for col in range(4):
            if (col, row) == (1, 1):
                continue
            rect = cell_rect(col, row)
            alpha = 0.92 if zoom_out else 0.30
            if not zoom_out:
                # 近景时只画相邻的淡线（交代还有别的格子）
                if col == 2 and row == 1:
                    cell_border(d, rect, 1.0, w=5.0, alpha=0.35, seed=300)
                continue
            cell_border(d, rect, 1.0, w=5.6, alpha=alpha, seed=310 + col * 7 + row)
            # 格子里的小人（远看都是"他"）
            cx = rect[0] + rect[2] * 0.5
            gnd = rect[1] + rect[3] - 14
            jit = (hash1(BOIL * 3.1 + col * 7 + row) - 0.5) * 3.0 if t > 25.0 else 0.0
            draw_figure(d, cx + jit, gnd, K, pose_default(), 1.0, 400 + col * 13 + row, alpha, w=5.2)

    # ---- 主角格子 ----
    xf, pf, skip = figure_state(t)
    door_prog, door_open, door_alpha = door_state(t)
    cell_prog = smooth(t / 1.15)
    right_gap = None
    if t > 9.85:
        right_gap = (636.0, 636.0 + 74.0)
    left_gap = None
    if door_open > 0.02:
        left_gap = (650.0, 812.0)

    # 被擦掉的格子：15.65 之后边线开始消失
    erase_prog = clamp((t - 15.65) / 1.5, 0.0, 1.0)
    if erase_prog >= 1.0:
        cell_border(d, HERO, 1.0, gap_l=left_gap, gap_r=right_gap, w=5.0,
                    alpha=0.10, seed=100)
    else:
        cell_border(d, HERO, cell_prog, gap_l=left_gap, gap_r=right_gap,
                    w=6.2, alpha=1.0 - erase_prog * 0.95, seed=100)

    # 格子内的地面小投影（仅近景）
    if not zoom_out:
        g0, g1 = W2S(LEFT_B + 20, GROUND + 4), W2S(RIGHT_B - 20, GROUND + 15)
        d.ellipse([g0[0] * SS, g0[1] * SS, g1[0] * SS, g1[1] * SS],
                  fill=blend((150, 138, 118), 0.10))

    ex, ey, ea, crumbs = eraser_at(t)

    # ---- 被擦残影（橡皮走过的位置）----
    if t > 15.55:
        fade = 1.0 - clamp((t - 19.0) / 3.0, 0.0, 1.0)
        for i in range(5):
            xs = ex - 26 - i * 34
            if xs > LEFT_B + 16:
                smudge(im, xs, 626, 72, 116, 0.13 * fade * (1.0 - i * 0.18))

    # ---- 门 ----
    if door_prog > 0.01 and erase_prog < 0.5:
        dx0, dy0, dy1 = LEFT_B, 648.0, 812.0
        door_pts = [[(dx0, dy0), (dx0 + 24, dy0)],
                    [(dx0 + 24, dy0), (dx0 + 24, dy1)],
                    [(dx0 + 24, dy1), (dx0, dy1)]]
        for i, dp in enumerate(door_pts):
            stroke(d, dp, 5.0, INK, clamp(door_prog * 3 - i * 0.8, 0, 1), 210 + i,
                   door_alpha * (1 - door_open), 0.8)
        # 门把手
        stroke(d, circle_pts(dx0 + 17, 730, 3.0, 10), 2.8, INK,
               clamp(door_prog * 4 - 3.0, 0, 1), 214, door_alpha * (1 - door_open), 0.5)
        if door_open > 0.02:
            # 门扇向外摆开
            ang = lerp(0.0, 0.80, door_open)
            hx0, hy0 = dx0, dy1
            ex0 = hx0 - math.sin(ang) * 112
            ey0 = hy0 - math.cos(ang) * 112
            ex1 = ex0 - math.cos(ang) * 22
            ey1 = ey0 + math.sin(ang) * 22
            stroke(d, [(hx0, hy0), (ex0, ey0), (ex1, ey1), (hx0 + 22, hy0)],
                   4.2, INK, door_open, 218, door_alpha * 0.9, 0.7)
            stroke(d, arc_pts(dx0, dy1, 52, math.pi, math.pi + 0.9, 8, 46), 2.2, INK_SOFT,
                   door_open, 219, door_alpha * 0.45, 0.5)

    # ---- 主角 ----
    if t < 1.45:
        pass
    elif t < 3.05:
        # 逐笔自绘
        P = figure_parts(800, GROUND, K, pose_default())
        seq = [("head", 1.45, 0.30), ("body", 1.70, 0.25), ("legB", 1.90, 0.22),
               ("legA", 2.06, 0.22), ("armB", 2.24, 0.20), ("armA", 2.40, 0.20)]
        tip = None
        for i, (name, t0, dur) in enumerate(seq):
            pr = clamp((t - t0) / dur, 0, 1)
            if pr > 0:
                stroke(d, P[name], 5.4 * K ** 0.25, INK, pr, 170 + i * 3.7, 1.0, 1.0)
            if 0 < pr < 1:
                tip = stroke_head(P[name], pr)
        if t > 2.55:
            eye_x, eye_y = P["eye"]
            stroke(d, [(eye_x - 2.8 * K, eye_y), (eye_x + 2.8 * K, eye_y)], 4.0, INK,
                   clamp((t - 2.55) / 0.12, 0, 1), 191, 1.0, 0.6)
        if t > 2.62:
            stroke(d, arc_pts(P["mouth"][0], P["mouth"][1] - 5 * K, 7.4 * K, 0.35,
                              math.pi - 0.35, 12, 4.8 * K), 3.6, INK,
                   clamp((t - 2.62) / 0.2, 0, 1), 193, 1.0, 0.6)
            tip = None
        if tip is not None:
            draw_pencil(d, tip[0], tip[1], -2.1, 46, 1.0)
    else:
        ghost = 0.0
        for dt in (3.05, 3.75, 4.45):
            if dt <= t < dt + 0.13:
                ghost = 0.45
        arm_fade = 1.0 - clamp((t - 11.2) / 0.22, 0.0, 1.0)
        draw_figure(d, xf, GROUND, K, pf, 1.0, 150, 1.0, skip=skip, w=5.4,
                    ghost=ghost, arm_fade=arm_fade)
        # 手中的铅笔（画门 / 画小格子）
        if 13.2 <= t < 14.6 or 19.95 <= t < 20.8:
            P = figure_parts(xf, GROUND, K, pf)
            hx, hy = P["handF"]
            draw_pencil(d, hx, hy, -2.4 if t < 15 else -2.0, 40, 1.0)

    # ---- "?" 与惊叹 ----
    if 5.15 < t < 6.6:
        pr = clamp((t - 5.15) / 0.35, 0, 1)
        hand_text(im, "?", xf + 46, GROUND - 214, 54, pr, 5.1, INK, "center", 1.0, 1.2)

    # ---- 橡皮 ----
    if ea > 0.01:
        draw_eraser(d, ex, ey, 118.0, 74.0, ea, 0.5, crumbs * (0.6 + 0.4 * hash1(BOIL)))
    # 刚被擦掉的边线碎屑
    if 9.9 < t < 11.6:
        for i in range(6):
            cx = RIGHT_B + (hash1(i * 3.7) - 0.5) * 26
            cy = 640 + 66 * hash1(i * 5.1 + BOIL)
            p0 = W2S(cx, cy)
            rr = 1.4 + hash1(i * 2.2) * 1.8
            d.ellipse([(p0[0] - rr) * SS, (p0[1] - rr) * SS,
                       (p0[0] + rr) * SS, (p0[1] + rr) * SS],
                      fill=blend((110, 96, 80), 0.55))

    # ---- 他画的小格子 ----
    sc = small_cell_state(t)
    if sc > 0:
        SX0, SY0, SW, SHE = 818.0, 592.0, 124.0, 246.0
        rect = (SX0, SY0, SW, SHE)
        cell_border(d, rect, 0.55 + 0.45 * sc, w=5.6, alpha=1.0,
                    seed=520)
        if sc < 1.0:
            # 笔尖沿矩形走
            per = 2 * (SW + SHE)
            u = sc * per
            if u < SW:
                tip = (SX0 + u, SY0)
            elif u < SW + SHE:
                tip = (SX0 + SW, SY0 + (u - SW))
            elif u < 2 * SW + SHE:
                tip = (SX0 + SW - (u - SW - SHE), SY0 + SHE)
            else:
                tip = (SX0, SY0 + SHE - (u - 2 * SW - SHE))
            draw_pencil(d, tip[0], tip[1], 0.6, 40, 1.0)

    # ---- 汗滴 / 抬头 ----
    if t > 25.3:
        u = smooth(clamp((t - 25.3) / 0.5, 0, 1))
        P = figure_parts(xf, GROUND, K, pf)
        hx, hy = P["headc"]
        sy = hy + 18 * K + u * 26
        stroke(d, circle_pts(hx - 30 * K, sy, 7.5 * K * u, 14, ry=9.5 * K * u), 3.4, INK, 1, 610, 1, 0.5)
        stroke(d, [(hx - 30 * K, sy - 14 * K * u), (hx - 30 * K, sy - 8 * K * u)], 3.0, INK, 1, 612, 1, 0.4)

    # ---- 巨型橡皮（结尾）----
    if t > 24.2:
        u = smooth(clamp((t - 24.2) / 2.4, 0, 1))
        gx, gy = 1500.0, lerp(-760.0, -60.0, u)
        gw, gh = 760.0, 430.0
        # 投影
        sh_a = 0.09 * u
        p0, p1 = W2S(gx + 90, gy + gh * 1.02), W2S(gx + gw - 20, gy + gh * 1.14)
        d.ellipse([p0[0] * SS, p0[1] * SS, p1[0] * SS, p1[1] * SS],
                  fill=blend((60, 52, 44), sh_a * 0.85))
        draw_eraser(d, gx, gy, gw, gh, 1.0, 0.42, 0.0)

    # ---- 标题 ----
    tp = title_prog(t)
    if tp > 0:
        hand_text(im, "最后一格", 1200, 1424, 126, tp, 31.3, INK, "center", 1.0, 1.0)
        if tp > 0.55:
            hand_text(im, "THE  LAST  PANEL", 1205, 1474, 27,
                      clamp((tp - 0.55) / 0.45, 0, 1), 37.7, INK_SOFT, "center", 0.9, 0.7)

    # ---- 日期字幕 ----
    if t < 3.05:
        hand_text(im, "第 1 天", LEFT_B + 34, TOP_B + 44, 26, clamp((t - 0.65) / 0.5, 0, 1), 41.3, INK, "left", 0.95)
    elif t < 3.75:
        hand_text(im, "第 2 天", LEFT_B + 34, TOP_B + 44, 26, clamp((t - 3.05) / 0.2, 0, 1), 41.3, INK, "left", 0.95)
    elif t < 4.45:
        hand_text(im, "第 3 天", LEFT_B + 34, TOP_B + 44, 26, clamp((t - 3.75) / 0.2, 0, 1), 41.3, INK, "left", 0.95)
    elif t < 15.6:
        hand_text(im, "第 4 天", LEFT_B + 34, TOP_B + 44, 26, clamp((t - 4.45) / 0.2, 0, 1), 41.3, INK, "left", 0.95)
    elif t > 28.6:
        hand_text(im, "第 5 天", 836, 638, 30, clamp((t - 28.6) / 0.5, 0, 1), 43.1, INK, "left", 0.9)

    return im.convert("RGB").resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- 配乐
def make_score(duration, bpm):
    wa = wv.wa
    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.8)
    spb = 60.0 / bpm
    bars = int(math.ceil(duration / (spb * 4.0))) + 1

    pad = s.track("pad", name="pad", gain_db=-21.0, pan=0.0, seed=1)
    pl = s.track("pluck", name="pluck", gain_db=-12.0, pan=0.12, seed=2)
    bs = s.track("bass", name="bass", gain_db=-11.5, pan=-0.05, seed=3)

    # 和弦：Am - Am - F - F - C - C - G - E - Am - Am - F - E
    CH = [[57, 60, 64], [57, 60, 64], [53, 57, 60], [53, 57, 60],
          [48, 52, 55], [48, 52, 55], [55, 59, 62], [52, 56, 59],
          [57, 60, 64], [57, 60, 64], [53, 57, 60], [52, 56, 59]]
    ROOT = [45, 45, 41, 41, 36, 36, 43, 40, 45, 45, 41, 40]
    NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def nm(m):
        return NAMES[int(m) % 12] + str(int(m) // 12 - 1)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = CH[bi % 12]
        sec = bi
        # pad：前半完整，后半抽稀
        if sec < 6:
            for m in ch:
                pad.note(b0, nm(m), 3.9, 0.32)
        elif sec in (6, 7):
            pad.note(b0, nm(ch[0]), 3.9, 0.26)
        elif sec == 8:
            pad.note(b0, nm(ch[0]), 3.9, 0.30)

        # 旋律动机：前 3 小节唱主题，之后变形
        if sec < 3:
            mel = [(0.0, ch[0] + 12, 0.5, 0.50), (1.0, ch[2] + 12, 0.5, 0.42),
                   (1.75, ch[1] + 12, 0.4, 0.40), (2.5, ch[2] + 12, 0.6, 0.46),
                   (3.25, ch[0] + 24, 0.7, 0.34)]
            for (o, m, d, g) in mel:
                pl.note(b0 + o, nm(m), d, g)
        elif sec in (3, 4, 5):
            # 紧绷：八分音符邻音
            base = ch[0] + 12
            for k in range(8):
                m = base + (1 if k in (2, 5) else 0)
                pl.note(b0 + k * 0.5, nm(m), 0.22, 0.30 + 0.12 * (k % 2))
        elif sec in (6, 7):
            # 空：稀疏单音
            pl.note(b0 + 0.5, nm(ch[2] + 12), 0.5, 0.30)
            pl.note(b0 + 2.5, nm(ch[1] + 24), 0.5, 0.22)
        elif sec == 8:
            # 缓慢上行
            for k, o in enumerate((0.0, 1.5, 3.0)):
                pl.note(b0 + o, nm(ch[0] + 12 + k * 3), 0.6, 0.28)

        # 低音
        if sec < 4:
            bs.note(b0, nm(ROOT[bi % 12]), 1.9, 0.55)
            bs.note(b0 + 2.0, nm(ROOT[bi % 12] + 7), 1.4, 0.34)
        elif sec < 8:
            for k in range(4):
                bs.note(b0 + k, nm(ROOT[bi % 12] - 12), 0.5,
                        0.42 if k in (0, 2) else 0.28)
        else:
            bs.note(b0, nm(ROOT[bi % 12] - 12), 3.8, 0.62)

    # 结尾：深低音 + 一声高音
    end = max(0.0, duration / spb - 4.0)
    bs.note(end, nm(33), 4.0, 0.75)
    pl.note(end + 1.2, nm(81), 2.4, 0.34)
    pad.note(end, nm(57), 3.9, 0.22)

    s.length(beats=duration / spb)
    s.fade(out_seconds=1.6)
    return s


# ---------------------------------------------------------------- 装配
film = wv.Film(W, H, duration=30.0, fps=24, ss=1, grain=False,
               theme="paper", bpm=84, name="last-panel")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 30.0, transition="cut")
s1.draw(lambda c, t: c.paste_full(frame(t)), at=0, enter="none")

# 音效
film.sfx("swish", at=0.28, gain=-22)
film.sfx("swish", at=0.55, gain=-23)
film.sfx("swish", at=0.82, gain=-23)
film.sfx("swish", at=1.10, gain=-22)
film.sfx("swish", at=1.55, gain=-20, pitch=4)
film.sfx("swish", at=1.95, gain=-21, pitch=3)
film.sfx("tick", at=3.05, gain=-16)
film.sfx("tick", at=3.75, gain=-16)
film.sfx("tick", at=4.45, gain=-15)
film.sfx("pop", at=5.35, gain=-16, pitch=9)
film.sfx("click", at=7.25, gain=-20)
film.sfx("bassdrop", at=7.95, gain=-15)
film.sfx("swish", at=9.9, dur=0.9, gain=-12)
film.sfx("glitch", at=11.35, gain=-19)
film.sfx("tick", at=11.85, gain=-18, pitch=6)
film.sfx("tick", at=12.15, gain=-18, pitch=6)
film.sfx("tick", at=12.45, gain=-18, pitch=6)
film.sfx("swish", at=13.45, gain=-17)
film.sfx("swish", at=13.95, gain=-17)
film.sfx("click", at=14.62, gain=-14, pitch=-3)
film.sfx("whoosh", at=15.15, dur=0.5, gain=-10)
film.sfx("swish", at=15.8, dur=1.3, gain=-9)
film.sfx("sparkle", at=16.9, gain=-20)
film.sfx("riser", at=20.9, dur=3.6, gain=-16)
film.sfx("bassdrop", at=25.0, gain=-11)
film.sfx("chime", at=27.35, gain=-13)
film.flicker_exclude(0.0, 30.0)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "last-panel.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
