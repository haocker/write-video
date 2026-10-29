# -*- coding: utf-8 -*-
"""glass · 弥散渐变 玻璃拟态 · 极光壁纸做锁屏，玻璃卡片从药丸里长出来，玻璃珠掠过巨钟放大时间
（部分移植：WebGL SDF 折射换成 PIL blur 毛玻璃近似——壁纸画到离屏 → 高斯模糊 →
玻璃卡片区域从模糊图裁出贴回 + 白 5% 叠加 + 奶白描边 + sheen + 下缘内阴影 + 投影；
玻璃珠 = 珠位置的清晰壁纸放大 1.9x 圆形裁贴。）
11 秒 / 1920x1080 / 30fps
运行: PYTHONPATH=<write-video runtime> python3 film.py

底层壁纸：#070726→#140a3c→#22072e 径向渐变 + 5 团 aurora 光斑（glow，漂移 sin(t*0.35)）
+ 3 条横向极光带（多层半透明椭圆 blur 近似）+ 80px 细网格 + 70 颗星 + 430px 巨钟（21:38 确定性）。
编排：药丸 spring 落下(0.3) → 1.5s 胀成音乐卡（渐变图标 + 26 条均衡器 sin(t*5) + 播放键 2.5s）
→ 4.2s 玻璃珠从卡后拉出掠过时钟（r 46→135，时钟数字在珠里放大 1.9x）→ 7.0s 归位
→ 7.2s 音量条长出（珠化作滑块旋钮）。钩子 4.2-7.2s 玻璃珠掠钟。
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

W, H = 1920, 1080
SS = 2
OUT = os.path.join(HERE, "artifacts")

T_PILL = 0.3      # 药丸 spring 落下
T_EXPAND = 1.5    # 胀成音乐卡
T_PLAY = 2.5      # 播放键落下
T_BEAD = 4.2      # 玻璃珠拉出（钩子开始）
T_BACK = 6.6      # 珠开始归位
T_HOME = 7.2      # 珠归位 / 音量条长出
CARD = (960.0, 690.0, 800.0, 180.0)   # 音乐卡 cx cy w h
VCARD = (960.0, 880.0, 560.0, 100.0)  # 音量卡
CLOCK = (960.0, 350.0)


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0.0, 1.0))


def out_cubic(u):
    u = clamp(u, 0.0, 1.0)
    return 1.0 - (1.0 - u) ** 3


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def spring(t, damping=6.0, freq=2.2):
    if t < 0:
        return 0.0
    return 1.0 - math.exp(-damping * t) * math.cos(2 * math.pi * freq * t)


# === 底层壁纸（画进离屏，供贴屏 + 毛玻璃 + 放大珠共用） ===
STARS = [(hash1(i * 3.3) * W, hash1(i * 7.1) * H * 0.82,
          1.1 + hash1(i * 11.3) * 1.7, hash1(i * 5.9) * 6.28) for i in range(70)]

BLOBS = [(480, 260, 470, "#2b1e66", 0.55, 0.0),
         (1450, 210, 420, "#123a6e", 0.50, 1.7),
         (1620, 700, 500, "#43165e", 0.50, 3.1),
         (330, 760, 430, "#0e4f4a", 0.42, 4.4),
         (960, 520, 380, "#262a7e", 0.38, 5.3)]

BANDS = [(300.0, "#2fd4c0", 0.9), (620.0, "#7a5cff", 2.1), (170.0, "#ff5da2", 3.7)]


def wallpaper(cv, t):
    cv.gradient(0, 0, W, H, colors=[(0, "#070726"), (0.55, "#140a3c"), (1, "#22072e")],
                direction="radial")
    for (bx, by, r, col, amp, ph) in BLOBS:
        x = bx + math.sin(t * 0.35 + ph) * 90
        y = by + math.cos(t * 0.28 + ph * 1.3) * 60
        cv.glow(x, y, r, col, amp)
    for (by0, col, ph) in BANDS:
        y0 = by0 + math.sin(t * 0.22 + ph) * 34
        for k in range(4):
            cv.ellipse(W * 0.5 + math.sin(t * 0.4 + ph + k * 0.8) * 60,
                       y0 + k * 26 - 40, 860 - k * 60, 62 - k * 8, fill=col,
                       alpha=0.075 - k * 0.012)
    cv.grid(spacing=80, color="#8fa0ff", alpha=0.05, width=1.0)
    for i, (x, y, r, ph) in enumerate(STARS):
        a = 0.30 + 0.38 * (0.5 + 0.5 * math.sin(t * 1.8 + ph))
        cv.circle(x, y, r, fill="#dfe8ff", alpha=a)
        if i % 9 == 0:
            cv.line(x - r * 4, y, x + r * 4, y, color="#dfe8ff", width=1.0, alpha=a * 0.5)
            cv.line(x, y - r * 4, x, y + r * 4, color="#dfe8ff", width=1.0, alpha=a * 0.5)
    cv.text("21:38", CLOCK[0], CLOCK[1], 430, "#e3e9ff", bold=True, alpha=0.93)
    cv.text("10·25 星期日", CLOCK[0], CLOCK[1] + 268, 42, "#aab4e8", alpha=0.6)
    cv.text("G L A S S   M O R P H I S M", CLOCK[0], 64, 26, "#8b96c8", alpha=0.75)


def build_wallpaper(t):
    im = Image.new("RGB", (W * SS, H * SS))
    cv = wv.canvas.Canvas(im, ss=SS, width=W, height=H)
    wallpaper(cv, t)
    cv.flush()
    return im


# === 毛玻璃卡片（模糊裁贴 + 白叠 + 描边 + sheen + 内阴影 + 投影） ===
def rounded_mask(w, h, radius):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=max(1, int(radius)), fill=255)
    return m


def frost_card(c, blur_img, x, y, w, h, radius, depth=1.0):
    """depth: 卡生长进度 0~1（h 按此缩放）。"""
    hh = h * depth
    yy = y + (h - hh) / 2.0
    if hh < 6:
        return yy
    x0, y0 = int(x * SS), int(yy * SS)
    w2, h2 = int(w * SS), int(hh * SS)
    # 投影（先画，两叠近似软影）
    c.rect(x + 6, yy + 18, w, hh, fill=(4, 6, 18), radius=radius, alpha=0.30)
    c.rect(x + 2, yy + 10, w, hh, fill=(4, 6, 18), radius=radius, alpha=0.22)
    # 毛玻璃：从模糊小图裁出放大贴回
    bx0, by0 = int(clamp(x, 0, W - 1)), int(clamp(yy, 0, H - 1))
    bx1, by1 = int(clamp(x + w, 1, W)), int(clamp(yy + hh, 1, H))
    crop = blur_img.crop((bx0, by0, bx1, by1)).resize((w2, h2), Image.LANCZOS)
    mask = rounded_mask(w2, h2, radius * SS)
    c.img.paste(crop, (x0, y0), mask)
    # 白色叠层（整体增亮 + 上半更强）：必须把目标 alpha 烘进贴图自身再贴
    tint = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
    td = ImageDraw.Draw(tint)
    td.rounded_rectangle([0, 0, w2 - 1, h2 - 1], radius=max(1, int(radius * SS)),
                         fill=(255, 252, 248, 22))
    td.rounded_rectangle([0, 0, w2 - 1, int(h2 * 0.5)], radius=max(1, int(radius * SS)),
                         fill=(255, 255, 255, 34))
    c.img.paste(tint, (x0, y0), tint)
    # 奶白描边
    c.rect(x, yy, w, hh, outline=(255, 244, 235), width=2.2, radius=radius, alpha=0.5)
    # sheen 上缘亮线 + 下缘内阴影
    c.rect(x + 12, yy + 5, w - 24, max(4, hh - 10), outline=(255, 255, 255), width=1.3,
           radius=max(2, radius - 10), alpha=0.3)
    c.line(x + 34, yy + hh - 7, x + w - 34, yy + hh - 7, color=(8, 10, 26), width=5, alpha=0.26)
    return yy


# === 玻璃珠（清晰壁纸放大 1.9x 圆形裁贴） ===
def bead_state(t):
    """返回 None 或 (x, y, r)。钩子 4.2-7.2s。"""
    if t < T_BEAD or t > T_HOME + 0.05:
        return None
    if t < T_BEAD + 0.9:                       # 从卡后升起（ease_io 起步缓）
        u = ease_io((t - T_BEAD) / 0.9)
        y = 660.0 + (448.0 - 660.0) * u
        r = 46.0 + (138.0 - 46.0) * u
        return (960.0, y, r)
    if t < T_BACK:                             # 掠过钟面数字缓慢漂移
        u = (t - T_BEAD - 0.9) / (T_BACK - T_BEAD - 0.9)
        x = 960.0 + 190.0 * u + math.sin(u * math.pi) * 22.0
        y = 448.0 - 24.0 * math.sin(u * math.pi)
        r = 138.0
        return (x, y, r)
    u = ease_io((t - T_BACK) / (T_HOME - T_BACK))   # 归位沉入卡后
    x = 1150.0 + (960.0 - 1150.0) * u
    y = 448.0 + (660.0 - 448.0) * u
    r = 138.0 + (46.0 - 138.0) * u
    return (x, y, r)


def draw_bead(c, off_img, t):
    st = bead_state(t)
    if st is None:
        return
    bx, by, r = st
    M = 2.2
    half = r / M
    cx0, cy0 = int((bx - half) * SS), int((by - half) * SS)
    cx1, cy1 = int((bx + half) * SS), int((by + half) * SS)
    crop = off_img.crop((cx0, cy0, cx1, cy1)).resize((int(r * 2 * SS), int(r * 2 * SS)),
                                                     Image.LANCZOS)
    mask = rounded_mask(crop.width, crop.height, crop.width // 2)
    # 珠内提亮（玻璃折光感）
    tint = Image.new("RGBA", crop.size, (255, 255, 255, 0))
    ImageDraw.Draw(tint).ellipse([0, 0, crop.width - 1, crop.height - 1],
                                 fill=(255, 255, 255, 16))
    crop = crop.convert("RGBA")
    crop.alpha_composite(tint)
    crop = crop.convert("RGB")
    # 外圈柔光 + 珠体
    c.glow(bx, by, r * 1.35, "#9fb4ff", 0.22)
    c.img.paste(crop, (int(bx * SS - crop.width / 2), int(by * SS - crop.height / 2)), mask)
    # 玻璃质感：奶白描边 + 内亮环 + 上缘高光点
    c.circle(bx, by, r, outline=(255, 244, 235), width=2.8, alpha=0.55)
    c.circle(bx, by, r * 0.84, outline=(255, 255, 255), width=1.5, alpha=0.25)
    c.circle(bx - r * 0.38, by - r * 0.42, r * 0.13, fill=(255, 255, 255), alpha=0.55)
    c.circle(bx - r * 0.30, by - r * 0.34, r * 0.05, fill=(255, 255, 255), alpha=0.95)


# === 音量条滑块旋钮（珠归位后化成） ===
def draw_volume(c, blur_img, t, off_img):
    u = out_cubic((t - T_HOME - 0.1) / 0.6)
    if u <= 0:
        return
    cx, cy, w, h = VCARD
    yy = frost_card(c, blur_img, cx - w / 2, cy - h / 2, w, h, 34, depth=u)
    if u > 0.65:
        ua = (u - 0.65) / 0.35
        fill_u = out_cubic((t - T_HOME - 0.4) / 0.7)
        # 喇叭图标
        ix, iy = cx - w / 2 + 56, cy
        ta = clamp(ua * 2, 0, 1)
        c.polygon([(ix - 12, iy - 8), (ix - 2, iy - 8), (ix + 10, iy - 18), (ix + 10, iy + 18),
                   (ix - 2, iy + 8), (ix - 12, iy + 8)], fill="#dfe6ff", alpha=0.9 * ta)
        c.arc(ix + 14, iy, 12, -55, 55, color="#dfe6ff", width=3, alpha=0.9 * ta)
        c.arc(ix + 14, iy, 20, -55, 55, color="#dfe6ff", width=3, alpha=0.6 * ta)
        # 轨道 + 填充
        tx0, tx1 = cx - w / 2 + 118, cx + w / 2 - 46
        ty = cy
        c.rect(tx0, ty - 5, tx1 - tx0, 10, fill=(255, 255, 255), radius=5, alpha=0.22 * ta)
        fw = (tx1 - tx0) * 0.72 * fill_u
        if fw > 4:
            c.rect(tx0, ty - 5, fw, 10, fill="#8fb4ff", radius=5, alpha=0.85 * ta)
        # 旋钮（珠的化身）
        if fill_u > 0.02:
            kx = tx0 + fw
            c.glow(kx, ty, 30, "#9fb4ff", 0.3 * ta)
            c.circle(kx, ty, 24, fill=(235, 240, 255), alpha=0.9 * ta)
            c.circle(kx, ty, 24, outline=(255, 255, 255), width=2.4, alpha=0.7 * ta)
            c.circle(kx - 7, ty - 8, 6, fill=(255, 255, 255), alpha=0.8 * ta)


# === 音乐卡内容 ===
_ICON_CACHE = {}


def rounded_gradient(c, x, y, w, h, radius, colors):
    key = ("rg", w, h, radius, tuple(map(tuple, colors)))
    if key not in _ICON_CACHE:
        im = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
        cv = wv.canvas.Canvas(im, ss=SS, width=w, height=h)
        cv.gradient(0, 0, w, h, colors=colors, direction="vertical")
        cv.flush()
        _ICON_CACHE[key] = (im, rounded_mask(im.width, im.height, radius * SS))
    im, mask = _ICON_CACHE[key]
    c.img.paste(im, (int(x * SS), int(y * SS)), mask)


def draw_music_card(c, blur_img, t):
    u = out_cubic((t - T_EXPAND) / 0.7)
    if u <= 0:
        return
    cx, cy, w, h = CARD
    cw = 170.0 + (w - 170.0) * u
    ch = 50.0 + (h - 50.0) * u
    frost_card(c, blur_img, cx - cw / 2, cy - ch / 2, cw, ch, 34)
    if u < 0.72:
        return
    ua = (u - 0.72) / 0.28
    x0, y0 = cx - w / 2, cy - h / 2
    # 渐变图标
    rounded_gradient(c, x0 + 34, y0 + 50, 92, 92, 22,
                     [(0, "#ff6fb5"), (0.5, "#ffb347"), (1, "#6a5cff")])
    c.text("AURORA FM", x0 + 34, y0 + 26, 26, "#e8edff", bold=True, align="left",
           alpha=0.85 * ua)
    # 26 条均衡器
    bx0, bx1 = x0 + 170, x0 + 580
    base = y0 + h - 30
    for i in range(26):
        bxx = bx0 + i * (bx1 - bx0) / 25.0
        bh = 16 + 52 * (0.5 + 0.5 * math.sin(t * 5.0 + i * 0.55)) * (0.55 + 0.45 * ua)
        c.rect(bxx - 4, base - bh, 8, bh, fill="#ff8ac2", radius=3, alpha=0.9 * ua)
    # 播放键（2.5s 落下）
    sp = spring(t - T_PLAY, 7.0, 2.4)
    if sp > 0.01:
        px_, py_ = x0 + w - 96, y0 + h / 2 + (1 - sp) * -90
        c.glow(px_, py_, 70, "#ffffff", 0.16 * clamp(sp, 0, 1.2))
        c.circle(px_, py_, 52, fill=(255, 255, 255), alpha=0.94)
        c.polygon([(px_ - 14, py_ - 20), (px_ - 14, py_ + 20), (px_ + 22, py_)],
                  fill=(24, 26, 46), alpha=0.95)
        c.circle(px_, py_, 52, outline=(255, 255, 255), width=1.6, alpha=0.4)


# === 主场景 ===
def main_scene(c, t):
    off = build_wallpaper(t)
    c.paste_full(off)
    small = off.resize((W, H), Image.BILINEAR)
    blur = small.filter(ImageFilter.GaussianBlur(9))
    # 玻璃珠画在卡片下层：从卡后"拉出"的错觉
    draw_bead(c, off, t)
    c.flush()          # 珠的 skia 描边先落地，保证被后续卡片盖住（卡后拉出）
    draw_music_card(c, blur, t)
    draw_volume(c, blur, t, off)
    # 顶部药丸（灵动岛）
    sp = spring(t - T_PILL, 8.0, 2.1)
    if sp > 0.01:
        py_ = 118 + (1 - sp) * -170
        c.rect(960 - 85, py_ - 25, 170, 50, fill=(4, 4, 12), radius=25, alpha=0.96)
        c.rect(960 - 73, py_ - 19, 146, 12, outline=(150, 160, 210), width=1.0,
               radius=6, alpha=0.18)
        c.circle(960 + 52, py_, 7, fill=(28, 30, 44))


# === 配乐：A 小调氛围 76 BPM（pad 长音 + bell 稀疏 + 软 bass） ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    bars = max(1, int(math.ceil((duration - 1.5) / (spb * 4.0))))

    CHORDS = ([57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62])
    ROOTS = (33, 29, 24, 31)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] \
            + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=1.0)
    pad = s.track("pad", name="pad", gain_db=-15.0, pan=0.0, seed=1)
    bell = s.track("bell", name="bell", gain_db=-14.0, pan=0.15, seed=2)
    bass = s.track("bass", name="bass", gain_db=-11.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = CHORDS[bi % len(CHORDS)]
        if bi < 2:
            # 最后 2 小节 pad 不写新音（留给单音收的泛音空间）
            for m in ch:
                pad.note(b0, name(m), 4.1, 0.5)
                pad.note(b0, name(m + 12), 4.1, 0.22)
        if bi < 3:
            bass.note(b0, name(ROOTS[bi % len(ROOTS)]), 3.6, 0.55)
            ARP = (0, 4, 2, 5, 3, 4, 2, 5)
            pool = ch + [ch[0] + 12, ch[1] + 12, ch[2] + 12]
            for si, idx in enumerate(ARP):
                vel = 0.36 if si % 2 == 0 else 0.25
                bell.note(b0 + si * 0.5, name(pool[idx]), 0.55, vel)
    end_b = bars * 4.0
    # chime 式单音收：主音 + 高两个八度长泛音
    bell.note(end_b - 3.5, name(69), 2.5, 0.5)
    bell.note(end_b - 3.5, name(93), 2.5, 0.3)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.5)
    return s


# === 影片 ===
film = wv.Film(W, H, duration=11.0, fps=30, ss=2, theme="midnight",
               bpm=76, name="glass-aurora")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("弥散渐变 · 玻璃拟态", at=8.9, style="hero", y=1000)

film.sfx("whoosh", at=T_PILL, gain=-10)
film.sfx("swish", at=T_EXPAND, gain=-11)
film.sfx("pop", at=T_PLAY, gain=-11)
film.sfx("whoosh", at=4.35, gain=-9)
film.sfx("swipe", at=T_BACK + 0.1, gain=-12)
film.sfx("swish", at=T_HOME + 0.15, gain=-12)
film.sfx("chime", at=8.4, gain=-10)

# 玻璃珠掠钟：珠内放大内容随位移跳动，属有意折射效果——闪烁检测排除
film.flicker_exclude(4.2, 5.2)
film.flicker_exclude(6.5, 7.0)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "glass-aurora.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "glass-aurora.sheet.png"))
