# -*- coding: utf-8 -*-
"""morph · 形变动画 · 光点粒子
星云 → 「想法」→ 灯泡 → 播放键 → 「爆款」，每次卷起 curl 气流；6.0s 径向 burst 炸开。
形状：PIL 离屏 500×260 画形状，2px 采样 alpha>128（38% 边缘点 ±3px 邻域检测），
每形状 ~700 粒；时序 T_FORM=[0.55,2.0,3.45,4.9] DUR=1.0，错峰 t0+目标x偏移*0.045，
inOutCubic 独立插值 + swirl=sin(PI*u)*1.35×curl；落定弹性过冲 exp(-st*7)*sin(st*22)*0.04；
绘制：5 色 glow sprite，粒子先画半分辨率独立画布，主画布 2 遍叠回（大半径低 alpha + 原图）；
底 #141a3a→#05060f 径向渐变；相机慢摆（yaw/pitch 用 2D 平移缩放近似）。
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
from PIL import Image, ImageDraw, ImageFilter
import write_video as wv
from write_video import fonts

W, H = 1920, 1080
SS = 2
WPX, HPX = W * SS, H * SS
OUT = os.path.join(HERE, "artifacts")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0.0, 1.0))


def cubic_in_out(x):
    t = clamp(x, 0.0, 1.0)
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


# ---------- 形状采样（PIL 离屏 500×260，2px 采样，38% 边缘点） ----------
SW, SH = 500, 260


def _draw_shape(kind):
    im = Image.new("L", (SW, SH), 0)
    d = ImageDraw.Draw(im)
    if kind == 0:
        f = fonts.load("sans_bold", 150)
        d.text((250, 130), "想法", font=f, fill=255, anchor="mm")
    elif kind == 1:
        d.ellipse([170, 22, 330, 182], fill=255)                       # 玻璃球
        d.polygon([(214, 172), (286, 172), (276, 208), (224, 208)], fill=255)  # 颈
        for q in range(3):                                             # 3 道螺纹
            d.rectangle([222, 210 + q * 12, 278, 216 + q * 12], fill=255)
        d.rectangle([228, 84, 272, 128], fill=0)                       # 抠灯丝窗
        d.rectangle([238, 96, 262, 104], fill=255)                     # 灯丝
        d.rectangle([247, 104, 253, 126], fill=255)
    elif kind == 2:
        d.rounded_rectangle([135, 42, 365, 218], radius=44, fill=255)  # 圆角方
        d.polygon([(232, 92), (232, 168), (300, 130)], fill=0)         # 抠播放三角
    else:
        f = fonts.load("sans_bold", 150)
        d.text((250, 130), "爆款", font=f, fill=255, anchor="mm")
    return im


def _pick(pts, n, seed):
    """确定性抽取 n 个（hash 排序），不足则循环 + 抖动。"""
    if not pts:
        return []
    order = sorted(range(len(pts)), key=lambda i: hash1(i * 7.77 + seed))
    out = []
    for q in range(n):
        i = order[q % len(order)]
        x, y = pts[i]
        if q >= len(order):
            x += (hash1(q * 3.1 + seed) - 0.5) * 6.0
            y += (hash1(q * 5.7 + seed + 1) - 0.5) * 6.0
        out.append((x, y))
    return out


SHAPE_PTS = []   # SHAPE_PTS[k][p] = 粒子 p 在形状 k 的目标世界坐标 (x, y, z)
for kind in range(4):
    im = _draw_shape(kind)
    alpha = np.asarray(im, dtype=np.uint8)
    er = np.asarray(im.filter(ImageFilter.MinFilter(7)), dtype=np.uint8)
    edge, inner = [], []
    for y in range(0, SH, 2):
        for x in range(0, SW, 2):
            if alpha[y, x] > 128:
                if er[y, x] <= 128:
                    edge.append((float(x), float(y)))
                else:
                    inner.append((float(x), float(y)))
    n_e = int(700 * 0.38)
    picked = _pick(edge, n_e, kind * 17.0 + 1) + _pick(inner, 700 - n_e, kind * 17.0 + 2)
    pts = []
    for (x, y) in picked:
        pts.append(((x - SW / 2) * 0.02, -(y - SH / 2) * 0.02,
                    (hash1(x * 0.71 + y * 1.13 + kind * 7.0) - 0.5) * 0.18))
    pts.sort(key=lambda p: p[0] * 2.0 + p[1] * 0.01)   # 左右连贯，形变可读
    SHAPE_PTS.append(pts)

NP = 700
# 粒子固定属性：星云起点 / 颜色 / 尺寸 / 相位
NEB = []
COLIDX = []
BASE_R = []
PHASE = []
DIRXY = []
PAL = [(96, 150, 255), (255, 176, 92), (120, 224, 255), (255, 128, 156), (176, 148, 255)]
PAL2 = [(160, 120, 255), (255, 140, 110), (96, 200, 255), (255, 176, 120), (130, 170, 255)]
for p in range(NP):
    r = pow(hash1(p * 1.71 + 11.0), 0.6) * 4.2
    arm = (p % 2) * math.pi
    th = r * 1.25 + arm + (hash1(p * 2.31 + 5.0) - 0.5) * 0.6
    NEB.append((r * math.cos(th), r * math.sin(th) * 0.55,
                (hash1(p * 3.13 + 7.0) - 0.5) * 0.18))
    hx = (hash1(p * 7.71) * 0.7 + (SHAPE_PTS[3][p % len(SHAPE_PTS[3])][0] + 5) / 10.0 * 0.6)
    COLIDX.append(int(hx * 5) % 5)
    BASE_R.append(7.0 + hash1(p * 5.31) * 8.0)
    PHASE.append(hash1(p * 9.13) * 6.28)
    sx4, sy4, _ = SHAPE_PTS[3][p % len(SHAPE_PTS[3])]
    ln = math.hypot(sx4, sy4) or 1.0
    DIRXY.append((sx4 / ln, sy4 / ln))


def curl2(x, y, t):
    """sin·cos 伪噪声有限差分（e=0.08）。"""
    e = 0.35

    def nz(xx, yy):
        return math.sin(xx * 1.9 + t * 0.7) * math.cos(yy * 1.5 - t * 0.55)

    cx = (nz(x, y + e) - nz(x, y - e)) / (2 * e)
    cy = -(nz(x + e, y) - nz(x - e, y)) / (2 * e)
    return cx * 0.08, cy * 0.08


T_FORM = [0.55, 2.0, 3.45, 4.9]
DUR = 1.0

# ---------- 缓存：底 / 光晕 sprite ----------


def radial_bg():
    w, h = WPX, HPX
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.hypot((xx - w * 0.5) / (w * 0.62), (yy - h * 0.53) / (h * 0.62))
    a = np.clip(dist, 0.0, 1.0) ** 1.6
    c0 = (20, 26, 58)     # #141a3a 近似
    c1 = (5, 6, 15)       # #05060f
    arr = np.zeros((h, w, 3), np.uint8)
    for ch in range(3):
        arr[..., ch] = (c0[ch] + (c1[ch] - c0[ch]) * a).astype(np.uint8)
    return Image.fromarray(arr)


BG = radial_bg()

_GLOW_BASE = {}


def _glow_sprite(color):
    spr = _GLOW_BASE.get(color)
    if spr is None:
        n = 64
        yy, xx = np.mgrid[0:n, 0:n].astype(float)
        dist = np.hypot(xx - (n - 1) / 2.0, yy - (n - 1) / 2.0) / (n / 2.0)
        a = np.clip(1.0 - dist, 0.0, 1.0) ** 2.2
        arr = np.zeros((n, n, 4), np.uint8)
        arr[..., 0], arr[..., 1], arr[..., 2] = color
        arr[..., 3] = (a * 255).astype(np.uint8)
        spr = Image.fromarray(arr)
        _GLOW_BASE[color] = spr
    return spr


_SPR_RZ = {}


def _spr(color, d):
    spr = _SPR_RZ.get((color, d))
    if spr is None:
        spr = _glow_sprite(color).resize((d, d), Image.BILINEAR)
        if len(_SPR_RZ) > 96:
            _SPR_RZ.clear()
        _SPR_RZ[(color, d)] = spr
    return spr


# ---------- 场景 ----------
def main_scene(cnv, t):
    img = cnv.img
    img.paste(BG, (0, 0))
    # 相机慢摆（yaw/pitch → 2D 平移缩放近似）
    yaw = 0.35 * math.sin(t * 0.55) - 0.1
    pitch = 0.08 * math.sin(t * 0.4)
    cam_dx = yaw * 160.0
    cam_dy = pitch * 90.0
    cam_s = 1.0 + 0.012 * math.sin(t * 0.31)
    g_fade = 1.0 - ease_io(clamp((t - 9.6) / 0.8, 0.0, 1.0))   # 收尾淡出

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))            # 半分辨率粒子画布
    dl = ImageDraw.Draw(layer, "RGBA")
    for p in range(NP):
        # 当前段
        mseg = 0
        for i in range(4):
            if t >= T_FORM[i]:
                mseg = i
        if t < T_FORM[0]:
            x, y, z = NEB[p]
            sw = 0.0
            u = 0.0
        else:
            tgt = SHAPE_PTS[mseg][p % len(SHAPE_PTS[mseg])]
            src = NEB[p] if mseg == 0 else SHAPE_PTS[mseg - 1][p % len(SHAPE_PTS[mseg - 1])]
            t0p = T_FORM[mseg] + (tgt[0] + 5.0) * 0.045
            u = clamp((t - t0p) / DUR, 0.0, 1.0)
            m = cubic_in_out(u)
            x = src[0] + (tgt[0] - src[0]) * m
            y = src[1] + (tgt[1] - src[1]) * m
            z = src[2] + (tgt[2] - src[2]) * m
            sw = math.sin(math.pi * u) * 1.35
        # 气流扰动 + idle 微颤
        cx, cy = curl2(x, y, t)
        x += cx * sw + 0.012 * math.sin(t * 1.3 + PHASE[p])
        y += cy * sw + 0.012 * math.cos(t * 1.1 + PHASE[p] * 1.3)
        # 落定弹性过冲（sprite 缩放）
        sc = 1.0
        if t >= T_FORM[0]:
            st = t - (t0p + DUR)
            if st > 0:
                sc = 1.0 + math.exp(-st * 7.0) * math.sin(st * 22.0) * 0.04
        # 末章 burst 径向炸开 + 松散余云
        if mseg == 3 and u >= 1.0:
            if t < 5.95:
                bp = 0.0
            elif t < 6.15:
                bp = (t - 5.95) / 0.2
            else:
                bp = math.exp(-((t - 6.15) / 0.38) ** 2) + 0.30 * ease_io(clamp((t - 6.9) / 1.8, 0.0, 1.0))
            dx_, dy_ = DIRXY[p]
            x += dx_ * bp * 2.5
            y += dy_ * bp * 2.5
        # 投影
        pf = 1150.0 / (7.2 - z)
        px = W / 2 + 1150.0 * x / (7.2 - z)
        py = H * 0.53 - 1150.0 * y / (7.2 - z)
        px = (px - W / 2) * cam_s + W / 2 + cam_dx
        py = (py - H * 0.53) * cam_s + H * 0.53 + cam_dy
        rr = BASE_R[p] * sc * (1.0 + abs(z) * 2.2)
        a = (0.8 - abs(z) * 1.1) * (0.8 + 0.2 * math.sin(t * 2.0 + PHASE[p] * 3.0)) * g_fade
        if a <= 0.02:
            continue
        d = max(4, int(BASE_R[p] * 2 * sc * (1.0 + abs(z) * 2.2)))
        spr = _spr(PAL[COLIDX[p]], d)
        layer.paste(spr, (int(px - d / 2), int(py - d / 2)), spr)

    # 辉光合成：大半径低 alpha（降采样模糊）+ 原图，2 遍叠回
    small = layer.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    glow_up = small.resize((WPX, HPX), Image.BILINEAR)
    if g_fade < 0.996:
        al = glow_up.getchannel("A").point(lambda v: int(v * g_fade * 0.6))
        glow_up = glow_up.copy()
        glow_up.putalpha(al)
    else:
        al = glow_up.getchannel("A").point(lambda v: int(v * 0.6))
        glow_up = glow_up.copy()
        glow_up.putalpha(al)
    img.paste(glow_up, (0, 0), glow_up)
    sharp = layer.resize((WPX, HPX), Image.BILINEAR)
    if g_fade < 0.996:
        al = sharp.getchannel("A").point(lambda v: int(v * g_fade * 0.95))
        sharp = sharp.copy()
        sharp.putalpha(al)
    img.paste(sharp, (0, 0), sharp)


# ---------- 配乐（C 大调，120 BPM） ----------
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    bar = spb * 4.0
    total_beats = duration / spb
    bars = int(math.ceil((duration - 2.4) / bar))

    PROG = (0, 5, 3, 4)
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def arp_tones(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4, deg + 7, deg + 9, deg + 11)]

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.5)
    pad = s.track("pad", name="pad", gain_db=-16.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-11.0, pan=0.12, seed=2)
    bass = s.track("bass", name="bass", gain_db=-9.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = chord_midi(PROG[bi % 4])
        if bi == bars - 1:
            pad.note(b0, name(ch[0]), 5.0, 0.45)
            for j, (off, idx) in enumerate(((1.0, 2), (2.0, 1), (3.0, 0), (4.0, 2))):
                pluck.note(b0 + off, name(ch[idx]), 0.6, 0.5 - 0.08 * j)
        else:
            for m in ch:
                pad.note(b0, name(m), 4.05, 0.5)
            tn = arp_tones(PROG[bi % 4])
            for si, idx in enumerate((0, 2, 4, 1, 3, 5, 2, 4)):
                pluck.note(b0 + si * 0.5, name(tn[idx]), 0.55, 0.5)
        bass.note(b0, name(ch[0] - 24), 1.8, 0.75)
        bass.note(b0 + 2.0, name(ch[0] - 24), 1.8, 0.6)

    s.length(beats=total_beats)
    s.fade(out_seconds=2.5)
    return s


# ---------- 影片 ----------
film = wv.Film(W, H, duration=10.5, fps=30, ss=2, theme="midnight",
               bpm=120, name="morph")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 10.5, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("从想法到爆款", at=8.2, style="hero", y=180)
s1.text("MORPH · PARTICLES", at=8.7, style="subtitle", y=272)

film.flicker_exclude(5.9, 6.6)     # 末章 burst 径向炸开（有意急变）
# 音效（120 BPM 节拍对齐）：riser 起势 / pop ×3 形变成形 / impact 爆款炸开 / sparkle 收
film.sfx("riser", at=0.5, dur=1.2, gain=-13)
film.sfx("pop", at=1.5, gain=-8)
film.sfx("pop", at=3.0, gain=-8)
film.sfx("pop", at=4.5, gain=-8)
film.sfx("impact", at=6.0, gain=-9)
film.sfx("sparkle", at=6.5, gain=-8)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "morph.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "morph.sheet.png"))
