# -*- coding: utf-8 -*-
"""collage · 拼贴剪贴 · 牛皮纸上一张张撕下、剪好、贴上：报纸、杂志、riso、拍立得、压纹标签、红印章
（部分移植：跳过 WebGL 三缓冲高度场打光，用 sty.texture 纸纹 + 普通偏移投影近似）
11 秒 / 1920x1080 / 30fps
运行: PYTHONPATH=<write-video runtime> python3 film.py

12fps 定格感：t_q=floor(t*12)/12 驱动全部道具落位；每帧 hash 抖动 0.9px（f12 量化）；
曝光微闪 flick=1±0.0175（末帧白/黑 overlay）。
道具：撕边报纸卡（撕边=每 2.2px 一点双频噪声折线+白色纤维芯 band+4 栏假字行+mono 网点图）、
光面杂志页（gloss 高光+卷角）、riso 双色印刷卡（粉/蓝网角 0.26/1.31 错位 ±1.1px numpy multiply）、
拍立得（白框+泡沫垫投影）、Dymo 压纹标签（浮雕字）、美纹胶带 ×4（波形撕头半透明）。
飞入：from 偏移 + 旋转 + lift 110→0，dur 0.42s outCubic（t_q 量化）；2.15s 起 8 块标题芯片
0.21s 间隔啪啪落下（独立旋转+阴影收紧）；钩子 6.67s 红印章「印」scale 1.4→1 + 湿墨 glow 闪光，
7.0s 蓝色日期章跟上。影子统一：半透明深色偏移多边形。
所有道具 sprite 一次性离屏构建（Canvas 画 → PIL rotate expand）缓存；飞行中旋转按 1/24° 桶缓存。
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_RP = "/root/.codingmatrix/project-tpl/.ai-ready/skills/write-video/runtime"
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""), _RP,
           os.path.abspath(os.path.join(HERE, "..", "..", "runtime"))):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
from PIL import Image, ImageDraw
import write_video as wv
from write_video import fonts, styles

W, H = 1920, 1080
SS = 2
OUT = os.path.join(HERE, "artifacts")

KRAFT = (200, 168, 120)
INK = (56, 40, 24)

# 道具表：id / 目标中心 / 目标旋转 / 尺寸 / 飞入 from 偏移（须完全出画）/ frot / t0
PROPS = [
    ("news",   400.0, 640.0, -4.0, 560.0, 390.0, (-780.0, -880.0), 14.0, 0.35),
    ("mag",   1450.0, 360.0,  5.0, 430.0, 550.0, (900.0, -660.0), -12.0, 0.90),
    ("riso",  1430.0, 810.0, -3.0, 420.0, 280.0, (920.0, 780.0), 10.0, 1.45),
    ("polar",  930.0, 840.0,  3.0, 320.0, 380.0, (-640.0, 1000.0), -9.0, 1.90),
    ("dymo",   240.0, 300.0, -6.0, 360.0,  86.0, (-880.0, 580.0), 16.0, 3.90),
]
TAPES = [  # cx, cy, rot, 色, t0
    (620.0, 470.0, -18.0, (255, 209, 102), 4.30),
    (1520.0, 115.0, 10.0, (143, 224, 196), 4.45),
    (1190.0, 800.0, -8.0, (255, 159, 133), 4.60),
    (930.0, 668.0, 6.0, (175, 162, 245), 4.75),
]
CHIPS = "拼贴手账一纸收藏"
CHIP_POS = [(660, 180), (860, 180), (1060, 180), (1260, 180),
            (660, 330), (860, 330), (1060, 330), (1260, 330)]
CHIP_COL = [(255, 159, 133), (143, 224, 196), (255, 207, 74), (111, 180, 238),
            (175, 162, 245), (255, 126, 107), (122, 207, 158), (255, 183, 77)]
T_CHIP0 = 2.15
T_STAMP = 6.67
T_DATE = 7.0


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def out_cubic(u):
    u = clamp(u, 0.0, 1.0)
    return 1.0 - (1.0 - u) ** 3


def tri_noise(u, seed):
    """0~1 三角插值 hash 噪声。"""
    k = u * 97.0
    i = math.floor(k)
    f = k - i
    a = hash1(seed + i * 1.37)
    b = hash1(seed + (i + 1) * 1.37)
    return a + (b - a) * (3.0 - 2.0 * f) * f * f


# === 撕边多边形（每 2.2px 一点，双频噪声 + sin taper） ===
def torn_rect(x0, y0, x1, y1, seed, amp=7.5, step=2.2):
    def edge(ax, ay, bx, by, sgn, sd):
        ln = math.hypot(bx - ax, by - ay)
        n = max(2, int(ln / step))
        pts = []
        for i in range(n + 1):
            u = i / float(n)
            taper = math.sin(u * math.pi) ** 0.35
            off = amp * taper * (0.62 * (tri_noise(u * ln / 46.0, seed + sd) - 0.5) * 2.0
                                 + 0.38 * (tri_noise(u * ln / 9.5, seed + sd + 40) - 0.5) * 2.0)
            nx = -(by - ay) / ln * sgn
            ny = (bx - ax) / ln * sgn
            pts.append((ax + (bx - ax) * u + nx * off, ay + (by - ay) * u + ny * off))
        return pts
    top = edge(x0, y0, x1, y0, -1, 1.0)
    right = edge(x1, y0, x1, y1, 1, 2.0)
    bot = edge(x1, y1, x0, y1, -1, 3.0)
    left = edge(x0, y1, x0, y0, -1, 4.0)
    return top[:-1] + right[:-1] + bot[:-1] + left[:-1]


def draw_torn_card(cv, x0, y0, x1, y1, seed, fill, fiber=(250, 247, 238)):
    pts = torn_rect(x0, y0, x1, y1, seed)
    cv.polygon(pts, fill=fill)
    cv.lines(pts + [pts[0]], color=fiber, width=5.0, alpha=0.9)
    # 纤维短线
    for i in range(0, len(pts), 29):
        if hash1(seed * 3.1 + i) < 0.55:
            px, py = pts[i]
            a = hash1(seed * 7.7 + i) * 2 * math.pi
            ln = 4 + 5 * hash1(seed * 5.3 + i)
            cv.line(px, py, px + math.cos(a) * ln, py + math.sin(a) * ln,
                    color=fiber, width=1.6, alpha=0.8)
    return pts


# === 离屏 sprite 构建（一次性，缓存） ===
_SPRITES = {}


def build_sprite(key, w, h, fn):
    if key in _SPRITES:
        return _SPRITES[key]
    im = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
    cv = wv.canvas.Canvas(im, ss=SS, width=w, height=h)
    fn(cv, w, h)
    cv.flush()
    _SPRITES[key] = im
    return im


def rot_sprite(im, ang):
    """按 0.5° 桶缓存旋转。"""
    bucket = int(round(ang * 2.0))
    key = ("rot", id(im), bucket)
    got = _SPRITES.get(key)
    if got is not None:
        return got
    out = im.rotate(-bucket / 2.0, resample=Image.BICUBIC, expand=True) \
        if abs(bucket / 2.0) > 0.01 else im
    _SPRITES[key] = out
    return out


# ---------- 报纸 ----------
def _news(cv, w, h):
    pad = 26.0
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    draw_torn_card(cv, x0, y0, x1, y1, 11.0, (238, 232, 218))
    # 4 栏假字行
    for cidx in range(4):
        cx = x0 + 34 + cidx * ((x1 - x0 - 60) / 4.0)
        cw = (x1 - x0 - 60) / 4.0 - 12
        yy = y0 + 30
        r = 0
        while yy < y1 - 150:
            wl = cw * (0.45 + 0.5 * hash1(cidx * 31.0 + r * 7.3))
            cv.rect(cx, yy, min(wl, cw), 6, fill=(120, 112, 100), radius=2, alpha=0.75)
            yy += 13
            r += 1
        # 栏目标题粗条
        cv.rect(cx, y0 + 12, cw * 0.7, 11, fill=(70, 62, 52), radius=2)
    # mono 网点图（按亮度采样：假想日出场景）
    gx0, gy0, gx1, gy1 = x0 + 30, y1 - 136, x1 - 30, y1 - 24
    cv.rect(gx0 - 4, gy0 - 4, gx1 - gx0 + 8, gy1 - gy0 + 8, outline=(150, 140, 124),
            width=2, alpha=0.8)
    step = 7.0
    sx, sy = (gx0 + gx1) / 2, gy0 + 26
    j = 0
    yy = gy0 + step / 2
    while yy < gy1:
        xx = gx0 + step / 2
        while xx < gx1:
            d = math.hypot(xx - sx, yy - sy)
            b = 0.28 + 0.72 * clamp(1.0 - d / 95.0, 0, 1) \
                + 0.30 * clamp((yy - (gy0 + gy1) / 2) / (gy1 - gy0), -1, 1)
            k = clamp(b, 0.04, 1.0)
            rr = step * 0.6 * math.sqrt(k) * (0.92 + 0.16 * hash1(j * 3.7))
            if rr > 0.6:
                cv.circle(xx, yy, rr, fill=(62, 56, 48), alpha=0.82)
            j += 1
            xx += step
        yy += step


# ---------- 杂志页（卷角） ----------
def _mag(cv, w, h):
    pad = 24.0
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    fold = 64.0
    # 页面（右下角折起）
    pts = [(x0, y0), (x1, y0), (x1, y1 - fold), (x1 - fold, y1), (x0, y1)]
    cv.polygon(pts, fill=(247, 245, 240))
    cv.lines(pts + [pts[0]], color=(214, 208, 196), width=2.0, alpha=0.9)
    # 折角背面 + 折影
    cv.polygon([(x1, y1 - fold), (x1 - fold, y1), (x1, y1)], fill=(219, 214, 204))
    cv.polygon([(x1, y1 - fold), (x1 - fold, y1), (x1 - fold + 8, y1 - 8)],
               fill=(196, 190, 178), alpha=0.7)
    cv.line(x1 - fold, y1, x1, y1 - fold, color=(172, 165, 152), width=2.4, alpha=0.9)
    # 版头
    cv.rect(x0 + 30, y0 + 26, (x1 - x0) * 0.42, 22, fill=(40, 38, 44), radius=3)
    cv.rect(x0 + 30, y0 + 58, (x1 - x0) * 0.26, 12, fill=(150, 144, 134), radius=3)
    # 照片块（渐变 + 月亮）
    px0, py0, px1, py1 = x0 + 30, y0 + 92, x1 - 30, y1 - 96
    cv.gradient(px0, py0, px1 - px0, py1 - py0,
                colors=[(0, (38, 80, 96)), (0.55, (96, 70, 120)), (1, (196, 110, 92))],
                direction="vertical")
    cv.circle(px0 + (px1 - px0) * 0.68, py0 + 64, 30, fill=(255, 232, 200), alpha=0.95)
    cv.circle(px0 + (px1 - px0) * 0.68 - 10, py0 + 58, 26, fill=(96, 70, 120), alpha=0.55)
    # 山影
    cv.polygon([(px0, py1), (px0 + (px1 - px0) * 0.3, py1 - 66),
                (px0 + (px1 - px0) * 0.52, py1 - 18), (px0 + (px1 - px0) * 0.74, py1 - 52),
                (px1, py1)], fill=(30, 26, 44), alpha=0.85)
    # gloss 高光（对角亮带）
    cv.polygon([(px0, py0 + 40), (px1, py0 - 60), (px1, py0 - 10), (px0, py0 + 90)],
               fill=(255, 255, 255), alpha=0.10)
    # 图注条
    cv.rect(px0, py1 + 14, (px1 - px0) * 0.6, 9, fill=(120, 112, 100), radius=2, alpha=0.7)
    cv.rect(px0, py1 + 32, (px1 - px0) * 0.4, 9, fill=(120, 112, 100), radius=2, alpha=0.55)


# ---------- riso 双色印刷（numpy multiply） ----------
def _riso(cv, w, h):
    pad = 20.0
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    draw_torn_card(cv, x0, y0, x1, y1, 77.0, (247, 241, 227), fiber=(252, 248, 240))
    w2, h2 = int((x1 - x0) * SS), int((y1 - y0) * SS)
    step = 6.5
    pink, blue = (255, 72, 130), (36, 78, 206)
    base = np.ones((h2, w2, 3), dtype=np.float32)
    for ang, col, off in ((0.26, pink, -1.1), (1.31, blue, 1.1)):
        layer = Image.new("L", (w2, h2), 0)
        ld = ImageDraw.Draw(layer)
        ca, sa = math.cos(ang), math.sin(ang)
        diag = math.hypot(w2, h2) / SS
        n = int(diag / step) + 4
        j = 0
        for gy in range(-n // 2, n // 2):
            for gx in range(-n // 2, n // 2):
                # 旋转网格 → 卡面坐标（设计 px）
                ux = (gx * step + (j % 3) * off * 0.4) 
                uy = gy * step + off
                xx = ux * ca - uy * sa + (x1 - x0) / 2
                yy = ux * sa + uy * ca + (y1 - y0) / 2
                j += 1
                if xx < 2 or yy < 2 or xx > x1 - x0 - 2 or yy > y1 - y0 - 2:
                    continue
                d = math.hypot(xx - (x1 - x0) * 0.62, yy - (y1 - y0) * 0.36)
                k = clamp(1.05 - d / 120.0, 0.0, 1.0) + 0.30 * math.sin(xx / 26.0) \
                    + 0.22 * math.sin(yy / 17.0 + 1.3)
                k = clamp(k, 0.0, 1.0)
                rr = step * 0.6 * math.sqrt(k) * (0.92 + 0.16 * hash1(j * 7.9 + ang * 31))
                if rr > 0.55:
                    ld.ellipse([(xx - rr) * SS, (yy - rr) * SS, (xx + rr) * SS, (yy + rr) * SS],
                               fill=255)
        m = np.asarray(layer, dtype=np.float32) / 255.0
        for ch in range(3):
            cf = col[ch] / 255.0
            base[..., ch] *= (1.0 - m) + m * cf
    cv.img.paste(Image.fromarray(np.clip(base * 255.0, 0, 255).astype(np.uint8)),
                 (int(x0 * SS), int(y0 * SS)))
    cv.rect(x0, y0, x1 - x0, y1 - y0, outline=(210, 200, 184), width=2, alpha=0.0)
    # riso 卡标题
    cv.text("RISO PRESS", (x0 + x1) / 2, y1 - 26, 30, (60, 44, 90), bold=True, alpha=0.85)


# ---------- 拍立得 ----------
def _polar(cv, w, h):
    pad = 18.0
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    cv.rect(x0, y0, x1 - x0, y1 - y0, fill=(251, 249, 244), radius=6)
    cv.rect(x0, y0, x1 - x0, y1 - y0, outline=(224, 219, 208), width=2, radius=6)
    phx0, phy0 = x0 + 24, y0 + 24
    phx1, phy1 = x1 - 24, y1 - 96
    cv.gradient(phx0, phy0, phx1 - phx0, phy1 - phy0,
                colors=[(0, (255, 196, 138)), (0.5, (232, 130, 100)), (1, (88, 60, 96))],
                direction="vertical")
    cv.circle(phx0 + (phx1 - phx0) * 0.36, phy0 + (phy1 - phy0) * 0.34, 34,
              fill=(255, 244, 214), alpha=0.96)
    cv.polygon([(phx0, phy1), (phx0 + (phx1 - phx0) * 0.34, phy1 - 84),
                (phx0 + (phx1 - phx0) * 0.62, phy1 - 20),
                (phx0 + (phx1 - phx0) * 0.84, phy1 - 60), (phx1, phy1)],
               fill=(52, 36, 60), alpha=0.9)
    cv.rect(phx0, phy0, phx1 - phx0, phy1 - phy0, outline=(180, 172, 158), width=2, alpha=0.5)
    # 手写图注
    cv.text("sunSet · 35mm", (x0 + x1) / 2, y1 - 48, 30, (90, 80, 66), bold=False, alpha=0.85)


# ---------- Dymo 压纹标签 ----------
def _dymo(cv, w, h):
    pad = 14.0
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    cv.rect(x0, y0, x1 - x0, y1 - y0, fill=(232, 178, 66), radius=7)
    cv.rect(x0, y0, x1 - x0, y1 - y0, outline=(198, 146, 48), width=2.5, radius=7)
    # 链齿孔
    for i in range(1, int((x1 - x0) / 22.0)):
        xx = x0 + i * 22.0
        cv.circle(xx, y0 + 7, 2.2, fill=(150, 108, 34), alpha=0.85)
        cv.circle(xx, y1 - 7, 2.2, fill=(150, 108, 34), alpha=0.85)
    # 压纹字：白高光 + 深影 + 黑面
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 3
    for dx, dy, col in ((-1.8, -1.8, (255, 240, 200)), (1.8, 1.8, (120, 84, 22))):
        cv.text("HAND MADE", cx + dx, cy + dy, 44, col, bold=True, alpha=0.9)
    cv.text("HAND MADE", cx, cy, 44, (44, 38, 28), bold=True)


# ---------- 美纹胶带（波形撕头） ----------
def _tape(cv, w, h, col):
    pad = 10.0
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    pts = []
    n = 7
    for i in range(n + 1):
        u = i / float(n)
        off = (hash1(i * 7.3 + col[0]) - 0.5) * 14.0
        pts.append((x0 + off, y0 + (y1 - y0) * u))
    pts += [(x1, y1), (x1, y0)]
    for i in range(n + 1):
        u = 1.0 - i / float(n)
        off = (hash1(i * 5.1 + col[1]) - 0.5) * 14.0
        pts.append((x1 + off, y0 + (y1 - y0) * u))
    cv.polygon(pts, fill=col, alpha=0.72)
    cv.lines(pts + [pts[0]], color=(255, 255, 255), width=2.0, alpha=0.35)
    # 纸纹横线
    for i in range(3):
        yy = y0 + (y1 - y0) * (0.25 + i * 0.25)
        cv.line(x0 + 6, yy, x1 - 6, yy, color=(255, 255, 255), width=1.2, alpha=0.22)


# ---------- 标题芯片 ----------
def _chip(cv, w, h, ch, col):
    cv.rect(10, 10, w - 20, h - 20, fill=col, radius=10)
    cv.rect(10, 10, w - 20, h - 20, outline=tuple(max(0, c - 60) for c in col),
            width=3, radius=10, alpha=0.8)
    cv.rect(22, 22, w - 44, h - 44, outline=(255, 252, 244), width=2, radius=6, alpha=0.5)
    dark = sum(col) < 480
    cv.text(ch, w / 2, h / 2 + 2, 86, (255, 250, 240) if dark else (58, 40, 22), bold=True)


# ---------- 红印章 ----------
def _stamp(cv, w, h):
    cv.rect(30, 30, w - 60, h - 60, outline=(196, 40, 32), width=12, radius=26, alpha=0.92)
    cv.rect(48, 48, w - 96, h - 96, outline=(196, 40, 32), width=3, radius=16, alpha=0.75)
    cv.text("印", w / 2, h / 2 + 4, 150, (196, 40, 32), bold=True, alpha=0.94)
    # 油墨脱色斑 + 磨损
    for i in range(26):
        x = 40 + hash1(i * 3.3) * (w - 80)
        y = 40 + hash1(i * 7.1) * (h - 80)
        rr = 2 + 7 * hash1(i * 5.7)
        cv.circle(x, y, rr, fill=(226, 205, 178), alpha=0.5)


def _datestamp(cv, w, h):
    cv.rect(14, 14, w - 28, h - 28, outline=(36, 78, 206), width=8, radius=18, alpha=0.9)
    cv.text("2026·10·25", w / 2, h / 2 + 3, 54, (36, 78, 206), bold=True, alpha=0.9)
    for i in range(14):
        x = 24 + hash1(i * 9.3) * (w - 48)
        y = 24 + hash1(i * 4.1) * (h - 48)
        rr = 1.5 + 4 * hash1(i * 6.7)
        cv.circle(x, y, rr, fill=(210, 214, 232), alpha=0.45)


def get_prop_sprite(pid):
    if pid == "news":
        return build_sprite("news", 560 + 52, 390 + 52, _news)
    if pid == "mag":
        return build_sprite("mag", 430 + 48, 550 + 48, _mag)
    if pid == "riso":
        return build_sprite("riso", 420 + 40, 280 + 40, _riso)
    if pid == "polar":
        return build_sprite("polar", 320 + 36, 380 + 36, _polar)
    if pid == "dymo":
        return build_sprite("dymo", 360 + 28, 86 + 28, _dymo)
    raise KeyError(pid)


def get_tape_sprite(col):
    key = ("tape", col)
    if key not in _SPRITES:
        build_sprite(key, 230 + 40, 64 + 40, lambda cv, w, h: _tape(cv, w, h, col))
    return _SPRITES[key]


def get_chip_sprite(i):
    key = ("chip", i)
    if key not in _SPRITES:
        ch, col = CHIPS[i], CHIP_COL[i]

        def fn(cv, w, h, ch=ch, col=col):
            _chip(cv, w, h, ch, col)
        build_sprite(key, 150, 150, fn)
        im = _SPRITES[key]
        ang = (hash1(i * 3.7) - 0.5) * 16.0
        _SPRITES[key] = im.rotate(-ang, resample=Image.BICUBIC, expand=True)
    return _SPRITES[key]


def get_stamp_sprite():
    if ("stamp") not in _SPRITES:
        build_sprite("stamp", 260, 260, _stamp)
        _SPRITES["stamp"] = _SPRITES["stamp"].rotate(8, resample=Image.BICUBIC, expand=True)
    return _SPRITES["stamp"]


def get_date_sprite():
    if ("date") not in _SPRITES:
        build_sprite("date", 330, 100, _datestamp)
        _SPRITES["date"] = _SPRITES["date"].rotate(-4, resample=Image.BICUBIC, expand=True)
    return _SPRITES["date"]


def prewarm_sprites():
    """渲染前构建全部 sprite（含落定角度旋转）。

    关键：sprite 构建会创建 Canvas（skia 共享 scratch）——若发生在帧内，
    会清掉主画布未 flush 的 skia 覆盖层（暗角/阴影单帧消失）并可能重建
    scratch 导致主画布指针失效。必须在渲染前全部预热。
    """
    for (pid, _, _, ang, _, _, _, _, _) in PROPS:
        spr = get_prop_sprite(pid)
        rot_sprite(spr, ang)
    for (_, _, tang, col, _) in TAPES:
        spr = get_tape_sprite(col)
        rot_sprite(spr, tang)
    for i in range(len(CHIPS)):
        get_chip_sprite(i)
    rot_sprite(get_stamp_sprite(), 8.0)
    rot_sprite(get_date_sprite(), -4.0)


# === 牛皮纸底（纤维纹理线 + 暗角） ===
FIBERS = None


def get_fibers():
    global FIBERS
    if FIBERS is None:
        FIBERS = []
        for i in range(150):
            x = hash1(i * 3.1) * W
            y = hash1(i * 7.7) * H
            a = hash1(i * 5.3) * math.pi
            ln = 30 + hash1(i * 9.9) * 110
            dk = hash1(i * 2.9) < 0.5
            FIBERS.append((x, y, a, ln, dk))
    return FIBERS


def draw_background(c, t):
    c.rect(0, 0, W, H, fill=KRAFT)
    # 牛皮纸纤维（静态）
    for i, (x, y, a, ln, dk) in enumerate(get_fibers()):
        col = (168, 136, 92) if dk else (222, 194, 148)
        c.line(x, y, x + math.cos(a) * ln, y + math.sin(a) * ln,
               color=col, width=1.6, alpha=0.30)
    styles.texture(c, kind="paper", strength=0.32, seed=7)
    c.vignette(radius=0.62, power=1.9, color=(74, 52, 26), alpha=0.5)


# === 阴影（半透明深色偏移多边形，旋转随道具） ===
def draw_shadow(c, cx, cy, w, h, ang, lift, alpha=0.20):
    if lift <= 0.5:
        lift = 0.5
    off = (10.0 + lift * 0.16, 14.0 + lift * 0.22)
    a = alpha * (1.0 - lift / 260.0)
    if a <= 0.01:
        return
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    poly = [(cx + off[0] + x * ca - y * sa, cy + off[1] + x * sa + y * ca) for x, y in pts]
    c.polygon(poly, fill=(52, 36, 18), alpha=a)


def paste_center(c, sprite, cx, cy):
    c.img.paste(sprite, (int(round(cx * SS - sprite.width / 2.0)),
                         int(round(cy * SS - sprite.height / 2.0))), sprite)


# === 主场景 ===
def main_scene(c, t):
    t_q = math.floor(t * 12.0) / 12.0
    f12 = int(t * 12.0)
    draw_background(c, t_q)

    # 道具飞入（t_q 量化；飞行中旋转按桶缓存）
    for k, (pid, cx, cy, ang, pw, ph, (fx, fy), frot, t0) in enumerate(PROPS):
        u = out_cubic((t_q - t0) / 0.42)
        if u <= 0:
            continue
        lift = 110.0 * (1.0 - u)
        px = cx + fx * (1.0 - u) + (hash1(f12 * 7.3 + k) - 0.5) * 1.8
        py = cy + fy * (1.0 - u) - lift + (hash1(f12 * 9.1 + k) - 0.5) * 1.8
        rot = ang + frot * (1.0 - u)
        spr = get_prop_sprite(pid)
        spr = rot_sprite(spr, rot) if u < 0.999 else rot_sprite(spr, ang)
        # 影子跟随飞行位置落桌（避免道具未到影子先现的穿帮）
        draw_shadow(c, cx + fx * (1.0 - u), cy + fy * (1.0 - u), pw, ph, rot, lift * 0.45)
        paste_center(c, spr, px, py)

    # 胶带 ×4
    for k, (tx, ty, tang, col, t0) in enumerate(TAPES):
        u = out_cubic((t_q - t0) / 0.36)
        if u <= 0:
            continue
        lift = 90.0 * (1.0 - u)
        spr = get_tape_sprite(col)
        spr = rot_sprite(spr, tang + 14.0 * (1.0 - u))
        c.rect(tx - 100, ty - 26 + 6, 200, 52, fill=(52, 36, 18), radius=20,
               alpha=0.05 + 0.13 * u)
        paste_center(c, spr, tx + (hash1(f12 * 3.7 + k) - 0.5) * 1.6,
                     ty - lift + (hash1(f12 * 5.9 + k) - 0.5) * 1.6)

    # 标题芯片 ×8（0.21s 间隔啪啪落下，阴影收紧）
    for i in range(len(CHIPS)):
        t0 = T_CHIP0 + i * 0.21
        u = out_cubic((t_q - t0) / 0.21)
        if u <= 0:
            continue
        sc = 1.35 - 0.35 * u
        cx, cy = CHIP_POS[i]
        sh_off = 20.0 - 13.0 * u
        c.rect(cx - 75 * sc + sh_off * 0.4, cy - 75 * sc + sh_off * 0.6, 150 * sc, 150 * sc,
               fill=(52, 36, 18), radius=10, alpha=0.10 + 0.13 * u)
        spr = get_chip_sprite(i)
        w2 = max(1, int(round(spr.width * sc)))
        h2 = max(1, int(round(spr.height * sc)))
        if abs(sc - 1.0) > 0.004:
            bkey = ("chipsc", i, int(round(sc * 20)))
            rr = _SPRITES.get(bkey)
            if rr is None:
                rr = spr.resize((w2, h2), Image.BILINEAR)
                _SPRITES[bkey] = rr
            spr = rr
        paste_center(c, spr, cx + (hash1(f12 * 13.1 + i) - 0.5) * 1.6,
                     cy + (hash1(f12 * 17.3 + i) - 0.5) * 1.6)

    # Dymo 标签在 PROPS 里已画；钩子：红印章 6.67 + 蓝日期章 7.0
    u1 = out_cubic((t_q - T_STAMP) / 0.25)
    if u1 > 0:
        sc1 = 1.4 - 0.4 * u1
        spr = get_stamp_sprite()
        w2 = max(1, int(round(spr.width * sc1)))
        h2 = max(1, int(round(spr.height * sc1)))
        if abs(sc1 - 1.0) > 0.004:
            bkey = ("stampsc", int(round(sc1 * 24)))
            rr = _SPRITES.get(bkey)
            if rr is None:
                rr = spr.resize((w2, h2), Image.BILINEAR)
                _SPRITES[bkey] = rr
            spr = rr
        if t - T_STAMP < 1.6:
            c.glow(760, 560, 190, "#ff4a3a", 0.42 * math.exp(-(t - T_STAMP) * 2.2))
        paste_center(c, spr, 760, 560)
    u2 = out_cubic((t_q - T_DATE) / 0.25)
    if u2 > 0:
        sc2 = 1.4 - 0.4 * u2
        spr = get_date_sprite()
        w2 = max(1, int(round(spr.width * sc2)))
        h2 = max(1, int(round(spr.height * sc2)))
        if abs(sc2 - 1.0) > 0.004:
            bkey = ("datesc", int(round(sc2 * 24)))
            rr = _SPRITES.get(bkey)
            if rr is None:
                rr = spr.resize((w2, h2), Image.BILINEAR)
                _SPRITES[bkey] = rr
            spr = rr
        paste_center(c, spr, 1140, 500)

    # 曝光微闪（12fps 帧序量化 ±0.0175）
    flick = 1.0 + (hash1(f12 * 2.17) * 2.0 - 1.0) * 0.0175
    if flick > 1.0:
        c.rect(0, 0, W, H, fill=(255, 248, 236), alpha=flick - 1.0)
    elif flick < 1.0:
        c.rect(0, 0, W, H, fill=(20, 12, 4), alpha=1.0 - flick)


# === 配乐：G 大调轻快手账 92 BPM（pad + pluck 点缀 + 软 bass + hat） ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    # 收尾设计：小节循环只跑到印章 punch（T_DATE）后的小节线，之后短促三音和弦收
    bars = max(1, int(math.ceil(T_DATE / (spb * 4.0))))
    total_beats = bars * 4.0 + 1.0

    PROG = (0, 4, 5, 3)
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def chord4_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4, deg + 5)]

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] \
            + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.6)
    pad = s.track("pad", name="pad", gain_db=-17.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="marimba", gain_db=-11.0, pan=0.14, seed=2)
    bass = s.track("bass", name="bass", gain_db=-11.0, pan=0.0, seed=3)
    hat = s.track("hat", name="hat", gain_db=-17.0, pan=-0.15, seed=4)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = chord_midi(PROG[bi % 4])
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.42)
        ARP = (0, 2, 3, 2, 1, 2, 3, 2)
        chx = chord4_midi(PROG[bi % 4])
        for si, idx in enumerate(ARP):
            vel = 0.42 if si % 2 == 0 else 0.3
            pluck.note(b0 + si * 0.5, name(chx[idx]), 0.5, vel)
        bass.note(b0, name(ch[0] - 24), 1.9, 0.62)
        bass.note(b0 + 2.0, name(ch[0] - 24), 1.9, 0.5)
        for bt in range(8):
            if bt % 2 == 1:
                hat.hit(b0 + bt * 0.5, 0.22)
    end_b = bars * 4.0
    # 章落 punch 后：短促三音和弦（只 3 音、每音半拍、单八度、不铺开）+ 快 fade
    for m in (60, 64, 67):
        pluck.note(end_b, name(m), 0.5, 0.62)
    s.length(beats=total_beats)
    s.fade(out_seconds=1.2)
    return s


# === 影片 ===
prewarm_sprites()

film = wv.Film(W, H, duration=11.0, fps=30, ss=2, theme="light",
               bpm=92, name="collage-kraft")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("一纸一贴 · 皆是收藏", at=8.6, style="subtitle", pos="top left", color="#4a3420")

film.sfx("swish", at=0.35, gain=-13)
film.sfx("swish", at=0.90, gain=-13)
film.sfx("swish", at=1.45, gain=-13)
film.sfx("swish", at=1.90, gain=-13)
for i in range(8):
    film.sfx("pop", at=T_CHIP0 + i * 0.21, gain=-16)
film.sfx("swipe", at=3.90, gain=-13)
for k, (_, _, _, _, t0) in enumerate(TAPES):
    film.sfx("swipe", at=t0 + 0.1, gain=-16)
film.sfx("click", at=5.42, gain=-12)
film.sfx("impact", at=T_STAMP, gain=-6)
film.sfx("punch", at=T_DATE, gain=-9)
film.sfx("riser", at=7.05, dur=0.78, gain=-14)
film.sfx("chime", at=8.3, gain=-11)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "collage-kraft.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "collage-kraft.sheet.png"))
