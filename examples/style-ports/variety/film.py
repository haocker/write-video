# -*- coding: utf-8 -*-
"""variety · 综艺花字 · 多层描边花字把一颗煎蛋拍成综艺名场面
（部分移植：煎蛋 raymarch footage 换成 2D 直绘铸铁锅+煎蛋俯视）
10.5 秒 / 1920x1080 / 30fps
运行: PYTHONPATH=<write-video runtime> python3 film.py

花字 vText（核心资产）：三层描边——深色 0.34fs / 白 0.2fs / 彩色点缀 0.075fs；下方挤出
10 层（每层偏移 (i*0.55, i*0.9) 深色）；竖向线性渐变填充（亮→暗→更暗）；上半高光带。
每字独立 popIn（outBack 2.2）+ 独立抖动 sin(t*31+i*2)*5px。字 sprite 用 PIL stroke_width
一次性构建缓存，逐帧按 scale 桶缓存贴回（确定性）。
2D 煎蛋：铸铁锅（深灰圆+双耳+锅沿高光弧）+ 蛋白（噪声 blob 摊开过冲
R=R1*(1-exp(-u*5.5)cos(u*9)*0.92)，1-exp 收敛）+ 蛋黄（jiggle 1-0.32exp(-5u)cos(22u)，
7.25s 被筷子戳后流心：壳环裂弧+黄橙小圆溢出摆动）。
卡点：相机 punch z=1+amt*exp(-Δ*7)（缩放锅组，花字独立抖动）；命中闪白 fl*0.55 +
镜头抖 sin(61t)*0.012*sh；爆炸线 burst 楔形扇块双色交替；胡椒雨 70 条小矩形错 0.04s 落下。
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
from write_video import fonts

W, H = 1920, 1080
SS = 2
OUT = os.path.join(HERE, "artifacts")

# === 节拍表（画面与音效共用） ===
HIT1 = 0.62       # 蛋落锅
T_SIZI = 2.6      # 滋滋滋～
T_PEPPER = 5.0    # 撒黑胡椒
T_SUS = 6.55      # 悬念字幕
POKE = 7.25       # 筷子戳蛋黄（钩子）
T_PERFECT = 8.6   # 五星 + 满分红章

PAN = (960.0, 640.0)
PAN_R = 300.0


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def out_cubic(u):
    u = clamp(u, 0.0, 1.0)
    return 1.0 - (1.0 - u) ** 3


def out_back(u, c=2.2):
    u = clamp(u, 0.0, 1.0)
    return 1.0 + (c + 1.0) * (u - 1.0) ** 3 + c * (u - 1.0) ** 2


# === 相机 punch（只缩放锅组；花字独立抖动） ===
def punch_z(t):
    z = 1.0
    for t0, amt in ((HIT1 + 0.02, 0.12), (POKE + 0.02, 0.16)):
        if t >= t0:
            z += amt * math.exp(-(t - t0) * 7.0)
    return z


def shake_xy(t):
    sh = 0.0
    for t0 in (HIT1, POKE):
        if t >= t0:
            sh += math.exp(-(t - t0) * 6.5)
    return (math.sin(t * 61.0) * 0.012 * sh * W * 0.5,
            math.cos(t * 53.0) * 0.010 * sh * H * 0.5)


def make_T(z, sx, sy):
    cx, cy = PAN

    def T(x, y):
        return (cx + (x - cx) * z + sx, cy + (y - cy) * z + sy)

    def TZ(v):
        return v * z

    return T, TZ


# === 花字 vText（核心资产） ===
_VT_SPRITES = {}
_VT_SCALED = {}


def vtext_sprite(ch, fs, cols):
    """单字花字 sprite（一次性构建）：挤出 10 层 + 三层描边 + 渐变填充 + 高光带。
    cols = (dark, white, accent, grad3[(pos,(r,g,b)),...])"""
    dark, white, accent, grad3 = cols
    key = (ch, fs, tuple(dark), tuple(white), tuple(accent),
           tuple((p, tuple(c)) for p, c in grad3))
    if key in _VT_SPRITES:
        return _VT_SPRITES[key]
    fpx = max(8, int(round(fs * SS)))
    f = fonts.load("sans_bold", fpx)
    bb = f.getbbox(ch)
    gw, gh = bb[2] - bb[0], bb[3] - bb[1]
    sw_dk = max(2, int(fs * SS * 0.34))
    sw_wh = max(2, int(fs * SS * 0.20))
    sw_ac = max(2, int(fs * SS * 0.075))
    pad = int(fs * SS * 0.30) + sw_dk + 16
    img = Image.new("RGBA", (gw + 2 * pad, gh + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = pad - bb[0], pad - bb[1]
    dark, white, accent = tuple(dark), tuple(white), tuple(accent)
    for i in range(10, 0, -1):
        d.text((ox + i * 0.55 * SS, oy + i * 0.9 * SS), ch, font=f,
               fill=dark, stroke_width=sw_dk, stroke_fill=dark)
    d.text((ox, oy), ch, font=f, fill=dark, stroke_width=sw_dk, stroke_fill=dark)
    d.text((ox, oy), ch, font=f, fill=white, stroke_width=sw_wh, stroke_fill=white)
    d.text((ox, oy), ch, font=f, fill=accent, stroke_width=sw_ac, stroke_fill=accent)
    # 竖向线性渐变填充（亮→暗→更暗）
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text((ox, oy), ch, font=f, fill=255)
    gh2, gw2 = img.size[1], img.size[0]
    ys = np.linspace(0.0, 1.0, gh2)
    stops = cols[3]
    sp = [s[0] for s in stops]
    r = np.interp(ys, sp, [s[1][0] for s in stops])
    g = np.interp(ys, sp, [s[1][1] for s in stops])
    b = np.interp(ys, sp, [s[1][2] for s in stops])
    grad = np.zeros((gh2, gw2, 4), dtype=np.uint8)
    grad[..., 0] = r[:, None]
    grad[..., 1] = g[:, None]
    grad[..., 2] = b[:, None]
    grad[..., 3] = 255
    img.paste(Image.fromarray(grad), (0, 0), mask)
    # 上半高光带（source-atop 近似：白渐变 × mask）
    band = np.clip(1.0 - ys / 0.45, 0.0, 1.0)[:, None] * 0.24
    m = np.asarray(mask, dtype=np.float32) / 255.0
    hl = np.zeros((gh2, gw2, 4), dtype=np.uint8)
    hl[..., 0] = 255
    hl[..., 1] = 255
    hl[..., 2] = 255
    hl[..., 3] = (m * band * 255.0).astype(np.uint8)
    img.alpha_composite(Image.fromarray(hl))
    _VT_SPRITES[key] = (img, pad, gw, gh)
    return _VT_SPRITES[key]


def vtext(c, s, cx, cy, fs, cols, t, t0, seed, stag=0.06, dur=0.34, fade_out=None, z=1.0):
    """花字：逐字 popIn（outBack 2.2）+ 独立抖动。cx 为整串中心。"""
    if t < t0:
        return
    f = fonts.load("sans_bold", max(8, int(fs)))
    widths = [f.getlength(ch) for ch in s]
    total = sum(widths)
    x = cx - total / 2.0
    out_a = 1.0
    if fade_out is not None and t > fade_out[0]:
        out_a = 1.0 - clamp((t - fade_out[0]) / fade_out[1], 0.0, 1.0)
    if out_a <= 0.01:
        return
    cur = x
    for i, ch in enumerate(s):
        u = clamp((t - t0 - i * stag) / dur, 0.0, 1.0)
        if u <= 0:
            continue
        spr, pad, gw, gh = vtext_sprite(ch, fs, cols)
        sc = out_back(u) * z
        w2 = max(1, int(round(spr.width * sc)))
        h2 = max(1, int(round(spr.height * sc)))
        bkey = (ch, fs, cols[0], int(round(sc * 24)))
        rr = _VT_SCALED.get(bkey)
        if rr is None:
            rr = spr.resize((w2, h2), Image.BILINEAR)
            if len(_VT_SCALED) > 640:
                _VT_SCALED.pop(next(iter(_VT_SCALED)))
            _VT_SCALED[bkey] = rr
        if out_a < 0.995:
            key2 = (bkey, int(out_a * 32))
            rr2 = _VT_SCALED.get(key2)
            if rr2 is None:
                al = rr.getchannel("A").point(lambda v: int(v * out_a))
                rr2 = rr.copy()
                rr2.putalpha(al)
                _VT_SCALED[key2] = rr2
            rr = rr2
        jx = math.sin(t * 31.0 + i * 2.0 + seed) * 5.0
        jy = math.cos(t * 27.0 + i * 1.3 + seed) * 3.5
        ccx = cur + widths[i] / 2.0 + jx
        ccy = cy + jy
        anchor = (pad + gw / 2.0) * sc
        px = int(round(ccx * SS - anchor))
        py = int(round(ccy * SS - (pad + gh / 2.0) * sc))
        c.img.paste(rr, (px, py), rr)
        cur += widths[i] * 1.07


# === 爆炸线 burst（楔形扇块双色交替） ===
def draw_burst(c, t, T, TZ, t0, r_max, n=14, cols=((255, 209, 102), (255, 255, 255)), g=0.85):
    if t < t0:
        return
    u = (t - t0) / 0.5
    if u >= 1.0:
        return
    X, Y = T(PAN[0], PAN[1])
    r = TZ(r_max * (1.0 - math.exp(-u * 4.2)))
    alpha = (1.0 - u) ** 1.3
    for k in range(n):
        a0 = 0.12 + k / float(n) * 2 * math.pi
        a1 = a0 + 2 * math.pi / n * 0.42
        wedge = [(X, Y)]
        for q in range(5):
            aa = a0 + (a1 - a0) * q / 4.0
            wedge.append((X + math.cos(aa) * r, Y + math.sin(aa) * r))
        c.polygon(wedge, fill=cols[k % 2], alpha=g * alpha)


# === 2D 煎蛋（锅 + 蛋白 + 蛋黄 + 流心） ===
def draw_food(c, t, T, TZ):
    px, py = PAN
    X, Y = T(px, py)
    R = TZ(PAN_R)
    # 锅影
    c.ellipse(X + 0.07 * R, Y + 0.11 * R, R * 1.02, R * 0.56, fill=(8, 5, 8), alpha=0.4)
    # 铸铁锅：锅身 + 内面 + 沿口高光弧 + 双耳
    c.circle(X, Y, R, fill=(42, 42, 48))
    c.circle(X, Y, R * 0.92, fill=(55, 55, 62))
    for k in range(10):
        a0 = math.pi * 1.02 + k * 0.085
        c.arc(X, Y, R * 0.955, math.degrees(a0), math.degrees(a0 + 0.05),
              color=(96, 96, 110), width=max(2.0, 6.0 * TZ(1)), alpha=0.8)
    for sgn in (-1, 1):
        hx = X + sgn * (R + R * 0.13)
        c.rect(hx - R * 0.14, Y - R * 0.10, R * 0.28, R * 0.20,
               fill=(35, 35, 41), radius=R * 0.09)
        c.circle(hx - sgn * R * 0.10, Y, R * 0.045, fill=(74, 74, 86))
    if t < HIT1:
        return
    # 蛋白：摊开过冲涟漪 R = R1*(1-exp(-u*5.5)cos(u*9)*0.92)
    u = clamp((t - HIT1) / 1.25, 0.0, 1.0)
    rip = 1.0 - math.exp(-u * 5.5) * math.cos(u * 9.0) * 0.92
    R1 = R * 0.68 * rip
    a_eg = clamp((t - HIT1) / 0.18, 0.0, 1.0)
    pts = []
    for k in range(46):
        a = k / 46.0 * 2 * math.pi
        wob = 0.085 * math.sin(3 * a + 1.7) + 0.055 * math.sin(7 * a + 4.2) \
            + 0.03 * math.sin(13 * a + 0.6)
        rr = R1 * (1.0 + wob)
        pts.append((X + math.cos(a) * rr, Y + math.sin(a) * rr * 0.86))
    c.polygon(pts, curve=True, fill=(247, 243, 234), alpha=0.97 * a_eg)
    c.lines(pts + [pts[0]], color=(214, 160, 90), width=max(1.5, 3.5 * TZ(1)),
            alpha=0.7 * a_eg, curve=True)
    # 油泡（确定性生命周期循环）
    for q in range(10):
        hq = hash1(q * 7.3 + 1)
        ba = q / 10.0 * 2 * math.pi + hq * 2.0
        br = R1 * (0.2 + 0.52 * hash1(q * 3.1))
        ph = (t * 0.85 + hq * 2.0) % 1.0
        rmax = (2.0 + 3.5 * hash1(q * 11.7)) * TZ(1)
        bx = X + math.cos(ba) * br
        by = Y + math.sin(ba) * br * 0.86
        c.circle(bx, by, rmax * math.sin(ph * math.pi), outline=(226, 218, 200),
                 width=1.6, alpha=0.7 * a_eg)
    # 蛋黄
    uj = clamp((t - HIT1) / 1.0, 0.0, 1.0)
    jig = 1.0 - 0.32 * math.exp(-5.0 * uj) * math.cos(22.0 * uj)
    r_y = R * 0.215 * jig
    yc = Y - r_y * 0.06
    if t < POKE:
        c.circle(X, yc, r_y, fill=(244, 158, 44))
        c.circle(X - r_y * 0.32, yc - r_y * 0.34, r_y * 0.30, fill=(252, 208, 120), alpha=0.85)
        c.circle(X - r_y * 0.32, yc - r_y * 0.34, r_y * 0.13, fill=(255, 241, 205), alpha=0.9)
    else:
        # 戳破：壳环裂弧 + 流心溢出摆动
        up = t - POKE
        for k in range(5):
            a0 = 0.4 + k * 1.256 + (hash1(k * 3.7) - 0.5) * 0.3
            a1 = a0 + 0.6 + (hash1(k * 9.1) - 0.5) * 0.2
            wob = math.sin(t * 7.0 + k * 2.1) * 0.04
            arc = [(X + math.cos(a0 + (a1 - a0) * q / 8.0) * r_y * (1.0 + wob),
                    yc + math.sin(a0 + (a1 - a0) * q / 8.0) * r_y * (1.0 + wob))
                   for q in range(9)]
            c.lines(arc, color=(244, 158, 44), width=max(2.0, 7.0 * TZ(1)), alpha=0.95)
        for k in range(4):
            a = 1.2 + k * 1.5 + hash1(k * 5.3) * 0.8
            d = r_y * (0.5 + 1.15 * (1.0 - math.exp(-up * 3.2)))
            wob = math.sin(t * 6.0 + k * 2.3) * 6.0
            fx = X + math.cos(a) * d + wob
            fy = yc + math.sin(a) * d * 0.7 + wob * 0.4
            rr2 = (9.0 + 5.0 * hash1(k * 13.1)) * TZ(1) * (0.85 + 0.2 * math.sin(t * 8.0 + k))
            c.circle(fx, fy, rr2, fill=(250, 190, 60), alpha=0.95)
        c.circle(X, yc, r_y * 0.42, fill=(240, 150, 36))
    # 筷子戳（7.25 伸入 0.12s，0.3s 后收回）
    if POKE <= t < POKE + 0.55:
        uq = clamp((t - POKE) / 0.12, 0.0, 1.0)
        back = clamp((t - POKE - 0.30) / 0.2, 0.0, 1.0)
        ext = math.sin(uq * math.pi / 2.0) * (1.0 - back)
        for k in (-1, 1):
            sx0, sy0 = T(1470 + k * 26, 250)
            exx, eyy = T(1015 + k * 15, 570)
            qx = sx0 + (exx - sx0) * ext
            qy = sy0 + (eyy - sy0) * ext
            c.line(sx0, sy0, qx, qy, color=(146, 96, 60), width=max(3.0, 9.0 * TZ(1)))
            c.circle(qx, qy, 5.0 * TZ(1), fill=(120, 78, 46))
    # 胡椒雨：70 条小矩形错 0.04s 落下
    if t >= T_PEPPER:
        for q in range(70):
            dl = (q % 18) * 0.04 + hash1(q * 1.7) * 0.22
            ts = T_PEPPER + dl
            if t < ts:
                continue
            uf = clamp((t - ts) / 0.5, 0.0, 1.0)
            ang = hash1(q * 3.3) * 2 * math.pi
            pr = R * (0.12 + 0.62 * hash1(q * 9.7))
            tx0 = X + math.cos(ang) * pr
            ty0 = Y - 430 - hash1(q * 5.1) * 230
            ty1 = Y + math.sin(ang) * pr * 0.86 - 6
            yy = ty0 + (ty1 - ty0) * out_cubic(uf)
            rot = hash1(q * 7.9) * math.pi
            pw = (4.0 + 3.5 * hash1(q * 2.3)) * TZ(1)
            ph2 = (2.2 + 1.6 * hash1(q * 4.7)) * TZ(1)
            ca, sa = math.cos(rot), math.sin(rot)
            quad = [(-pw / 2, -ph2 / 2), (pw / 2, -ph2 / 2), (pw / 2, ph2 / 2), (-pw / 2, ph2 / 2)]
            c.polygon([(tx0 + x * ca - y * sa, yy + x * sa + y * ca) for x, y in quad],
                      fill=(28, 26, 30), alpha=0.92)
    # 热气（blur 近似：同心椭圆上浮）
    a_h = clamp((t - HIT1) / 1.0, 0.0, 1.0)
    for q in range(6):
        hq = hash1(q * 3.9)
        ph = (t * 0.35 + hq) % 1.0
        wx = X + (hash1(q * 7.1) - 0.5) * R * 1.05 + math.sin(t * 1.1 + q * 2.2) * 26
        wy = Y - R * 0.9 - ph * 300
        aa = (1.0 - ph) * 0.10 * a_h
        for k in range(3):
            c.ellipse(wx, wy - k * 14, (34 + 14 * k) * TZ(1), (58 + 22 * k) * TZ(1),
                      fill=(255, 250, 240), alpha=aa * (0.6 - k * 0.15))


# === 五星 + 满分红章 ===
def star_pts(cx, cy, r, rot=-math.pi / 2, inner=0.42):
    return [(cx + math.cos(rot + k * math.pi / 5.0) * (r if k % 2 == 0 else r * inner),
             cy + math.sin(rot + k * math.pi / 5.0) * (r if k % 2 == 0 else r * inner))
            for k in range(10)]


def draw_perfect(c, t, T, TZ):
    if t < T_PERFECT:
        return
    for k in range(5):
        u = clamp((t - T_PERFECT - k * 0.08) / 0.3, 0.0, 1.0)
        if u <= 0:
            continue
        sc = out_back(u)
        X, Y = T(700 + k * 110, 330)
        c.polygon(star_pts(X, Y, 46 * sc * TZ(1)), fill=(255, 209, 74), alpha=0.96)
        c.polygon(star_pts(X, Y, 46 * sc * TZ(1)), outline=(122, 74, 10),
                  width=max(1.5, 3.0 * TZ(1)))
        c.circle(X - 8 * sc, Y - 10 * sc, 7 * sc * TZ(1), fill=(255, 241, 195), alpha=0.85)


_STAMP = {}


def stamp_sprite():
    if "m" in _STAMP:
        return _STAMP["m"]
    fs = 96 * SS
    f = fonts.load("sans_bold", fs)
    w = int(f.getlength("满分")) + 64 * SS
    h = fs + 48 * SS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=22 * SS,
                        fill=(217, 48, 48, 235), outline=(150, 24, 24, 255), width=7 * SS)
    d.text((w / 2, h / 2 - 6 * SS), "满分", font=f, fill=(255, 246, 238, 255), anchor="mm")
    for q in range(14):
        x = hash1(q * 3.1) * w
        y = hash1(q * 7.7) * h
        rr = (2 + 4 * hash1(q * 5.3)) * SS
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(200, 60, 60, 110))
    _STAMP["m"] = im.rotate(6, resample=Image.BICUBIC, expand=True)
    return _STAMP["m"]


def draw_stamp(c, t):
    if t < T_PERFECT:
        return
    u = clamp((t - T_PERFECT) / 0.35, 0.0, 1.0)
    sc = 1.0 + 0.6 * math.exp(-9.0 * u)
    a = clamp(u * 4.0, 0.0, 1.0)
    spr = stamp_sprite()
    w2 = max(1, int(round(spr.width * sc)))
    h2 = max(1, int(round(spr.height * sc)))
    if abs(sc - 1.0) > 0.004:
        spr = spr.resize((w2, h2), Image.BILINEAR)
    if a < 0.995:
        al = spr.getchannel("A").point(lambda v: int(v * a))
        spr = spr.copy()
        spr.putalpha(al)
    c.img.paste(spr, (int(round(1330 * SS - spr.width / 2)),
                      int(round(330 * SS - spr.height / 2))), spr)


# === 左上角红底白边 tag 药丸 ===
def draw_tag(c, t):
    a = clamp((t - 0.15) / 0.3, 0.0, 1.0)
    if a <= 0:
        return
    c.rect(64, 52, 300, 60, fill=(217, 48, 48), radius=30, alpha=0.95 * a)
    c.rect(64, 52, 300, 60, outline=(255, 240, 230), width=2.5, radius=30, alpha=0.8 * a)
    c.text("深夜食堂 · EP.01", 214, 83, 29, (255, 244, 236), bold=True, alpha=a)


# === 主场景 ===
COL_A = ((64, 20, 16), (255, 248, 238), (255, 77, 106),
         [(0.0, (255, 224, 138)), (0.45, (255, 154, 60)), (1.0, (217, 90, 32))])
COL_B = ((14, 42, 42), (240, 255, 250), (77, 208, 196),
         [(0.0, (184, 255, 233)), (0.45, (90, 223, 201)), (1.0, (42, 168, 147))])
COL_C = ((58, 10, 18), (255, 242, 244), (255, 209, 102),
         [(0.0, (255, 138, 154)), (0.45, (240, 77, 104)), (1.0, (194, 39, 68))])


def main_scene(c, t):
    z = punch_z(t)
    sx, sy = shake_xy(t)
    # 深色暖偏底
    c.gradient(0, 0, W, H, colors=[(0, (38, 18, 20)), (0.6, (24, 12, 14)), (1, (13, 8, 10))],
               direction="vertical")
    c.glow(960 + sx * 0.3, 640 + sy * 0.3, 640, "#ff8a4d", 0.13)
    c.glow(300 + math.sin(t * 0.4) * 40, 190, 320, "#c23a3a", 0.10)
    T, TZ = make_T(z, sx, sy)
    draw_food(c, t, T, TZ)
    draw_burst(c, t, T, TZ, HIT1 + 0.02, 340, n=14)
    draw_burst(c, t, T, TZ, POKE + 0.02, 760, n=18, g=0.55,
               cols=((255, 209, 102), (255, 138, 154)))
    draw_perfect(c, t, T, TZ)
    draw_stamp(c, t)
    draw_tag(c, t)
    vtext(c, "外酥里嫩！", 960, 240, 168, COL_A, t, HIT1 + 0.04, 0.0,
          stag=0.06, fade_out=(2.3, 0.25))
    vtext(c, "滋滋滋～", 1330, 262, 116, COL_B, t, T_SIZI, 2.0,
          stag=0.09, fade_out=(6.3, 0.25))
    vtext(c, "流心了！！！", 960, 236, 196, COL_C, t, POKE + 0.02, 4.0,
          stag=0.05, fade_out=(8.35, 0.3))
    # 命中闪白 rgba(255,255,255,fl*0.55)
    fl = 0.0
    for t0 in (HIT1 + 0.02, POKE + 0.02):
        if t >= t0:
            fl += math.exp(-(t - t0) * 10.0)
    if fl > 0.004:
        c.rect(0, 0, W, H, fill=(255, 255, 255), alpha=min(0.6, fl * 0.55))


# === 配乐：C 大调 I–vi–IV–V 综艺 groove，120 BPM ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    bars = max(1, int(math.ceil((duration - 1.2) / (spb * 4.0))))

    PROG = (0, 5, 3, 4)
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] \
            + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.6)
    pad = s.track("pad", name="pad", gain_db=-17.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="riff", gain_db=-12.0, pan=0.12, seed=2)
    bass = s.track("bass", name="bass", gain_db=-10.0, pan=0.0, seed=3)
    kick = s.track("kick", name="kick", gain_db=-8.0, seed=4)
    hat = s.track("hat", name="hat", gain_db=-15.0, pan=0.2, seed=5)
    clap = s.track("clap", name="clap", gain_db=-13.0, seed=6)

    STAB = (0, 0, 2, 0, 0, 4, 0, 2)
    for bi in range(bars):
        b0 = bi * 4.0
        ch = chord_midi(PROG[bi % 4])
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.4)
        pool = ch + [ch[0] + 12, ch[1] + 12]
        for si, idx in enumerate(STAB):
            vel = 0.48 if si % 2 == 0 else 0.4
            pluck.note(b0 + si * 0.5, name(pool[idx]), 0.22, vel)
        bass.note(b0, name(ch[0] - 24), 1.7, 0.7)
        bass.note(b0 + 2.5, name(ch[0] - 24), 1.2, 0.55)
        for bt in range(4):
            kick.hit(b0 + bt, 0.75)
        for bt in range(8):
            hat.hit(b0 + bt * 0.5, 0.38 if bt % 2 else 0.22)
        clap.hit(b0 + 1, 0.5)
        clap.hit(b0 + 3, 0.5)
    end_b = bars * 4.0
    # 短强一拍和弦收 + pluck 顿音一个，戛然 fade
    for m in (60, 64, 67):
        pluck.note(end_b, name(m), 1.0, 0.85)
    pluck.note(end_b + 0.5, name(72), 0.2, 0.6)
    s.length(beats=total_beats)
    s.fade(out_seconds=0.8)
    return s


# === 影片 ===
film = wv.Film(W, H, duration=10.5, fps=30, ss=2, theme="punch",
               bpm=120, name="variety-fried-egg")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 10.5, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("最关键的一步……", at=T_SUS, style="subtitle", y=985, enter="fade", out=8.3)

# 音效对齐节拍
film.sfx("whoosh", at=0.15, gain=-10)
film.sfx("impact", at=HIT1 + 0.02, gain=-6)
film.sfx("swish", at=T_SIZI, gain=-12)
film.sfx("sparkle", at=T_PEPPER, gain=-10)
film.sfx("riser", at=6.6, dur=0.62, gain=-12)
film.sfx("impact", at=POKE + 0.02, gain=-5)
film.sfx("punch", at=POKE + 0.1, gain=-9)
film.sfx("success", at=T_PERFECT + 0.02, gain=-8)
film.sfx("chime", at=9.7, gain=-11)

# 卡点 punch/闪白/花字 popIn 为有意急变：闪烁检测排除
film.flicker_exclude(0.5, 1.35)
film.flicker_exclude(2.55, 3.15)
film.flicker_exclude(7.1, 7.95)

if __name__ == "__main__":
    import time
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "variety-fried-egg.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "variety-fried-egg.sheet.png"))
