# -*- coding: utf-8 -*-
"""editorial · 数据新闻编辑风：镜头像读者的视线一样游走一整版报纸
11 秒 / 1920x1080 / 30fps
运行: python3 film.py

报纸版面 1600x2600 一次性画好（PSS=1.5 超采样 sprite）→ 每帧相机 keyframe 游走
（缩放 log 空间插值 + 拉远 skew）→ 活图形逐帧画（折线图生长/大数字滚动/华夫图/
引言/荧光笔）→ 9.4s 拉远 z 1.32→0.41 整版揭示（钩子）。
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           "/root/.codingmatrix/project-tpl/.ai-ready/skills/write-video/runtime"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import write_video as wv
from write_video.canvas import Canvas, ease

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")

PSS = 1.5
PAGE_W, PAGE_H = 1600, 2600
PAPER = (246, 242, 231)
INK = (26, 24, 22)
GRAY = (96, 88, 78)
RED = (200, 48, 43)
YELLOW = (255, 214, 51)
SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SERIF_R = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def wrap_cjk(c, text, size, width, bold=False, font=None):
    lines, cur = [], ""
    for ch in text:
        if cur and c.text_width(cur + ch, size, bold, font) > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def spaced(c, s, x, y, size, ls, color, font=None, alpha=1.0):
    w = sum(c.text_width(ch, size, False, font) for ch in s) + ls * (len(s) - 1)
    cx = x - w / 2
    for ch in s:
        c.text(ch, cx, y, size, color, font=font, align="left", valign="top", alpha=alpha)
        cx += c.text_width(ch, size, False, font) + ls


# === 报纸版面（一次性画好） ===
def build_page():
    im = Image.new("RGB", (int(PAGE_W * PSS), int(PAGE_H * PSS)), PAPER)
    c = Canvas(im, ss=PSS)
    for i in range(2600):
        x = hash1(i * 3.17) * PAGE_W
        y = hash1(i * 7.71) * PAGE_H
        ln = 5 + hash1(i * 1.7) * 16
        ang = hash1(i * 9.13) * 3.1416
        c.line(x, y, x + math.cos(ang) * ln, y + math.sin(ang) * ln,
               color=(90, 70, 40), width=1, alpha=0.02 + 0.018 * hash1(i * 5.3))
    c.text("数据日报", PAGE_W / 2, 88, 118, INK, bold=True)
    spaced(c, "THE DATA LEDGER · DATA JOURNALISM WEEKLY", PAGE_W / 2, 244, 24, 10, GRAY, font=SERIF)
    c.rect(80, 296, 1440, 5, fill=INK)
    c.rect(80, 307, 1440, 2, fill=INK)
    c.text("2026年10月25日 星期日", 80, 328, 22, GRAY, align="left")
    c.text("第 1024 期 · 数据新闻特刊", 1520, 328, 22, GRAY, align="right")
    c.rect(80, 398, 14, 14, fill=RED)
    c.text("深度 · AI 就业观察", 106, 405, 26, RED, bold=True, align="left")
    c.text("机器接管之后", PAGE_W / 2, 450, 148, INK, bold=True)
    c.text("七成岗位被重塑", PAGE_W / 2, 628, 148, INK, bold=True)
    dek = "本研究追踪 12 个行业 4600 个岗位样本，绘制自动化浪潮下的职业版图变迁——技能的重合、消失与新生。"
    for i, ln in enumerate(wrap_cjk(c, dek, 34, 1240)):
        c.text(ln, PAGE_W / 2, 816 + i * 50, 34, (70, 66, 60), align="center")
    c.text("文 · 数据新闻组　　数据 · 视觉实验室", PAGE_W / 2, 934, 22, GRAY, align="center")
    c.rect(80, 972, 1440, 2, fill=(130, 120, 106))
    # 左栏：首字下沉段
    c.text("七", 80, 1006, 120, RED, bold=True, align="left", valign="top")
    p1 = ("成岗位将在未来十年被深度重塑。自动化带走的是重复劳动，留下的是判断与创造："
          "沟通、审美、跨领域整合的价值正在被急速放大，而单一的执行型技能正在快速折旧。")
    for i, ln in enumerate(wrap_cjk(c, p1, 26, 500)):
        c.text(ln, 208, 1016 + i * 46, 26, INK, align="left", valign="top")
    # 左栏：折线图框（数据线为活图形）
    c.rect(80, 1252, 640, 400, fill=(252, 249, 243), outline=(150, 142, 128), width=2)
    c.text("技能需求重合度 · 8 周追踪", 102, 1272, 24, INK, bold=True, align="left")
    c.text("— 岗位技能A　— 岗位技能AI", 700, 1276, 20, GRAY, align="right")
    c.line(110, 1612, 690, 1612, color=(150, 142, 128), width=2)
    c.line(110, 1330, 110, 1612, color=(150, 142, 128), width=2)
    for wk in range(1, 9):
        c.text("W%d" % wk, 110 + (wk - 1) * 82.9, 1620, 18, GRAY, align="center")
    # 左栏：补段
    p2 = ("重塑并不等于消失。报告显示，被重塑的岗位中有 54% 新增了数据协作职责，"
          "31% 要求掌握至少一种 AI 工具链，一线的技能半衰期已经缩短到 2.7 年。")
    for i, ln in enumerate(wrap_cjk(c, p2, 26, 640)):
        c.text(ln, 80, 1694 + i * 46, 26, INK, align="left", valign="top")
    # 左栏：大数字块（数字与主标注为活图形）
    c.rect(80, 1962, 640, 2, fill=INK)
    c.text("岗位技能半衰期 · 2.7 年", 400, 2348, 24, GRAY, align="center")
    # 右栏
    p3 = ("薪酬的分化同样明显。掌握 AI 协作技能的从业者平均溢价 34%，而纯执行型岗位的时薪中位数"
          "在三年内下降了 11%。企业招聘描述里，「与 AI 共事」出现的频率一年内翻了三倍，"
          "猎头们开始按工具链而非行业划分候选人。")
    for i, ln in enumerate(wrap_cjk(c, p3, 26, 640)):
        c.text(ln, 800, 1016 + i * 46, 26, INK, align="left", valign="top")
    p4 = ("政策的松动在加速这一切。多个城市把「技能重塑」写入产业补贴目录，"
          "职业培训的报销比例从 40% 提高到 70%，一场面向人机协作的再培训潮已经开始。")
    for i, ln in enumerate(wrap_cjk(c, p4, 26, 640)):
        c.text(ln, 800, 1878 + i * 46, 26, INK, align="left", valign="top")
    # 右栏：华夫图标签（格子为活图形）
    c.text("受访岗位中技能将被重塑的比例", 800, 2206, 22, INK, bold=True, align="left")
    # 页脚
    c.rect(80, 2468, 1440, 2, fill=(130, 120, 106))
    c.text("注：文中数字均为示意数据 · 数据新闻实验室 出品", PAGE_W / 2, 2494, 20, GRAY, align="center")
    return im.convert("RGBA")


PAGE = build_page()


def build_desktop():
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    r = np.sqrt(xx * xx + (yy * 1.25) ** 2)
    k = np.clip(r / 1.15, 0, 1)[..., None]
    a = np.array([58, 54, 47], np.float32)
    b = np.array([24, 22, 19], np.float32)
    return Image.fromarray((a[None, None, :] + (b - a)[None, None, :] * k).astype(np.uint8))


DESKTOP = build_desktop()

# === 相机：10 个 keyframe 沿阅读视线游走 ===
KEYS = [
    (0.0, 800, 260, 1.10),
    (0.9, 800, 570, 1.30),
    (2.0, 400, 1470, 1.10),
    (3.3, 400, 1120, 1.02),
    (4.8, 400, 2150, 1.10),
    (5.6, 1120, 2320, 1.10),
    (6.6, 1110, 1660, 1.16),
    (7.6, 760, 1330, 0.92),
    (9.0, 800, 1300, 1.28),
    (9.4, 800, 1300, 1.32),
]


def camera(t):
    if t <= KEYS[0][0]:
        px, py, z = KEYS[0][1:]
    else:
        px, py, z = KEYS[-1][1:]
        for i in range(len(KEYS) - 1):
            t0, x0, y0, z0 = KEYS[i]
            t1, x1, y1, z1 = KEYS[i + 1]
            if t0 <= t <= t1:
                e = ease("inOutSine", (t - t0) / (t1 - t0))
                z = math.exp(math.log(z0) + (math.log(z1) - math.log(z0)) * e)
                px = x0 + (x1 - x0) * e
                py = y0 + (y1 - y0) * e
                break
    intro = ease("outCubic", clamp(t / 0.5, 0, 1))
    z *= 1.0 - 0.22 * (1.0 - intro)
    pull = ease("outCubic", clamp((t - 9.4) / 1.4, 0, 1))
    z += (0.41 - z) * pull
    return px, py, z, -0.06 * pull


def fwd(px, py, z, skew, X, Y):
    u = (X - px) * z
    v = (Y - py) * z
    return (W / 2 + u + skew * v, H / 2 + v)


# === 折线图数据（页面坐标） ===
MAN = (62, 63, 64, 65, 66, 66.5, 67, 67.5)
AI = (18, 26, 33, 42, 52, 63, 71, 78)


def chart_xy(wk, v):
    return (110 + wk * 82.9, 1612 - v / 80.0 * 270)


def draw_chart(c, t, px, py, z, skew):
    gp = clamp((t - 2.0) / 1.6, 0, 1)
    if gp <= 0:
        return
    nseg = gp * 7.0
    full = min(7, int(nseg))
    frac = nseg - full if full < 7 else 0.0

    def pts_at(series):
        out = [chart_xy(i, series[i]) for i in range(full + 1)]
        if full < 7:
            v0 = series[full]
            v1 = series[full + 1] if full + 1 < 8 else v0
            out.append(chart_xy(full + frac, v0 + (v1 - v0) * frac))
        return out

    pm = pts_at(MAN)
    pa = pts_at(AI)
    a = 1.0
    sm = [fwd(px, py, z, skew, X, Y) for (X, Y) in pm]
    sa = [fwd(px, py, z, skew, X, Y) for (X, Y) in pa]
    if len(sm) >= 2:
        c.polygon(sa + sm[::-1], fill=RED, alpha=0.10)
        c.lines(sa, color=RED, width=3.5 * max(1.0, z), alpha=a)
        c.lines(sm, color=(96, 88, 78), width=3.5 * max(1.0, z), alpha=a)
    an = ease("outBack", clamp((t - 3.1) / 0.4, 0, 1))
    if an > 0.01:
        ax, ay = chart_xy(5, AI[5])
        sx, sy = fwd(px, py, z, skew, ax, ay)
        c.line(sx, sy, sx + 34 * z * an, sy - 52 * z * an, color=RED, width=2 * max(1.0, z), alpha=an)
        c.circle(sx, sy, 6 * z * an, fill=RED, alpha=an)
        c.text("交叉点 · W6", sx + 16 * z * an, sy - 60 * z * an, 18 * max(1.0, z), RED,
               bold=True, align="left", alpha=an)


def draw_number(c, t, px, py, z, skew):
    pr = clamp((t - 4.8) / 0.9, 0, 1)
    if pr <= 0:
        return
    v = min(7, 1 + int(6.999 * pr))
    sx, sy = fwd(px, py, z, skew, 400, 2140)
    c.text(str(v), sx, sy, 250 * z, RED, bold=True, alpha=clamp((t - 4.8) / 0.15, 0, 1))
    a2 = clamp((t - 5.5) / 0.3, 0, 1)
    if a2 > 0:
        sx2, sy2 = fwd(px, py, z, skew, 400, 2296)
        c.text("种核心技能将被重写", sx2, sy2, 30 * z, INK, bold=True, alpha=a2)


def draw_waffle(c, t, px, py, z, skew):
    u = clamp((t - 5.2) / 1.0, 0, 1)
    if u <= 0:
        return
    nfill = int(round(u * 68))
    for i in range(100):
        col, row = i % 20, i // 20
        X, Y = 800 + col * 32, 2246 + row * 32
        sx, sy = fwd(px, py, z, skew, X, Y)
        if i < nfill:
            c.rect(sx, sy, 26 * z, 26 * z, fill=RED)
        else:
            c.rect(sx, sy, 26 * z, 26 * z, fill=(238, 233, 222), outline=(198, 190, 176), width=1)


def draw_quote(c, t, px, py, z, skew):
    aq = clamp((t - 6.6) / 0.3, 0, 1)
    if aq <= 0:
        return
    dy = (1.0 - aq) * 24
    sx, sy = fwd(px, py, z, skew, 806, 1462 + dy)
    c.text("\u201c", sx, sy, 150 * z, RED, bold=True, align="left", valign="top", alpha=aq)
    sx1, sy1 = fwd(px, py, z, skew, 810, 1636 + dy)
    c.text("被替代的从来不是人，", sx1, sy1, 44 * z, INK, bold=True, align="left", valign="top", alpha=aq)
    sx2, sy2 = fwd(px, py, z, skew, 810, 1704 + dy)
    c.text("而是停滞的技能。", sx2, sy2, 44 * z, INK, bold=True, align="left", valign="top", alpha=aq)
    a3 = clamp((t - 6.95) / 0.3, 0, 1)
    if a3 > 0:
        sx3, sy3 = fwd(px, py, z, skew, 810, 1786 + dy)
        c.text("—— 报告主笔 · 沈知微", sx3, sy3, 22 * z, GRAY, align="left", valign="top", alpha=a3)


def highlighter(c, t, px, py, z, skew, t0, x0, y0, x1, y1, redraw=None):
    u = ease("inOutSine", clamp((t - t0) / 0.45, 0, 1))
    if u <= 0:
        return
    w = (x1 - x0) * u
    skew_l = 14
    quad = [(x0 - 6, y0 + 10), (x0 + w, y0 - 2), (x0 + w + skew_l, y1 + 2), (x0 - 2, y1 + 14)]
    sq = [fwd(px, py, z, skew, X, Y) for (X, Y) in quad]
    c.polygon(sq, fill=YELLOW, alpha=0.5)
    if redraw:
        redraw()


def draw_grain(c, t):
    for i in range(220):
        x = hash1(i * 13.7) * W
        y = hash1(i * 7.9) * H
        c.rect(x, y, 2, 2, fill=(20, 18, 14), alpha=0.06)
    for i in range(50):
        x = hash1(i * 31.3) * W
        y = hash1(i * 17.9) * H
        c.rect(x, y, 2, 2, fill=(255, 250, 240), alpha=0.035)


def main_scene(c, t):
    px, py, z, skew = camera(t)
    view = DESKTOP.copy().convert("RGBA")
    quad = [fwd(px, py, z, skew, X, Y)
            for (X, Y) in ((0, 0), (PAGE_W, 0), (PAGE_W, PAGE_H), (0, PAGE_H))]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def shift(q, ddx, ddy):
        return [(x + ddx, y + ddy) for (x, y) in q]

    d.polygon(shift(quad, 14 * z + 18, 20 * z + 26), fill=(12, 10, 8, 90))
    d.polygon(shift(quad, 7 * z + 9, 10 * z + 13), fill=(12, 10, 8, 60))
    view.alpha_composite(ov)
    a = PSS / z
    b = -skew * PSS / z
    coefs = (a, b, px * PSS - (W / 2 - skew * H / 2) * PSS / z,
             0.0, PSS / z, py * PSS - (H / 2) * PSS / z)
    page_t = PAGE.transform((W, H), Image.AFFINE, coefs, resample=Image.BICUBIC)
    view.alpha_composite(page_t)
    c.paste_full(view)

    def _rl1():
        tx, ty = fwd(px, py, z, skew, 800, 450)
        c.text("机器接管之后", tx, ty, 148 * z, INK, bold=True)

    def _rl2():
        tx, ty = fwd(px, py, z, skew, 810, 1704)
        c.text("而是停滞的技能。", tx, ty, 44 * z, INK, bold=True, align="left", valign="top")

    highlighter(c, t, px, py, z, skew, 0.9, 356, 386, 1244, 552, redraw=_rl1)
    draw_chart(c, t, px, py, z, skew)
    draw_number(c, t, px, py, z, skew)
    draw_waffle(c, t, px, py, z, skew)
    draw_quote(c, t, px, py, z, skew)
    highlighter(c, t, px, py, z, skew, 7.2, 806, 1698, 1180, 1762, redraw=_rl2)
    draw_grain(c, t)
    c.vignette(radius=0.72, power=1.6, alpha=0.35)


# === 配乐：C 宫 96 BPM，纸面新闻编辑部的克制 ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    CHORDS = [(53, 57, 60, 64), (57, 60, 64, 67), (50, 53, 57, 60), (48, 52, 55, 59)]
    ROOTS = (41, 45, 38, 36)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.8)
    pad = s.track("pad", name="pad", gain_db=-16.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="mel", gain_db=-12.0, pan=0.12, seed=2)
    bass = s.track("bass", name="bass", gain_db=-11.0, pan=0.0, seed=3)
    hat = s.track("hat", name="ticks", gain_db=-22.0, pan=-0.08, seed=4)
    bell = s.track("bell", name="acc", gain_db=-14.0, pan=0.05, seed=5)

    for bi in range(4):
        b0 = bi * 4.0
        ch = CHORDS[bi]
        for m in ch:
            pad.note(b0, name(m), 4.1, 0.5)
        bass.note(b0, name(ROOTS[bi] - 12), 2.2, 0.75)
        bass.note(b0 + 2.0, name(ROOTS[bi] - 12), 1.8, 0.55)
        tones = list(ch) + [ch[0] + 12]
        for si, idx in enumerate((4, 3, 2, 1, 0, 2, 1, 0)):
            pluck.note(b0 + si * 0.5, name(tones[idx]), 0.55, 0.5)
        if bi >= 1:
            for si in range(8):
                hat.note(b0 + si * 0.5, None, None, 0.35 if si % 2 else 0.6)
    bell.note(7.5, "E5", 1.2, 0.6)
    bell.note(10.5, "G5", 1.6, 0.6)
    pluck.note(total_beats - 1.0, "C5", 1.0, 0.5)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.2)
    return s


film = wv.Film(W, H, duration=11.0, fps=30, ss=2, theme="light",
               bpm=96, name="editorial-paper")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(main_scene, at=0, enter="none")

film.sfx("swish", at=0.3, gain=-14)
film.sfx("swipe", at=0.95, gain=-12)
film.sfx("whoosh", at=2.0, gain=-14)
film.sfx("pop", at=3.1, gain=-12)
film.sfx("typing", at=4.8, dur=0.9, gain=-16)
film.sfx("notification", at=5.3, gain=-14)
film.sfx("impact", at=6.6, gain=-13)
film.sfx("swipe", at=7.25, gain=-12)
film.sfx("riser", at=8.7, dur=1.0, gain=-14)
film.sfx("whoosh", at=9.45, gain=-9)
film.sfx("chime", at=10.5, gain=-11)
film.sfx("typing", at=8.9, dur=0.4, gain=-18)
film.sfx("tick", at=9.4, gain=-20)
film.sfx("typing", at=10.3, dur=0.4, gain=-22)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "editorial-paper.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "editorial-paper.sheet.png"))
