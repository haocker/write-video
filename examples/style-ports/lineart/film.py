# -*- coding: utf-8 -*-
"""lineart · 线条动画 · 金线山脊
504 根金色流线（42 排 × 12 根 × 40 段，curl 场 + 风 (0.55,-0.08) 预烘焙）
错峰 inOutCubic 从流线路径 lerp 排成透视山脊（ROWZ=3+52*(i/N)^1.35 近疏远密）；
4.0-5.6s 山脊下填深色遮挡变实心风景（线色按深度 GOLD→蓝灰，近亮远淡）；
4.6-8.2s 线框太阳（14 圈同心圆 + halo）升起；120 点光路 5.4-8.1s 沿山脊从近走到
最远山顶，3 遍描边叠光近似 'lighter'，抵达 flare；6.4s 标题「远方」字距收拢。
10.5 秒 / 1920x1080 / 30fps
运行: python3 film.py
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
WPX, HPX = W * SS, H * SS
OUT = os.path.join(HERE, "artifacts")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mix3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0.0, 1.0))


def out_cubic(x):
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 3


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def vnoise3(x, y, z):
    """3D value noise（hash 格点三线性），返回 0..1。"""
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - xi, y - yi, z - zi
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    uz = fz * fz * (3 - 2 * fz)

    def h(i, j, k):
        return hash1(xi * 7.13 + yi * 157.31 + zi * 269.7 + i * 3.71 + j * 11.93 + k * 29.31 + 5.0)

    c00 = h(0, 0, 0) + (h(1, 0, 0) - h(0, 0, 0)) * ux
    c10 = h(0, 1, 0) + (h(1, 1, 0) - h(0, 1, 0)) * ux
    c01 = h(0, 0, 1) + (h(1, 0, 1) - h(0, 0, 1)) * ux
    c11 = h(0, 1, 1) + (h(1, 1, 1) - h(0, 1, 1)) * ux
    c0 = c00 + (c10 - c00) * uy
    c1 = c01 + (c11 - c01) * uy
    return c0 + (c1 - c0) * uz


# ---------- 地形（5 阶脊状噪声 + 远峰高斯 + 谷地压制 + 近处压平） ----------
def terrain(x, z):
    f = 0.055
    amp = 1.0
    h = 0.0
    norm = 0.0
    for o in range(5):
        n = vnoise3(x * f, z * f, o * 7.7) * 2.0 - 1.0
        h += amp * (1.0 - abs(n)) ** 2
        norm += amp
        f *= 2.05
        amp *= 0.55
    h = h / norm
    dx = (x - 8.5) / 7.5
    dz = (z - 34.0) / 10.0
    h = h * 5.2 + 9.5 * math.exp(-(dx * dx + dz * dz))
    h = max(0.0, h - 1.25)
    return h * min(1.0, z / 5.0)


# ---------- 山脊网格 + 流线预烘焙 ----------
NR = 42          # 排（深度行）
NPSeg = 40       # 每根 40 段
NPT = NPSeg + 1  # 41 点
LPR = 12         # 每排 12 根 → 504 根
XR = 46.0
ROWZ = [3.0 + 52.0 * (i / (NR - 1)) ** 1.35 for i in range(NR)]

RIDGE = []  # 每排山脊折线（世界坐标）
for i in range(NR):
    zr = ROWZ[i]
    pts = []
    for k in range(NPT):
        x = -XR / 2 + XR * k / NPSeg
        pts.append((x, terrain(x, zr)))
    RIDGE.append(pts)


def curl_v(x, h, z):
    """curl 场 = 伪噪声有限差分（e=1.2 幅度），加恒定风。"""
    e = 0.4
    s = 0.10

    def psi(xx, hh):
        return vnoise3(xx * s, hh * s, z * 0.05 + 3.7) * 2.0 - 1.0

    cx = (psi(x, h + e) - psi(x, h - e)) / (2 * e)
    cy = -(psi(x + e, h) - psi(x - e, h)) / (2 * e)
    vx = cx * 1.2 + 0.55
    vy = cy * 1.2 - 0.08
    ln = math.hypot(vx, vy) or 1.0
    return vx / ln, vy / ln


FLOW = []  # FLOW[i][j] = 第 i 排第 j 根的流线路径（世界坐标）
STEP = 0.55
for i in range(NR):
    zr = ROWZ[i]
    row = []
    for j in range(LPR):
        sd = i * 13.7 + j * 3.11
        x = -26.0 + 52.0 * hash1(sd + 1.0)
        h = terrain(x, zr) + 5.5 + hash1(sd + 2.0) * 9.0
        pts = [(x, h)]
        for k in range(NPSeg):
            vx, vy = curl_v(x, h, zr)
            x += vx * STEP
            h += vy * STEP
            h = max(h, terrain(x, zr) + 0.6)
            pts.append((x, h))
        row.append(pts)
    FLOW.append(row)

# 走山的光：120 采样点沿地形从近到远（5 点平均高度 + 0.14 抬升）
LIGHT_PATH = []
for k in range(120):
    u = k / 119.0
    zk = 2.5 + 32.0 * u
    xk = -16.0 + 24.5 * u + math.sin(u * 5.2) * 3.2 * (1.0 - u)
    hk = sum(terrain(xk + dx, zk) for dx in (-1.2, -0.6, 0.0, 0.6, 1.2)) / 5.0 + 0.14
    LIGHT_PATH.append((xk, hk, zk))

GOLD = (232, 196, 128)
FARGRAY = (108, 128, 164)

# ---------- 缓存：天空 / 暗角 / 光晕 sprite ----------


def vgrad(w, h, stops):
    arr = np.zeros((h, w, 3), np.uint8)
    px = np.array([s[0] for s in stops], float)
    cols = np.array([s[1] for s in stops], float)
    ys = np.linspace(0.0, 1.0, h)
    for ch in range(3):
        arr[..., ch] = np.interp(ys, px, cols[:, ch])[:, None]
    return Image.fromarray(arr)


SKY_NIGHT = vgrad(960, 540, [(0.0, (8, 12, 26)), (0.62, (26, 32, 56)), (1.0, (52, 56, 84))]).resize((WPX, HPX), Image.BILINEAR)
SKY_DAWN = vgrad(960, 540, [(0.0, (26, 32, 62)), (0.55, (74, 66, 92)), (0.82, (168, 108, 84)), (1.0, (232, 150, 96))]).resize((WPX, HPX), Image.BILINEAR)


def vignette_img(alpha_max):
    w, h = WPX, HPX
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    dist = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    a = np.clip((dist - 0.58) / 0.42, 0.0, 1.0) ** 1.7 * alpha_max
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr)


VIG = vignette_img(120)

_GLOW_BASE = {}


def _glow_sprite(color):
    spr = _GLOW_BASE.get(color)
    if spr is None:
        n = 96
        yy, xx = np.mgrid[0:n, 0:n].astype(float)
        dist = np.hypot(xx - (n - 1) / 2.0, yy - (n - 1) / 2.0) / (n / 2.0)
        a = np.clip(1.0 - dist, 0.0, 1.0) ** 2.0
        arr = np.zeros((n, n, 4), np.uint8)
        arr[..., 0], arr[..., 1], arr[..., 2] = color
        arr[..., 3] = (a * 255).astype(np.uint8)
        spr = Image.fromarray(arr)
        _GLOW_BASE[color] = spr
    return spr


_GLOW_RZ = {}


def glow(img, x, y, r, color, alpha=1.0):
    d = int(max(8, int(r * 2) // 8 * 8))
    spr = _GLOW_RZ.get((color, d))
    if spr is None:
        spr = _glow_sprite(color).resize((d, d), Image.BILINEAR)
        _GLOW_RZ[(color, d)] = spr
    if alpha < 0.996:
        k2 = (color, d, int(alpha * 16))
        spr2 = _GLOW_RZ.get(k2)
        if spr2 is None:
            a = spr.getchannel("A").point(lambda v: int(v * alpha))
            spr2 = spr.copy()
            spr2.putalpha(a)
            _GLOW_RZ[k2] = spr2
        spr = spr2
    img.paste(spr, (int(x - d / 2), int(y - d / 2)), spr)


_FONT_TITLE = None

# ---------- 相机与投影 ----------
F = 980.0


def cam(t):
    p = ease_io(clamp((t - 2.2) / 7.8, 0.0, 1.0))
    return (-7.0 + 8.5 * p, 7.4 - 1.2 * p)  # (camz, camY)


def main_scene(cnv, t):
    _GLOW_RZ.clear()
    img = cnv.img
    d = ImageDraw.Draw(img, "RGBA")
    camz, camY = cam(t)
    horizon = H * 0.40
    rise = ease_io(clamp((t - 4.6) / 3.6, 0.0, 1.0))     # 太阳升起
    sun_a = clamp((t - 4.2) / 1.0, 0.0, 1.0)

    def proj(x, h, z):
        dz = max(0.35, z - camz)
        return (W / 2 + F * x / dz, horizon + F * (camY - h) / dz)

    # 天空（夜→破晓）
    img.paste(SKY_NIGHT, (0, 0))
    if rise > 0.01:
        warm = SKY_DAWN.copy()
        warm.putalpha(int(255 * min(1.0, rise * 0.85)))
        img.paste(warm, (0, 0), warm)

    # 线框太阳（14 圈同心圆 + halo，从山脊后升起）
    pk_h = terrain(8.5, 34.0)
    pk = proj(8.5, pk_h, 34.0)
    sun_x = pk[0]
    sun_y = (pk[1] + 190.0) + ((pk[1] - 235.0) - (pk[1] + 190.0)) * rise
    if sun_a > 0.01:
        glow(img, sun_x * SS, sun_y * SS, 320 * SS, (255, 210, 130), 0.42 * sun_a)
        for q in range(14):
            r = (165 - q * 9) * SS
            a = int(255 * (0.13 + 0.05 * q) * sun_a)
            d.ellipse([sun_x * SS - r, sun_y * SS - r, sun_x * SS + r, sun_y * SS + r],
                      outline=(255, 214, 130, a), width=max(1, int(2.2 * SS)))

    # 山脊：远→近 逐排（遮挡填充 + 12 根金线 × 亮线两层）
    for i in range(NR - 1, -1, -1):
        dep = i / (NR - 1)
        zr = ROWZ[i]
        ridge_px = [proj(x, h, zr) for (x, h) in RIDGE[i]]
        sol = ease_io(clamp((t - (4.0 + dep * 0.62)) / 1.05, 0.0, 1.0))
        if sol > 0.01:
            fa = int(255 * sol * (0.94 - dep * 0.38))
            fc = mix3((24, 30, 52), (9, 13, 24), dep)
            poly = [(px * SS, py * SS) for (px, py) in ridge_px]
            poly.append((ridge_px[-1][0] * SS, HPX + 60))
            poly.append((ridge_px[0][0] * SS, HPX + 60))
            d.polygon(poly, fill=fc + (fa,))
        # 线色按深度 GOLD→蓝灰，近亮远淡
        lc = mix3(GOLD, FARGRAY, dep)
        row_a = 1.0 - dep * 0.5
        t0_row = 2.1 + dep * 1.1
        for j in range(LPR):
            m = ease_io(clamp((t - (t0_row + (j % 12) * 0.035)) / 1.0, 0.0, 1.0))
            g = out_cubic(clamp(t / 2.1, 0.0, 1.0))
            n_seg = int(g * NPSeg)
            if n_seg < 2:
                continue
            flow = FLOW[i][j]
            offx = (j - 5.5) * 6.0 * (1.0 - m)
            pts = []
            for k in range(n_seg + 1):
                if m >= 0.999:
                    fx, fh = RIDGE[i][k]
                elif m <= 0.001:
                    fx, fh = flow[k]
                else:
                    fx = flow[k][0] + (RIDGE[i][k][0] - flow[k][0]) * m
                    fh = flow[k][1] + (RIDGE[i][k][1] - flow[k][1]) * m
                sx, sy = proj(fx, fh, zr)
                pts.append(((sx + offx) * SS, sy * SS))
            if len(pts) < 2:
                continue
            wa = int(255 * 0.12 * row_a)
            ta = int(255 * 0.8 * row_a)
            d.line(pts, fill=lc + (wa,), width=max(2, int(6 * SS)), joint="curve")
            d.line(pts, fill=lc + (ta,), width=max(1, int(1.6 * SS)), joint="curve")

    # 走山的光（3 遍描边叠光 + 头部 glow，8.1s 抵达最远山顶 flare）
    pw = ease_io(clamp((t - 5.4) / 2.7, 0.0, 1.0))
    if pw > 0.01:
        n_pts = max(2, int(pw * 119) + 2)
        lp = [proj(x, h, z) for (x, h, z) in LIGHT_PATH[:n_pts]]
        lp = [(x * SS, y * SS) for (x, y) in lp]
        for (wd, al) in ((9, 0.06), (4, 0.16), (1.6, 0.95)):
            d.line(lp, fill=(255, 238, 186, int(255 * al)), width=max(1, int(wd * SS)), joint="curve")
        flare = math.exp(-(t - 8.1) * 2.2) if t > 8.1 else 0.0
        hx, hy = lp[-1]
        glow(img, hx, hy, (26 + flare * 120) * SS, (255, 226, 150), 0.9)
        if flare > 0.02:
            glow(img, hx, hy, 320 * SS, (255, 210, 130), 0.4 * flare)

    # 标题「远方」：6.4s 落笔，字距收拢
    global _FONT_TITLE
    if t > 6.35:
        if _FONT_TITLE is None:
            _FONT_TITLE = fonts.load("sans_bold", 150 * SS)
        a_in = clamp((t - 6.4) / 0.6, 0.0, 1.0)
        e = ease_io(clamp((t - 6.4) / 1.2, 0.0, 1.0))
        gap = 75.0 + 45.0 * (1.0 - e)   # 字距从 240 收到 150（中心距）
        ca = int(255 * a_in)
        col = (255, 242, 214, ca)
        cy = H * 0.42 * SS
        d.text((W / 2 * SS - gap * SS / 2, cy), "远", font=_FONT_TITLE, fill=col, anchor="mm")
        d.text((W / 2 * SS + gap * SS / 2, cy), "方", font=_FONT_TITLE, fill=col, anchor="mm")

    img.paste(VIG, (0, 0), VIG)


# ---------- 配乐（D 宫五声，116 BPM） ----------
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    bar = spb * 4.0
    total_beats = duration / spb
    bars = int(math.ceil((duration - 2.4) / bar))

    CHORDS = ([62, 66, 69], [59, 62, 66], [57, 62, 66], [62, 66, 69])
    ROOTS = (38, 35, 33, 38)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.8)
    pad = s.track("pad", name="pad", gain_db=-15.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="guzheng", gain_db=-11.0, pan=0.10, seed=2)
    bass = s.track("bass", name="bass", gain_db=-10.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = CHORDS[bi % len(CHORDS)]
        for m in ch:
            pad.note(b0, name(m), 4.1, 0.5)
            pad.note(b0, name(m + 12), 4.1, 0.25)
        bass.note(b0, name(ROOTS[bi % len(ROOTS)]), 2.2, 0.8)
        bass.note(b0 + 2.0, name(ROOTS[bi % len(ROOTS)] + 12), 1.8, 0.5)
        tones = list(ch) + [ch[0] + 12, ch[1] + 12, ch[2] + 12]
        for si, idx in enumerate((0, 1, 2, 3, 2, 3, 4, 5)):
            pluck.note(b0 + si * 0.5, name(tones[idx]), 0.55, 0.5)

    end = (duration - 2.4) / spb
    ln = (2.4 + 0.8) / spb
    pluck.note(end, name(74), ln, 0.55)
    pluck.note(end, name(86), ln, 0.28)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.5)
    return s


# ---------- 影片 ----------
film = wv.Film(W, H, duration=10.5, fps=30, ss=2, theme="midnight",
               bpm=116, name="lineart")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 10.5, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("LINEART · 金线山脊", at=7.3, style="subtitle", y=760)

# 音效（116 BPM 八分网格对齐）：riser 起势 / whoosh 排成山脊 / chime 实心化 / pop 成景 / sparkle 光抵达
film.flicker_exclude(2.3, 3.7)     # 流线错峰变形期（亮线高速重排，有意急变）
film.sfx("riser", at=0.52, dur=1.4, gain=-13)
film.sfx("whoosh", at=2.59, gain=-10)
film.sfx("chime", at=4.40, gain=-9)
film.sfx("pop", at=5.69, gain=-9)
film.sfx("sparkle", at=8.01, gain=-8)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "lineart.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "lineart.sheet.png"))
