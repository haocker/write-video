# -*- coding: utf-8 -*-
"""blueprint · 蓝图工程图 · 扫描线一过图纸变实物（播客麦克风 2.5D 假投影移植）
11 秒 / 1920x1080 / 30fps
运行: python3 film.py

3D raymarch 降级为 2.5D 假投影直绘：椭圆+描边+offset 深色副本模拟厚度。
图纸 0.35-2.7s 自上而下擦入（uReveal 行掩膜 + 绘图仪辉光 tip）→ 引线/尺寸/标题栏 →
3.85-4.45s 沿 y 爆炸 6 零件 → 4.45-5.2s 组装 + 到位微震 0.02exp(-9Δt)sin(40Δt) →
5.25-6.55s 扫描线逐行 mix 蓝图线稿→实物（numpy 行掩膜 Image.composite）→
7.0-8.6s 扫光棒掠过 → 7.2s 字幕「从图纸 到实物」。
全确定性：hash1 伪随机，无全局随机态。
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           "/root/.codingmatrix/project-tpl/.ai-ready/skills/write-video/runtime"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import write_video as wv

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")
SS = 2  # 与 film ss 一致
CX = 960.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_io(x):
    x = clamp(x, 0.0, 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def out_cubic(x):
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 3


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


LINEC = (224, 236, 255)      # 蓝图亮线
DIMC = (159, 195, 239)       # 次级线
PAPERF = (16, 41, 79)        # 蓝图零件填充
SIDEC = (8, 28, 56)          # 厚度侧影
AXISC = (127, 168, 220)

# === 零件（装配位 cy / 爆炸偏移 px）；绘制顺序 = 遮挡顺序（底座先于铭牌） ===
PARTS = [
    ("grille", 360.0, -170.0),
    ("ring", 486.0, -80.0),
    ("yoke", 585.0, 45.0),
    ("pole", 712.0, 95.0),
    ("plate", 833.0, 90.0),
    ("base", 846.0, 150.0),
]
DRAW_ORDER = [0, 1, 2, 3, 5, 4]


def part_e(i, t):
    """第 i 个零件爆炸量 0..1：3.85+0.04i 起 0.55s 展开；4.45+0.05i 起 0.5s 合拢。"""
    st = 3.85 + i * 0.04
    up = ease_io((t - st) / 0.55) if t > st else 0.0
    ad = 4.45 + i * 0.05
    dn = 1.0 - ease_io((t - ad) / 0.5) if t > ad else 1.0
    return min(up, dn)


def part_cy(i, t):
    """零件当前 y（爆炸偏移 + 到位微震 0.02·exp(-9Δ)·sin(40Δ)·190）。"""
    name, cy_a, off = PARTS[i]
    e = part_e(i, t)
    dy = off * e
    ta = 4.95 + i * 0.05
    if t > ta:
        dt = t - ta
        dy += 0.02 * math.exp(-9.0 * dt) * math.sin(40.0 * dt) * 190.0 * clamp(1.0 - dt / 0.6, 0, 1)
    return cy_a + dy, e


def reveal_y(t):
    """uReveal 自上而下擦入前沿（设计 y）。"""
    if t <= 0.35:
        return 120.0
    return 120.0 + (1070.0 - 120.0) * ease_io((t - 0.35) / 2.35)


def spring_pop(t):
    if t <= 0:
        return 0.0
    return 1.0 - math.exp(-8.0 * t) * math.cos(2 * math.pi * 1.9 * t)


# === 绘制封装（设计坐标 → ×SS，PIL RGBA 半透明混合） ===
def _ink(col, a=1.0):
    if col is None:
        return None
    if len(col) == 4:
        return col
    return col + (int(a * 255),)


class G(object):
    def __init__(self, im):
        self.d = ImageDraw.Draw(im, "RGBA")

    def line(self, x1, y1, x2, y2, col, w=2.0, a=1.0):
        self.d.line([x1 * SS, y1 * SS, x2 * SS, y2 * SS], fill=_ink(col, a),
                    width=max(1, int(round(w * SS))))

    def circle(self, x, y, r, fill=None, outline=None, w=2.0, a=1.0):
        box = [(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS]
        self.d.ellipse(box, fill=_ink(fill, a), outline=_ink(outline, a),
                       width=max(1, int(round(w * SS))))

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, w=2.0, a=1.0):
        box = [(x - rx) * SS, (y - ry) * SS, (x + rx) * SS, (y + ry) * SS]
        self.d.ellipse(box, fill=_ink(fill, a), outline=_ink(outline, a),
                       width=max(1, int(round(w * SS))))

    def rect(self, x, y, w_, h_, fill=None, outline=None, lw=2.0, a=1.0, r=0):
        box = [x * SS, y * SS, (x + w_) * SS, (y + h_) * SS]
        f, o = _ink(fill, a), _ink(outline, a)
        if r > 0:
            self.d.rounded_rectangle(box, radius=int(r * SS), fill=f, outline=o,
                                     width=max(1, int(round(lw * SS))))
        else:
            self.d.rectangle(box, fill=f, outline=o, width=max(1, int(round(lw * SS))))

    def arc(self, x, y, r, a0, a1, col, w=3.0, a=1.0):
        box = [(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS]
        self.d.arc(box, a0, a1, fill=_ink(col, a), width=max(1, int(round(w * SS))))

    def poly(self, pts, fill=None, outline=None, lw=2.0, a=1.0):
        pix = [(x * SS, y * SS) for x, y in pts]
        self.d.polygon(pix, fill=_ink(fill, a), outline=_ink(outline, a),
                       width=max(1, int(round(lw * SS))))

    def text(self, s, x, y, size, col, bold=False, align="center", a=1.0):
        from write_video import fonts as _fonts
        f = _fonts.load("sans_bold" if bold else "sans", max(1, int(round(size * SS))))
        anchor = {"center": "mm", "left": "lm", "right": "rm"}[align]
        self.d.text((x * SS, y * SS), s, font=f, fill=_ink(col, a), anchor=anchor)


# === 图纸底（缓存一次）：深蓝渐变 + 细/粗双层格 + hash 斑 + 图框 ===
def build_paper():
    im = Image.new("RGB", (W * SS, H * SS), (10, 30, 62))
    d = ImageDraw.Draw(im, "RGBA")
    top, bot = (10, 30, 62), (18, 49, 89)
    for yy in range(H * SS):
        u = yy / float(H * SS)
        d.line([(0, yy), (W * SS, yy)],
               fill=(int(top[0] + (bot[0] - top[0]) * u), int(top[1] + (bot[1] - top[1]) * u),
                     int(top[2] + (bot[2] - top[2]) * u), 255))
    fine, coarse = H / 54.0, H / 10.8
    x = 0.0
    while x < W:
        d.line([(x * SS, 0), (x * SS, H * SS)], fill=(42, 74, 122, 70), width=int(SS))
        x += fine
    y = 0.0
    while y < H:
        d.line([(0, y * SS), (W * SS, y * SS)], fill=(42, 74, 122, 70), width=int(SS))
        y += fine
    x = 0.0
    while x < W:
        d.line([(x * SS, 0), (x * SS, H * SS)], fill=(58, 96, 150, 110), width=int(1.5 * SS))
        x += coarse
    y = 0.0
    while y < H:
        d.line([(0, y * SS), (W * SS, y * SS)], fill=(58, 96, 150, 110), width=int(1.5 * SS))
        y += coarse
    for i in range(46):
        bx = hash1(i * 3.1 + 1) * W
        by = hash1(i * 7.7 + 2) * H
        br = 60 + hash1(i * 13.3 + 3) * 220
        col = (58, 110, 168) if hash1(i * 5.9 + 4) > 0.5 else (6, 18, 38)
        d.ellipse([(bx - br) * SS, (by - br) * SS, (bx + br) * SS, (by + br) * SS],
                  fill=col + (int((0.02 + hash1(i * 2.3 + 5) * 0.03) * 255),))
    for i in range(420):
        sx = hash1(i * 11.7 + 50) * W
        sy = hash1(i * 17.3 + 51) * H
        sr = 1 + hash1(i * 23.1 + 52) * 2.2
        d.ellipse([(sx - sr) * SS, (sy - sr) * SS, (sx + sr) * SS, (sy + sr) * SS],
                  fill=(120, 170, 220, 14))
    d.rectangle([30 * SS, 30 * SS, (W - 30) * SS, (H - 30) * SS],
                outline=(74, 118, 170, 150), width=2 * int(SS))
    for (cx0, cy0, dx, dy) in ((30, 30, 1, 1), (W - 30, 30, -1, 1),
                               (30, H - 30, 1, -1), (W - 30, H - 30, -1, -1)):
        d.line([(cx0 * SS, cy0 * SS), ((cx0 + dx * 34) * SS, cy0 * SS)],
               fill=(122, 168, 220, 200), width=3 * int(SS))
        d.line([(cx0 * SS, cy0 * SS), (cx0 * SS, (cy0 + dy * 34) * SS)],
               fill=(122, 168, 220, 200), width=3 * int(SS))
    return im


PAPER = build_paper()
PAPER_RGBA = PAPER.convert("RGBA")


# === 零件绘制（mode: line 蓝图线稿 / real 实物；offset 深色副本模拟厚度） ===
def draw_grille(g, cy, mode):
    r = 108.0
    if mode == "line":
        g.circle(CX + 10, cy + 14, r, fill=SIDEC + (150,))
        g.circle(CX, cy, r, fill=PAPERF, outline=LINEC, w=3)
        for k in (0.30, 0.62, 0.86):
            g.ellipse(CX, cy, r * k, r, outline=DIMC + (170,), w=1.6)
        for dy in (-54, -18, 18, 54):
            hw = math.sqrt(max(4.0, r * r - dy * dy)) - 5
            g.line(CX - hw, cy + dy, CX + hw, cy + dy, DIMC + (170,), 1.6)
        g.circle(CX, cy, 40, fill=(10, 26, 50), outline=DIMC + (140,), w=1.5)
        g.arc(CX, cy, r - 8, 195, 255, (242, 248, 255), 4)
    else:
        g.circle(CX + 10, cy + 14, r, fill=(4, 6, 10, 170))
        for i in range(12, 0, -1):
            u = i / 12.0
            g.circle(CX, cy, r * u, fill=(int(112 - 74 * (1 - u)), int(124 - 84 * (1 - u)),
                                          int(140 - 96 * (1 - u))))
        g.circle(CX, cy, r, outline=(14, 17, 22), w=2.5)
        for k in (0.30, 0.62, 0.86):
            g.ellipse(CX, cy, r * k, r, outline=(168, 180, 194, 140), w=1.6)
        for dy in (-54, -18, 18, 54):
            hw = math.sqrt(max(4.0, r * r - dy * dy)) - 5
            g.line(CX - hw, cy + dy, CX + hw, cy + dy, (168, 180, 194, 140), 1.6)
        g.circle(CX, cy, 40, fill=(8, 10, 14))
        g.arc(CX, cy, r - 10, 200, 250, (210, 224, 240), 4)
        g.ellipse(CX - 52, cy - 62, 13, 7, fill=(235, 242, 250, 70))


def draw_ring(g, cy, mode):
    w_, h_ = 176.0, 40.0
    if mode == "line":
        g.rect(CX - w_ / 2 + 10, cy - h_ / 2 + 14, w_, h_, fill=SIDEC + (150,), r=12)
        g.rect(CX - w_ / 2, cy - h_ / 2, w_, h_, fill=PAPERF, outline=LINEC, lw=3, r=12)
        for k in (-1, 0, 1):
            g.line(CX + k * 44, cy - h_ / 2 + 4, CX + k * 44, cy + h_ / 2 - 4, DIMC + (190,), 2.5)
        g.line(CX - w_ / 2 + 14, cy - h_ / 2 + 3, CX + w_ / 2 - 14, cy - h_ / 2 + 3,
               (242, 248, 255), 2.5)
    else:
        g.rect(CX - w_ / 2 + 10, cy - h_ / 2 + 14, w_, h_, fill=(4, 6, 10, 170), r=12)
        g.rect(CX - w_ / 2, cy - h_ / 2, w_, h_, fill=(201, 210, 220), r=12)
        g.rect(CX - w_ / 2, cy - h_ / 2, w_, h_ * 0.45, fill=(160, 172, 186), r=12)
        g.rect(CX - w_ / 2 + 6, cy - h_ / 2 + 4, w_ - 12, 8, fill=(235, 242, 250, 200), r=4)
        for k in (-1, 0, 1):
            g.line(CX + k * 44, cy - h_ / 2 + 5, CX + k * 44, cy + h_ / 2 - 5,
                   (90, 100, 114, 160), 2.5)
        g.rect(CX - w_ / 2, cy - h_ / 2, w_, h_, outline=(30, 36, 46), lw=2, r=12)


def draw_yoke(g, cy, mode):
    hy = cy + 77
    ax, ay = 80.0, -80.0
    if mode == "line":
        for s in (-1, 1):
            g.line(CX + s * ax + 10, hy + ay + 14, CX + s * ax * 0.72 + 10, hy + 20,
                   SIDEC + (150,), 10)
            g.line(CX + s * ax, hy + ay, CX + s * ax * 0.72, hy + 6, LINEC, 9)
            g.circle(CX + s * ax, hy + ay, 8, fill=PAPERF, outline=LINEC, w=2.5)
        g.circle(CX + 10, hy + 14, 16, fill=SIDEC + (150,))
        g.circle(CX, hy, 16, fill=PAPERF, outline=LINEC, w=3)
        g.circle(CX, hy, 6, outline=DIMC + (190,), w=2)
    else:
        for s in (-1, 1):
            g.line(CX + s * ax, hy + ay, CX + s * ax * 0.72, hy + 6, (86, 96, 110), 11)
            g.line(CX + s * ax, hy + ay, CX + s * ax * 0.72, hy + 6, (138, 148, 162, 130), 2)
            g.circle(CX + s * ax, hy + ay, 8, fill=(96, 106, 120), outline=(26, 31, 38), w=2)
        g.circle(CX, hy, 16, fill=(96, 106, 120), outline=(26, 31, 38), w=2)
        g.circle(CX, hy, 6, fill=(24, 28, 35))


def draw_pole(g, cy, mode):
    w_, h_ = 26.0, 108.0
    x0, y0 = CX - w_ / 2, cy - h_ / 2
    if mode == "line":
        g.rect(x0 + 10, y0 + 14, w_, h_, fill=SIDEC + (150,), r=10)
        g.rect(x0, y0, w_, h_, fill=PAPERF, outline=LINEC, lw=3, r=10)
        for k in (0.3, 0.62):
            g.line(x0 + 4, y0 + h_ * k, x0 + w_ - 4, y0 + h_ * k, DIMC + (170,), 1.8)
        g.line(x0 + 5, y0 + 4, x0 + 5, y0 + h_ - 4, (242, 248, 255), 2)
    else:
        g.rect(x0 + 10, y0 + 14, w_, h_, fill=(4, 6, 10, 170), r=10)
        g.rect(x0, y0, w_, h_, fill=(66, 74, 86), r=10)
        g.rect(x0, y0, w_ * 0.4, h_, fill=(46, 52, 62), r=10)
        for k in (0.3, 0.62):
            g.line(x0 + 4, y0 + h_ * k, x0 + w_ - 4, y0 + h_ * k, (90, 100, 114, 150), 1.8)
        g.rect(x0, y0, w_, h_, outline=(14, 17, 22), lw=2, r=10)


def draw_plate(g, cy, mode):
    w_, h_ = 92.0, 26.0
    x0, y0 = CX - w_ / 2, cy - h_ / 2
    if mode == "line":
        g.rect(x0 + 8, y0 + 12, w_, h_, fill=SIDEC + (150,), r=5)
        g.rect(x0, y0, w_, h_, fill=PAPERF, outline=LINEC, lw=2.5, r=5)
        for k in (0.3, 0.62):
            g.line(x0 + 14, y0 + h_ * k, x0 + w_ - 14, y0 + h_ * k, DIMC + (170,), 1.6)
    else:
        g.rect(x0 + 8, y0 + 12, w_, h_, fill=(4, 6, 10, 170), r=5)
        g.rect(x0, y0, w_, h_, fill=(116, 126, 138), r=5)
        for i in range(7):
            g.line(x0 + 5, y0 + 4 + i * 3.0, x0 + w_ - 5, y0 + 4 + i * 3.0,
                   (170, 182, 196, 60), 1.0)
        g.text("PM-02", CX, cy, 13, (38, 43, 50), bold=True)
        g.rect(x0, y0, w_, h_, outline=(30, 36, 46), lw=1.5, r=5)


def draw_base(g, cy, mode):
    rx, ry = 150.0, 36.0
    top_dy = -26.0
    if mode == "line":
        g.ellipse(CX + 10, cy + 14, rx, ry, fill=SIDEC + (140,))
        g.rect(CX - rx, cy + top_dy, rx * 2, -top_dy, fill=PAPERF)
        g.ellipse(CX, cy, rx, ry, fill=PAPERF, outline=LINEC, w=3)
        g.line(CX - rx, cy + top_dy, CX - rx, cy, LINEC, 3)
        g.line(CX + rx, cy + top_dy, CX + rx, cy, LINEC, 3)
        g.ellipse(CX, cy + top_dy, rx, ry, fill=(20, 52, 94), outline=LINEC, w=3)
        kx, ky, kr = CX + 108, cy + top_dy - 2, 22.0
        g.circle(kx + 8, ky + 12, kr, fill=SIDEC + (150,))
        g.circle(kx, ky, kr, fill=PAPERF, outline=LINEC, w=3)
        for a in range(0, 360, 30):
            g.line(kx + math.cos(math.radians(a)) * kr * 0.45,
                   ky + math.sin(math.radians(a)) * kr * 0.45,
                   kx + math.cos(math.radians(a)) * kr * 0.9,
                   ky + math.sin(math.radians(a)) * kr * 0.9, DIMC + (190,), 1.8)
        g.arc(CX, cy + top_dy, rx - 8, 200, 250, (242, 248, 255), 4)
    else:
        g.ellipse(CX + 10, cy + 14, rx, ry, fill=(4, 6, 10, 170))
        g.rect(CX - rx, cy + top_dy, rx * 2, -top_dy, fill=(48, 55, 66))
        g.ellipse(CX, cy, rx, ry, fill=(34, 40, 49))
        g.ellipse(CX, cy + top_dy, rx, ry, fill=(78, 88, 102), outline=(24, 29, 36), w=2)
        g.ellipse(CX, cy + top_dy, rx * 0.82, ry * 0.72, fill=(96, 108, 124, 150))
        kx, ky, kr = CX + 108, cy + top_dy - 2, 22.0
        g.circle(kx + 8, ky + 12, kr, fill=(4, 6, 10, 170))
        g.circle(kx, ky, kr, fill=(104, 114, 128), outline=(28, 33, 41), w=2)
        for a in range(0, 360, 30):
            g.line(kx + math.cos(math.radians(a)) * kr * 0.45,
                   ky + math.sin(math.radians(a)) * kr * 0.45,
                   kx + math.cos(math.radians(a)) * kr * 0.9,
                   ky + math.sin(math.radians(a)) * kr * 0.9, (30, 35, 43, 200), 2.0)
        g.arc(CX, cy + top_dy, rx - 8, 200, 250, (180, 196, 214), 3.5)


PART_DRAW = {"grille": draw_grille, "ring": draw_ring, "yoke": draw_yoke,
             "pole": draw_pole, "plate": draw_plate, "base": draw_base}


def draw_axis(g, alpha=1.0):
    """中心轴点划线 [34,8,4,8]。"""
    x, y0, y1 = CX, 140.0, 1050.0
    pat = (34, 8, 4, 8)
    y = y0
    k = 0
    while y < y1:
        seg = pat[k % 4]
        if k % 2 == 0:
            g.line(x, y, x, min(y + seg, y1), AXISC + (int(200 * alpha),), 2)
        y += seg
        k += 1


def draw_content(g, t):
    """蓝图内容：线稿零件（按当前爆炸/组装位）+ 中心轴。"""
    for i in DRAW_ORDER:
        cy, _e = part_cy(i, t)
        PART_DRAW[PARTS[i][0]](g, cy, "line")
    draw_axis(g, clamp((reveal_y(t) - 140) / 120.0, 0, 1))


def build_line_full(t):
    im = PAPER_RGBA.copy()
    g = G(im)
    draw_content(g, t)
    return im


def build_content(t):
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    g = G(im)
    draw_content(g, t)
    return im


def build_real():
    """实物层：暗棚背景 + 实体材质麦克风 + 地面软影/反射。"""
    im = Image.new("RGB", (W * SS, H * SS), (5, 7, 11))
    d = ImageDraw.Draw(im, "RGBA")
    top, bot = (14, 20, 29), (4, 6, 10)
    for yy in range(H * SS):
        u = yy / float(H * SS)
        d.line([(0, yy), (W * SS, yy)],
               fill=(int(top[0] + (bot[0] - top[0]) * u), int(top[1] + (bot[1] - top[1]) * u),
                     int(top[2] + (bot[2] - top[2]) * u), 255))
    for i in range(14):
        rr = 760 - i * 48
        d.ellipse([(CX - rr) * SS, (560 - rr * 0.72) * SS, (CX + rr) * SS, (560 + rr * 0.72) * SS],
                  fill=(44, 58, 78, 26))
    floor = 895.0
    for yy in range(int(floor * SS), H * SS):
        u = (yy - floor * SS) / float(H * SS - floor * SS)
        d.line([(0, yy), (W * SS, yy)],
               fill=(11 + int(4 * u), 14 + int(5 * u), 20 + int(6 * u), 255))
    d.line([(0, floor * SS), (W * SS, floor * SS)], fill=(70, 86, 108, 90), width=2 * int(SS))
    sh = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.ellipse([(CX - 240) * SS, (floor - 26) * SS, (CX + 240) * SS, (floor + 30) * SS],
               fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(18 * SS))
    im.paste(Image.new("RGB", im.size, (0, 0, 0)), (0, 0), sh.getchannel("A").point(lambda v: v // 2))
    g = G(im)
    for i in DRAW_ORDER:
        PART_DRAW[PARTS[i][0]](g, PARTS[i][1], "real")
    # 地面反射（底座 + 立杆倒影，快速衰减）
    refl = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    gr = G(refl)
    draw_base(gr, 2 * floor - 846.0, "real")
    draw_pole(gr, 2 * floor - 712.0, "real")
    arr = np.asarray(refl, dtype=np.uint8).copy()
    h0 = int(floor * SS)
    fade = np.linspace(255, 0, arr.shape[0] - h0).astype(np.uint16)
    arr[h0:, :, 3] = (arr[h0:, :, 3].astype(np.uint16) * 20 // 255 * fade[:, None] // 255).astype(np.uint8)
    refl = Image.fromarray(arr, "RGBA")
    im.paste(refl, (0, 0), refl)
    return im


REAL = build_real().convert("RGBA")

# === 2D 标注层（引线 / 尺寸线 / 标题栏） ===
LEADERS = [
    (0, 76.0, -60.0, (1330.0, 250.0), (1374.0, 250.0), "1"),
    (1, 84.0, 0.0, (1350.0, 420.0), (1394.0, 420.0), "2"),
    (2, -86.0, 40.0, (560.0, 640.0), (516.0, 640.0), "3"),
    (5, 120.0, 10.0, (1360.0, 800.0), (1404.0, 800.0), "4"),
]


def build_ann(t):
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    g = G(im)
    for k, (pi, axo, ayo, elbow, npos, lab) in enumerate(LEADERS):
        t0 = 1.0 + k * 0.22
        if t <= t0:
            continue
        cy_a = PARTS[pi][1]
        anchor = (CX + axo, cy_a + ayo)
        p1 = out_cubic((t - t0) / 0.5)
        ex = anchor[0] + (elbow[0] - anchor[0]) * p1
        ey = anchor[1] + (elbow[1] - anchor[1]) * p1
        g.line(anchor[0], anchor[1], ex, ey, LINEC, 2)
        if p1 >= 1.0:
            p2 = out_cubic((t - t0 - 0.25) / 0.4)
            dx, dy = npos[0] - elbow[0], npos[1] - elbow[1]
            g.line(elbow[0], elbow[1], elbow[0] + dx * p2, elbow[1] + dy * p2, LINEC, 2)
            sp = clamp(spring_pop(t - t0 - 0.35), 0, 1.05)
            if sp > 0:
                g.circle(npos[0], npos[1], 22.0 * sp, fill=(16, 41, 79, 230), outline=LINEC, w=2.5)
                g.text(lab, npos[0], npos[1], 22, LINEC, bold=True)
        g.circle(anchor[0], anchor[1], 5, fill=LINEC)
    pd = out_cubic((t - 2.6) / 0.8)
    if pd > 0:
        gx = 1178.0
        half = 108.0 * pd
        g.line(gx, 360 - half, gx, 360 + half, LINEC, 2)
        for sgn in (-1, 1):
            ye = 360 + sgn * half
            g.poly([(gx - 7, ye - sgn * 16), (gx + 7, ye - sgn * 16), (gx, ye)], fill=LINEC)
        g.line(1068, 252, 1196, 252, DIMC + (150,), 1.2)
        g.line(1068, 468, 1196, 468, DIMC + (150,), 1.2)
        g.text("Ø88", gx + 18, 360, 30, LINEC, bold=True, align="left")
        dy_ = 940.0
        halfw = 150.0 * pd
        g.line(CX - halfw, dy_, CX + halfw, dy_, LINEC, 2)
        for sgn in (-1, 1):
            xe = CX + sgn * halfw
            g.poly([(xe - sgn * 16, dy_ - 7), (xe - sgn * 16, dy_ + 7), (xe, dy_)], fill=LINEC)
        g.line(810, 892, 810, 950, DIMC + (150,), 1.2)
        g.line(1110, 892, 1110, 950, DIMC + (150,), 1.2)
        g.text("462→286", CX, dy_ + 26, 30, LINEC, bold=True)
    ta = clamp((reveal_y(t) - 880) / 132.0, 0, 1)
    if ta > 0:
        x0, y0, bw, bh = 1360.0, 880.0, 520.0, 132.0
        g.rect(x0, y0, bw, bh, fill=(10, 30, 62, int(200 * ta)),
               outline=LINEC + (int(255 * ta),), lw=2)
        g.line(x0 + 260, y0, x0 + 260, y0 + bh, LINEC + (int(220 * ta),), 1.5)
        g.line(x0, y0 + 66, x0 + bw, y0 + 66, LINEC + (int(220 * ta),), 1.5)
        cells = [("DWG. NO.", "XX-2026-020", x0 + 16, y0 + 20),
                 ("SCALE", "1:2", x0 + 276, y0 + 20),
                 ("DRAWN", "", x0 + 16, y0 + 86),
                 ("DATE", "2026-10-25", x0 + 276, y0 + 86)]
        for lab, val, cx0, cy0 in cells:
            g.text(lab, cx0, cy0, 14, DIMC + (int(220 * ta),), align="left")
            g.text(val, cx0, cy0 + 26, 22, LINEC + (int(255 * ta),), bold=True, align="left")
    return im


LINE_CACHE = {}
ANN_CACHE = {}


def get_line(t):
    if t < 5.85:
        return build_line_full(t)
    if "final" not in LINE_CACHE:
        LINE_CACHE["final"] = build_line_full(5.85)
    return LINE_CACHE["final"]


def get_ann(t):
    if t < 3.6:
        return build_ann(t)
    if "final" not in ANN_CACHE:
        ANN_CACHE["final"] = build_ann(3.6)
    return ANN_CACHE["final"]


def row_mask(y_front, band=60.0, invert=False):
    """行掩膜：y < 前沿 → 255，y > 前沿 → 0，±band/2 过渡。"""
    yy = np.arange(H * SS, dtype=np.float32) / SS
    vals = np.clip(0.5 + (y_front - yy) / band, 0.0, 1.0)
    if invert:
        vals = 1.0 - vals
    m = np.repeat((vals * 255).astype(np.uint8)[:, None], W * SS, axis=1)
    return Image.fromarray(m, "L")


# === 扫光棒（7.0-8.6s 斜亮带，构建一次） ===
def build_sweep():
    sw_img = Image.new("RGBA", (340, 1150), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sw_img)
    for x in range(340):
        a = 255.0 * math.exp(-(((x - 170) / 85.0) ** 2))
        ds.line([(x, 0), (x, 1150)], fill=(210, 230, 255, int(a * 0.5)))
    return sw_img.rotate(16, expand=True, resample=Image.BICUBIC)


SWEEP = build_sweep()


def main_scene(c, t):
    ry = reveal_y(t)
    if t < 5.25:
        c.img.paste(PAPER, (0, 0))
        content = build_content(t)
        if t < 2.75:
            m = ImageChops.multiply(content.getchannel("A"), row_mask(ry, band=50.0))
            c.img.paste(content, (0, 0), m)
        else:
            c.img.paste(content, (0, 0), content)
        ann = get_ann(t)
        c.img.paste(ann, (0, 0), ann)
    elif t < 6.75:
        scan_y = 190.0 + (1130.0 - 190.0) * clamp((t - 5.25) / 1.3, 0, 1)
        comp = Image.composite(REAL, get_line(t), row_mask(scan_y))
        c.img.paste(comp, (0, 0))
        ann = get_ann(t)
        m2 = ImageChops.multiply(ann.getchannel("A"), row_mask(scan_y))
        c.img.paste(ann, (0, 0), m2)
        c.flush()
        for k in range(26):
            yy = scan_y + k * 3.2
            c.line(0, yy, W, yy, color=(115, 204, 255), width=2.5, alpha=0.30 * math.exp(-k / 8.0))
        c.line(0, scan_y, W, scan_y, color=(225, 242, 255), width=3, alpha=0.95)
        c.line(0, scan_y - 4, W, scan_y - 4, color=(150, 214, 255), width=1.5, alpha=0.4)
        c.glow(W / 2, scan_y, 460, "#73CCFF", 0.5)
        c.glow(30, scan_y, 40, "#BFE2FF", 0.8)
        c.glow(W - 30, scan_y, 40, "#BFE2FF", 0.8)
    else:
        c.img.paste(REAL, (0, 0))
    c.flush()

    # 绘图仪辉光（0.35-2.75s 前沿 + 笔头）
    if 0.35 < t < 2.75:
        c.flush()
        c.line(500, ry, 1420, ry, color=(140, 210, 255), width=2.5, alpha=0.75)
        c.glow(960, ry, 300, "#5FB8FF", 0.5)
        pen_x = CX + 430 * math.sin((t - 0.35) * 2.1)
        c.glow(pen_x, ry, 26, "#EAF4FF", 0.9)
        c.circle(pen_x, ry, 5, fill="#F4F9FF")
    c.flush()

    # 扫光棒掠过成品（7.0-8.6s）
    if 7.0 <= t <= 8.6:
        p = (t - 7.0) / 1.6
        sx = -600 + p * 3000
        env = math.sin(math.pi * clamp(p, 0, 1)) * 0.75
        if env > 0.01:
            c.img.paste(SWEEP, (int(sx) * SS, -60 * SS), SWEEP)
    c.flush()
    c.vignette(radius=0.66, power=1.8, alpha=0.38)


# === 配乐：A 小调 120 BPM，pad+稀疏 pluck+bass ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    PROG = [(57, 60, 64), (53, 57, 60), (60, 64, 67), (55, 59, 62)]
    ROOTS = (33, 29, 36, 31)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][
            int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.7)
    pad = s.track("pad", name="pad", gain_db=-17.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="pen", gain_db=-13.0, pan=0.1, seed=2)
    bass = s.track("bass", name="bass", gain_db=-10.0, pan=0.0, seed=3)

    bars = 5
    for bi in range(bars):
        b0 = bi * 4.0
        ch = PROG[bi % 4]
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.45 if bi else 0.28)
        if bi >= 1:
            bass.note(b0, name(ROOTS[bi % 4]), 1.8, 0.7)
            bass.note(b0 + 2.5, name(ROOTS[bi % 4]), 1.2, 0.5)
        if bi >= 2:
            # 四度跳进：八分宽跳
            pool = list(ch) + [ch[0] + 12, ch[1] + 12]
            LEAP = (0, 3, 1, 4, 0, 3, 2, 4)
            for si, idx in enumerate(LEAP):
                vel = 0.42 if si % 2 == 0 else 0.32
                pluck.note(b0 + si * 0.5, name(pool[idx]), 0.3, vel)
    end_b = bars * 4.0
    # 金属 ding 单音收：bass 一拍短墩，无长和弦
    bass.note(end_b, name(ROOTS[0]), 1.0, 0.75)
    s.length(beats=total_beats)
    s.fade(out_seconds=1.2)
    return s


film = wv.Film(W, H, duration=11.0, fps=30, ss=2, theme="midnight",
               bpm=120, name="blueprint")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("从图纸 到实物", at=7.2, style="hero", y=120)
s1.text("BLUEPRINT · 工程图变身实录", at=7.7, style="subtitle", y=205)

# 音效对齐 120BPM 八分网格(0.25s)：pen ticks / whoosh 爆炸 / clink 组装到位 / data+riser 扫描 / sparkle 扫光
film.sfx("tick", at=0.75, gain=-16)
film.sfx("tick", at=1.0, gain=-16)
film.sfx("tick", at=1.25, gain=-16)
film.sfx("whoosh", at=4.0, gain=-9)
film.sfx("ding", at=5.25, gain=-12)
film.sfx("swipe", at=5.5, gain=-12)
film.sfx("riser", at=5.75, dur=0.8, gain=-12)
film.sfx("sparkle", at=7.0, gain=-12)
film.sfx("chime", at=8.5, gain=-9)
film.sfx("ding", at=10.2, gain=-12)

# 扫描线横掠为有意整幅内容替换，全帧排除闪烁检测窗口
film.flicker_exclude(5.25, 6.75)
film.flicker_exclude(7.0, 8.7)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "blueprint.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "blueprint.sheet.png"))
