# -*- coding: utf-8 -*-
"""《一张科普海报的诞生》 — sticker 贴纸风科普（牛皮纸变体）
11 秒 / 1920x1080 / 30fps / 12fps 定格感
牛皮纸底 + 模切贴纸依次啪啪贴下（白边/影子收紧/反光扫过/squash 微震）+
马克笔箭头串步骤 + 8.4s 拉远露全板（钩子）+ 提示便签 + 爆炸星 + 红印章
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
from PIL import Image, ImageDraw, ImageFilter

import write_video as wv
from write_video import fonts as wfonts

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")

# 展示板（拉远后全貌）：16:9
BW, BH = 2900, 1630
KRAFT = (201, 169, 125)
KRAFT_DK = (172, 140, 96)


_FC = {}


def fnt(size, kind="sans_bold"):
    k = (kind, int(size))
    f = _FC.get(k)
    if f is None:
        f = wfonts.load(kind, size)
        _FC[k] = f
    return f


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mix3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0, 1))


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


# ---------------- 展示板（牛皮纸，一次烘焙） ----------------
def build_board():
    im = Image.new("RGB", (BW, BH), KRAFT)
    d = ImageDraw.Draw(im, "RGBA")
    # 纤维纹理
    for i in range(900):
        x, y = hash1(i * 3.1) * BW, hash1(i * 7.3) * BH
        ln = 8 + hash1(i * 11.7) * 26
        ang = hash1(i * 5.9) * math.pi
        a = 0.020 + 0.022 * hash1(i * 13.3)
        col = (110, 84, 52, int(a * 255))
        d.line((x, y, x + math.cos(ang) * ln, y + math.sin(ang) * ln), fill=col, width=1)
    # 色斑
    for i in range(46):
        x, y = hash1(i * 17.3) * BW, hash1(i * 19.7) * BH
        r = 20 + hash1(i * 23.1) * 70
        d.ellipse((x - r, y - r, x + r, y + r), fill=(160, 128, 88, 14))
    # 边缘压暗（暗角）
    vg = Image.new("L", (BW, BH), 0)
    dv = ImageDraw.Draw(vg)
    dv.rectangle((0, 0, BW, BH), fill=70)
    dv.rounded_rectangle((70, 70, BW - 70, BH - 70), radius=80, fill=0)
    vg = vg.filter(ImageFilter.GaussianBlur(90))
    dark = Image.new("RGB", (BW, BH), (120, 94, 62))
    im = Image.composite(dark, im, vg)
    # 顶光（左上亮）
    gl = Image.new("L", (BW, BH), 0)
    dg = ImageDraw.Draw(gl)
    for i in range(12):
        r = 1400 - i * 110
        dg.ellipse((180 - r, 60 - r, 180 + r, 60 + r), fill=int(10 + i * 1.2))
    light = Image.new("RGB", (BW, BH), (250, 228, 186))
    im = Image.composite(light, im, gl)
    return im


BOARD = build_board()

# ---------------- 贴纸工厂（模切白边） ----------------
def sticker_sprite(w, h, art_fn, radius=22, border=16):
    W_, H_ = int(w + border * 2), int(h + border * 2)
    im = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1, 1, W_ - 2, H_ - 2), radius=radius + border, fill=(251, 248, 241, 255))
    d.rounded_rectangle((1, 1, W_ - 2, H_ - 2), radius=radius + border, outline=(226, 218, 204, 255), width=2)
    art = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    da = ImageDraw.Draw(art, "RGBA")
    art_fn(da, w, h)
    im.paste(art, (border, border), art)
    return im


def title_art(d, w, h):
    d.rounded_rectangle((0, 0, w, h), radius=22, fill=(255, 209, 102, 255))
    d.rounded_rectangle((0, 0, w, h), radius=22, outline=(60, 44, 30, 255), width=5)
    d.text((w / 2, h / 2 - 6), "把想法做成一支视频", font=fnt(40), fill=(48, 34, 22, 255), anchor="mm")
    d.text((w / 2, h - 34), "四步走", font=fnt(22, "sans"), fill=(120, 84, 40, 255), anchor="mm")


STEPS = [
    ("1", "定主题", "给谁看？讲什么", (46, 156, 148), (520, 940)),
    ("2", "画分镜", "一镜一事", (232, 116, 62), (1210, 720)),
    ("3", "写脚本", "画面+声音+节拍", (74, 106, 200), (1880, 980)),
    ("4", "渲出片", "检查，交付", (196, 74, 96), (2480, 700)),
]


def step_art(idx):
    num, name_, tip, col, _pos = STEPS[idx]

    def fn(d, w, h):
        d.rounded_rectangle((0, 0, w, h), radius=20, fill=col + (255,))
        d.ellipse((26, 22, 98, 94), fill=(255, 255, 255, 235))
        d.text((62, 58), num, font=fnt(34), fill=col + (255,), anchor="mm")
        d.text((132, 58), name_, font=fnt(36), fill=(255, 255, 255, 255), anchor="lm")
        d.text((26, 128), tip, font=fnt(24, "sans"), fill=(255, 255, 255, 220), anchor="lm")
    return fn


def star_art(d, w, h):
    cx, cy = w / 2, h / 2
    pts = []
    for i in range(28):
        a = i / 28.0 * math.pi * 2
        r = (w / 2) * (1.0 if i % 2 == 0 else 0.72)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r * 0.92))
    d.polygon(pts, fill=(255, 96, 72, 255))
    d.text((cx, cy - 6), "爆了！", font=fnt(44), fill=(255, 244, 224, 255), anchor="mm")


def note_art(text, col):
    def fn(d, w, h):
        d.rectangle((0, 0, w, h), fill=col + (255,))
        d.rectangle((0, 0, w, 26), fill=(70, 56, 40, 255))
        d.text((w / 2, h / 2 + 12), text, font=fnt(26), fill=(60, 46, 30, 255), anchor="mm")
    return fn


TITLES = {
    "title": sticker_sprite(600, 190, title_art, border=18),
    "s0": sticker_sprite(370, 210, step_art(0)),
    "s1": sticker_sprite(370, 210, step_art(1)),
    "s2": sticker_sprite(370, 210, step_art(2)),
    "s3": sticker_sprite(370, 210, step_art(3)),
    "star": sticker_sprite(280, 280, star_art, radius=140, border=14),
    "n0": sticker_sprite(430, 150, note_art("先想清楚给谁看", (255, 236, 150)), radius=8, border=10),
    "n1": sticker_sprite(430, 150, note_art("画面比文字有力", (178, 226, 200)), radius=8, border=10),
    "n2": sticker_sprite(430, 150, note_art("配乐跟着节拍", (255, 190, 150)), radius=8, border=10),
}

# 部署时刻（12fps 定格量化）
SPR = [
    ("title", 520, 320, 0.25, 0.10),
    ("s0", STEPS[0][4][0], STEPS[0][4][1] - 90, 0.95, -0.14),
    ("s1", STEPS[1][4][0], STEPS[1][4][1] - 90, 2.20, 0.12),
    ("s2", STEPS[2][4][0], STEPS[2][4][1] - 90, 3.45, -0.10),
    ("s3", STEPS[3][4][0], STEPS[3][4][1] - 90, 4.70, 0.13),
    ("star", 2620, 1120, 5.75, 0.22),
    ("n0", 760, 1430, 6.95, -0.07),
    ("n1", 1460, 1460, 7.25, 0.05),
    ("n2", 2160, 1420, 7.55, -0.05),
]
ARROWS = [((700, 480), (560, 800), 1.95), ((900, 760), (1150, 760), 3.25),
          ((1400, 760), (1780, 900), 4.55), ((2080, 900), (2400, 760), 5.45)]

_cache = {}


def placed_sprite(key, rot_deg, scale):
    """旋转+缩放 sprite（桶缓存）。"""
    ck = (key, round(rot_deg * 2) / 2, round(scale * 20) / 20)
    sp = _cache.get(ck)
    if sp is None:
        sp0 = TITLES[key]
        if abs(rot_deg) > 0.01:
            sp0 = sp0.rotate(rot_deg, resample=Image.BICUBIC, expand=True)
        sc = clamp(scale, 0.3, 2.0)
        if abs(sc - 1.0) > 0.02:
            sp0 = sp0.resize((max(2, int(sp0.width * sc)), max(2, int(sp0.height * sc))), Image.LANCZOS)
        sp = sp0
        if len(_cache) > 96:
            _cache.clear()
        _cache[ck] = sp
    return sp


def draw_arrow(d, p0, p1, prog):
    """马克笔箭头：贝塞尔 + 手抖 + 箭头。"""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 90
    n = 26
    pts = []
    for i in range(int(n * prog) + 1):
        u = i / n
        x = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * mx + u * u * p1[0]
        y = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * my + u * u * p1[1]
        x += math.sin(u * 17 + p0[0]) * 2.4
        y += math.sin(u * 13 + p0[1]) * 2.4
        pts.append((x, y))
    if len(pts) < 2:
        return
    d.line(pts, fill=(64, 58, 52, 210), width=11, joint="curve")
    if prog >= 0.999:
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        a = math.atan2(by - ay, bx - ax)
        for sgn in (2.6, -2.6):
            d.line([(bx, by), (bx - math.cos(a + sgn) * 40, by - math.sin(a + sgn) * 40)],
                   fill=(64, 58, 52, 210), width=11)


# ---------------- 相机 ----------------
CAMX, CAMY, CAMZ = 960.0, 540.0, 1.0


def cam_at(t):
    """镜头巡游：跟每张贴纸，8.4s 拉远露全板。"""
    KF = [(0.25, 860, 470, 1.0), (1.5, 700, 900, 0.92), (2.8, 1300, 760, 0.94),
          (4.1, 1960, 940, 0.94), (5.4, 2500, 820, 0.92), (7.0, 1450, 1100, 0.85),
          (8.4, BW / 2, BH / 2, 0.662), (11.0, BW / 2, BH / 2, 0.662)]
    for i in range(len(KF) - 1):
        t0, x0, y0, z0 = KF[i]
        t1, x1, y1, z1 = KF[i + 1]
        if t0 <= t <= t1:
            p = ease_io((t - t0) / (t1 - t0))
            return (x0 + (x1 - x0) * p, y0 + (y1 - y0) * p,
                    math.exp(math.log(z0) + (math.log(z1) - math.log(z0)) * p))
    return (BW / 2, BH / 2, 0.662)


# ---------------- 帧 ----------------
def frame(t):
    global CAMX, CAMY, CAMZ
    # 12fps 定格量化（贴纸动画时间）
    tq = math.floor(t * 12) / 12.0
    CAMX, CAMY, CAMZ = cam_at(t)
    # 定格抖动
    jx = (hash1(math.floor(t * 12) * 3.1) - 0.5) * 1.8
    jy = (hash1(math.floor(t * 12) * 7.7) - 0.5) * 1.8

    view = BOARD.copy().convert("RGBA")
    d = ImageDraw.Draw(view, "RGBA")

    # 箭头（世界坐标，12fps 量化进度）
    for p0, p1, t0 in ARROWS:
        prog = clamp((tq - t0) / 0.5, 0, 1)
        if prog > 0:
            draw_arrow(d, p0, p1, prog)

    # 印章（钩子：6.67s 红章 / 7.0s 蓝章）
    def stamp(cx, cy, r, col, text, t0, ang=-0.12):
        tt = tq - t0
        if tt < 0:
            return
        u = clamp(tt / 0.22, 0, 1)
        sc = 1.5 - 0.5 * (u * u)
        wet = clamp((tt - 0.2) / 1.6, 0, 1)
        d.ellipse((cx - r * sc, cy - r * sc, cx + r * sc, cy + r * sc),
                  outline=col + (int(210 * u * 255 // 255),), width=9)
        d.text((cx, cy), text, font=fnt(34), fill=col + (int(215 * u * 255 // 255),), anchor="mm")
        if wet > 0.02:
            d.ellipse((cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8),
                      outline=(255, 240, 200, int(60 * wet)), width=3)

    stamp(2740, 240, 92, (200, 48, 43), "印", 6.67, -0.12)
    stamp(2560, 150, 66, (48, 88, 200), "10.25", 7.0, 0.08)

    # 贴纸（啪地贴下：scale 1.35→1、旋转收掉、影子收紧、squash 微震）
    for (key, x, y, t0, rot) in SPR:
        tt = tq - t0
        if tt < 0:
            continue
        u = clamp(tt / 0.22, 0, 1)
        sc = 1.35 - 0.35 * (u * u)
        lift = 1 - u
        rot_now = rot * (1 - u)
        sp = placed_sprite(key, math.degrees(rot_now), sc)
        # squash 微震
        st = tt - 0.22
        sq = 1 - 0.06 * math.exp(-st * 14) * math.cos(st * 34) if st > 0 else 1.0
        sp2 = sp
        if abs(sq - 1.0) > 0.01 and u >= 1:
            ck = (key, "sq", round(sq * 40) / 40)
            sp2 = _cache.get(ck)
            if sp2 is None:
                sp2 = sp.resize((sp.width, max(2, int(sp.height * sq))), Image.LANCZOS)
                _cache[ck] = sp2
        # 影子（lift 张开）
        sa = 0.20 - 0.10 * (1 - lift)
        sx, sy = x - sp2.width / 2 + (6 + lift * 34), y - sp2.height / 2 + (10 + lift * 48)
        sh = Image.new("RGBA", sp2.size, (0, 0, 0, 0))
        mask = sp2.getchannel("A").point(lambda v: int(v * sa))
        black = Image.new("RGBA", sp2.size, (60, 44, 28, 255))
        sh.paste(black, (0, 0), mask)
        view.paste(sh, (int(sx + jx), int(sy + jy)), sh)
        # 本体
        px, py = x - sp2.width / 2, y - sp2.height / 2 - lift * 40
        view.paste(sp2, (int(px + jx), int(py + jy)), sp2)
        # 反光扫过（落定后 0.9s）+ 静态光泽
        if u >= 1:
            gt = tt - 0.22
            band_p = clamp(gt / 0.9, 0, 1.3)
            if band_p < 1.0:
                ov = Image.new("RGBA", sp2.size, (0, 0, 0, 0))
                do = ImageDraw.Draw(ov)
                bx = -sp2.width * 0.4 + band_p * sp2.width * 1.8
                do.polygon([(bx - 60, 0), (bx + 60, 0), (bx - 60, sp2.height), (bx - 60 - 120, sp2.height)],
                           fill=(255, 255, 255, 80))
                mask2 = ov.getchannel("A")
                mask2 = ImageChops_min(mask2, sp2.getchannel("A"))
                view.paste(ov, (int(px + jx), int(py + jy)), mask2)
            else:
                ov = Image.new("RGBA", sp2.size, (0, 0, 0, 0))
                do = ImageDraw.Draw(ov)
                do.polygon([(sp2.width * 0.15, 0), (sp2.width * 0.38, 0),
                            (sp2.width * 0.1, sp2.height), (sp2.width * -0.13, sp2.height)],
                           fill=(255, 255, 255, 34))
                mask2 = ImageChops_min(ov.getchannel("A"), sp2.getchannel("A"))
                view.paste(ov, (int(px + jx), int(py + jy)), mask2)

    # 视口裁切：z 缩放居中 CAM
    vw, vh = W / CAMZ, H / CAMZ
    x0 = clamp(CAMX - vw / 2, 0, BW - vw)
    y0 = clamp(CAMY - vh / 2, 0, BH - vh)
    view = view.convert("RGB").crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh))) \
        .resize((W, H), Image.LANCZOS)
    return view


def ImageChops_min(a, b):
    from PIL import ImageChops
    return ImageChops.darker(a, b)


# ---------------- 配乐 ----------------
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    bars = int(math.ceil(duration / (spb * 4.0)))
    PROG = (0, 4, 5, 3)
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def arp_tones(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4, deg + 7, deg + 9)]

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.5)
    pad = s.track("pad", name="pad", gain_db=-17.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-11.5, pan=0.1, seed=2)
    bass = s.track("bass", name="bass", gain_db=-10.0, pan=0.0, seed=3)
    for bi in range(bars):
        b0 = bi * 4.0
        ch = chord_midi(PROG[bi % 4])
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.45)
        tn = arp_tones(PROG[bi % 4])
        for si, idx in enumerate((0, 2, 1, 2, 3, 2, 4, 2)):
            pluck.note(b0 + si * 0.5, name(tn[idx]), 0.5, 0.5)
        bass.note(b0, name(ch[0] - 24), 1.8, 0.75)
        bass.note(b0 + 2.0, name(ch[0] - 24), 1.8, 0.55)
    end = (duration - 2.0) / spb
    pluck.note(end, name(chord_midi(PROG[0])[0] + 12), 1.0, 0.55)
    pluck.note(end, name(chord_midi(PROG[0])[0] + 24), 1.0, 0.25)
    s.length(beats=total_beats)
    s.fade(out_seconds=1.8)
    return s


film = wv.Film(W, H, duration=11.0, fps=30, ss=1, grain=False, theme="midnight",
               bpm=120, name="sticker-poster")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(lambda c, t: c.paste_full(frame(t)), at=0, enter="none")

for key, x, y, t0, rot in SPR:
    film.sfx("pop", at=t0 + 0.02, gain=-14 if key.startswith("n") else -11)
for p0, p1, t0 in ARROWS:
    film.sfx("swish", at=t0, dur=0.45, gain=-15)
film.sfx("impact", at=5.78, gain=-8)
film.sfx("stamp" if False else "punch", at=6.7, gain=-9)
film.sfx("whoosh", at=8.4, dur=0.8, gain=-10)
film.sfx("chime", at=9.3, gain=-11)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "sticker-poster.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "sticker-poster.sheet.png"))
