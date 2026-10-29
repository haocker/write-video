# -*- coding: utf-8 -*-
"""HUD · 赛博朋克无人机飞进激光雷达点云城市，扫描波点亮街区，锁定一辆飞车
11 秒 / 1920x1080 / 30fps
运行: python3 film.py

点云城市预生成（numpy 数组 ~3 万点）→ yaw/pitch/roll 旋转 + F=1050 透视，
加色散射光栅化（'lighter' 近似）→ 扫描波 rev/wave 点亮 → HUD 逐个 boot →
2.8s 捕获 → 6.25s 锁定 → 7.65s 大 glitch → 8.0s RGB 分离标题砸入。
"""
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           "/root/.codingmatrix/project-tpl/.ai-ready/skills/write-video/runtime"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import write_video as wv
from write_video.canvas import ease

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")
F = 1050.0

CYANH = (110, 240, 255)
PINKH = (255, 80, 180)
AMBERH = (255, 200, 90)
WHITEH = (235, 250, 255)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


# === 点云城市预生成（世界坐标 x 横向 / y 向上 / z 前向） ===
K_BLDG, K_PINK, K_AMBER, K_NCYAN, K_GRID, K_LANE = 0, 1, 2, 3, 4, 5
_px, _py, _pz, _pk, _ph = [], [], [], [], []


def _add(x, y, z, k):
    _px.append(x)
    _py.append(y)
    _pz.append(z)
    _pk.append(k)
    _ph.append(hash1(len(_px) * 7.31) * 6.2832)


def _line3(p0, p1, step, k):
    n = max(1, int(math.dist(p0, p1) / step))
    for i in range(n + 1):
        u = i / n
        _add(p0[0] + (p1[0] - p0[0]) * u,
             p0[1] + (p1[1] - p0[1]) * u,
             p0[2] + (p1[2] - p0[2]) * u, k)


def _peri(x0, z0, x1, z1, y, step, k):
    _line3((x0, y, z0), (x1, y, z0), step, k)
    _line3((x1, y, z0), (x1, y, z1), step, k)
    _line3((x1, y, z1), (x0, y, z1), step, k)
    _line3((x0, y, z1), (x0, y, z0), step, k)


for _row in range(24):
    zc = -60 + _row * 30 + (hash1(_row * 3.7) - 0.5) * 10
    for _side in (-1, 1):
        for _col in range(5):
            r1 = hash1(_row * 13.1 + _side * 7.0 + _col * 3.0)
            r2 = hash1(_row * 5.3 + _col * 11.7 + _side * 2.0)
            r3 = hash1(_row * 9.7 + _col * 17.3 + _side * 5.0)
            r4 = hash1(_row * 21.3 + _col * 29.7 + _side * 11.0)
            if r1 > 0.85:
                continue
            xc = _side * (26 + _col * 18 + (r2 - 0.5) * 7)
            bw = 10 + r2 * 5
            bd = 12 + r3 * 8
            bh = clamp(16 + r4 * 34 + max(0.0, 60 - abs(xc)) * 0.5, 12, 88)
            floors = min(15, max(2, int(bh / 3.2)))
            x0, x1 = xc - bw / 2, xc + bw / 2
            z0, z1 = zc - bd / 2, zc + bd / 2
            for f in range(1, floors + 1):
                _peri(x0, z0, x1, z1, f * 3.2, 2.8, K_BLDG)
            n = max(2, int(bh / 5.0))
            for (ex, ez) in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
                for i in range(n + 1):
                    _add(ex, bh * i / n, ez, K_BLDG)
            _peri(x0, z0, x1, z1, bh, 2.8, K_BLDG)
            if r3 > 0.52 and floors >= 4:
                sx = x0 if _side > 0 else x1
                ky = K_PINK + int(r4 * 3) % 3
                y1 = 3.2 * (floors - 1)
                y0 = y1 - 9.0
                zA, zB = zc - min(bd / 2, 4.5), zc + min(bd / 2, 4.5)
                ny = max(2, int((y1 - y0) / 1.1))
                nz = max(2, int((zB - zA) / 1.1))
                for i in range(ny + 1):
                    for j in range(nz + 1):
                        _add(sx, y0 + (y1 - y0) * i / ny,
                             zA + (zB - zA) * j / nz, ky)

for _gx in range(-240, 241, 30):
    _line3((_gx, 0, -120), (_gx, 0, 940), 7.0, K_GRID)
for _gz in range(-120, 941, 30):
    _line3((-240, 0, _gz), (240, 0, _gz), 7.0, K_GRID)
for _lx in (-15.5, 15.5):
    _line3((_lx, 0, -120), (_lx, 0, 940), 4.0, K_BLDG)
for _lx in (-10.5, -3.5, 3.5, 10.5):
    _z = -120.0
    while _z < 940:
        _line3((_lx, 0, _z), (_lx, 0, min(_z + 5, 940)), 1.6, K_LANE)
        _z += 11.0

PX = np.array(_px, dtype=np.float32)
PY = np.array(_py, dtype=np.float32)
PZ = np.array(_pz, dtype=np.float32)
PK = np.array(_pk, dtype=np.int8)
PH = np.array(_ph, dtype=np.float32)
NP_ = len(PX)

CYAN = np.array([70, 235, 255], np.float32)
PURP = np.array([175, 105, 255], np.float32)
PINKC = np.array([255, 75, 170], np.float32)
AMBER = np.array([255, 195, 85], np.float32)
NCYAN = np.array([110, 245, 255], np.float32)
GRIDD = np.array([45, 120, 210], np.float32)
LANEC = np.array([255, 215, 140], np.float32)
WHITEW = np.array([230, 255, 255], np.float32)

DW, DH = W * 2, H * 2  # 设备分辨率缓冲（ss=2）


def build_bg():
    row = (np.array([3, 8, 20], np.float32) +
           (np.array([8, 17, 36], np.float32) - np.array([3, 8, 20], np.float32)) *
           np.linspace(0, 1, DH, dtype=np.float32)[:, None])
    return np.tile(row[:, None, :], (1, DW, 1))


BG = build_bg()


# === 相机 ===
def cam_state(t):
    camy = 38.0 - 16.0 * ease("inOutSine", clamp(t / 10.0, 0, 1))
    camz = -40.0 + 46.0 * t + 70.0 * ease("inOutSine", clamp(t / 10.0, 0, 1))
    yaw = 0.085 * math.sin(t * 0.5)
    pitch = 0.13 + 0.055 * ease("inOutSine", clamp((t - 1.2) / 6.5, 0, 1))
    roll = 0.18 * ease("inOutSine", clamp((t - 7.6) / 1.3, 0, 1))
    return camy, camz, yaw, pitch, roll


def proj_pt(x, y, z, cs):
    camy, camz, yaw, pitch, roll = cs
    yy, zz = y - camy, z - camz
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    x2 = x * cy_ + zz * sy_
    z2 = -x * sy_ + zz * cy_
    cp, sp = math.cos(pitch), math.sin(pitch)
    y2 = yy * cp + z2 * sp
    z3 = -yy * sp + z2 * cp
    if z3 <= 2.0:
        return None
    cr, sr = math.cos(roll), math.sin(roll)
    x3 = x2 * cr - y2 * sr
    y3 = x2 * sr + y2 * cr
    s = F / z3
    return (W * 0.5 + x3 * s, H * 0.5 - y3 * s)


# === 点云帧渲染：加色散射光栅化（'lighter' 近似） ===
def city_view(t):
    cs = cam_state(t)
    camy, camz, yaw, pitch, roll = cs
    x = PX
    y = PY - camy
    z = PZ - camz
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    x2 = x * cy_ + z * sy_
    z2 = -x * sy_ + z * cy_
    cp, sp = math.cos(pitch), math.sin(pitch)
    y2 = y * cp + z2 * sp
    z3 = -y * sp + z2 * cp
    cr, sr = math.cos(roll), math.sin(roll)
    x3 = x2 * cr - y2 * sr
    y3 = x2 * sr + y2 * cr
    valid = z3 > 2.0
    inv = np.where(valid, F / np.maximum(z3, 2.0), 0.0).astype(np.float32)
    sx = DW * 0.5 + x3 * inv
    sy = DH * 0.5 - y3 * inv
    dist = np.sqrt(x2 * x2 + y * y + z2 * z2).astype(np.float32)

    scanR = (t - 0.9) * 260.0
    rev = np.clip((scanR - dist) / 30.0, 0.0, 1.0)
    wave = np.exp(-((dist - scanR) / 10.0) ** 2)

    col = np.empty((NP_, 3), np.float32)
    d01 = np.clip(dist / 420.0, 0.0, 1.0)
    bm = PK == K_BLDG
    m = bm & (d01 < 0.45)
    col[m] = CYAN
    m = bm & (d01 >= 0.45)
    col[m] = PURP
    col[bm] *= (1.0 - d01[bm] * 0.25)[:, None]
    flick = 0.72 + 0.28 * np.sin(t * 8.0 + PH)
    for k, cc in ((K_PINK, PINKC), (K_AMBER, AMBER), (K_NCYAN, NCYAN)):
        m = PK == k
        col[m] = cc[None, :] * flick[m][:, None] * 1.15
    m = PK == K_GRID
    col[m] = GRIDD[None, :] * np.exp(-dist[m] / 200.0)[:, None] * 2.2
    m = PK == K_LANE
    col[m] = LANEC[None, :] * np.exp(-dist[m] / 220.0)[:, None] * 1.3

    col *= (0.20 + 0.80 * rev)[:, None]
    col += WHITEW[None, :] * wave[:, None] * 0.9

    vis = (rev > 0.0) & valid
    xs = sx[vis].astype(np.int32)
    ys = sy[vis].astype(np.int32)
    cv = col[vis]
    big = dist[vis] < 140.0
    inb = (xs >= 2) & (xs < DW - 3) & (ys >= 2) & (ys < DH - 3)
    xs, ys, cv, big = xs[inb], ys[inb], cv[inb], big[inb]

    buf = BG.copy()
    flat = buf.reshape(-1, 3)
    idx = ys * DW + xs

    def scatter(idxs, cols, offs, wgts):
        ia = np.concatenate([idxs + dy * DW + dx for dx, dy in offs])
        ca = np.concatenate([cols * w for w in wgts])
        ok = (ia >= 0) & (ia < flat.shape[0])
        ia, ca = ia[ok], ca[ok]
        for ch in range(3):
            flat[:, ch] += np.bincount(ia, weights=ca[:, ch], minlength=flat.shape[0])

    scatter(idx, cv * 0.30,
            ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)),
            (1, 1, 1, 1, 1, 1, 1, 1, 1))
    if big.any():
        ib, cb = idx[big], cv[big]
        scatter(ib, cb, ((-1, 0), (1, 0), (0, -1), (0, 1), (2, 0), (0, 2), (-2, 0), (0, -2),
                         (1, 1), (1, -1), (-1, 1), (-1, -1)),
                (0.18, 0.18, 0.18, 0.18, 0.12, 0.12, 0.12, 0.12, 0.14, 0.14, 0.14, 0.14))

    yh = DH * 0.5 - F * 2.0 * math.tan(pitch)
    band = np.exp(-((np.arange(DH, dtype=np.float32) - yh) / 130.0) ** 2) * 0.5
    buf += band[:, None, None] * np.array([22, 60, 95], np.float32)[None, None, :]

    np.clip(buf, 0, 255, out=buf)
    return Image.fromarray(buf.astype(np.uint8))


# === HUD 组件 ===
def boot(t, t0, d=0.35):
    return ease("outCubic", clamp((t - t0) / d, 0, 1))


def draw_corners(c, t):
    b = boot(t, 0.10)
    if b <= 0.01:
        return
    s = 0.7 + 0.3 * b
    m, L = 46, 52
    for sx_, sy_ in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        ax = W / 2 + sx_ * (W / 2 - m) * s
        ay = H / 2 + sy_ * (H / 2 - m) * s
        c.line(ax, ay, ax - sx_ * L * s, ay, color=CYANH, width=2.5, alpha=0.9 * b)
        c.line(ax, ay, ax, ay - sy_ * L * s, color=CYANH, width=2.5, alpha=0.9 * b)


def draw_reticle(c, t):
    b = boot(t, 0.10)
    if b <= 0.01:
        return
    c.circle(960, 540, 26 * (0.7 + 0.3 * b), outline=CYANH, width=1.5, alpha=0.85 * b)
    c.line(960 - 40, 540, 960 - 14, 540, color=CYANH, width=1.5, alpha=0.85 * b)
    c.line(960 + 14, 540, 960 + 40, 540, color=CYANH, width=1.5, alpha=0.85 * b)
    c.line(960, 540 - 40, 960, 540 - 14, color=CYANH, width=1.5, alpha=0.85 * b)
    c.line(960, 540 + 14, 960, 540 + 40, color=CYANH, width=1.5, alpha=0.85 * b)


def draw_compass(c, t, yaw, b):
    b = boot(t, 0.35)
    if b <= 0.01:
        return
    hdg = (37.0 + t * 2.2 + math.degrees(yaw)) % 360.0
    y0 = 44
    for off in range(-30, 31, 5):
        xx = 960 + off * 10
        deg = (hdg + off) % 360.0
        a = b * clamp(1.6 * (1 - abs(off) / 32.0), 0, 1)
        major = off % 15 == 0
        c.line(xx, y0, xx, y0 + (14 if major else 8), color=CYANH, width=2, alpha=a)
        if major:
            c.text("%03d" % int(deg), xx, y0 + 24, 14, CYANH, font="mono", alpha=a)
    c.polygon([(960, y0 + 2), (960 - 6, y0 - 8), (960 + 6, y0 - 8)],
              fill=AMBERH, alpha=b)
    c.text("HDG %03.0f" % hdg, 960, y0 + 52, 16, AMBERH, font="mono", alpha=b)


def draw_tape(c, t, x, val, label, b, side):
    b = boot(t, 0.6)
    if b <= 0.01:
        return
    cy0, span, px_per = 470, 300, 2.4
    v0 = math.ceil((val - 65) / 5.0) * 5
    for k in range(28):
        v = v0 + k * 5
        dy = (val - v) * px_per
        if abs(dy) > span / 2:
            continue
        yy = cy0 + dy
        a = b * clamp(1 - abs(dy) / (span / 2) * 0.9, 0, 1)
        major = v % 20 == 0
        ln = 16 if major else 9
        if side > 0:
            c.line(x, yy, x + ln, yy, color=CYANH, width=2, alpha=a)
            if major:
                c.text(str(v), x + ln + 6, yy, 15, CYANH, font="mono",
                       align="left", alpha=a)
        else:
            c.line(x, yy, x - ln, yy, color=CYANH, width=2, alpha=a)
            if major:
                c.text(str(v), x - ln - 6, yy, 15, CYANH, font="mono",
                       align="right", alpha=a)
    bx = x - 72 if side > 0 else x - 72
    c.rect(bx, cy0 - 21, 144, 42, outline=CYANH, width=1.5, alpha=0.85 * b)
    c.text("%s %.0f" % (label, val), bx + 72, cy0, 19, WHITEH, font="mono",
           bold=False, alpha=b)


def draw_ladder(c, t, pitch, roll, b):
    b = boot(t, 0.8)
    if b <= 0.01:
        return
    pitch_deg = math.degrees(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    for pd in range(-20, 25, 5):
        dy = (pitch_deg - pd) * 26
        if abs(dy) > 210:
            continue
        a = b * clamp(1.5 - abs(dy) / 210.0, 0, 1) * 0.8
        for sgn in (-1, 1):
            for u in range(44, 152, 24):
                p0 = (sgn * u * cr - dy * sr, sgn * u * sr + dy * cr)
                p1 = (sgn * (u + 14) * cr - dy * sr, sgn * (u + 14) * sr + dy * cr)
                c.line(960 + p0[0], 540 + p0[1], 960 + p1[0], 540 + p1[1],
                       color=CYANH, width=1.8, alpha=a)
        lx, ly = (168 * cr - dy * sr, 168 * sr + dy * cr)
        c.text(str(pd), 960 + lx, 540 + ly, 14, CYANH, font="mono", alpha=a)


def draw_radar(c, t, b):
    b = boot(t, 1.0)
    if b <= 0.01:
        return
    cxr, cyr, R = 205, 852, 92
    c.circle(cxr, cyr, R, outline=CYANH, width=2, alpha=0.8 * b)
    c.circle(cxr, cyr, R * 0.62, outline=CYANH, width=1, alpha=0.35 * b)
    c.circle(cxr, cyr, R * 0.3, outline=CYANH, width=1, alpha=0.3 * b)
    c.line(cxr - R, cyr, cxr + R, cyr, color=CYANH, width=1, alpha=0.22 * b)
    c.line(cxr, cyr - R, cxr, cyr + R, color=CYANH, width=1, alpha=0.22 * b)
    sweep = (t * 2.6) % (2 * math.pi)
    for i in range(24):
        ang = sweep - i * 0.045
        a = (1 - i / 24.0) * 0.45 * b
        c.line(cxr, cyr, cxr + math.cos(ang) * R * 0.96, cyr + math.sin(ang) * R * 0.96,
               color=CYANH, width=3 if i == 0 else 2, alpha=a)
    for i in range(9):
        ang = hash1(i * 3.3) * 6.2832
        rr = (0.25 + 0.7 * hash1(i * 7.7)) * R
        da = (sweep - ang) % (2 * math.pi)
        vis = clamp(1 - da / 2.5, 0, 1)
        fl = 0.6 + 0.4 * math.sin(t * 6 + i * 2.1)
        a = vis * fl * b
        if a > 0.02:
            bx, by = cxr + math.cos(ang) * rr, cyr + math.sin(ang) * rr
            c.circle(bx, by, 3.5, fill=CYANH, alpha=a)
            c.glow(bx, by, 12, "#64F4DC", 0.5 * a)
    c.text("RDR 2.4KM", cxr, cyr + R + 26, 15, CYANH, font="mono", alpha=b)


PANEL_LINES = [
    ("SYS.CHECK", "OK", (240, 250, 255)),
    ("LIDAR.GAIN", "88%", CYANH),
    ("UPLINK", "SECURE", (240, 250, 255)),
    ("PWR.CORE", "96%", AMBERH),
    ("GRID.SECTOR", "7-KILO", CYANH),
    ("WIND.VEL", "12KT", CYANH),
    ("THRUST", "64%", CYANH),
    ("MODE", "HUNT", PINKH),
]


def draw_panel(c, t):
    b = boot(t, 1.2)
    if b <= 0.01:
        return
    x0, y0, w_, h_ = 1556, 700, 304, 252
    c.rect(x0, y0, w_, h_, outline=CYANH, width=1.5, alpha=0.55 * b)
    c.rect(x0, y0, w_, 30, fill=(20, 40, 52), alpha=0.65 * b)
    c.text("DRONE-07 // TACTICAL", x0 + 12, y0 + 15, 15, CYANH, font="mono",
           align="left", alpha=b)
    for i, (k, v, col) in enumerate(PANEL_LINES):
        t0 = 1.3 + i * 0.14
        pr = clamp((t - t0) / 0.45, 0, 1)
        if pr <= 0:
            continue
        full = "%s %s %s" % (k, "." * max(1, 12 - len(k)), v)
        c.text(full[:int(len(full) * pr)], x0 + 12, y0 + 48 + i * 25, 15, col,
               font="mono", align="left", alpha=b)


def draw_status(c, t):
    b = boot(t, 0.15)
    if b <= 0.01:
        return
    blink = 0.5 + 0.5 * math.sin(t * 4.0)
    c.circle(86, 64, 5, fill=(255, 60, 60), alpha=0.3 + 0.7 * blink)
    c.text("REC 00:%02d" % int(t), 102, 64, 16, (240, 90, 90), font="mono",
           align="left", alpha=b)
    b2 = boot(t, 0.3)
    c.text("BAT 87%", 1830, 64, 16, CYANH, font="mono", align="right", alpha=b2)
    for i in range(4):
        c.rect(1786 + i * 12, 76 - i * 2, 8, 6 + i * 2,
               fill=CYANH if i < 3 else (60, 90, 110), alpha=b2)
    c.text("POS 31.2304 / 121.4737", 960, 1014, 15, (100, 190, 210),
           font="mono", alpha=0.75 * b)


# === 目标飞车 + 锁定 ===
def draw_target(c, t):
    cs = cam_state(t)
    camz = cs[1]

    def carpos(tt):
        return (4.5 + 2.2 * math.sin(tt * 0.85), 7.0,
                camz + 160.0 + 22.0 * math.sin(tt * 0.6))

    czc = camz + 160.0 + 22.0 * math.sin(t * 0.6)
    for i in range(13, -1, -1):
        cx_, cy_, cz_ = carpos(t - i * 0.05)
        cx_ += (hash1(i * 13.7) - 0.5) * 0.6
        p = proj_pt(cx_, cy_, cz_ - i * 6.5, cs)
        if p is None:
            continue
        a = (1 - i / 14.0) * 0.85
        c.circle(p[0], p[1], 2 + (14 - i) * 0.18, fill=(255, 60, 60), alpha=a)
    hp = proj_pt(*carpos(t), cs)
    if hp is None:
        return
    tx, ty = hp
    scr = F * 6.0 / 165.0
    c.rect(tx - scr, ty - scr * 0.4, scr * 2, scr * 0.8, fill=(70, 24, 30),
           outline=(255, 80, 80), width=1.5)
    c.glow(tx, ty, scr * 2.4, "#ff4d4d", 0.5)
    blink = max(0.0, math.sin(t * 12.0))
    c.circle(tx - scr * 1.6, ty, 2.5, fill=WHITEH, alpha=blink)
    c.circle(tx + scr * 1.6, ty, 2.5, fill=(255, 60, 60), alpha=blink)

    appear = ease("outCubic", clamp((t - 2.8) / 0.5, 0, 1))
    if appear <= 0.01:
        return
    lk = clamp((t - 6.25) / 0.4, 0, 1)
    s = 220.0 - 140.0 * ease("outCubic", clamp((t - 2.8) / 1.1, 0, 1))
    s += (46.0 - 80.0) * ease("outBack", lk)
    s += math.sin(t * 7.3) * 18 * (1 - lk) * appear
    ang = math.radians(45) * lk
    col = PINKH if lk > 0.02 else CYANH
    h = s / 2
    ca, sa = math.cos(ang), math.sin(ang)
    for sx_, sy_ in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        lx, ly = sx_ * h * ca - sy_ * h * sa, sx_ * h * sa + sy_ * h * ca
        arm = s * 0.28
        d1x, d1y = -sx_ * ca, -sx_ * sa
        d2x, d2y = sy_ * sa, -sy_ * ca
        c.line(tx + lx, ty + ly, tx + lx + d1x * arm, ty + ly + d1y * arm,
               color=col, width=2.5, alpha=appear)
        c.line(tx + lx, ty + ly, tx + lx + d2x * arm, ty + ly + d2y * arm,
               color=col, width=2.5, alpha=appear)
    if lk > 0.02:
        c.circle(tx, ty, s * 0.8, outline=col, width=2, alpha=lk * 0.9)
        lk_ = 0.55 + 0.45 * math.sin(t * 14)
        c.pixel_text("LOCKED", tx - 30, ty - s * 0.8 - 30, px=4, color=PINKH,
                     align="left")
    else:
        n = 16
        for i in range(0, n, 2):
            u0, u1 = i / n, (i + 1) / n
            c.line(960 + (tx - 960) * u0, 540 + (ty - 540) * u0,
                   960 + (tx - 960) * u1, 540 + (ty - 540) * u1,
                   color=CYANH, width=1.5, alpha=0.4 * appear)
        c.text("TRK ACQ", tx, ty - s / 2 - 26, 16, CYANH, font="mono", alpha=appear)


def draw_title(c, t):
    tt = t - 8.0
    if tt < 0:
        return
    a = clamp(tt / 0.12, 0, 1)
    sc = 1.45 - 0.45 * ease("outCubic", clamp(tt / 0.3, 0, 1))
    split = 18 * math.exp(-tt * 5.5)
    c.text("目标锁定", 960 - split, 855, 110 * sc, (255, 60, 60), bold=True, alpha=0.85 * a)
    c.text("目标锁定", 960 + split, 855, 110 * sc, (80, 240, 255), bold=True, alpha=0.85 * a)
    c.text("目标锁定", 960, 855, 110 * sc, WHITEH, bold=True, alpha=a)
    c.text("TARGET LOCKED · SECTOR 7-KILO", 960, 940, 24, (140, 245, 255),
           font="mono", alpha=a)


# === glitch 后期（9 条水平切片 + RGB split） ===
GLITCHES = ((3.35, 0.08, 0.6), (6.22, 0.10, 0.6), (7.65, 0.28, 1.0))


def post_glitch(c, t):
    amt = 0.0
    gi = 0
    for i, (t0, dur, amp) in enumerate(GLITCHES):
        if t0 <= t <= t0 + dur:
            amt = amp * clamp(min((t - t0) / 0.02, (t0 + dur - t) / 0.05), 0, 1)
            gi = i
            break
    if amt <= 0.01:
        return
    im = c.img
    arr = np.asarray(im).copy()
    n = 9
    hh = arr.shape[0] // n
    for i in range(n):
        off = int((hash1(gi * 97 + i * 13) - 0.5) * 240 * amt) * 2
        if off:
            arr[i * hh:(i + 1) * hh] = np.roll(arr[i * hh:(i + 1) * hh], off, axis=1)
    sp = int(16 * amt)
    r = np.roll(arr[..., 0], sp, axis=1)
    bch = np.roll(arr[..., 2], -sp, axis=1)
    arr[..., 0] = r
    arr[..., 2] = bch
    im.paste(Image.fromarray(arr), (0, 0))


def main_scene(c, t):
    c.paste_full(city_view(t))
    cs = cam_state(t)
    draw_corners(c, t)
    draw_reticle(c, t)
    draw_compass(c, t, cs[2], 1.0)
    draw_tape(c, t, 76, cs[0] * 10.0, "ALT", 1.0, 1)
    draw_tape(c, t, 1830, 168 + 160 * ease("inOutSine", clamp(t / 10, 0, 1)), "SPD", 1.0, -1)
    draw_ladder(c, t, cs[3], cs[4], 1.0)
    draw_radar(c, t, 1.0)
    draw_panel(c, t)
    draw_status(c, t)
    draw_target(c, t)
    draw_title(c, t)
    c.flush()
    post_glitch(c, t)
    c.scanlines(spacing=3, alpha=0.18)
    c.vignette(radius=0.62, power=1.9, alpha=0.5)


# === 配乐：A 小调 128 BPM，暗色脉冲 ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    PROG = [(57, 60, 64), (53, 57, 60), (55, 59, 62), (52, 55, 59)]
    ROOTS = (33, 29, 31, 28)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.6)
    pad = s.track("pad", name="pad", gain_db=-15.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-13.0, pan=0.1, seed=2)
    bass = s.track("bass", name="bass", gain_db=-9.0, pan=0.0, seed=3)
    hat = s.track("hat", name="tick", gain_db=-21.0, pan=-0.05, seed=4)
    drop = s.track("bassdrop", name="drop", gain_db=-7.0, seed=5)

    bars = 6
    for bi in range(bars):
        b0 = bi * 4.0
        ch = PROG[bi % 4]
        if bi < 5:
            for m in ch:
                pad.note(b0, name(m), 4.05, 0.5)
            bass.note(b0, name(ROOTS[bi % 4]), 1.5, 0.8)
            bass.note(b0 + 1.5, name(ROOTS[bi % 4]), 0.9, 0.6)
            bass.note(b0 + 3.0, name(ROOTS[bi % 4]), 0.9, 0.65)
            if bi >= 1:
                for si in range(8):
                    idx = (0, 1, 0, 1, 2, 1, 0, 1)[si]
                    pluck.note(b0 + si * 0.5, name(ch[idx] + 12), 0.5, 0.4)
            if bi >= 2:
                for si in range(8):
                    hat.note(b0 + si * 0.5, None, None, 0.4 if si % 2 else 0.7)
        else:
            for m in (57, 60, 64):
                pad.note(b0, name(m), 4.0, 0.45)
            drop.note(b0, None, None, 1.0)
    s.length(beats=total_beats)
    s.fade(out_seconds=1.8)
    return s


film = wv.Film(W, H, duration=11.0, fps=30, ss=2, theme="midnight",
               bpm=128, name="hud-pointcloud")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(main_scene, at=0)

film.sfx("click", at=0.1, gain=-14)
film.sfx("whoosh", at=0.85, gain=-8)
film.sfx("swipe", at=2.8, gain=-12)
for tt in (3.4, 4.4, 5.4):
    film.sfx("tick", at=tt, gain=-16)
film.sfx("ding", at=6.25, gain=-6)
film.sfx("impact", at=6.32, gain=-10)
film.sfx("glitch", at=7.65, gain=-8)
film.sfx("punch", at=8.0, gain=-8)
film.sfx("impact", at=8.25, gain=-14)
film.sfx("glitch", at=9.0, gain=-14)
film.sfx("tick", at=9.8, gain=-18)
film.sfx("tick", at=10.8, gain=-20)

if __name__ == "__main__":
    print("点云点数:", NP_)
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "hud-pointcloud.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "hud-pointcloud.sheet.png"))
