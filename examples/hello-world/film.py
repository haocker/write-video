# -*- coding: utf-8 -*-
"""《Hello, World!》 — write-video 示例片。

20 秒 / 1920x1080 / 30fps。题材：程序员的第一句话。
运行：  python film.py        （首次运行会自动探测编码器；产物在 artifacts/ 目录）

演示了：打字代码卡（方框自绘）、hero slam、逐字浮现、清单、计数器、
招牌星海自绘（全屏 draw）、全片层光尘、fade/wipe 转场、配乐与音效对齐。
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           os.path.abspath(os.path.join(HERE, "..", "..", "runtime")),
           os.path.abspath(os.path.join(HERE, "..", "runtime"))):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import write_video as wv

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")

CODE = 'print("Hello, World!")'


# ---------------------------------------------------------------- 自绘 ①：终端代码卡
def code_card(c, t):
    """S1：三个圆点 + 逐字打出的代码 + 闪烁光标。"""
    w, h = c.width, c.height
    c.rect(0, 0, w, h, fill="panel", radius=22)
    c.rect(0, 0, w, h, outline="line", width=2, radius=22)
    for i, col in enumerate(("emph", "accent", "dim")):
        c.circle(46 + i * 36, 44, 9, fill=col, alpha=0.9)
    n = int(len(CODE) * min(1.0, max(0.0, (t - 0.35) / 1.15)))
    txt = CODE[:n]
    size = 44
    c.text(txt, 46, 112, size, "fg", font="mono", align="left", valign="top")
    if (n < len(CODE) or t < 2.1) and (t * 2.0) % 1.0 < 0.55:
        x = 46 + c.text_width(txt, size, font="mono") + 7
        c.rect(x, 112, 3, size * 1.15, fill="accent", alpha=0.9)


# ---------------------------------------------------------------- 自绘 ②：招牌星海
def starfield(c, t):
    """S4：每一行代码都化作一颗星——240 颗星依次点亮、漂移、连线。"""
    if t < 0:
        return
    N = 240
    W_, H_ = c.width, c.height

    def star_pt(i):
        rx = c.rand(i * 3 + 11) * 0.86 + 0.07
        ry = c.rand(i * 3 + 12) * 0.70 + 0.15
        return (W_ * rx + c.wiggle(t * 0.22, 0.4, 13, i),
                H_ * ry + c.wiggle(t * 0.22, 0.36, 9, i + 501))

    # 星间连线（生长动画）
    for k in range(46):
        a = int(c.rand(k * 7 + 301) * (N - 1))
        b = int(c.rand(k * 7 + 302) * (N - 1))
        if a == b:
            continue
        ta = 1.0 + c.rand(k + 600) * 1.6
        p = c.progress(ta, ta + 0.7, "easeOutCubic")
        if p <= 0:
            continue
        xa, ya = star_pt(a)
        xb, yb = star_pt(b)
        c.line(xa, ya, xa + (xb - xa) * p, ya + (yb - ya) * p, color="accent", width=1.5,
               alpha=0.16 * p)

    c.glow(W_ / 2, H_ * 0.52, 300 + 36 * math.sin(t * 0.7), "accent", 0.10)

    # 星星（后画的在上）
    for i in range(N):
        st = 0.12 + (i / float(N)) * 1.5
        if t < st:
            continue
        age = t - st
        pop = min(1.0, age / 0.45)
        s = 0.35 + 0.65 * c.spring(pop, 5.0, 2.0)
        x, y = star_pt(i)
        tw = 0.55 + 0.45 * math.sin(t * 2.2 + c.rand(i + 41) * 6.283)
        r = (1.1 + c.rand(i + 7) * 2.1) * s
        a = (0.35 + 0.55 * tw) * pop
        c.circle(x, y, r, fill="fg", alpha=a)
        if c.rand(i + 77) > 0.85:
            c.glow(x, y, 26 * s, "accent", 0.10 * a)


# ---------------------------------------------------------------- 自绘 ③：全片层光尘
def dust(c, t):
    """全片层：极淡的微粒漂动（演示 film.draw 跨场景连续世界）。"""
    W_, H_ = c.width, c.height
    for i in range(34):
        x = (c.rand(i + 900) * W_ + t * (6 + c.rand(i + 950) * 10)) % W_
        y = (c.rand(i + 980) * H_ + math.sin(t * 0.3 + c.rand(i + 990) * 6.28) * 26) % H_
        a = 0.05 + 0.05 * math.sin(t * 1.3 + c.rand(i + 960) * 6.28)
        c.circle(x, y, 1.4 + c.rand(i + 970) * 1.4, fill="soft", alpha=max(0.0, a))


# ================================================================ 配乐（AI 写的乐谱）
# 配乐由内置的渲染模块渲染：曲式、和弦、鼓型、旋律全部在下面显式写出。
# 没有风格预设、没有随机——改一个音符就只改一个音符。
_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def make_score(duration, bpm):
    """《Hello, World!》的配乐：C 大调，I–V–vi–IV 循环，20 秒收尾落主和弦。"""
    wa = wv.wa
    spb = 60.0 / bpm                      # 每拍秒数
    bar = spb * 4.0                       # 每小节秒数
    total_beats = duration / spb
    bars = int(math.ceil((duration - 2.4) / bar))

    PROG = (0, 4, 5, 3)                   # I  V  vi  IV（级数）
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def name(m):
        return _NOTE_NAMES[int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.5)
    pad = s.track("pad", name="pad", gain_db=-16.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-11.0, pan=0.12, seed=2)
    bass = s.track("bass", name="bass", gain_db=-9.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0                     # 该小节起点（拍）
        ch = chord_midi(PROG[bi % 4])
        # 和声垫：整小节长音
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.5)
        # 琶音：八分音符上行（根-三-五-三）
        for si, idx in enumerate((0, 1, 2, 1, 0, 1, 2, 1)):
            pluck.note(b0 + si * 0.5, name(ch[idx]), 0.55, 0.5)
        # 低音：一、三拍
        bass.note(b0, name(ch[0] - 24), 1.8, 0.75)
        bass.note(b0 + 2.0, name(ch[0] - 24), 1.8, 0.6)

    # 收尾：片尾前 2.4 秒落主和弦（C 大三，八度铺开）+ 渐出
    end = (duration - 2.4) / spb
    for m in (48, 60, 64, 67, 72):
        pad.note(end, name(m), (2.4 + 0.8) / spb, 0.7)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.5)
    return s


# ================================================================ 影片
film = wv.Film(W, H, duration=20.0, fps=30, ss=2, theme="midnight",
               bpm=120, name="hello-world")
film.music = make_score(film.duration, film.bpm)

film.draw(dust, at=0)

# #1 0–4 开场：敲下第一行代码
s1 = film.scene(0, 4, transition="cut")
s1.draw(code_card, at=0.35, width=780, height=190, x=W / 2, y=330)
hero = s1.text("Hello, World!", at=2.2, style="hero", enter="slam")
s1.text("你好，世界", at=2.95, style="subtitle", enter="rise", split="char")
s1.burst("sparkle", on=hero)
film.sfx("riser", at=1.15, dur=1.05, gain=-8)

# #2 4–8 起源：1972 贝尔实验室
s2 = film.scene(4, 8, transition="cut")
s2.text("1972 · 贝尔实验室", at=4.35, style="title")
s2.text("半个世纪前，它在这里诞生", at=4.95, style="subtitle")
s2.text('printf("hello, world\\n");', at=5.45, size=46, font="mono", color="accent", enter="type")

# #3 8–13 学会每一种语言
s3 = film.scene(8, 13, transition="fade")
s3.text("它学会了每一种语言", at=8.4, style="title")
s3.list(["Python", "JavaScript", "C++", "Go", "Rust"], at=9.0, icon="dot", stagger=0.26, size=46)

# #4 13–17 【招牌】每一行代码，都化作一颗星
s4 = film.scene(13, 17, transition="wipe")
s4.draw(starfield, at=13.0)
s4.counter(0, 240, at=13.5, dur=1.5, format="%d 颗星", size=42, color="soft", pos="top")
s4.text("每一行代码，都化作一颗星", at=13.7, style="title", pos="bottom")
film.sfx("whoosh", at=13.02, gain=-6)
for _tt in (13.6, 13.95, 14.3):
    film.sfx("pop", at=_tt, gain=-12)
film.sfx("chime", at=16.3, gain=-9)

# #5 17–20 落版
s5 = film.scene(17, 20, transition="fade")
s5.text("你好，世界", at=17.35, style="hero", enter="slam")
s5.text("致每一个从这里出发的人", at=17.95, style="subtitle", enter="rise")
film.sfx("riser", at=16.72, dur=0.63, gain=-8)


if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "hello-world.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "hello-world.sheet.png"))
