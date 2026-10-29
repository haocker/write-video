# -*- coding: utf-8 -*-
"""《紫禁城》 — 国风插画分层航拍
10 秒 / 1920x1080 / 30fps
四层视差：远境(haze) → 太和殿群(重檐庑殿顶/斗拱/汉白玉台基) → 午门宫墙(宫灯) → 天空
航拍调度：晨光降落(zoom out→in) → 沿中轴推进飞越午门 → 黄昏横摇金顶宫灯 → 拉升收全景
运行: python3 forbidden_city.film.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           os.path.abspath(os.path.join(HERE, "..", "..", "runtime"))):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import write_video as wv

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mix3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0, 1))


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


RED = (158, 44, 38)
RED_DK = (122, 32, 28)
GOLD = (214, 170, 68)
GOLD_DK = (150, 108, 40)
MARBLE = (235, 231, 221)
DOOR = (58, 24, 20)
PLAQUE = (36, 62, 104)
LANTERN = (238, 118, 58)

WARM = 0.0  # 1=晨/昏金光


def tint_g(col, k=1.0, haze=0.0, sky=(191, 227, 245)):
    c = mix3(col, sky, haze) if haze else col
    tt = mix3((255, 255, 255), (255, 196, 150), WARM)
    return (clamp(int(c[0] * tt[0] / 255.0 * k), 0, 255),
            clamp(int(c[1] * tt[1] / 255.0 * k), 0, 255),
            clamp(int(c[2] * tt[2] / 255.0 * k), 0, 255))


def _bez(p0, p1, p2, n=12):
    return [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
             (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1])
            for u in (i / n for i in range(n + 1))]


# === 凹曲面庑殿顶（正立面：檐口起翘 + 凹形屋面 + 瓦垄 + 正脊鸱吻） ===
def curved_roof(c, cx, ey, w_e, w_r, h, s, alpha=1.0, tile=True, haze=0.0):
    if s * w_e < 8:
        return
    lift = 0.28 * h * s
    half_e, half_r = w_e / 2 * s, w_r / 2 * s
    ry_ = ey - h * s
    eave = []
    for i in range(17):
        u = i / 16.0
        v = 2 * u - 1
        eave.append((cx - half_e + w_e * s * u, ey - lift * v * v))
    lt, rt = eave[0], eave[-1]
    ctrl_y = ey - (ey - ry_) * 0.12
    right = _bez(rt, (cx + half_e * 0.40, ctrl_y), (cx + half_r, ry_), 10)
    left = _bez(lt, (cx - half_e * 0.40, ctrl_y), (cx - half_r, ry_), 10)
    poly = eave + right[1:] + [(cx + half_r, ry_), (cx - half_r, ry_)] + left[::-1][1:]
    roof_col = tint_g(mix3(GOLD, (255, 214, 120), WARM * 0.35), 1.0, haze)
    c.polygon(poly, fill=roof_col, alpha=alpha)
    # 檐口瓦当带（深金描边）
    c.lines(eave, color=tint_g(GOLD_DK, 1.0, haze), width=max(2.0, 4.5 * s), alpha=alpha)
    # 瓦垄竖线（正脊跨度内）
    if tile and w_e * s > 90:
        n = max(6, int(w_r * s / 26))
        for i in range(1, n):
            x = cx - half_r + 2 * half_r * i / float(n)
            y0 = ey - lift * (2 * ((x - (cx - half_e)) / (w_e * s)) - 1) ** 2
            c.line(x, y0 - 2, x, ry_ + 2, color=tint_g(GOLD_DK, 1.0, haze),
                   width=max(1.0, 1.6 * s), alpha=0.4 * alpha)
    # 正脊 + 鸱吻 + 脊兽
    c.line(cx - half_r, ry_, cx + half_r, ry_, color=tint_g(GOLD_DK, 1.0, haze),
           width=max(2.0, 3.2 * s), alpha=alpha)
    for sgn in (-1, 1):
        q = (cx + sgn * half_r, ry_)
        c.circle(q[0], q[1], max(2.0, 4.5 * s), fill=tint_g(GOLD_DK, 1.05, haze), alpha=alpha)
    nb = max(1, int(half_r / (18 * s))) if s > 0.5 else 0
    for i in range(-nb, nb + 1):
        x = cx + i * 18 * s
        c.rect(x - 2 * s, ry_ - 5 * s, 4 * s, 5 * s, fill=tint_g(GOLD_DK, 1.0, haze), alpha=alpha)


# === 汉白玉台基（阶梯 + 望柱栏杆） ===
def terrace(c, cx, gy, tiers, s, alpha=1.0, haze=0.0):
    y = gy
    for w_, h_ in tiers:
        c.rect(cx - w_ / 2 * s, y - h_ * s, w_ * s, h_ * s,
               fill=tint_g(MARBLE, 1.0, haze), alpha=alpha)
        # 望柱
        n = max(3, int(w_ * s / 46))
        for i in range(n + 1):
            px = cx - w_ / 2 * s + w_ * s * i / float(n)
            c.rect(px - 1.6 * s, y - h_ * s - 9 * s, 3.2 * s, 9 * s,
                   fill=tint_g((248, 246, 240), 1.0, haze), alpha=alpha)
        c.line(cx - w_ / 2 * s, y - h_ * s - 9 * s, cx + w_ / 2 * s, y - h_ * s - 9 * s,
               color=tint_g((248, 246, 240), 1.0, haze), width=2.2 * s, alpha=alpha)
        y -= h_ * s
    return y  # 台基顶面 y


# === 太和殿（重檐庑殿顶 + 斗拱 + 匾额） ===
def draw_taihe(c, cx, gy, s, alpha=1.0, haze=0.0, plaque=True):
    top = terrace(c, cx, gy, [(640, 24), (570, 22), (505, 20)], s, alpha, haze)
    bw, bh = 400 * s, 158 * s
    by0 = top - bh
    c.rect(cx - bw / 2, by0, bw, bh, fill=tint_g(RED, 1.0, haze), alpha=alpha)
    # 廊柱
    for i in range(9):
        x = cx - bw / 2 + bw * (i + 0.5) / 9.0
        c.line(x, by0 + 8 * s, x, top - 6 * s, color=tint_g(RED_DK, 1.0, haze),
               width=4.5 * s, alpha=alpha)
    # 门钉门
    dw, dh = 40 * s, 92 * s
    for i in (-1, 0, 1):
        dx = cx + i * 62 * s
        c.rect(dx - dw / 2, top - dh, dw, dh, fill=tint_g(DOOR, 1.0, haze), alpha=alpha)
        nd = max(2, int(dh / (13 * s)))
        for r in range(nd):
            for q in (-1, 1):
                c.circle(dx + q * 11 * s, top - dh + (r + 1) * dh / (nd + 1.0),
                         max(1.0, 2.2 * s), fill=tint_g((255, 214, 120), 1.05, haze), alpha=alpha)
    # 匾额
    if plaque and s > 0.6:
        pw, ph = 104 * s, 36 * s
        py = by0 + 12 * s
        c.rect(cx - pw / 2, py, pw, ph, fill=tint_g(PLAQUE, 1.0, haze), alpha=alpha)
        c.rect(cx - pw / 2, py, pw, ph, outline=tint_g((255, 214, 120), 1.1, haze),
               width=2.0 * s, alpha=alpha)
        c.text("太和殿", cx, py + ph / 2, 24 * s, tint_g((255, 220, 140), 1.1, haze),
               bold=True, alpha=alpha)
    # 斗拱带 + 下檐
    eave1_y = by0 - 20 * s
    c.rect(cx - 470 * s / 2, eave1_y, 470 * s, 20 * s, fill=tint_g(RED_DK, 1.0, haze), alpha=alpha)
    for i in range(int(470 * s / 15)):
        x = cx - 235 * s + i * 15 * s
        c.line(x, eave1_y + 3 * s, x, eave1_y + 17 * s, color=tint_g((255, 208, 120), 1.0, haze),
               width=2.0 * s, alpha=0.75 * alpha)
    curved_roof(c, cx, eave1_y, 540, 320, 86, s, alpha, haze=haze)
    # 上檐（重檐）
    drum_w, drum_h = 290 * s, 22 * s
    dy = eave1_y - 86 * s * 0.78 - drum_h
    c.rect(cx - drum_w / 2, dy, drum_w, drum_h, fill=tint_g(RED, 1.0, haze), alpha=alpha)
    curved_roof(c, cx, dy, 360, 170, 78, s, alpha, haze=haze)


# === 角楼（三重檐做多檐塔） ===
def draw_corner_tower(c, cx, gy, s, alpha=1.0, haze=0.0):
    c.rect(cx - 46 * s, gy - 56 * s, 92 * s, 56 * s, fill=tint_g(RED, 1.0, haze), alpha=alpha)
    y = gy - 56 * s
    for i, (w_, h_) in enumerate([(140, 40), (108, 36), (76, 32)]):
        curved_roof(c, cx, y, w_, w_ * 0.55, h_, s, alpha, haze=haze, tile=(i == 0))
        y -= h_ * s * 0.85
        if i < 2:
            c.rect(cx - w_ * 0.30 * s, y - 16 * s, w_ * 0.60 * s, 16 * s,
                   fill=tint_g(RED, 1.0, haze), alpha=alpha)
            y -= 16 * s
    c.rect(cx - 3 * s, y - 16 * s, 6 * s, 16 * s, fill=tint_g(GOLD_DK, 1.0, haze), alpha=alpha)
    c.circle(cx, y - 18 * s, 3.4 * s, fill=tint_g(GOLD, 1.1, haze), alpha=alpha)


# === 午门（城台 + 三门洞 + 城楼） ===
def draw_wumen(c, cx, gy, s, dusk, alpha=1.0):
    tw, th = 780 * s, 150 * s
    c.rect(cx - tw / 2, gy - th, tw, th, fill=tint_g((150, 40, 34), 1.0), alpha=alpha)
    # 门洞（中间大，两侧小，圆顶）
    for i, (dw, dh) in enumerate([(64, 116), (46, 92), (46, 92)]):
        dx = cx + (0 if i == 0 else (1 if i == 1 else -1)) * 92 * s
        c.rect(dx - dw / 2, gy - dh, dw, dh, fill=tint_g(DOOR, 1.0), alpha=alpha)
        c.circle(dx, gy - dh, dw / 2, fill=tint_g(DOOR, 1.0), alpha=alpha)
    # 城台琉璃檐口
    c.rect(cx - tw / 2 - 12 * s, gy - th - 12 * s, tw + 24 * s, 12 * s,
           fill=tint_g(GOLD, 1.0), alpha=alpha)
    # 城楼
    pw, ph = 310 * s, 108 * s
    py0 = gy - th - 12 * s - ph
    c.rect(cx - pw / 2, py0, pw, ph, fill=tint_g(RED, 1.0), alpha=alpha)
    for i in range(7):
        x = cx - pw / 2 + pw * (i + 0.5) / 7.0
        c.line(x, py0 + 8 * s, x, py0 + ph - 6 * s, color=tint_g(RED_DK, 1.0),
               width=4.0 * s, alpha=alpha)
    c.rect(cx - 78 * s, py0 + 14 * s, 156 * s, 30 * s, fill=tint_g(PLAQUE, 1.0), alpha=alpha)
    c.text("午门", cx, py0 + 29 * s, 21 * s, tint_g((255, 220, 140), 1.1), bold=True, alpha=alpha)
    curved_roof(c, cx, py0, 420, 210, 76, s, alpha)
    # 宫灯（黄昏点亮）
    if dusk > 0.25:
        for i in (-1, 1):
            lx = cx + i * 250 * s
            ly = gy - th * 0.62
            c.rect(lx - 9 * s, ly - 12 * s, 18 * s, 24 * s,
                   fill=tint_g(LANTERN, 1.15), alpha=alpha)
            c.glow(lx, ly, 26 * s, "#ff9a50", 0.5 * dusk)


# === 宫墙（近景两侧 + 宫灯） ===
def draw_wall_band(c, gy, s, dusk, alpha=1.0):
    wh = 96 * s
    c.rect(0, gy - wh, W, wh, fill=tint_g((150, 40, 34), 1.0), alpha=alpha)
    c.rect(0, gy - wh - 10 * s, W, 10 * s, fill=tint_g(GOLD, 1.0), alpha=alpha)
    if dusk > 0.25:
        for i in range(7):
            lx = 150 + i * 270
            c.rect(lx - 8 * s, gy - wh * 0.62 - 11 * s, 16 * s, 22 * s,
                   fill=tint_g(LANTERN, 1.15), alpha=alpha)
            c.glow(lx, gy - wh * 0.62, 24 * s, "#ff9a50", 0.45 * dusk)


# === 远境（haze 剪影） ===
def draw_far(c, cx, gy, s, sky_top, alpha=1.0):
    haze = 0.62
    draw_taihe(c, cx, gy, s * 0.62, alpha=alpha * 0.9, haze=haze)
    draw_corner_tower(c, cx - W * 0.30, gy, s * 0.62, alpha * 0.9, haze)
    draw_corner_tower(c, cx + W * 0.30, gy, s * 0.62, alpha * 0.9, haze)


def birds(c, t, alpha=1.0):
    a = clamp(t / 1.2, 0, 1) * clamp((8.6 - t) / 1.0, 0, 1) * alpha
    if a <= 0:
        return
    for i in range(4):
        bx = (0.18 + i * 0.11 + t * 0.016) * W
        by = H * (0.16 + i * 0.05) + math.sin(t * 1.3 + i * 2.2) * 12
        fl = math.sin(t * 7 + i * 1.7) * 6
        c.lines([(bx - 13, by - fl), (bx, by), (bx + 13, by - fl)],
                color=(90, 74, 66), width=2.2, alpha=0.75 * a)


def main_scene(c, t):
    global WARM
    dawn = 1.0 - ease_io((t - 0.8) / 2.0)
    dusk = ease_io((t - 5.6) / 2.0)
    WARM = max(dawn, dusk)

    rise = ease_io(t / 2.2)
    push = ease_io((t - 2.4) / 2.8)
    pull = ease_io((t - 7.3) / 2.4)
    pan = math.sin(clamp((t - 5.0) / 2.4, 0, 1) * math.pi)

    # 天空
    day_top, day_bot = (191, 227, 245), (241, 247, 234)
    dawn_top, dawn_bot = (247, 185, 138), (252, 224, 176)
    dusk_top, dusk_bot = (109, 106, 208), (255, 171, 106)
    if dawn >= dusk:
        top, bot = mix3(day_top, dawn_top, dawn), mix3(day_bot, dawn_bot, dawn)
    else:
        top, bot = mix3(day_top, dusk_top, dusk), mix3(day_bot, dusk_bot, dusk)
    mid = mix3(top, bot, 0.5)
    c.gradient(0, 0, W, H, colors=[(0, top), (0.45, mid), (1, bot)], direction="vertical")

    # 日 + 光晕
    sun_x = W * (0.78 - 0.55 * dawn + 0.0) if dawn >= dusk else W * (0.78 - 0.54 * dusk)
    sun_y = H * (0.30 + 0.06 * math.sin(t * 0.4))
    c.glow(sun_x, sun_y, 240, "#ffe2b0", 0.30 + 0.25 * WARM)
    c.circle(sun_x, sun_y, 34, fill=(255, 236, 200), alpha=0.9)

    # 云
    for i in range(3):
        clx = ((i * 0.38 + 0.1 + t * 0.008) % 1.3) * (W + 500) - 250
        cly = H * (0.14 + i * 0.07)
        cc = mix3((255, 255, 255), top, 0.25)
        for (j, (ox, oy, r)) in enumerate([(-70, 6, 46), (0, 0, 62), (66, 8, 42), (20, -14, 40)]):
            c.ellipse(clx + ox, cly + oy, r, r * 0.55, fill=cc, alpha=0.5)

    birds(c, t)

    # 层参数（视差）
    far_gy = H * 0.50 + (1 - rise) * H * 0.50 - push * H * 0.34 + pull * H * 0.30
    far_s = 0.52 + push * 0.04 - pull * 0.05
    far_dx = -pan * W * 0.014
    mid_gy = H * 0.635 + (1 - rise) * H * 0.66 - push * H * 0.07 + pull * H * 0.015
    mid_s = 0.80 + push * 0.50 - pull * 0.38
    mid_dx = -pan * W * 0.035
    near_gy = H * 0.80 + (1 - rise) * H * 0.85 + push * H * 0.24 - pull * H * 0.20
    near_s = 1.0 + push * 0.32 - pull * 0.22
    near_dx = -pan * W * 0.09

    # 远境（haze）
    draw_far(c, W / 2 + far_dx, far_gy, far_s, top)
    # 晨雾
    if dawn > 0.1:
        for i in range(2):
            my = far_gy - 30 + i * 34
            c.ellipse(W * (0.3 + 0.1 * i) + math.sin(t * 0.5 + i * 2) * 60, my, 420, 30,
                      fill=(255, 250, 242), alpha=0.22 * dawn * (1 - push))

    # 中景：太和殿群
    draw_corner_tower(c, W * 0.5 + mid_dx - W * 0.315, mid_gy, mid_s * 0.8)
    draw_corner_tower(c, W * 0.5 + mid_dx + W * 0.315, mid_gy, mid_s * 0.8)
    draw_taihe(c, W * 0.5 + mid_dx - W * 0.20, mid_gy, mid_s * 0.5, alpha=0.96, plaque=False)
    draw_taihe(c, W * 0.5 + mid_dx + W * 0.20, mid_gy, mid_s * 0.5, alpha=0.96, plaque=False)
    draw_taihe(c, W * 0.5 + mid_dx, mid_gy - 6 * mid_s, mid_s)

    # 近景：宫墙 + 午门
    draw_wall_band(c, near_gy, near_s, dusk)
    draw_wumen(c, W * 0.5 + near_dx, near_gy, near_s, dusk)


# === 配乐：D 宫五声，72 BPM ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    bar = spb * 4.0
    total_beats = duration / spb
    bars = int(math.ceil(duration / bar))

    CHORDS = ([62, 66, 69], [59, 62, 66], [55, 59, 62], [62, 66, 69])
    ROOTS = (38, 35, 43, 38)
    MEL = [
        [(0.0, 74, 2.0), (2.0, 69, 2.0)],
        [(0.0, 71, 3.0), (3.0, 69, 1.0)],
        [(0.0, 66, 2.0), (2.0, 69, 1.5), (3.5, 71, 0.5)],
        [(0.0, 74, 2.5), (2.5, 62, 1.5)],
    ]

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.8)
    pad = s.track("pad", name="pad", gain_db=-15.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="guzheng", gain_db=-11.5, pan=0.10, seed=2)
    bass = s.track("bass", name="bass", gain_db=-10.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = CHORDS[bi % len(CHORDS)]
        for m in ch:
            pad.note(b0, name(m), 4.1, 0.5)
            pad.note(b0, name(m + 12), 4.1, 0.25)
        bass.note(b0, name(ROOTS[bi % len(ROOTS)]), 2.2, 0.8)
        bass.note(b0 + 2.0, name(ROOTS[bi % len(ROOTS)] + 12), 1.8, 0.5)
        for (beat, m, ln) in MEL[bi % len(MEL)]:
            pluck.note(b0 + beat, name(m), ln * spb * 1.05, 0.55)
            if ln >= 2.0:
                pluck.note(b0 + beat + 0.5, name(m - 12), 0.8, 0.3)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.2)
    return s


film = wv.Film(W, H, duration=10.0, fps=30, ss=2, theme="midnight",
               bpm=72, name="forbidden-city")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 10, transition="cut")
s1.draw(main_scene, at=0)
s1.text("紫禁城", at=8.2, style="hero", y=170)
s1.text("THE FORBIDDEN CITY", at=8.7, style="subtitle", y=270)

film.sfx("whoosh", at=0.3, gain=-8)
film.sfx("swish", at=2.5, gain=-12)
film.sfx("swish", at=5.3, gain=-12)
film.sfx("riser", at=7.2, dur=1.1, gain=-10)
film.sfx("chime", at=8.5, gain=-9)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "forbidden-city.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "forbidden-city.sheet.png"))
