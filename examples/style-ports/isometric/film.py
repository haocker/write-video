# -*- coding: utf-8 -*-
"""Isometric City · 等轴 2.5D 悬浮小城十秒长出来
10 秒 / 1920x1080 / 30fps
运行: python3 film.py

相机：开场 spring 落入 + 3.2s 起缓慢环绕 AZ+0.55rad + 推近 SC 76→84。
深度：楼/树/灯/车/摩天轮全部按旋转深度 ry 排序后画家算法绘制。
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

# === 参数 ===
N = 14
FH = 0.32  # 每层楼高

# 相机状态（每帧由 render(t) 驱动，保持确定性）
AZ = math.pi / 4
SC = 76.0
CX, CY = 960.0, 585.0
K = W / 1920.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mix3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ease_io(x):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x, 0, 1))


def spring_drop(t, k=90.0, c=13.0):
    """欠阻尼弹簧 0→1（开场相机落入）。"""
    if t <= 0:
        return 0.0
    wd = math.sqrt(k - c * c / 4.0)
    return 1.0 - math.exp(-c * t / 2.0) * (math.cos(wd * t) + (c / (2.0 * wd)) * math.sin(wd * t))


# === 正交投影 ===
def P(x, y, z):
    xx, yy = x - 7, y - 7
    c, s = math.cos(AZ), math.sin(AZ)
    rx = xx * c - yy * s
    ry = xx * s + yy * c
    return ((CX + rx * SC) * K, (CY + ry * SC * math.sin(EL) - z * SC * math.cos(EL)) * K)


EL = 0.52


def depth(x, y):
    """物体深度（旋转后的 ry，越大越靠近相机）。"""
    xx, yy = x - 7, y - 7
    c, s = math.cos(AZ), math.sin(AZ)
    return xx * s + yy * c


# === 全局色调（昼→黄昏→夜） ===
def tint_g(col, dusk, night, k=1.0):
    if night > 0:
        tt = mix3((255, 179, 138), (96, 104, 192), night)
        m = (1 - night * 0.42) * k
    else:
        tt = mix3((255, 255, 255), (255, 179, 138), dusk)
        m = k
    return (clamp(int(col[0] * tt[0] / 255.0 * m), 0, 255),
            clamp(int(col[1] * tt[1] / 255.0 * m), 0, 255),
            clamp(int(col[2] * tt[2] / 255.0 * m), 0, 255))


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


# === 城市数据 ===
roadX = {4, 9}
roadY = {6}


def isRoad(x, y):
    return y in roadX or x in roadY


PALB = [(255, 244, 224), (255, 159, 133), (111, 180, 238), (255, 207, 74),
        (143, 224, 196), (175, 162, 245), (255, 255, 255), (255, 126, 107),
        (95, 208, 168)]

lots = []
used = set()
key = lambda x, y: f"{x},{y}"
PARK = {"x0": 7, "y0": 0, "x1": 13, "y1": 3}
inPark = lambda x, y: PARK["x0"] <= x <= PARK["x1"] and PARK["y0"] <= y <= PARK["y1"]

for y in range(N):
    for x in range(N):
        if isRoad(x, y) or key(x, y) in used or inPark(x, y):
            continue
        w, d = 1, 1
        if hash1(x * 7 + y * 13) > 0.6 and x + 1 < N and not isRoad(x + 1, y) \
                and key(x + 1, y) not in used and not inPark(x + 1, y):
            w = 2
        if hash1(x * 3 + y * 17) > 0.65 and y + 1 < N and not isRoad(x, y + 1) \
                and key(x, y + 1) not in used and not inPark(x, y + 1) \
                and (w == 1 or (not isRoad(x + 1, y + 1) and key(x + 1, y + 1) not in used)):
            d = 2
        for j in range(d):
            for i in range(w):
                used.add(key(x + i, y + j))
        cx, cy = x + w / 2.0, y + d / 2.0
        dc = math.hypot(cx - 7, cy - 7)
        floors = 1 + int(hash1(x * 31 + y * 7) * 3.5 + max(0, 6 - dc) * 1.1 * hash1(x * 3 + y * 19 + 1))
        if hash1(x + y * 41) > 0.9:
            floors = 0
        tower = (x == 5 and y == 7)
        if tower:
            floors = 13
        col = PALB[int(hash1(x * 11 + y * 5) * len(PALB))]
        t0 = 0.9 + dc * 0.14 + hash1(x * 5 + y) * 0.25
        lots.append({"x": x, "y": y, "w": w, "d": d, "floors": floors, "col": col,
                     "t0": t0, "tower": tower, "seed": x * 17 + y * 3})

TREES = []
for i in range(26):
    x = PARK["x0"] + 0.4 + hash1(i * 3.1) * (PARK["x1"] - PARK["x0"] + 0.2)
    y = PARK["y0"] + 0.3 + hash1(i * 7.3) * (PARK["y1"] - PARK["y0"] + 0.4)
    if math.hypot(x - 11.6, y - 1.8) < 1.6:
        continue
    TREES.append((x, y, 0.28 + hash1(i) * 0.14, 2.2 + hash1(i * 9) * 0.6))

LAMPS = []
for i in range(0, N, 2):
    LAMPS.append((i + 0.5, 3.88))
    LAMPS.append((i + 0.5, 10.12))
    LAMPS.append((5.88, i + 0.5))

CARS = []
for i in range(12):
    CARS.append({"road": i % 3, "dir": 1 if i % 2 else -1,
                 "off": hash1(i * 5.7) * N, "v": 1.1 + hash1(i * 2.3) * 0.7,
                 "col": ["#ff5d5d", "#ffffff", "#3d7bff", "#ffcf3d", "#2ec4b6", "#1f2937"][i % 6]})


# === 等轴 box 渲染器（侧面法线剔除 + 窗户 + 顶棱） ===
def box(ctx, x0, y0, z0, x1, y1, z1, col, floors=0, seed=0, dusk=0.0, night=0.0, alpha=1.0):
    v = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    top = [P(x, y, z1) for x, y in v]
    bot = [P(x, y, z0) for x, y in v]
    normals = [[0, -1], [1, 0], [0, 1], [-1, 0]]
    c, s = math.cos(AZ), math.sin(AZ)
    for i in range(4):
        nx, ny = normals[i]
        nry = nx * s + ny * c
        if nry <= 0.001:
            continue
        j = (i + 1) % 4
        k = (0.62 + 0.42 * max(0, (nx * -0.6 + ny * -0.35) / math.hypot(-0.6, -0.35))) * (0.86 + 0.14 * nry)
        ctx.polygon([bot[i], bot[j], top[j], top[i]], fill=tint_g(col, dusk, night, k), alpha=alpha)
        if floors > 0:
            L = math.hypot(v[j][0] - v[i][0], v[j][1] - v[i][1])
            cols = max(1, round(L * 1.6))
            fh = (z1 - z0) / floors
            for f in range(floors):
                for q in range(cols):
                    u0 = (q + 0.3) / cols
                    u1 = (q + 0.7) / cols
                    zz0 = z0 + f * fh + fh * 0.32
                    zz1 = z0 + f * fh + fh * 0.74
                    pax = v[i][0] + (v[j][0] - v[i][0]) * u0
                    pay = v[i][1] + (v[j][1] - v[i][1]) * u0
                    pbx = v[i][0] + (v[j][0] - v[i][0]) * u1
                    pby = v[i][1] + (v[j][1] - v[i][1]) * u1
                    quad = [P(pax, pay, zz0), P(pbx, pby, zz0), P(pbx, pby, zz1), P(pax, pay, zz1)]
                    hs = hash1(seed * 13 + f * 7 + q * 3 + i * 31)
                    on = night > 0 and hs < 0.82 and night > hs * 0.75 + 0.05
                    if on:
                        wc = (191, 233, 255) if hs < 0.15 else ((255, 216, 138) if hs < 0.55 else (255, 233, 194))
                        ctx.polygon(quad, fill=tint_g(wc, dusk, night * 0.3), alpha=alpha)
                    else:
                        day = mix3((169, 205, 234), (42, 52, 96), night * 0.6)
                        ctx.polygon(quad, fill=tint_g(day, dusk, night, k * 0.95), alpha=alpha)
    ctx.polygon(top, fill=tint_g(col, dusk, night, 0.64 + 0.42 * 0.72), alpha=alpha)
    ctx.lines(top + [top[0]], color=tint_g((255, 255, 255), dusk, night, 1.0),
              width=1.2 * K, alpha=0.55 * (1 - night * 0.8) * alpha)


def frange(a, b, step):
    out = []
    v = a
    while v < b:
        out.append(v)
        v += step
    return out


# === 场景绘制 ===
def sky(ctx, t, dusk, night):
    if night > 0:
        top = mix3((125, 127, 214), (12, 16, 51), night)
        bot = mix3((255, 179, 138), (42, 33, 96), night)
    else:
        top = mix3((191, 227, 245), (125, 127, 214), dusk)
        bot = mix3((241, 247, 234), (255, 179, 138), dusk)
    ctx.gradient(0, 0, W, H, colors=[(0, top), (1, bot)], direction="vertical")
    if night > 0.2:
        for i in range(90):
            x = hash1(i * 3.3) * W
            y = hash1(i * 7.1) * H * 0.7
            a = (night - 0.2) * (0.5 + 0.5 * math.sin(t * 2 + i)) * 0.8
            ctx.circle(x, y, 2 * K, fill="#ffffff", alpha=a)


def draw_slab(ctx, dusk, night):
    layers = [(-1.1, -0.75, (138, 90, 60)), (-0.75, -0.35, (168, 112, 74)),
              (-0.35, -0.12, (197, 139, 91)), (-0.12, 0, (124, 192, 106))]
    for a, b, c in layers:
        box(ctx, -0.15, -0.15, a, N + 0.15, N + 0.15, b, c)
    g = [P(-0.15, -0.15, 0), P(N + 0.15, -0.15, 0), P(N + 0.15, N + 0.15, 0), P(-0.15, N + 0.15, 0)]
    ctx.polygon(g, fill=tint_g((155, 212, 122), dusk, night, 1.02))


def draw_roads(ctx, t, dusk, night):
    rv = 1.0 if t > 1.25 else max(0.0, 1.0 - (1.0 - t / 0.9) ** 3)
    road, walk = (89, 96, 117), (221, 216, 203)
    for y in roadX:
        L = N * rv
        if L <= 0.1:
            continue
        ctx.polygon([P(0, y - 0.08, 0.01), P(L, y - 0.08, 0.01), P(L, y + 1.08, 0.01), P(0, y + 1.08, 0.01)],
                    fill=tint_g(walk, dusk, night))
        ctx.polygon([P(0, y + 0.06, 0.02), P(L, y + 0.06, 0.02), P(L, y + 0.94, 0.02), P(0, y + 0.94, 0.02)],
                    fill=tint_g(road, dusk, night))
        for x in frange(0.3, L - 0.4, 0.8):
            ctx.polygon([P(x, y + 0.48, 0.025), P(x + 0.4, y + 0.48, 0.025),
                         P(x + 0.4, y + 0.52, 0.025), P(x, y + 0.52, 0.025)],
                        fill=tint_g((242, 242, 242), dusk, night))
    for x in roadY:
        L = N * rv
        if L <= 0.1:
            continue
        ctx.polygon([P(x - 0.08, 0, 0.011), P(x + 1.08, 0, 0.011), P(x + 1.08, L, 0.011), P(x - 0.08, L, 0.011)],
                    fill=tint_g(walk, dusk, night))
        ctx.polygon([P(x + 0.06, 0, 0.021), P(x + 0.94, 0, 0.021), P(x + 0.94, L, 0.021), P(x + 0.06, L, 0.021)],
                    fill=tint_g(road, dusk, night))
        for y in frange(0.3, L - 0.4, 0.8):
            ctx.polygon([P(x + 0.48, y, 0.026), P(x + 0.52, y, 0.026),
                         P(x + 0.52, y + 0.4, 0.026), P(x + 0.48, y + 0.4, 0.026)],
                        fill=tint_g((242, 242, 242), dusk, night))
    for y in roadX:
        for x in roadY:
            ctx.polygon([P(x, y, 0.03), P(x + 1, y, 0.03), P(x + 1, y + 1, 0.03), P(x, y + 1, 0.03)],
                        fill=tint_g(road, dusk, night))


def draw_shadow(ctx, t, items, sun):
    if t > 6.0:
        return
    alpha = 0.16 * max(0.0, 1.0 - t / 7.5)
    if alpha <= 0:
        return
    sx, sy = -sun[0] / sun[2], -sun[1] / sun[2]
    for (x0, y0, x1, y1, h) in items:
        pts = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        proj = [[x + sx * h, y + sy * h] for x, y in pts]
        all_pts = sorted(pts + proj)
        lo, up = [], []
        for p in all_pts:
            while len(lo) >= 2 and ((lo[-1][0] - lo[-2][0]) * (p[1] - lo[-1][1])
                                    - (lo[-1][1] - lo[-2][1]) * (p[0] - lo[-1][0])) <= 0:
                lo.pop()
            lo.append(p)
        for p in reversed(all_pts):
            while len(up) >= 2 and ((up[-1][0] - up[-2][0]) * (p[1] - up[-1][1])
                                    - (up[-1][1] - up[-2][1]) * (p[0] - up[-1][0])) <= 0:
                up.pop()
            up.append(p)
        hull = lo[:-1] + up[:-1]
        if len(hull) >= 3:
            ctx.polygon([P(p[0], p[1], 0.035) for p in hull], fill="#1d2a52", alpha=alpha)


def draw_tree(ctx, t, x, y, r, sc, dusk, night):
    if sc <= 0:
        return
    sway = math.sin(t * 2 + x) * 0.015
    box(ctx, x - 0.04, y - 0.04, 0, x + 0.04, y + 0.04, 0.28 * sc, (138, 90, 60), dusk=dusk, night=night)
    c = P(x + sway, y, 0.28 * sc + r * sc)
    rr = r * SC * K * sc
    base = (92, 191, 106) if hash1(x * 13) > 0.5 else (123, 207, 98)
    ctx.circle(c[0], c[1], rr, fill=tint_g(base, dusk, night, 1.15))
    ctx.circle(c[0] - rr * 0.3, c[1] - rr * 0.35, rr * 0.55, fill=tint_g(base, dusk, night, 1.3))


def draw_ferris(ctx, t, dusk, night):
    cx, cy, R, hz = 11.4, 1.7, 1.5, 1.8
    sc = clamp((t - 2.0) / 0.5, 0, 1.1)
    if sc <= 0:
        return
    for (lx, ly) in [(cx - 0.55, cy - 0.12), (cx + 0.55, cy - 0.12),
                     (cx - 0.55, cy + 0.12), (cx + 0.55, cy + 0.12)]:
        a, b = P(lx, ly, 0), P(cx, cy, hz * sc)
        ctx.line(a[0], a[1], b[0], b[1], color=tint_g((233, 228, 242), dusk, night), width=5 * K)
    hub = P(cx, cy, hz * sc)
    rim = [P(cx + math.cos(i / 48.0 * math.pi * 2) * R * sc, cy,
             hz * sc + math.sin(i / 48.0 * math.pi * 2) * R * sc) for i in range(49)]
    ctx.lines(rim, color=tint_g((255, 122, 162), dusk, night), width=5 * K)
    ang = t * 0.5
    for i in range(12):
        a = ang + i / 12.0 * math.pi * 2
        px, py = cx + math.cos(a) * R * sc, cy
        pz = hz * sc + math.sin(a) * R * sc
        pe = P(px, py, pz)
        cab = P(px, py, pz - 0.12)
        ctx.line(hub[0], hub[1], pe[0], pe[1], color=tint_g((255, 255, 255), dusk, night), width=2 * K, alpha=0.9)
        cbg = ["#ffd166", "#93c5ea", "#ffb7a1", "#b6e3d2"][i % 4]
        ctx.rect(cab[0] - 8 * K, cab[1] - 6 * K, 16 * K, 13 * K,
                 fill=tint_g(wv.canvas.parse_color(cbg), dusk, night), radius=4 * K)
        if night > 0.3:
            ctx.glow(pe[0], pe[1], 7 * K, ["#ff7aa2", "#ffd166", "#7fe3ff"][i % 3], 0.9 * night)
    ctx.circle(hub[0], hub[1], 6 * K, fill="#ffffff")


def car_pos(c, t):
    """车的世界坐标脚印（纯函数）。"""
    L = N + 2
    u = ((c["off"] + c["dir"] * c["v"] * t) % L + L) % L - 1
    if c["road"] < 2:
        ry = list(roadX)[c["road"]] + (0.62 if c["dir"] > 0 else 0.38)
        return (u - 0.22, ry - 0.13, u + 0.22, ry + 0.13, c["dir"], 0, c["col"])
    rx = list(roadY)[0] + (0.38 if c["dir"] > 0 else 0.62)
    return (rx - 0.13, u - 0.22, rx + 0.13, u + 0.22, 0, c["dir"], c["col"])


def draw_car(ctx, cc, dusk, night, on):
    x0, y0, x1, y1, hx, hy, colstr = cc
    if x0 < -0.2 or x1 > N + 0.2 or y0 < -0.2 or y1 > N + 0.2:
        return
    col = wv.canvas.parse_color(colstr)
    a = clamp(on, 0, 1)
    box(ctx, x0, y0, 0.03, x1, y1, 0.13, col, alpha=a)
    box(ctx, x0 + 0.08 * abs(hy) + 0.05 * abs(hx), y0 + 0.08 * abs(hx) + 0.05 * abs(hy),
        0.13, x1 - 0.08 * abs(hy) - 0.05 * abs(hx), y1 - 0.08 * abs(hx) - 0.05 * abs(hy),
        0.2, (207, 230, 255), alpha=a)
    if night > 0.2:
        fx, fy = (x1 if hx > 0 else (x0 if hx < 0 else (x0 + x1) / 2)), \
                 (y1 if hy > 0 else (y0 if hy < 0 else (y0 + y1) / 2))
        bx, by = (x0 if hx > 0 else (x1 if hx < 0 else (x0 + x1) / 2)), \
                 (y0 if hy > 0 else (y1 if hy < 0 else (y0 + y1) / 2))
        f, bk = P(fx, fy, 0.09), P(bx, by, 0.09)
        ctx.glow(f[0], f[1], 6 * K, "#fff6d0", 0.5 * night * a)
        ctx.glow(bk[0], bk[1], 5 * K, "#ff3d3d", 0.5 * night * a)


def draw_lamp(ctx, t, x, y, dusk, night):
    a, b = P(x, y, 0), P(x, y, 0.55)
    ctx.line(a[0], a[1], b[0], b[1], color=tint_g((61, 68, 88), dusk, night), width=2.5 * K)
    on = night > 0.25 + hash1(x * 7 + y) * 0.3
    ctx.circle(b[0], b[1], 4 * K, fill="#fff3c4" if on else tint_g((217, 217, 227), dusk, night))
    if on:
        ctx.glow(b[0], b[1], 10 * K, "#ffe08a", 0.9)
        ctx.glow(a[0], a[1], 30 * K, "#ffcf6b", 0.35)


def main_scene(ctx, t):
    global AZ, SC, CY
    dusk = clamp((t - 4.4) / 1.6, 0, 1)
    night = clamp((t - 5.9) / 1.6, 0, 1)
    sun = (-0.6, -0.35, 0.72)

    # 相机：开场 spring 落入 + 缓慢环绕 + 推近
    drop = spring_drop(t - 0.05)
    AZ = math.pi / 4 + ease_io((t - 3.2) / 6.8) * 0.55
    SC = 76.0 + 8.0 * ease_io((t - 2.0) / 8.0)
    CY = 585.0 + (1.0 - drop) * 900.0

    sky(ctx, t, dusk, night)
    draw_slab(ctx, dusk, night)
    draw_roads(ctx, t, dusk, night)

    # 收集全部物件（含深度），影子先画
    items = []
    for l in lots:
        sc = clamp((t - l["t0"]) / 0.55, 0, 1)
        if sc <= 0 or l["floors"] <= 0:
            continue
        pop = 1.0 + 0.12 * math.sin(min(1.0, sc) * math.pi) * (1 - sc)
        h = l["floors"] * FH * sc * pop
        items.append({"kind": "b", "l": l, "sc": sc, "h": h,
                      "fl": max(1, round(l["floors"] * min(sc * 1.4, 1))),
                      "ry": depth(l["x"] + l["w"] / 2, l["y"] + l["d"] / 2)})
    for (x, y, r, t0) in TREES:
        sc = clamp((t - t0) / 0.4, 0, 1.2)
        if sc > 0:
            items.append({"kind": "t", "x": x, "y": y, "r": r, "sc": sc, "ry": depth(x, y)})
    for (lx, ly) in LAMPS:
        items.append({"kind": "l", "x": lx, "y": ly, "ry": depth(lx, ly)})
    cars_on = clamp((t - 2.6) / 0.4, 0, 1)
    if cars_on > 0:
        for c in CARS:
            cc = car_pos(c, t)
            if cc:
                items.append({"kind": "c", "cc": cc, "on": cars_on,
                              "ry": depth((cc[0] + cc[2]) / 2, (cc[1] + cc[3]) / 2)})
    items.append({"kind": "f", "ry": depth(11.6, 1.8) + 0.2})

    # 影子：脚印 + 沿太阳反向投影的凸包
    sh_items = []
    for it in items:
        if it["kind"] == "b":
            l = it["l"]
            sh_items.append((l["x"] + 0.08, l["y"] + 0.08, l["x"] + l["w"] - 0.08,
                             l["y"] + l["d"] - 0.08, it["h"]))
        elif it["kind"] == "t":
            sh_items.append((it["x"] - it["r"], it["y"] - it["r"],
                             it["x"] + it["r"], it["y"] + it["r"], 0.5 * it["sc"]))
    draw_shadow(ctx, t, sh_items, sun)

    # 画家算法：远→近
    items.sort(key=lambda it: it["ry"])
    for it in items:
        if it["kind"] == "b":
            l = it["l"]
            box(ctx, l["x"] + 0.08, l["y"] + 0.08, 0, l["x"] + l["w"] - 0.08, l["y"] + l["d"] - 0.08,
                it["h"], l["col"], floors=it["fl"], seed=l["seed"], dusk=dusk, night=night)
            if l["tower"] and it["sc"] > 0.95:
                tip = P((l["x"] + (l["x"] + l["w"])) / 2, (l["y"] + (l["y"] + l["d"])) / 2, it["h"] + 0.9)
                base = P((l["x"] + (l["x"] + l["w"])) / 2, (l["y"] + (l["y"] + l["d"])) / 2, it["h"])
                ctx.line(base[0], base[1], tip[0], tip[1], color=tint_g((226, 226, 234), dusk, night), width=3 * K)
                if math.sin(t * 5) > 0:
                    ctx.glow(tip[0], tip[1], 9 * K, "#ff3b3b", 1.0)
        elif it["kind"] == "t":
            draw_tree(ctx, t, it["x"], it["y"], it["r"], it["sc"], dusk, night)
        elif it["kind"] == "l":
            draw_lamp(ctx, t, it["x"], it["y"], dusk, night)
        elif it["kind"] == "c":
            draw_car(ctx, it["cc"], dusk, night, it["on"])
        elif it["kind"] == "f":
            draw_ferris(ctx, t, dusk, night)


# === 配乐 ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    bar = spb * 4.0
    total_beats = duration / spb
    bars = int(math.ceil((duration - 2.4) / bar))

    PROG = (0, 4, 5, 3)
    MAJ = wa.resolve_scale("major")

    def chord_midi(deg):
        k = len(MAJ)
        return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.5)
    pad = s.track("pad", name="pad", gain_db=-16.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-11.0, pan=0.12, seed=2)
    bass = s.track("bass", name="bass", gain_db=-9.0, pan=0.0, seed=3)

    for bi in range(bars):
        b0 = bi * 4.0
        ch = chord_midi(PROG[bi % 4])
        for m in ch:
            pad.note(b0, name(m), 4.05, 0.5)
        for si, idx in enumerate((0, 1, 2, 1, 0, 1, 2, 1)):
            pluck.note(b0 + si * 0.5, name(ch[idx]), 0.55, 0.5)
        bass.note(b0, name(ch[0] - 24), 1.8, 0.75)
        bass.note(b0 + 2.0, name(ch[0] - 24), 1.8, 0.6)

    end = (duration - 2.4) / spb
    for m in (48, 60, 64, 67, 72):
        pad.note(end, name(m), (2.4 + 0.8) / spb, 0.7)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.5)
    return s


# === 影片：单场景（世界连续），快速运镜处帧用 ss 提高平滑 ===
film = wv.Film(W, H, duration=10.0, fps=30, ss=2, theme="midnight",
               bpm=120, name="isometric-city")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 10, transition="cut")
s1.draw(main_scene, at=0)
s1.text("一座城，十秒长出来", at=7.8, style="hero", y=180)
s1.text("ISOMETRIC CITY", at=8.3, style="subtitle", y=270)

# 音效 cues（三波楼 = bassdrop；日落后 riser；chime 收）
film.sfx("whoosh", at=0.35, gain=-8)
for tt in (1.0, 1.6, 2.2):
    film.sfx("bassdrop", at=tt, gain=-10)
film.sfx("riser", at=5.2, dur=1.0, gain=-12)
film.sfx("chime", at=6.4, gain=-9)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "isometric-city.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "isometric-city.sheet.png"))
