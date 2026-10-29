# -*- coding: utf-8 -*-
"""write-video — 笔触图元（ 笔触技法移植版）。

梵高风"区域笔触"三板斧：
    palette  区域色板（若干种子色 hex）
    boil     8fps 沸腾：相邻种子色按 ease 平滑渐变，无单帧跳变
    field    方向场铺笔：网格上按角度函数铺凸四边形笔触

用法（s.draw 回调内，坐标为设计像素）：
    from write_video import strokes as st
    st.stroke(c, x, y, ang, 34, 9, "#24338f", alpha=0.85)
    for i, (x, y) in st.grid(0, 0, 1920, 700, sx=16, sy=14):
        st.stroke(c, x, y, angle_fn(x, y, t), 34, 9,
                  st.boil(c, i, PAL, BASE["sky"], 0.4), 0.85)

配套：stroke_path（沿路径连续笔触）、ell（色块椭圆）、steam（热气卷曲，
 U.steam 移植，逐段 alpha 顶淡出）。相机变换由调用方处理。
"""
import math
import random

# ---------------- 色彩工具 ----------------

def hx(s):
    """'#RRGGBB' -> (r,g,b)。"""
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def rgb(t):
    return "#%02x%02x%02x" % (int(t[0]), int(t[1]), int(t[2]))


def mix(c1, c2, k):
    """线性混色（hex 或元组 -> hex）。"""
    a, b = (c1 if isinstance(c1, tuple) else hx(c1)), (c2 if isinstance(c2, tuple) else hx(c2))
    return rgb(tuple(round(a[i] + (b[i] - a[i]) * k) for i in range(3)))


def ease(p):
    """平滑缓动（用于沸腾渐变）。"""
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


# ---------------- 沸腾色 ----------------

def boil(c, i, palette, base=None, mix_k=0.3, fps=8.0):
    """第 i 笔的沸腾色：相邻种子色按 8fps 平滑渐变，再向 base 靠拢 mix_k。

    palette 种子色数 3+ 为佳；base 为该区域底色（hex），沸腾围绕它抖动。
    """
    gt = c.ctx.time
    bp = gt * fps
    b0 = int(bp)
    pal = list(palette)
    c1, c2 = pal[(i + b0) % len(pal)], pal[(i + b0 + 1) % len(pal)]
    col = mix(c1, c2, ease(bp - b0))
    return mix(col, base, mix_k) if base else col


# ---------------- 笔触本体 ----------------

def stroke(c, x, y, ang, ln, wd, col, alpha=1.0, round_cap=True):
    """单笔：以 (x,y) 为中心、ang 方向 ln 长 wd 宽的圆头笔触。

    本体为凸四边形（点序 [p1+n, p2+n, p2-n, p1-n] 防蝴蝶结），
    round_cap 时两端各补一个半圆（ lineCap='round' 的等效），
    相邻笔自然融接，无砖块感。
    """
    dx, dy = math.cos(ang) * ln * 0.5, math.sin(ang) * ln * 0.5
    nx, ny = -dy / (ln * 0.5) * wd * 0.5, dx / (ln * 0.5) * wd * 0.5
    c.polygon([(x + dx + nx, y + dy + ny), (x - dx + nx, y - dy + ny),
               (x - dx - nx, y - dy - ny), (x + dx - nx, y + dy - ny)],
              fill=col, alpha=alpha)
    if round_cap and ln > wd:
        c.circle(x + dx, y + dy, wd * 0.5, fill=col, alpha=alpha)
        c.circle(x - dx, y - dy, wd * 0.5, fill=col, alpha=alpha)


def stroke_path(c, pts, wd, col, alpha=1.0, round_cap=True):
    """沿折线的连续笔触：逐段凸四边形拼接（转角自然搭接）。"""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy)
        if ln < 1e-6:
            continue
        stroke(c, (x0 + x1) * 0.5, (y0 + y1) * 0.5, math.atan2(dy, dx),
               ln + (wd if round_cap else 0), wd, col, alpha)


def ell(c, cx, cy, rx, ry, rot, col, alpha=1.0):
    """椭圆色块（10 边近似）。"""
    pts = [(cx + math.cos(rot + math.pi * 2 * i / 10) * rx,
            cy + math.sin(rot + math.pi * 2 * i / 10) * ry) for i in range(10)]
    c.polygon(pts, fill=col, alpha=alpha)


def ribbon(c, pts, width_fn, col, alpha=1.0, taper=(0.0, 0.0)):
    """可变宽度路径（10_nouveau 外粗内细 / 敦煌披帛 / 书法线）：
    沿点列两侧按 width_fn(q) 法线偏移拼多边形，一次填充。

    pts: [(x,y),...]；width_fn(q) -> 宽度，q 为弧长参数 0..1；
    taper: (头,尾) 收尖比例——头尾各占这段弧长比例内宽度乘 (q/头)^0.7 之类的收尖。
    """
    if len(pts) < 2:
        return
    # 弧长参数化
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(seg) or 1.0
    qs = [0.0]
    for ln in seg:
        qs.append(qs[-1] + ln / total)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        q = qs[i]
        # 法线（用相邻点方向）
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == len(pts) - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        wdt = width_fn(q) * 0.5
        h0, t0 = taper
        if h0 > 0 and q < h0:
            wdt *= (q / h0) ** 0.7
        if t0 > 0 and q > 1.0 - t0:
            wdt *= ((1.0 - q) / t0) ** 0.7
        left.append((x + nx * wdt, y + ny * wdt))
        right.append((x - nx * wdt, y - ny * wdt))
    c.polygon(left + right[::-1], fill=col, alpha=alpha)


def brush(c, pts, width=6.0, tone=0.8, dry=0.4, head=0.08, tail=0.18, col=(16, 14, 12),
          alpha=1.0, seed=0, reveal=None):
    """毛笔笔触（17_ink 水墨）：笔压包络 + 湿笔芯 + 连续笔毛飞白。

    pts: [(x,y),...]；tone: 墨色浓度 0..1（焦 .9/浓 .8/重 .6/淡 .35/清 .15）；
    dry: 飞白程度 0..1；head/tail: 起收笔的笔压渐变段（弧长比例）；
    reveal: (d, l, p) 段内揭示进度 0..1（开场逐笔写出用），None=整笔全画。
    飞白实现：笔毛是每根一条连续折线（butt cap 拼接），噪声低于阈值断开露纸。
    """
    if len(pts) < 2:
        return
    # Catmull-Rom 加密 + 等弧长重采样（不重采样飞白噪声频率会随笔画长短变化）
    dense = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for k in range(4):
            u = k / 4.0
            u2, u3 = u * u, u * u * u
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * u +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * u +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3)
            dense.append((x, y))
    dense.append(pts[-1])
    res = [dense[0]]
    target = 4.0
    acc = 0.0
    for a, b in zip(dense, dense[1:]):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        acc += ln
        while acc >= target:
            k = 1.0 - (acc - target) / max(1e-6, ln)
            res.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
            acc -= target
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(res, res[1:])]
    total = sum(seg) or 1.0
    qs = [0.0]
    for ln in seg:
        qs.append(qs[-1] + ln / total)
    # 揭示进度裁剪
    q_end = 1.0
    if reveal is not None:
        d, l, p = reveal
        q_end = min(1.0, max(0.0, (p * (d + l) - d) / max(1e-6, l))) if l > 0 else 1.0
    rng = random.Random(seed * 977 + int(qs[-1] * 1000))
    # 笔压包络
    def prof(q):
        e_head = _smoothstep(0.0, head, q) if head > 0 else 1.0
        e_tail = 1.0 - 0.7 * _smoothstep(1.0 - tail, 1.0, q) if tail > 0 else 1.0
        return e_head * e_tail * (0.85 + 0.15 * (math.sin(q * 23.7 + seed) * 0.5 + 0.5))
    # 湿笔芯（ribbon 填充）
    def core_w(q):
        return width * prof(q) * (1.0 - 0.85 * dry * (q ** 0.8))
    core = [(x, y) for i, (x, y) in enumerate(res) if qs[i] <= q_end]
    if len(core) >= 2:
        ribbon(c, core, core_w, _ink_col(col, tone * 0.72 * alpha), alpha=1.0)
    # 笔毛（连续折线，断开处露纸 = 飞白）
    nb = max(3, int(width / 2.2))
    for bi in range(nb):
        fr = (bi + 0.5) / nb - 0.5
        run = []
        for i, (x, y) in enumerate(res):
            q = qs[i]
            if q > q_end:
                break
            if i == 0:
                dx, dy = res[1][0] - x, res[1][1] - y
            elif i == len(res) - 1:
                dx, dy = x - res[i - 1][0], y - res[i - 1][1]
            else:
                dx, dy = res[i + 1][0] - res[i - 1][0], res[i + 1][1] - res[i - 1][1]
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            wdt = width * prof(q) * (0.475 + fr * 0.94)
            n = math.sin(q * 41.3 + bi * 1.9 + seed * 3.1) * 0.5 + 0.5
            if n < dry * (q ** 1.2) * 0.95 + 0.05:
                if len(run) >= 2:
                    c.lines(run, _ink_col(col, tone * 0.55 * alpha), max(1.0, width * 0.09),
                            alpha=alpha)
                run = []
                continue
            run.append((x + nx * wdt, y + ny * wdt))
        if len(run) >= 2:
            c.lines(run, _ink_col(col, tone * 0.55 * alpha), max(1.0, width * 0.09),
                    alpha=alpha)


def _smoothstep(a, b, x):
    k = min(1.0, max(0.0, (x - a) / max(1e-9, b - a)))
    return k * k * (3.0 - 2.0 * k)


def _ink_col(col, a_factor):
    if isinstance(col, (tuple, list)) and len(col) == 3:
        return (int(col[0]), int(col[1]), int(col[2]), int(255 * min(1.0, a_factor)))
    return col


# ---------------- 方向场铺笔 ----------------

def grid(x0, y0, x1, y1, sx=16.0, sy=14.0, mask=None):
    """区域网格：yield (i, x, y)；mask(x, y) 为 False 的点跳过（不计数）。"""
    i = 0
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            if mask is None or mask(x, y):
                yield i, x, y
                i += 1
            x += sx
        y += sy


def field(c, x0, y0, x1, y1, angle_fn, palette, base=None, mix_k=0.3,
          ln=34.0, wd=9.0, sx=16.0, sy=14.0, alpha=0.85, mask=None, fps=8.0,
          jitter=0.0):
    """区域笔触铺满：网格 + 方向场 + 沸腾色。返回实际画的笔数。

    angle_fn(x, y, t) -> 弧度；jitter 为每笔角度抖动弧度上限（用 c.rand 确定）。
    """
    gt = c.ctx.time
    n = 0
    for i, x, y in grid(x0, y0, x1, y1, sx, sy, mask):
        a = angle_fn(x, y, gt)
        if jitter:
            a += (c.rand(i) - 0.5) * 2.0 * jitter
        stroke(c, x, y, a, ln, wd, boil(c, i, palette, base, mix_k, fps=fps), alpha)
        n += 1
    return n


# ----------------  移植：热气 ----------------

def steam(c, x, y, h=70.0, n=3, w=3.0, color="fg", spread=14.0, speed=1.0,
          seed=1, wobble=8.0, alpha=0.8):
    """热气/炊烟：多条正弦卷曲的半透明笔触，顶端淡出（ U.steam 移植）。

    PIL 无渐变描边，逐段画并按高度衰减 alpha。
    """
    gt = c.ctx.time
    seg = 12
    for k in range(n):
        ox = (k - (n - 1) / 2.0) * spread
        ph = gt * 2.2 * speed + k * 1.7 + seed
        prev = None
        for s_i in range(seg + 1):
            q = s_i / seg
            xx = x + ox + math.sin(ph + q * 5) * wobble * q
            yy = y - q * h
            if prev is not None:
                c.line(prev[0], prev[1], xx, yy, color, w,
                       alpha=alpha * (1.0 - q) * (0.75 + 0.25 * math.sin(gt * 1.7 + k)))
            prev = (xx, yy)
