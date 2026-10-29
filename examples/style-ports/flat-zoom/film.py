# -*- coding: utf-8 -*-
"""《画中屋》 — flat-zoom 全新重做 · 一镜到底无限推进
黄昏小屋（亮着的窗）→ 屋内（墙上挂画）→ 画里正是这栋小屋 → 循环
10.5 秒 / 1920x1080 / 30fps（内部 2x 超采样）
核心：
  · 传送门＝真实物件（窗 240x135、画心 640x360，均 16:9）
  · 对数匀速推进，不动点锚定传送门中心→屏幕中心：F=(Pc-s·C)/(1-s)
  · 每层单变换直绘（矢量，任意倍率清晰）；门内层用临时画布 + AFFINE 浮点 1:1 贴回
  · 三层循环中「画的内容」就是 L0 小屋本身——循环由构图保证，天然无缝
运行: python3 film.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           os.path.abspath(os.path.join(HERE, "..", "..", "runtime"))):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
from PIL import Image, ImageDraw

import write_video as wv

W, H = 1920, 1080
SS = 2
WPX, HPX = W * SS, H * SS
OUT = os.path.join(HERE, "artifacts")
CSCREEN = (960.0, 540.0)

# ---- 传送门（设计坐标，均 16:9）----
WIN = (1120.0, 655.0, 240.0, 135.0)      # L0 亮窗（小屋右侧）
PAINT = (560.0, 300.0, 640.0, 360.0)     # L1 画心
S0 = WIN[2] / W                           # 0.125 → 8x
S1 = PAINT[2] / W                         # 1/3 → 3x
LOG0 = math.log(1.0 / S0)
LOG1 = math.log(1.0 / S1)
TOTAL = LOG0 + LOG1
T0, TEND = 0.35, 8.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mix3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0, 1))


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def flog(t):
    """对数推进：0 → TOTAL，起 0.55s 缓入、尾 0.9s 缓出，中段匀速。"""
    a, d = 0.55, 0.9
    c = TEND - T0 - a - d
    v = TOTAL / (a / 2 + c + d / 2)
    if t <= T0:
        return 0.0
    if t < T0 + a:
        u = (t - T0) / a
        return v * a * u * u / 2
    if t < T0 + a + c:
        return v * a / 2 + v * (t - T0 - a)
    if t < TEND:
        u = (t - T0 - a - c) / d
        return v * a / 2 + v * c + v * d * (u - u * u / 2)
    # 收尾：极缓微推（1.0 → 1.012）制造呼吸感
    u = clamp((t - TEND) / 2.5, 0, 1)
    return TOTAL + 0.012 * ease_io(u)


# ---- 不动点：传送门中心最终落在屏幕中心 ----
def fixed_pt(pc, s):
    return ((pc[0] - s * CSCREEN[0]) / (1 - s), (pc[1] - s * CSCREEN[1]) / (1 - s))


PC0 = (WIN[0] + WIN[2] / 2, WIN[1] + WIN[3] / 2)
PC1 = (PAINT[0] + PAINT[2] / 2, PAINT[1] + PAINT[3] / 2)
F0 = fixed_pt(PC0, S0)
F1 = fixed_pt(PC1, S1)


# ---- 天空预渲染（设计尺寸，一次性）----
def build_sky():
    A = np.zeros((H, W, 3), float)
    ys = np.arange(H)[:, None].astype(float) / H
    stops = [(0.00, (16, 20, 48)), (0.35, (38, 34, 80)), (0.58, (86, 54, 104)),
             (0.74, (196, 108, 96)), (0.86, (255, 158, 104))]
    for y in range(H):
        u = y / float(H)
        c = stops[0][1]
        for i in range(len(stops) - 1):
            a0, c0 = stops[i]
            a1, c1 = stops[i + 1]
            if a0 <= u <= a1:
                c = mix3(c0, c1, (u - a0) / (a1 - a0))
                break
        else:
            c = stops[-1][1]
        A[y] = c
    im = Image.fromarray(A.astype(np.uint8))
    d = ImageDraw.Draw(im, "RGBA")
    # 月 + 光晕
    mx, my, mr = 1560, 190, 64
    for i in range(9):
        rr = mr + 18 + i * 22
        a = int(16 * (1 - i / 9.0))
        d.ellipse([mx - rr, my - rr, mx + rr, my + rr], fill=(255, 236, 200, a))
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 240, 210, 255))
    d.ellipse([mx - mr + 16, my - mr + 12, mx + mr - 26, my + mr - 30], fill=(236, 222, 190, 120))
    # 星
    for i in range(48):
        sx, sy = hash1(i * 3.3) * W, hash1(i * 7.1) * 620 + 20
        b = 120 + hash1(i * 13) * 135
        r = 1.0 + hash1(i * 17) * 1.6
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(int(b), int(b), 255, 230))
        if hash1(i * 23) > 0.86:
            d.line([sx - 5, sy, sx + 5, sy], fill=(220, 228, 255, 110), width=1)
            d.line([sx, sy - 5, sx, sy + 5], fill=(220, 228, 255, 110), width=1)
    return im.convert("RGB")


SKY = build_sky()


def paste_sky(img, Tf, zb):
    """把天空按当前变换贴入（一次双线性重采样，平滑渐变无痕）。"""
    x0, y0 = Tf((0.0, 0.0))
    # inverse: design = (device - T0)/zb ; sprite px = design (sky 是设计尺寸)
    aff = SKY.transform((WPX, HPX), Image.AFFINE,
                        (1.0 / zb, 0.0, -x0 / zb, 0.0, 1.0 / zb, -y0 / zb),
                        resample=Image.BILINEAR)
    img.paste(aff, (0, 0))


def lw(zb, w):
    return max(1, int(round(w * zb)))


# ================================================================ L0 小屋
def draw_house(d, img, Tf, zb, t, depth=0):
    paste_sky(img, Tf, zb)
    # 远山
    d.polygon([Tf((0, 780)), Tf((420, 700)), Tf((760, 780))], fill=(44, 38, 74))
    d.polygon([Tf((640, 780)), Tf((1080, 690)), Tf((1520, 780))], fill=(40, 35, 70))
    d.polygon([Tf((1300, 782)), Tf((1720, 706)), Tf((1920, 760)), Tf((1920, 790))], fill=(36, 32, 64))
    # 松树剪影
    for i, (tx, th, tw_, col) in enumerate([
            (250, 380, 150, (26, 34, 52)), (430, 300, 120, (24, 32, 50)),
            (1520, 340, 130, (26, 34, 52)), (1700, 260, 104, (24, 32, 50))]):
        for s_ in range(3):
            u = s_ / 3.0
            w0 = tw_ * (0.45 + 0.55 * u)
            y0 = 790 - th * (u + 0.18)
            y1 = 790 - th * (u * 0.72)
            d.polygon([Tf((tx - w0 * (1 - u * 0.55), y0)), Tf((tx + w0 * (1 - u * 0.55), y0)),
                       Tf((tx, y1 - th * 0.30))], fill=col)
    # 地面
    d.polygon([Tf((0, 958)), Tf((W, 958)), Tf((W, H)), Tf((0, H))], fill=(26, 40, 40))
    # 烟囱 + 烟
    d.rectangle([*Tf((1108, 300)), *Tf((1188, 470))], fill=(58, 44, 54))
    d.rectangle([*Tf((1098, 288)), *Tf((1198, 312))], fill=(74, 56, 66))
    for i in range(3):
        age = ((t * 0.22) + i * 0.33) % 1.0
        sx = 1150 + math.sin(age * 5 + i) * 26
        sy = 268 - age * 190
        rr = 16 + age * 34
        a = int(70 * (1 - age))
        if a > 2:
            d.ellipse([*Tf((sx - rr, sy - rr)), *Tf((sx + rr, sy + rr))], fill=(200, 196, 214, a))
    # 屋顶
    d.polygon([Tf((524, 604)), Tf((1396, 604)), Tf((1184, 396)), Tf((736, 396))], fill=(38, 30, 58))
    d.polygon([Tf((524, 604)), Tf((1396, 604)), Tf((1396, 626)), Tf((524, 626))], fill=(26, 20, 42))
    d.line([Tf((736, 396)), Tf((1184, 396))], fill=(64, 52, 88), width=lw(zb, 7))
    # 屋顶瓦缝（斜线）
    for i in range(12):
        u = i / 11.0
        xl = 524 + (736 - 524) * u
        xt = 736 + (1184 - 736) * u * 0.5
        d.line([Tf((xl, 604)), Tf((xt, 396))], fill=(30, 23, 46), width=lw(zb, 2.2))
    for i in range(12):
        u = i / 11.0
        xr = 1396 - (1396 - 1184) * u
        xt = 1184 - (1184 - 736) * u * 0.5
        d.line([Tf((xr, 604)), Tf((xt, 396))], fill=(30, 23, 46), width=lw(zb, 2.2))
    # 墙体
    d.rectangle([*Tf((600, 604)), *Tf((1320, 980))], fill=(122, 80, 52))
    for i in range(16):
        x = 600 + i * 45
        d.line([Tf((x, 606)), Tf((x, 978))], fill=(108, 70, 46), width=lw(zb, 2.4))
    d.rectangle([*Tf((600, 604)), *Tf((1320, 628))], fill=(98, 64, 42))
    # 暗窗 ×2
    for (wx, wy, ww, wh) in [(646, 676, 118, 116), (1002, 676, 92, 96)]:
        d.rectangle([*Tf((wx - 7, wy - 7)), *Tf((wx + ww + 7, wy + wh + 7))], fill=(56, 40, 34))
        d.rectangle([*Tf((wx, wy)), *Tf((wx + ww, wy + wh))], fill=(32, 42, 74))
        d.line([Tf((wx + 8, wy + wh - 18)), Tf((wx + ww - 24, wy + 18))],
               fill=(70, 88, 130, 120), width=lw(zb, 4))
        d.line([Tf((wx + ww / 2, wy)), Tf((wx + ww / 2, wy + wh))], fill=(56, 40, 34), width=lw(zb, 5))
        d.line([Tf((wx, wy + wh / 2)), Tf((wx + ww, wy + wh / 2))], fill=(56, 40, 34), width=lw(zb, 5))
    # 门
    d.rectangle([*Tf((828, 706)), *Tf((962, 980))], fill=(74, 48, 36))
    for i in range(3):
        x = 862 + i * 34
        d.line([Tf((x, 710)), Tf((x, 976))], fill=(60, 38, 28), width=lw(zb, 3))
    d.ellipse([*Tf((890, 760)), *Tf((924, 794))], fill=(30, 40, 68), outline=(52, 36, 28), width=lw(zb, 4))
    d.ellipse([*Tf((938, 852)), *Tf((952, 866))], fill=(196, 158, 92))
    d.rectangle([*Tf((806, 980)), *Tf((984, 1004))], fill=(88, 82, 78))
    # 亮窗（传送门）：暖光 + 光溢 + 窗框
    wx, wy, ww, wh = WIN
    pulse = 1.0 + 0.06 * math.sin(t * 1.7)
    gcx, gcy = Tf((wx + ww / 2, wy + wh / 2))
    _glow(img, gcx, gcy, ww * zb * 1.15 * pulse, (255, 176, 96), 0.38)
    d.rectangle([*Tf((wx - 12, wy - 12)), *Tf((wx + ww + 12, wy + wh + 12))], fill=(64, 44, 34))
    d.rectangle([*Tf((wx - 12, wy - 12)), *Tf((wx + ww + 12, wy - 4))], fill=(84, 58, 42))
    if depth >= 1:
        # 嵌套视角：窗内画"屋内一瞥"（暖底 + 小画框 + 灯点 + 窗棂）
        d.rectangle([*Tf((wx, wy)), *Tf((wx + ww, wy + wh))], fill=(196, 146, 96))
        d.rectangle([*Tf((wx, wy + wh * 0.72)), *Tf((wx + ww, wy + wh))], fill=(120, 84, 56))
        d.rectangle([*Tf((wx + ww * 0.28, wy + wh * 0.18)),
                     *Tf((wx + ww * 0.62, wy + wh * 0.50))], fill=(160, 120, 76))
        d.rectangle([*Tf((wx + ww * 0.31, wy + wh * 0.22)),
                     *Tf((wx + ww * 0.59, wy + wh * 0.46))], fill=(60, 52, 80))
        d.ellipse([*Tf((wx + ww * 0.74, wy + wh * 0.34)),
                   *Tf((wx + ww * 0.90, wy + wh * 0.62))], fill=(255, 214, 140))
        d.line([Tf((wx + ww / 2, wy)), Tf((wx + ww / 2, wy + wh))], fill=(64, 44, 34), width=lw(zb, 5))
        d.line([Tf((wx, wy + wh / 2)), Tf((wx + ww, wy + wh / 2))], fill=(64, 44, 34), width=lw(zb, 5))
    # 光溢到地面（柔和光斑，不用实心梯形）
    for i in range(3):
        u = i / 2.0
        ex = Tf((wx + ww / 2, 1000 + u * 40))
        d.ellipse([ex[0] - (150 + u * 90) * zb, ex[1] - (26 + u * 16) * zb,
                   ex[0] + (150 + u * 90) * zb, ex[1] + (26 + u * 16) * zb],
                  fill=(255, 196, 126, int(20 - i * 5)))
    # 围栏（左）
    for i in range(4):
        fx = 96 + i * 104
        d.rectangle([*Tf((fx, 862)), *Tf((fx + 14, 986))], fill=(52, 42, 36))
    d.rectangle([*Tf((90, 892)), *Tf((420, 906))], fill=(58, 46, 38))
    d.rectangle([*Tf((90, 940)), *Tf((420, 954))], fill=(58, 46, 38))
    # 石板小径
    for i in range(5):
        cx = 900 + math.sin(i * 1.7) * 40
        cy = 1010 + i * 16
        w_ = 66 - i * 6
        d.ellipse([*Tf((cx - w_ / 2, cy - 8)), *Tf((cx + w_ / 2, cy + 8))], fill=(96, 96, 92))
    # 草丛点缀
    for i in range(26):
        gx = hash1(i * 5.3) * W
        gy = 972 + hash1(i * 9.1) * 96
        h_ = 8 + hash1(i * 3.7) * 14
        d.polygon([Tf((gx - 4, gy)), Tf((gx + 4, gy)), Tf((gx, gy - h_))], fill=(22, 36, 34))
    # 前景灌木剪影
    d.ellipse([*Tf((-60, 980)), *Tf((240, 1090))], fill=(18, 30, 30))
    d.ellipse([*Tf((1700, 986)), *Tf((2000, 1100))], fill=(18, 30, 30))


# ================================================================ L1 屋内
def draw_room(d, img, Tf, zb, t, depth=0):
    # 墙 / 护墙板
    d.rectangle([*Tf((0, 0)), *Tf((W, H))], fill=(44, 40, 66))
    d.rectangle([*Tf((0, 0)), *Tf((W, 96))], fill=(36, 33, 56))
    d.line([Tf((0, 96)), Tf((W, 96))], fill=(52, 46, 74), width=lw(zb, 3))
    d.rectangle([*Tf((0, 700)), *Tf((W, 836))], fill=(54, 46, 70))
    d.line([Tf((0, 700)), Tf((W, 700))], fill=(66, 56, 84), width=lw(zb, 4))
    for i in range(22):
        x = 30 + i * 90
        d.line([Tf((x, 706)), Tf((x, 832))], fill=(48, 41, 64), width=lw(zb, 2.4))
    # 地板
    d.rectangle([*Tf((0, 836)), *Tf((W, H))], fill=(94, 64, 44))
    for i in range(9):
        y = 852 + i * 26
        d.line([Tf((0, y)), Tf((W, y))], fill=(78, 52, 36), width=lw(zb, 2.4))
    # 地毯
    d.rectangle([*Tf((520, 880)), *Tf((1430, 1024))], fill=(118, 58, 58))
    d.rectangle([*Tf((536, 892)), *Tf((1414, 1012))], outline=(172, 100, 78), width=lw(zb, 5))
    for i in range(9):
        for j in range(2):
            cx = 592 + i * 92
            cy = 934 + j * 44
            d.ellipse([*Tf((cx - 7, cy - 7)), *Tf((cx + 7, cy + 7))], fill=(150, 82, 66))
    # 书架（右）
    d.rectangle([*Tf((1444, 300)), *Tf((1820, 824))], fill=(86, 58, 40))
    d.rectangle([*Tf((1456, 312)), *Tf((1808, 812))], fill=(64, 42, 30))
    for s_ in range(4):
        sy = 372 + s_ * 116
        d.rectangle([*Tf((1456, sy + 74)), *Tf((1808, sy + 86))], fill=(110, 76, 50))
        n = 7
        for b in range(n):
            bx = 1470 + b * 47
            bhh = 52 + hash1(b * 3.1 + s_ * 7.7) * 16
            col = [(226, 92, 76), (255, 205, 102), (58, 176, 162), (110, 130, 196),
                   (196, 118, 160), (150, 190, 120), (236, 160, 96)][(b + s_) % 7]
            d.rectangle([*Tf((bx, sy + 74 - bhh)), *Tf((bx + 38, sy + 74))], fill=col)
    # 挂画（传送门）：外框 + 内画心
    px, py, pw, ph = PAINT
    d.rectangle([*Tf((px - 44, py - 44)), *Tf((px + pw + 44, py + ph + 44))], fill=(140, 100, 56))
    d.rectangle([*Tf((px - 30, py - 30)), *Tf((px + pw + 30, py + ph + 30))], fill=(168, 124, 72))
    d.rectangle([*Tf((px - 30, py - 30)), *Tf((px + pw + 30, py - 18))], fill=(190, 146, 88))
    d.rectangle([*Tf((px - 10, py - 10)), *Tf((px + pw + 10, py + ph + 10))], fill=(88, 60, 38))
    if depth >= 1:
        # 缩略小屋（与 L0 构图同源，避免嵌套视角里画框是空的）
        sx, sy = px + pw * 0.06, py + ph * 0.10
        sw, sh = pw * 0.88, ph * 0.80
        d.rectangle([*Tf((sx, sy)), *Tf((sx + sw, sy + sh * 0.62))], fill=(46, 38, 76))
        d.rectangle([*Tf((sx, sy + sh * 0.62)), *Tf((sx + sw, sy + sh * 0.74))],
                    fill=(126, 88, 96))
        d.rectangle([*Tf((sx, sy + sh * 0.74)), *Tf((sx + sw, sy + sh))], fill=(24, 36, 38))
        hw, hh = sw * 0.44, sh * 0.34
        hx, hy = sx + sw * 0.28, sy + sh * 0.46
        d.rectangle([*Tf((hx, hy)), *Tf((hx + hw, hy + hh))], fill=(122, 80, 52))
        d.polygon([Tf((hx - hw * 0.14, hy)), Tf((hx + hw * 1.14, hy)),
                   Tf((hx + hw * 0.80, hy - hh * 0.52)), Tf((hx + hw * 0.20, hy - hh * 0.52))],
                  fill=(38, 30, 58))
        d.rectangle([*Tf((hx + hw * 0.62, hy + hh * 0.30)), *Tf((hx + hw * 0.86, hy + hh * 0.66))],
                    fill=(255, 206, 124))
        d.ellipse([*Tf((sx + sw * 0.74, sy + sh * 0.12)), *Tf((sx + sw * 0.86, sy + sh * 0.24))],
                  fill=(255, 240, 210))
    # 侧窗（左，夜空 + 月）
    d.rectangle([*Tf((96, 300)), *Tf((392, 604))], fill=(52, 40, 34))
    d.rectangle([*Tf((110, 314)), *Tf((378, 590))], fill=(30, 38, 70))
    d.ellipse([*Tf((300, 356)), *Tf((342, 398))], fill=(255, 240, 208))
    for i in range(9):
        sx = 126 + hash1(i * 5.1) * 230
        sy = 330 + hash1(i * 9.3) * 200
        d.ellipse([*Tf((sx, sy)), *Tf((sx + 3, sy + 3))], fill=(214, 222, 255))
    d.line([Tf((244, 314)), Tf((244, 590))], fill=(52, 40, 34), width=lw(zb, 9))
    d.line([Tf((110, 452)), Tf((378, 452))], fill=(52, 40, 34), width=lw(zb, 9))
    d.rectangle([*Tf((84, 596)), *Tf((404, 618))], fill=(74, 56, 44))
    # 边桌 + 台灯 + 杯
    d.rectangle([*Tf((1546, 762)), *Tf((1812, 836))], fill=(104, 72, 48))
    d.rectangle([*Tf((1560, 836)), *Tf((1580, 900))], fill=(88, 60, 40))
    d.rectangle([*Tf((1778, 836)), *Tf((1798, 900))], fill=(88, 60, 40))
    # 灯罩 + 灯光
    lcx, lcy = Tf((1690, 690))
    _glow(img, lcx, lcy, 205 * zb, (255, 198, 124), 0.26)
    d.polygon([Tf((1610, 712)), Tf((1770, 712)), Tf((1738, 612)), Tf((1642, 612))], fill=(255, 198, 124))
    d.rectangle([*Tf((1682, 712)), *Tf((1698, 764))], fill=(58, 44, 34))
    d.ellipse([*Tf((1668, 748)), *Tf((1712, 772))], fill=(58, 44, 34))
    d.polygon([Tf((1618, 712)), Tf((1762, 712)), Tf((1846, 1036)), Tf((1534, 1036))],
              fill=(255, 210, 146, 13))
    # 杯 + 热气
    d.rectangle([*Tf((1580, 726)), *Tf((1626, 762))], fill=(238, 232, 220))
    d.arc([*Tf((1624, 730)), *Tf((1652, 758))], 270, 90, fill=(238, 232, 220), width=lw(zb, 5))
    for i in range(2):
        pts = [Tf((1596 + i * 16 + math.sin(t * 1.8 + u * 4 + i) * 6, 716 - u * 56))
               for u in [q / 6.0 for q in range(7)]]
        d.line(pts, fill=(240, 236, 228, 60), width=lw(zb, 3))
    # 猫（蜷在毯上）
    br = 1.0 + 0.028 * math.sin(t * 2.1)
    d.ellipse([*Tf((812, 944 - 46 * br)), *Tf((1000, 1004))], fill=(112, 118, 148))
    d.ellipse([*Tf((982, 926 - 40 * br)), *Tf((1052, 996))], fill=(124, 130, 160))
    d.polygon([Tf((992, 934)), Tf((1002, 908)), Tf((1016, 932))], fill=(124, 130, 160))
    d.polygon([Tf((1022, 932)), Tf((1036, 906)), Tf((1048, 934))], fill=(124, 130, 160))
    d.line([Tf((818, 980)), Tf((790, 962)), Tf((812, 942))], fill=(112, 118, 148), width=lw(zb, 12))


def _glow(img, x, y, r, color, alpha):
    """径向柔光（numpy 小图，贴回）。"""
    R = int(clamp(r, 8, 1400))
    if R < 8:
        return
    yy, xx = np.mgrid[0:R, 0:R]
    dist = np.hypot(xx - R / 2, yy - R / 2) / (R / 2)
    a = np.clip(1 - dist, 0, 1) ** 2 * alpha
    spr = np.zeros((R, R, 4), np.uint8)
    spr[..., 0] = color[0]
    spr[..., 1] = color[1]
    spr[..., 2] = color[2]
    spr[..., 3] = (a * 255).astype(np.uint8)
    im = Image.fromarray(spr)
    img.paste(im, (int(x - R / 2), int(y - R / 2)), im)


# ================================================================ 帧
def frame(t):
    f = flog(t)
    if f < LOG0:
        k, zr = 0, math.exp(f)
    elif f < LOG0 + LOG1:
        k, zr = 1, math.exp(f - LOG0)
    else:
        k, zr = 0, math.exp(f - LOG0 - LOG1)

    F = (F0, F1)[k]
    zb = zr * SS

    def Tf(q):
        return ((zr * q[0] + F[0] * (1 - zr)) * SS, (zr * q[1] + F[1] * (1 - zr)) * SS)

    img = Image.new("RGBA", (WPX, HPX), (0, 0, 0, 255))
    d = ImageDraw.Draw(img, "RGBA")

    if k == 0:
        draw_house(d, img, Tf, zb, t)
        portal = WIN
        next_draw = draw_room
    else:
        draw_room(d, img, Tf, zb, t)
        portal = PAINT
        next_draw = draw_house

    # 门内层：临时画布 + AFFINE 浮点 1:1 贴回
    px, py, pw, ph = portal
    cx, cy = Tf((px, py))
    sc = zr * (pw / W) * SS     # 下一层：设计像素 → 设备像素（含超采样倍率）
    tw, th = int(round(W * sc)) + 2, int(round(H * sc)) + 2
    if tw >= 6 and th >= 6 and cx < WPX and cy < HPX and cx + tw > 0 and cy + th > 0:
        tmp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(tmp, "RGBA")

        def Tfn(q):
            return (q[0] * sc + 1.0, q[1] * sc + 1.0)

        next_draw(d2, tmp, Tfn, sc, t, depth=1)
        aff = tmp.transform((WPX, HPX), Image.AFFINE,
                            (1.0, 0.0, -cx, 0.0, 1.0, -cy), resample=Image.BILINEAR)
        img.paste(aff, (0, 0), aff)
        # 窗棂压在门内容之上（小屋亮窗才需要，画心不加）
        if k == 0:
            pwc, phc = pw * zb, ph * zb
            d.line([(cx + pwc / 2, cy), (cx + pwc / 2, cy + phc)], fill=(64, 44, 34), width=lw(zb, 7))
            d.line([(cx, cy + phc / 2), (cx + pwc, cy + phc / 2)], fill=(64, 44, 34), width=lw(zb, 7))
            d.rectangle([(cx, cy), (cx + pwc, cy + phc)], outline=(52, 36, 28), width=lw(zb, 5))

    # 暗角（轻微）
    if k == 0:
        vg = Image.new("L", (64, 36), 0)
        dv = ImageDraw.Draw(vg)
        dv.ellipse([-6, -6, 70, 42], fill=255)
        vg = vg.resize((WPX, HPX), Image.BILINEAR)
        dark = Image.new("RGBA", (WPX, HPX), (8, 8, 18, 0))
        dark.putalpha(vg.point(lambda v: int((255 - v) * 0.30)))
        img.paste(dark, (0, 0), dark)

    return img.convert("RGB")


# ================================================================ 配乐
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    bar = spb * 4.0
    total_beats = duration / spb
    bars = int(math.ceil(duration / bar))
    # G 大调：G - Em - C - D
    CHORDS = ([55, 59, 62], [52, 55, 59], [48, 52, 55], [50, 54, 57])
    ROOTS = (43, 40, 36, 38)
    # 波浪动机（0,2,1,3,2,4,3,1）
    ARP = (0, 2, 1, 3, 2, 4, 3, 1)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.6)
    pad = s.track("pad", name="pad", gain_db=-16.5, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-11.0, pan=0.1, seed=2)
    bass = s.track("bass", name="bass", gain_db=-10.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = CHORDS[bi % 4]
        pool = list(ch) + [ch[0] + 12, ch[1] + 12]
        if b0 < total_beats - 3.0:      # 收尾前停 pad，让结尾单音干净
            for m in ch:
                pad.note(b0, name(m), 4.05, 0.42)
        for si in range(8):
            pluck.note(b0 + si * 0.5, name(pool[ARP[si] % len(pool)]), 0.5, 0.5)
        bass.note(b0, name(ROOTS[bi % 4]), 1.8, 0.72)
        bass.note(b0 + 2.0, name(ROOTS[bi % 4] + 12), 1.6, 0.45)

    # 收尾：不落大和弦——高音主音单音 + 高八度泛音，慢 fade
    end_b = total_beats - 2.2
    pluck.note(end_b, name(79), 2.0, 0.55)
    pluck.note(end_b, name(86), 1.6, 0.24)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.2)
    return s


film = wv.Film(W, H, duration=10.5, fps=30, ss=2, grain=False, theme="midnight",
               bpm=100, name="painted-house")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 10.5, transition="cut")
s1.draw(lambda c, t: c.paste_full(frame(t)), at=0, enter="none")
s1.text("画中屋", at=8.35, style="hero", y=200)
s1.text("THE PAINTED HOUSE · 一镜到底", at=8.85, style="subtitle", y=296)

film.sfx("whoosh", at=0.5, gain=-9)
film.sfx("swish", at=3.1, gain=-14)
film.sfx("chime", at=7.6, gain=-11)
film.sfx("sparkle", at=8.5, gain=-13)
film.flicker_exclude(0.4, 7.9)   # 连续推进 + 穿门（本片核心动效，有意）

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "flat-zoom.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "flat-zoom.sheet.png"))
