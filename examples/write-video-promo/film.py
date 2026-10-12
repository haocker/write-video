# -*- coding: utf-8 -*-
"""《write-video 介绍片》v5 —— 黑黄冲击主题 / 1920x1080 / 30fps / 黑底黄强调，120 BPM。

分镜见同目录 HANDOFF.md（#编号对应下面各段）。
运行： python3 film.py        （产物在 artifacts/ 目录）
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "res")
RUNTIME = os.environ.get("WRITE_VIDEO_RUNTIME",
                         "/root/.codingmatrix/project-tpl/.ai-ready/skills/write-video/runtime")
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

import write_video as wv

W, H = 1920, 1080
BPM = 120
OUT = os.path.join(HERE, "artifacts")
LOGO = os.path.join(RES, "logo.png")

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

BEATS = {"cross": 0.55, "frame": 1.20, "brace": 2.10, "wave": 2.95, "play": 3.55}


def _polyline(pts, p):
    """按进度 p∈[0,1] 截取折线（含段内插值）。"""
    if p <= 0 or len(pts) < 2:
        return []
    if p >= 1:
        return list(pts)
    segs = []
    total = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        d = math.hypot(x2 - x1, y2 - y1)
        segs.append((d, x1, y1, x2, y2))
        total += d
    if total <= 1e-6:
        return [pts[0]]
    remain = total * p
    out = [(pts[0][0], pts[0][1])]
    for d, x1, y1, x2, y2 in segs:
        if remain <= 0:
            break
        if remain >= d:
            out.append((x2, y2))
            remain -= d
        else:
            u = remain / d
            out.append((x1 + (x2 - x1) * u, y1 + (y2 - y1) * u))
            remain = 0
    return out


def _brace_pts(cx, cy, h, w, side):
    """side=-1 为 `{`，+1 为 `}`。开口朝内、尖朝外。"""
    n = 28
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        y = cy + (t - 0.5) * h
        mid = math.exp(-((t - 0.5) / 0.07) ** 2)
        curl = 0.0
        if t < 0.18:
            u = t / 0.18
            curl = math.sin(u * math.pi) * 0.55
        elif t > 0.82:
            u = (1.0 - t) / 0.18
            curl = math.sin(u * math.pi) * 0.55
        x = cx + side * w * (0.22 + 0.78 * mid + 0.38 * curl)
        pts.append((x, y))
    return pts


def _wave_pts(x0, x1, cy, amp, n=64):
    pts = []
    span = x1 - x0
    for i in range(n + 1):
        u = i / float(n)
        y = (1.18 * math.exp(-((u - 0.28) / 0.085) ** 2)
             - 1.08 * math.exp(-((u - 0.50) / 0.075) ** 2)
             + 0.58 * math.exp(-((u - 0.72) / 0.090) ** 2))
        pts.append((x0 + span * u, cy - amp * y))
    return pts


def sign_scene(c, t):
    """招牌：电费单划掉 → 花括号 → 波形 → 播放点亮（适配黑黄主题）。"""
    if t < -20:
        return
    cx, cy = c.width / 2.0, c.height * 0.50
    local = t  # sign_scene 的 t 是场景本地秒（场景5 20.5-25.5 → local 0-5s）

    # 0) 电费单亮相并整页划掉（黄线划）
    age = local - BEATS["cross"]
    if age >= 0:
        w_, h_ = 580, 300
        x, y = cx - w_ / 2.0, cy - 20 - h_ / 2.0
        fade = min(1.0, age / 0.4)
        c.rect(x - 10, y - 26, w_ + 20, h_ + 40, fill="panel", radius=22, alpha=0.9 * fade)
        c.text("电费单", cx, y - 16, 26, "dim", alpha=0.75 * fade)
        lines = ["生成视频 x 1      -¥ 6.0", "修改一版 x 1      -¥ 6.0", "修改两版 x 1      -¥ 12.0"]
        for i, ln in enumerate(lines):
            c.text(ln, x + 28, y + 28 + i * 52, 30, "fg", alpha=fade)
        # 黄线划掉
        swirl = c.progress(BEATS["cross"] + 0.18, BEATS["cross"] + 0.85, "easeInOutCubic")
        if swirl > 0:
            c.line(x - 10, y + h_, x + w_ + 10, y - 10, "emph", 10, alpha=0.95 * swirl)
            c.glow(cx, cy + 40, 240 * swirl, "emph", 0.20 * swirl)
        if age > 1.1:
            bb = c.progress(BEATS["frame"], BEATS["frame"] + 0.8, "easeOutCubic")
            if bb > 0:
                for xx, yy in ((x - 20, y - 20), (x + w_ + 20, y - 20)):
                    c.glow(xx, yy, 90 * bb, "emph", 0.22 * bb)

    # 1) 框架描出
    pf = c.progress(BEATS["frame"], BEATS["frame"] + 1.05, "easeInOutCubic")
    if pf > 0:
        fw, fh = 980, 520
        x, y = cx - fw / 2.0, cy - 20 - fh / 2.0
        r = 48
        frame = [
            (x + r, y), (x + fw - r, y),
            (x + fw, y + r), (x + fw, y + fh - r),
            (x + fw - r, y + fh), (x + r, y + fh),
            (x, y + fh - r), (x, y + r), (x + r, y),
        ]
        drawn = _polyline(frame, pf)
        if len(drawn) >= 2:
            c.lines(drawn, color="soft", width=7, alpha=0.22 * pf)
            c.lines(drawn, color="fg", width=3.2, alpha=0.55 * pf)

    # 2) 花括号（黄边）
    pb = c.progress(BEATS["brace"], BEATS["brace"] + 1.05, "easeInOutCubic")
    if pb > 0:
        left = _brace_pts(cx - 310, cy - 20, 340, 78, -1)
        right = _brace_pts(cx - 170, cy - 20, 340, 78, 1)
        for pts in (left, right):
            drawn = _polyline(pts, pb)
            if len(drawn) >= 2:
                c.lines(drawn, color="fg", width=16, alpha=0.18 * pb)
                c.lines(drawn, color="emph", width=7, alpha=0.95 * pb)  # punch 主题用 accent=emph=黄色
        if pb > 0.92:
            tip = left[len(left) // 2]
            c.glow(tip[0], tip[1], 36, "emph", 0.18)

    # 3) 波形生长（黄色）
    pw = c.progress(BEATS["wave"], BEATS["wave"] + 1.45, "easeOutCubic")
    if pw > 0:
        wave = _wave_pts(cx - 70, cx + 390, cy - 20, 150)
        drawn = _polyline(wave, pw)
        if len(drawn) >= 2:
            c.lines(drawn, color="emph", width=22, alpha=0.16 * pw)
            c.lines(drawn, color="emph", width=8, alpha=0.95 * pw)
            hx, hy = drawn[-1]
            c.glow(hx, hy, 42, "emph", 0.28 * pw)
            c.circle(hx, hy, 6, fill="fg", alpha=0.9 * pw)

    # 4) 播放点亮（黄色 glow）
    age = local - BEATS["play"]
    if age >= 0:
        sc = c.spring(age, 5.2, 2.1)
        if sc > 0.02:
            px, py = cx + 360, cy + 168
            s = 34 * sc
            tri = [(px - s * 0.55, py - s), (px - s * 0.55, py + s), (px + s, py)]
            c.glow(px, py, 90 * sc, "emph", 0.22 * min(1.0, age / 0.35))
            c.polygon(tri, fill=None, outline="fg", width=6, alpha=min(1.0, sc))
            c.polygon(tri, fill="fg", alpha=0.12 * min(1.0, sc))


def make_bg():
    """预渲染静态背景（渐变 + 网格 + 暗角），缓存为 PIL Image 供逐帧复用。"""
    from PIL import Image as _PIL
    from write_video.canvas import Canvas as _Canvas
    _img = _PIL.new("RGBA", (W, H), (0, 0, 0, 255))
    _c = _Canvas(_img, ss=1, width=W, height=H)
    _c.gradient(colors=[(0, "accent"), (0.4, "bg"), (0.75, (3, 2, 6)), (1, (0, 0, 0))],
                direction="radial", alpha=0.35)
    _c.grid(spacing=100, color="fg", alpha=0.03)
    _c.vignette(radius=0.55, power=1.6, alpha=0.45)
    return _img


_BG_CACHE = None


def dust(c, t):
    """全片层：静态背景 + 微粒漂动。"""
    global _BG_CACHE
    if _BG_CACHE is None:
        _BG_CACHE = make_bg()
    bg = _BG_CACHE
    c.img.paste(bg, (0, 0), bg) if bg.mode == "RGBA" else c.img.paste(bg, (0, 0))
    # 极淡的微粒漂动
    W_, H_ = c.width, c.height
    for i in range(40):
        x = (c.rand(i + 900) * W_ + t * (7 + c.rand(i + 950) * 10)) % W_
        y = (c.rand(i + 980) * H_ + math.sin(t * 0.4 + c.rand(i + 990) * 6.28) * 28) % H_
        a = 0.06 + 0.06 * math.sin(t * 1.2 + c.rand(i + 960) * 6.28)
        c.circle(x, y, 1.6 + c.rand(i + 970) * 1.4, fill="soft", alpha=max(0.0, a))


def make_score(duration, bpm):
    """punch 主题 tech 律动：I–V–vi–IV，pad + pluck + bass，120 BPM 强化节奏冲击。"""
    wa = wv.wa
    spb = 60.0 / bpm
    bar = spb * 4.0
    total_beats = duration / spb
    bars = int(math.ceil((duration - 2.0) / bar))

    PROG = (0, 4, 5, 3)  # I–V–vi–IV
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def name(m):
        return NOTE_NAMES[int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.5)
    pad = s.track("pad", name="pad", gain_db=-18.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-12.0, pan=0.15, seed=2)
    bass = s.track("bass", name="bass", gain_db=-11.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = chord_midi(PROG[bi % 4])
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.5)
        # pluck.grid 可能参数不兼容，改用 note 逐音符
        pluck.note(b0 + 0.0, name(ch[0]), 0.55, 0.5)
        pluck.note(b0 + 0.5, name(ch[1]), 0.55, 0.5)
        pluck.note(b0 + 1.0, name(ch[2]), 0.55, 0.5)
        pluck.note(b0 + 1.5, name(ch[1]), 0.55, 0.5)
        pluck.note(b0 + 2.0, name(ch[0]), 0.55, 0.5)
        pluck.note(b0 + 2.5, name(ch[1]), 0.55, 0.5)
        pluck.note(b0 + 3.0, name(ch[2]), 0.55, 0.5)
        pluck.note(b0 + 3.5, name(ch[1]), 0.55, 0.5)
        bass.note(b0, name(ch[0] - 24), 1.9, 0.75)
        bass.note(b0 + 2.0, name(ch[0] - 24), 1.6, 0.65)

    end = (duration - 2.0) / spb
    for m in (48, 60, 64, 67, 72):
        pad.note(end, name(m), (2.0 + 0.6) / spb, 0.7)
    s.length(beats=total_beats)
    s.fade(out_seconds=1.8)
    return s


VOICES = {
    "v01_cost": "用过AI生成视频的都懂，贵，真贵。",
    "v02_deduct": "跑一次，扣一笔。改一版，再扣一笔。改几遍，钱就没了。",
    "v03_turn": "现在有个东西，叫write-video，完全是另一条路。",
    "v04_code": "它不让AI去猜视频，而是让AI帮你把视频用代码写出来，在你自己的电脑上跑。",
    "v05_elec": "跑一次，花的是电，不是钱。想改就改，想试就试，改到满意为止。",
    "v06_diy": "动画自己画，音乐自己写，配音自动处理好，出片前，还自己检查一遍。",
    "v07_nocharge": "有电脑就行，不卡配置，不用充值。",
    "v08_save": "贵的那一步，它帮你省了。",
}


def V(name, rate=None):
    path = os.path.join(RES, name + ".mp3")
    kw = {"voice": "晓晓"}
    if rate:
        kw["rate"] = rate
    return wv.voice.tts(VOICES[name], path, **kw)


film = wv.Film(W, H, duration=38.0, fps=30, ss=2, theme="punch",
               bpm=BPM, name="write-video-demo")
film.music = make_score(film.duration, film.bpm)
film.draw(dust, at=0)

# #1 0–4.2 痛点钩子：贵
s1 = film.scene(0, 4.2, transition="cut")
s1.text("贵", at=0.6, style="hero", enter="slam", color="emph")
s1.text("用过AI生成视频的都懂", at=1.7, style="subtitle", enter="rise", split="char")
v1 = s1.audio(V("v01_cost"), at=0.35)
film.sfx("riser", at=0.25, dur=0.5, gain=-7)
film.sfx("impact", at=0.6, gain=-9)

# #2 4.2–9.5 连环扣款快剪
s2 = film.scene(4.2, 9.5, transition="cut")
s2.text("跑一次，扣一笔", at=5.1, style="hero", enter="punch", color="soft")
s2.text("改一版，再扣一笔", at=6.7, style="hero", enter="punch", color="soft")
s2.text("改几遍，钱就没了", at=8.3, style="hero", enter="slam", color="emph")
v2 = s2.audio(V("v02_deduct"), at=4.5)
for tt in (5.1, 6.7, 8.3):
    film.sfx("impact", at=tt, gain=-8)
film.sfx("riser", at=8.0, dur=0.5, gain=-7)

# #3 9.5–14.0 转折宣告
s3 = film.scene(9.5, 14.0, transition="wipe")
s3.image(LOGO, at=10.1, width=140, radius=20, pos="top", bg=False)
s3.text("write-video", at=11.2, style="hero", enter="slam", color="emph")
s3.text("完全是另一条路", at=12.3, style="subtitle", enter="rise", split="char")
v3 = s3.audio(V("v03_turn"), at=9.8)
film.sfx("riser", at=9.6, dur=0.4, gain=-7)
film.sfx("impact", at=11.2, gain=-6)

# #4 14.0–20.5 代码写出来（在电脑上跑）
s4 = film.scene(14.0, 20.5, transition="fade")
s4.text("不让 AI 猜视频", at=14.6, style="title", color="soft")
s4.text("让 AI 帮你，用代码写出来", at=15.5, style="subtitle", enter="rise")
s4.text("film = wv.Film(1920, 1080, duration=30)", at=16.6, size=38, font="mono",
        color="emph", enter="type")
s4.text("film.render()                 # 在你电脑上跑", at=18.1, size=38,
        font="mono", color="emph", enter="type")
v4 = s4.audio(V("v04_code"), at=14.5)

# #5 20.5–25.5 【招牌】电费单划掉 → 括号→波形→播放（适配黑黄主题）
s5 = film.scene(20.5, 25.5, transition="wipe")
s5.draw(sign_scene, at=20.5)
v5 = s5.audio(V("v05_elec"), at=20.8)
s5.text("跑一次，花的是电，不是钱", at=21.9, style="title", pos="bottom")
film.sfx("whoosh", at=20.5, dur=0.55, gain=-7)
film.sfx("whoosh", at=20.5 + BEATS["brace"], gain=-8)
film.sfx("whoosh", at=20.5 + BEATS["wave"], gain=-9)
film.sfx("chime", at=20.5 + BEATS["play"], gain=-7)
film.sfx("pop", at=20.5 + BEATS["play"] + 0.08, gain=-9)

# #6 25.5–31.0 卖点清单
s6 = film.scene(25.5, 31.0, transition="fade")
s6.list(["动画自己画", "音乐自己写", "配音自动处理好", "出片前自己检查"], at=26.2,
        icon="check", stagger=0.55, size=48, gap=20)
v6 = s6.audio(V("v06_diy"), at=25.8)

# #7 31.0–35.2 门槛快剪
s7 = film.scene(31.0, 35.2, transition="cut")
s7.text("有电脑就行", at=31.8, style="hero", enter="punch", color="soft")
s7.text("不卡配置", at=32.8, style="hero", enter="punch", color="soft")
s7.text("不用充值", at=34.2, style="hero", enter="slam", color="emph")
v7 = s7.audio(V("v07_nocharge"), at=31.5)
for tt in (31.8, 32.8, 34.2):
    film.sfx("impact", at=tt, gain=-8)
film.sfx("riser", at=33.8, dur=0.5, gain=-7)

# #8 35.2–38.0 金句 + 落版
s8 = film.scene(35.2, 38.0, transition="fade")
lg = s8.image(LOGO, at=35.8, width=240, radius=28, pos="center",
              bg=False, border=False, shadow=True)
s8.burst("sparkle", on=lg, radius=120)
s8.text("贵的那一步，它帮你省了", at=36.4, style="hero", enter="slam", color="emph")
s8.text("github.com/haocker/write-video", at=37.1, style="caption", enter="rise", split="char")
v8 = s8.audio(V("v08_save"), at=35.5)
film.sfx("riser", at=35.2, dur=0.6, gain=-7)
film.sfx("impact", at=36.4, gain=-4)


if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    check = os.path.join(HERE, "check")
    if not os.path.isdir(check):
        os.makedirs(check)
    # 关键帧适配 120 BPM 快剪，调整时间点
    for t in (1.5, 5.5, 8.5, 12.5, 18.0, 22.5, 25.0, 28.0, 32.5, 36.5):
        film.frame(t, os.path.join(check, "fv5_%.1f.png" % t))
        print("frame", t)
    rep = film.render(os.path.join(OUT, "write-video-demo-v5.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "write-video-demo-v5.sheet.png"))