# -*- coding: utf-8 -*-
"""write-video — 风格渲染器（huashu-art-motion 移植 · 第一期 8 种）。

huashu 的画法：平涂底稿 → 渲染器把底稿当取色源整幅重画。移植为三步：

    arr, scale = styles.base(c, base_fn)        # 1. 底稿：离屏平涂（scale 倍分辨率）
    styles.dabs(c, arr, scale, cell=13)         # 2. 渲染器取色重画（整幅）
    #  c 上已有最终画面

第一期渲染器：dabs 印象派色点 / seurat 修拉点彩 / mosaic 镶嵌 / facets 立体主义切面 /
halftone 波普网点 / pixel8 像素 / ink 水墨 / watercolor 水彩洗染。

实现约定：
  * 渲染器画到离屏整幅 RGBA 层（成片分辨率），`c.paste_full` 贴回；
  * 全部确定性：每个格子的随机数来自本地 random.Random(seed)（huashu"稳定调色板"教训）；
  * 取色走 numpy 底稿（getpixel 逐点太慢），格网采样一次向量化完成。
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .canvas import Canvas, parse_color

# ---------------- 底稿采样基建 ----------------


def base(c, fn, scale=0.5, bg=(246, 244, 238)):
    """平涂底稿：新建 scale 倍离屏画布跑 fn(bc, t)（bc 是正常 Canvas，设计坐标），
    返回 (numpy arr h×w×3, scale)。渲染器用它取色。"""
    w = max(1, int(round(c.width * scale)))
    h = max(1, int(round(c.height * scale)))
    img = Image.new("RGB", (w, h), bg)
    bc = Canvas(img, ss=scale, width=c.width, height=c.height, ctx=c.ctx, aa=False)
    fn(bc, c.ctx.t)
    return np.asarray(img).astype(np.int16), scale


def sample(arr, scale, x, y):
    """底稿取色（设计像素坐标 → (r,g,b)）。"""
    h, w = arr.shape[:2]
    xx = int(min(max(x * scale, 0.0), w - 1))
    yy = int(min(max(y * scale, 0.0), h - 1))
    v = arr[yy, xx]
    return (int(v[0]), int(v[1]), int(v[2]))


def grid_samples(arr, scale, cell, w, h, jx=0.0, jy=0.0):
    """整幅格网中心采样（向量化）。返回 (rows, cols, 3) int16。jx/jy 为格内抖动比例。"""
    hh, ww = arr.shape[:2]
    cols = int(math.ceil(w / cell)) + 1
    rows = int(math.ceil(h / cell)) + 1
    gi = np.arange(cols) * (cell * scale)
    gj = np.arange(rows) * (cell * scale)
    if jx > 0 or jy > 0:
        rs = np.random.RandomState(12345)
        gi = gi + (rs.rand(cols) - 0.5) * cell * scale * jx
        gj = gj + (rs.rand(rows) - 0.5) * cell * scale * jy
    xi = np.clip(gi.astype(int), 0, ww - 1)
    yi = np.clip(gj.astype(int), 0, hh - 1)
    return arr[np.ix_(yi, xi)], cols, rows


def luma(px):
    return 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]


def _layer(c):
    """整屏离屏层（成片分辨率）。注意 "RGBA" 混合模式：多边形叠加而非替换。"""
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im, "RGBA"), float(c.ss)


def _bp(c, fps):
    """沸腾帧号（fps 换种子），fps<=0 返回 0（全静止）。"""
    return int(c.ctx.time * fps) if fps and fps > 0 else 0


def _clamp8(v):
    return int(max(0, min(255, v)))


# ---------------- 1. dabs 印象派色点 ----------------


def dabs(c, arr, scale, cell=13.0, len_k=0.95, wd_k=0.58, mix=26.0, ang=None,
         seed=0, boil_fps=0.0, alpha=1.0, jitter_pos=0.7):
    """印象派色点：冷暖偏移的椭圆短笔铺满（莫奈）。不是点彩——无纯色板、点不等大。

    ang(x, y, t) -> 弧度：可选方向场（墙竖、水横之类）；缺省随机角。
    """
    im, d, ss = _layer(c)
    bp = _bp(c, boil_fps)
    gs, cols, rows = grid_samples(arr, scale, cell, c.width, c.height, jitter_pos, jitter_pos)
    rng = random.Random(seed * 7919 + bp)
    a255 = int(255 * max(0.0, min(1.0, alpha)))
    half = cell * 0.5
    for j in range(rows):
        cy = (j + 0.5) * cell
        for i in range(cols):
            cx = (i + 0.5) * cell
            px, py = cx + (rng.random() - 0.5) * cell * jitter_pos, \
                cy + (rng.random() - 0.5) * cell * jitter_pos
            v = gs[j, i]
            r2 = _clamp8(int(v[0]) + mix * (rng.random() * 2 - 1))
            g2 = _clamp8(int(v[1]) + mix * 0.6 * (rng.random() * 2 - 1))
            b2 = _clamp8(int(v[2]) + mix * (rng.random() * 2 - 1))
            a = ang(px, py, c.ctx.time) if ang else rng.random() * math.pi
            ln = cell * len_k * (0.72 + rng.random() * 0.55)
            wd = max(2, int(round(cell * wd_k * (0.8 + rng.random() * 0.45) * ss)))
            dx, dy = math.cos(a) * ln * half / cell * 2 * ss, math.sin(a) * ln * half / cell * 2 * ss
            d.line([px * ss - dx, py * ss - dy, px * ss + dx, py * ss + dy],
                   fill=(r2, g2, b2, a255), width=wd)
    c.paste_full(im, alpha)


# ---------------- 2. seurat 修拉点彩 ----------------


SEURAT_PAL = ((72, 116, 178), (96, 168, 148), (222, 178, 76), (214, 96, 72),
              (120, 84, 148), (238, 226, 196), (52, 60, 96), (158, 196, 128),
              (140, 180, 222), (232, 164, 152))


def seurat(c, arr, scale, cell=10.0, palette=None, comp=True, halo=True,
           seed=0, alpha=1.0, boil_fps=0.0, under=True):
    """修拉点彩：纯色板等大圆点并置（视觉混色）；明暗交界补色点 + 光渗。

    under=True 先铺一遍低透明底色块（2×cell 粗格），避免纸色从点缝里漏出来。
    """
    pal = np.array(palette or SEURAT_PAL, dtype=np.int16)
    im, d, ss = _layer(c)
    bp = _bp(c, boil_fps)
    gs, cols, rows = grid_samples(arr, scale, cell, c.width, c.height)
    lumas = (0.299 * gs[:, :, 0] + 0.587 * gs[:, :, 1] + 0.114 * gs[:, :, 2])
    flat = gs.reshape(-1, 3).astype(np.int16)
    idx = np.abs(pal[None, :, :] - flat[:, None, :]).sum(axis=2).argmin(axis=1)
    idx = idx.reshape(rows, cols)
    rng = random.Random(seed * 6271 + bp)
    a255 = int(255 * max(0.0, min(1.0, alpha)))
    if under:
        uc = cell * 2.0
        for j in range(0, rows, 2):
            for i in range(0, cols, 2):
                v = gs[j, i]
                d.rectangle([(i * cell) * ss, (j * cell) * ss,
                             ((i + 2) * cell) * ss, ((j + 2) * cell) * ss],
                            fill=(int(v[0]), int(v[1]), int(v[2]), int(255 * 0.55 * a255)))
    rad = cell * 0.52 * ss
    for j in range(rows):
        cy = (j + 0.5) * cell
        for i in range(cols):
            cx = (i + 0.5) * cell
            pi = idx[j, i]
            col = tuple(int(v) for v in pal[pi])
            px = gs[j, i]
            d.ellipse([cx * ss - rad, cy * ss - rad, cx * ss + rad, cy * ss + rad],
                      fill=col + (a255,))
            lm = lumas[j, i]
            if (comp or halo) and 0 < j < rows - 1 and 0 < i < cols - 1:
                nb = (lumas[j, i + 1], lumas[j, i - 1], lumas[j + 1, i], lumas[j - 1, i])
                edge = max(nb) - min(nb)
                if edge > 56:
                    ox = 1 if nb[0] < nb[1] else (-1 if nb[0] > nb[1] else 0)
                    oy = 1 if nb[2] < nb[3] else (-1 if nb[2] > nb[3] else 0)
                    if comp and lm > 128:
                        cc = (int(255 - px[0] * 0.75), int(255 - px[1] * 0.75),
                              int(255 - px[2] * 0.55))
                        rr = rad * 0.5
                        d.ellipse([cx * ss + ox * cell * ss - rr, cy * ss + oy * cell * ss - rr,
                                   cx * ss + ox * cell * ss + rr, cy * ss + oy * cell * ss + rr],
                                  fill=cc + (int(a255 * 0.7),))
                    if halo and lm > 150:
                        rr = rad * 0.82
                        d.ellipse([cx * ss - rr, cy * ss - rr, cx * ss + rr, cy * ss + rr],
                                  fill=(250, 244, 214, int(a255 * 0.45)))
    c.paste_full(im, alpha)


# ---------------- 3. mosaic 镶嵌 ----------------


def mosaic(c, arr, scale, cell=22.0, grow=0.68, dark=0.84, var=16, grout=(232, 226, 212),
           seed=0, alpha=1.0, boil_fps=0.0, shine=0.16):
    """镶嵌：不规则石块铺满，块径略大于间距 → 邻块相切自然留出灰缝；缝隙露 grout 色。

    grow: 石块基础半径 = cell * grow（>0.5 才相互搭接出碎缝）。
    """
    im, d, ss = _layer(c)
    bp = _bp(c, boil_fps)
    g255 = grout + (int(255 * max(0.0, min(1.0, alpha))),)
    d.rectangle([0, 0, c.width * ss, c.height * ss], fill=g255)
    gs, cols, rows = grid_samples(arr, scale, cell, c.width, c.height)
    rng = random.Random(seed * 4231 + bp)
    for j in range(rows):
        for i in range(cols):
            cx, cy = (i + 0.5) * cell, (j + 0.5) * cell
            v = gs[j, i]
            dk = dark + (rng.random() - 0.5) * 0.12
            vr = (rng.random() * 2 - 1) * var
            col = (_clamp8(int(v[0]) * dk + vr), _clamp8(int(v[1]) * dk + vr),
                   _clamp8(int(v[2]) * dk + vr))
            base_r = cell * grow * (0.92 + rng.random() * 0.16)
            npt = 7
            pts = []
            for p in range(npt):
                aa = p / npt * math.pi * 2 + rng.random() * 0.5
                rr = base_r * (0.88 + rng.random() * 0.24)
                pts.append((cx * ss + math.cos(aa) * rr * ss, cy * ss + math.sin(aa) * rr * ss))
            d.polygon(pts, fill=col + (255,))
            if shine > 0:
                hi = (_clamp8(col[0] + 255 * shine), _clamp8(col[1] + 255 * shine),
                      _clamp8(col[2] + 255 * shine))
                d.line([pts[4][0], pts[4][1], pts[5][0], pts[5][1], pts[6][0], pts[6][1]],
                       fill=hi + (int(255 * 0.5),), width=max(1, int(1.5 * ss)))
    c.paste_full(im, alpha)


# ---------------- 4. facets 立体主义切面 ----------------


def facets(c, arr, scale, cell=74.0, a=0.88, lit=0.12, seed=0, alpha=1.0):
    """立体主义切面：网格逐格随机对角二分，半透明三角面叠出空间（毕加索/低多边形）。

    两批三角面分两层 alpha_composite——前层面透出后层面，空间感来自叠。
    """
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    la = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    da, db = ImageDraw.Draw(la), ImageDraw.Draw(lb)
    gs, cols, rows = grid_samples(arr, scale, cell, c.width, c.height, 0.2, 0.2)
    rng = random.Random(seed * 9137)
    fa = int(255 * max(0.0, min(1.0, a)) * max(0.0, min(1.0, alpha)))
    for j in range(rows):
        for i in range(cols):
            x0, y0 = i * cell, j * cell
            flip = rng.random() > 0.5
            tri = ([(x0, y0), (x0 + cell, y0), (x0 + cell, y0 + cell)]
                   if flip else [(x0, y0), (x0 + cell, y0), (x0, y0 + cell)])
            tri2 = ([(x0, y0), (x0 + cell, y0 + cell), (x0, y0 + cell)]
                    if flip else [(x0 + cell, y0), (x0 + cell, y0 + cell), (x0, y0 + cell)])
            for k, t3 in enumerate((tri, tri2)):
                cxx = sum(p[0] for p in t3) / 3.0 + (rng.random() - 0.5) * cell * 0.2
                cyy = sum(p[1] for p in t3) / 3.0 + (rng.random() - 0.5) * cell * 0.2
                v = gs[min(j + (0 if cyy < y0 + cell / 2 else 1), rows - 1),
                       min(i + (0 if cxx < x0 + cell / 2 else 1), cols - 1)]
                lk = 1.0 + (lit if (k == 0) != flip else -lit) * (0.6 + rng.random() * 0.8)
                col = (_clamp8(int(v[0]) * lk), _clamp8(int(v[1]) * lk), _clamp8(int(v[2]) * lk))
                (da if k == 0 else db).polygon([(p[0] * c.ss, p[1] * c.ss) for p in t3],
                                               fill=col + (fa,))
    c.paste_full(Image.alpha_composite(la, lb), alpha)


# ---------------- 5. halftone 波普网点 ----------------


def halftone(c, arr, scale, tile=15.0, ang_deg=45.0, ink_col=(24, 22, 34),
             color=False, posterize=4, seed=0, alpha=1.0, r_max=0.64):
    """波普网点：45° 旋转网格，点径 = 1 - 亮度；color=True 用底稿色（减色板）画彩点。"""
    im, d, ss = _layer(c)
    ang = math.radians(ang_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    diag = math.hypot(c.width, c.height)
    n_u = int(diag / tile) + 2
    n_v = n_u
    rr_max = tile * r_max * ss
    a255 = int(255 * max(0.0, min(1.0, alpha)))
    pal_n = max(2, int(posterize))
    kf = 255.0 / (pal_n - 1)
    for vi in range(-n_v // 2, n_v // 2 + 1):
        for ui in range(-n_u // 2, n_u // 2 + 1):
            ux, uy = ui * tile, vi * tile
            cx = c.width / 2 + ux * ca - uy * sa
            cy = c.height / 2 + ux * sa + uy * ca
            if -tile < cx < c.width + tile and -tile < cy < c.height + tile:
                r, g, b = sample(arr, scale, cx, cy)
                lm = luma((r, g, b)) / 255.0
                rad = rr_max * (1.0 - lm)
                if rad < 0.6 * ss:
                    continue
                if color:
                    col = (int(round(r / 255 * (pal_n - 1)) * kf),
                           int(round(g / 255 * (pal_n - 1)) * kf),
                           int(round(b / 255 * (pal_n - 1)) * kf))
                else:
                    col = ink_col
                d.ellipse([cx * ss - rad, cy * ss - rad, cx * ss + rad, cy * ss + rad],
                          fill=col + (a255,))
    c.paste_full(im, alpha)


# ---------------- 6. pixel8 像素 ----------------


PIXEL_PAL = ((28, 26, 40), (56, 48, 88), (96, 78, 140), (64, 120, 160), (88, 176, 168),
             (140, 200, 120), (222, 208, 120), (236, 160, 84), (208, 84, 72),
             (160, 52, 72), (240, 232, 214), (120, 108, 100), (200, 120, 150), (40, 90, 70))


def _bayer8():
    """8x8 Bayer 阈值阵（递归生成，归一到 [-0.5, 0.5)），有序抖动去色带。"""
    m = np.array([[0]], dtype=np.float64)
    while m.shape[0] < 8:
        m = np.block([[4 * m, 4 * m + 2.0], [4 * m + 3.0, 4 * m + 1.0]])
    return m / 64.0 - 0.5


# ---------------- 材质纹理 overlay ----------------

_TEX_CACHE = {"key": None, "tex": None}


def _fbm(h, w, seed, octaves=((3.0, 0.5), (9.0, 0.3), (28.0, 0.2))):
    """分形值噪声（白噪声 + 多尺度高斯模糊加权，确定性）。返回 (h, w) float32 0..1。"""
    rng = np.random.RandomState(seed)
    acc = np.zeros((h, w), dtype=np.float32)
    wsum = 0.0
    for radius, wt in octaves:
        n = rng.rand(h // 4 + 4, w // 4 + 4).astype(np.float32)
        im = Image.fromarray((n * 255).astype(np.uint8)).resize(
            (max(1, int(w * radius / 12)) or 1, max(1, int(h * radius / 12)) or 1),
            Image.BILINEAR).resize((w, h), Image.BILINEAR)
        acc += (np.asarray(im, dtype=np.float32) / 255.0) * wt
        wsum += wt
    return acc / wsum


def texture(c, kind="paper", strength=0.5, seed=0, boil_fps=0.0, mode="multiply",
            n=None):
    """材质纹理 overlay（画到当前画布上）：paper 宣纸/画布纹、rock 岩壁浮雕、
    crack 龟裂纹、drag 油画竖向拖笔（soft-light，霍珀）、brush 水粉长条刷痕
    （overlay，马蒂斯，n=笔痕数量，默认约 2600）。

    multiply/明暗合成保饱和（lighter/低 alpha 大面积会洗白底色——01_cave 火光踩坑）。
    boil_fps: 纹理按 N fps 沸腾（换种子重生成）；0 = 静态（缓存）。
    """
    t = getattr(getattr(c, "ctx", None), "t", 0.0) or 0.0
    step = int(t * boil_fps) if boil_fps > 0 else 0
    W2, H2 = c.img.size
    key = (kind, seed + step, W2, H2, n or 0)
    if _TEX_CACHE["key"] != key:
        _TEX_CACHE["key"] = key
        _TEX_CACHE["tex"] = _make_texture(kind, H2, W2, key[1], n)
    tex = _TEX_CACHE["tex"]
    a = np.asarray(c.img).astype(np.float32)
    if kind == "rock":
        gx = np.gradient(tex.astype(np.float32), axis=1)[0]
        gy = np.gradient(tex.astype(np.float32), axis=0)[0]
        shade = -(gx * 0.7 + gy * 0.7)
        shade = np.clip(shade * 3.0, -1.0, 1.0)
        a *= (1.0 + strength * shade)[..., None]
    elif kind == "crack":
        lines = np.clip(1.0 - np.abs(tex - 0.5) * 40.0, 0.0, 1.0)
        a *= (1.0 - strength * lines)[..., None]
    elif kind == "drag":
        top = np.clip(0.5 + (tex - 0.5) * min(1.0, strength * 2.2), 0.0, 1.0)
        a = _soft_light(a / 255.0, top) * 255.0
    elif kind == "brush":
        b = a / 255.0
        tt = np.clip(0.5 + (tex - 0.5) * min(1.0, strength * 4.0), 0.0, 1.0)[..., None]
        a = np.where(b < 0.5, 2.0 * b * tt, 1.0 - 2.0 * (1.0 - b) * (1.0 - tt)) * 255.0
    else:
        a *= (1.0 + strength * (tex - 0.5) * 0.6)[..., None]
    c.img.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), (0, 0))


def _soft_light(b, top):
    """soft-light 混合（b/top 均 0..1，top 可为单通道 (h,w)）。霍珀拖笔用：比 multiply 更轻。"""
    if top.ndim == 2:
        top = top[..., None]
    d = np.where(b <= 0.25, ((16.0 * b - 12.0) * b + 4.0) * b, np.sqrt(np.clip(b, 0.0, 1.0)))
    return np.where(top <= 0.5,
                    b - (1.0 - 2.0 * top) * b * (1.0 - b),
                    b + (2.0 * top - 1.0) * (d - b))


def _make_texture(kind, h, w, seed, n=None):
    if kind == "rock":
        tex = _fbm(h, w, seed, octaves=((2.0, 0.45), (7.0, 0.3), (22.0, 0.25)))
        return (tex - tex.min()) / max(1e-6, tex.max() - tex.min())
    if kind == "crack":
        tex = _fbm(h, w, seed, octaves=((6.0, 0.6), (18.0, 0.4)))
        tex = (tex - tex.min()) / max(1e-6, tex.max() - tex.min())
        return np.abs(tex - 0.5) * 2.0
    if kind == "drag":
        # 竖向拉长 fbm（x 高频 y 低频）为主、斜向为辅——霍珀的墙必须平，刷痕只能若有若无
        rs = np.random.RandomState(seed)
        nx, ny = max(2, w // 18), max(2, h // 140)
        n1 = Image.fromarray((rs.rand(ny, nx) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
        nx2, ny2 = max(2, w // 30), max(2, h // 30)
        n2 = Image.fromarray((rs.rand(ny2, nx2) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
        tex = np.asarray(n1, dtype=np.float32) * 0.85 + np.asarray(n2, dtype=np.float32) * 0.15
        tex = (tex - tex.min()) / max(1e-6, tex.max() - tex.min())
        return 0.5 + (tex - 0.5) * 0.8
    if kind == "brush":
        # 长条水粉刷痕：60-300px 长、6-22 宽、黑白各半、alpha 0.04-0.13、约 -0.25rad（马蒂斯）
        rng = np.random.RandomState(seed)
        kk = w / 1920.0
        cnt = int(n) if n else int(round(w * h / 800.0))
        im = Image.new("L", (w, h), 128)
        d = ImageDraw.Draw(im)
        for _ in range(cnt):
            ln = rng.uniform(60.0, 300.0) * kk
            wd = max(1.0, rng.uniform(6.0, 22.0) * kk)
            x0 = rng.uniform(-120.0 * kk, w + 120.0 * kk)
            y0 = rng.uniform(-60.0 * kk, h + 60.0 * kk)
            aa = -0.25 + rng.uniform(-0.35, 0.35)
            dx, dy = math.cos(aa) * ln * 0.5, math.sin(aa) * ln * 0.5
            v = 255.0 if rng.rand() < 0.5 else 0.0
            fill = int(128 + (v - 128.0) * rng.uniform(0.04, 0.13))
            d.line([x0 - dx, y0 - dy, x0 + dx, y0 + dy], fill=fill, width=int(wd))
        return np.asarray(im, dtype=np.float32) / 255.0
    n_ = np.random.RandomState(seed).rand(h, w).astype(np.float32)
    im = Image.fromarray((n_ * 255).astype(np.uint8))
    sx = im.resize((max(1, w // 6), h), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    sy = im.resize((w, max(1, h // 3)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    tex = (np.asarray(sx, dtype=np.float32) * 0.6 + np.asarray(sy, dtype=np.float32) * 0.4)
    return tex / 255.0


# ---------------- 深度模糊 DoF ----------------


def post_dof(img, depth="bottom", focus=0.5, max_coc=14.0, bands=6):
    """深度模糊（接 film.post）：按深度图分层 blur，越离焦越糊。

    depth: (h,w) 数组 0..1（0=焦点处，1=最远）或预设 "bottom"（下近上远）/ "top" / "center"（中心实四周虚）。
    focus: 焦点深度；max_coc: 最大弥散圆（像素）；bands: 分层数。
    """
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    if isinstance(depth, str):
        yy, xx = np.mgrid[0:h, 0:w]
        if depth == "bottom":
            d = 1.0 - yy / max(1, h - 1)          # 下近（深度 0）上远
        elif depth == "top":
            d = yy / max(1, h - 1)                # 上近下远
        else:
            d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 1.414
        depth = np.clip(d, 0.0, 1.0)
    else:
        depth = np.asarray(depth, dtype=np.float32)
    src = Image.fromarray(a.astype(np.uint8))
    acc = np.zeros_like(a, dtype=np.float32)
    wsum = np.zeros((h, w), dtype=np.float32)
    centers = np.linspace(0.0, 1.0, bands)
    bw = 1.6 / max(1, bands - 1)
    for dk in centers:
        r = max_coc * abs(float(dk) - focus)
        if r < 0.7:
            bl = np.asarray(src, dtype=np.float32)
        else:
            bl = np.asarray(src.filter(ImageFilter.GaussianBlur(radius=r)), dtype=np.float32)
        wk = np.exp(-((depth - dk) / bw) ** 2).astype(np.float32)
        acc += bl * wk[..., None]
        wsum += wk
    out = acc / np.maximum(wsum, 1e-6)[..., None]
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8))


def post_cinema(img, t, vignette=0.35, grain=0.035, ca=0.0, expo=1.0,
                contrast=1.0, sat=1.0, lift=(0.0, 0.0, 0.0), gain=(1.0, 1.0, 1.0),
                fps=30):
    """电影感后处理（接 film.post）：色散/曝光/对比/饱和/lift-gain 调色/暗角/确定性颗粒。

    grain 按帧号做种子（同一 t 永远同图）；ca 为色散强度（0 关，0.6 轻微）。
    """
    a = np.asarray(img).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    if ca > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        offx = np.round((xx - w * 0.5) / w * ca * 6.0).astype(np.int32)
        offy = np.round((yy - h * 0.5) / h * ca * 6.0).astype(np.int32)
        r = a[..., 0][np.clip(yy + offy, 0, h - 1), np.clip(xx - offx, 0, w - 1)]
        b = a[..., 2][np.clip(yy - offy, 0, h - 1), np.clip(xx + offx, 0, w - 1)]
        a = np.stack([r, a[..., 1], b], axis=-1)
    a = a * expo
    a = (a - 0.5) * contrast + 0.5
    if sat != 1.0:
        g = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        a = g[..., None] + (a - g[..., None]) * sat
    a = a * np.asarray(gain, dtype=np.float32) + np.asarray(lift, dtype=np.float32) * (1.0 - a)
    if vignette > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - w * 0.5) / w * 2.6) ** 2 + ((yy - h * 0.5) / h * 2.0) ** 2)
        a *= (1.0 - vignette * np.clip((d - 0.6) / 0.75, 0.0, 1.0))[..., None]
    if grain > 0:
        rng = np.random.RandomState(int(t * fps))
        a += (rng.rand(h, w, 1).astype(np.float32) - 0.5) * grain
    a += (np.random.RandomState(7).rand(h, w, 1).astype(np.float32) - 0.5) / 255.0
    return Image.fromarray((np.clip(a, 0.0, 1.0) * 255).astype(np.uint8))


def pixel8(c, arr, scale, cw=200, palette=None, alpha=1.0, dither=0.0, dither_mode="random",
           cycle=0):
    """8-bit：底稿降采样 + 最近色板量化 + 最近邻放大（240×135 情怀）。

    距离在 int32 里算：int16 平方会溢出回绕成负数，argmin 选中垃圾颜色。
    dither: 抖动强度（0-1）；dither_mode: "random"（随机去色带）/"ordered"（Bayer 有序，像素风渐变）。
    cycle: 调色板循环速度（每秒轮转几格，>0 时整幅色彩随 t 循环——瀑布/LED 流色）。
    """
    pal = np.array(palette or PIXEL_PAL, dtype=np.int32)
    cw = int(cw)
    ch = max(1, int(round(cw * c.height / c.width)))
    small = Image.fromarray(arr.astype(np.uint8)).resize((cw, ch), Image.BOX)
    sa = np.asarray(small).astype(np.int32).reshape(-1, 3)
    if dither > 0:
        if dither_mode == "ordered":
            B = _bayer8()[np.arange(ch)[:, None] % 8, np.arange(cw)[None, :] % 8]
            sa = sa + (B * 255 * dither).reshape(-1, 1).astype(np.int32)
        else:
            noise = (np.random.RandomState(7).rand(sa.shape[0], 1) - 0.5) * 255 * dither
            sa = sa + noise.astype(np.int32)
    dist = ((sa[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
    idx = dist.argmin(axis=1)
    if cycle > 0:
        ct = getattr(getattr(c, "ctx", None), "t", 0.0) or 0.0
        shift = int(ct * cycle) % len(pal)
        idx = (idx + shift) % len(pal)
    quant = pal[idx].reshape(ch, cw, 3).astype(np.uint8)
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    big = Image.fromarray(quant).resize((W, H), Image.NEAREST)
    if alpha < 0.996:
        big = big.convert("RGBA")
        big.putalpha(int(255 * alpha))
    c.paste_full(big, alpha)


# ---------------- 7. ink 水墨 ----------------


def ink(c, arr, scale, cell=9.0, thresh=172, wet=2.6, seed=0, alpha=1.0,
        ink_col=(30, 30, 38), ang=None, boil_fps=0.0):
    """水墨：纸为底，底稿暗部化墨——墨点短笔 + 飞白（淡处分丝）+ 墨晕（糊层垫底）。

    底稿应画成"素描"：亮部留白（>= thresh 不出墨），形用明暗塑造。
    """
    rng = random.Random(seed * 3571 + bp_seed(seed, boil_fps, c))
    gs, cols, rows = grid_samples(arr, scale, cell, c.width, c.height)
    lumas = (0.299 * gs[:, :, 0] + 0.587 * gs[:, :, 1] + 0.114 * gs[:, :, 2])
    # 墨层画在设计分辨率（墨晕靠 paste_full 上采样放大，快且更润）
    W, H = int(round(c.width)), int(round(c.height))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    a255 = int(255 * max(0.0, min(1.0, alpha)))
    for j in range(rows):
        cy = (j + 0.5) * cell
        for i in range(cols):
            cx = (i + 0.5) * cell
            lm = lumas[j, i]
            if lm >= thresh:
                continue
            dark = (thresh - lm) / thresh
            aa = ang(cx, cy, c.ctx.time) if ang else rng.random() * math.pi
            ln = cell * (0.9 + rng.random() * 0.8)
            dx, dy = math.cos(aa) * ln * 0.5, math.sin(aa) * ln * 0.5
            al = int(255 * min(1.0, dark * 2.2) * 0.92)
            col = ink_col + (int(al * a255 / 255),)
            if dark < 0.42:
                # 飞白：淡处分 2-3 丝，丝间留缝
                n = 2 + (1 if rng.random() > 0.6 else 0)
                for k in range(n):
                    off = (k - (n - 1) / 2.0) * cell * 0.36
                    ox, oy = -math.sin(aa) * off, math.cos(aa) * off
                    d.line([cx - dx + ox, cy - dy + oy, cx + dx + ox, cy + dy + oy],
                           fill=col, width=max(1, int(cell * 0.17)))
            else:
                d.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=col,
                       width=max(2, int(cell * (0.4 + dark * 0.6))))
    wet_im = im.filter(ImageFilter.GaussianBlur(wet))
    c.paste_full(wet_im, 0.5 * alpha)
    c.paste_full(im, 0.92 * alpha)


def bp_seed(seed, boil_fps, c):
    return seed * 3571 + _bp(c, boil_fps)


# ---------------- 8. watercolor 水彩洗染 ----------------


def watercolor(c, arr, scale, cell=50.0, passes=3, a0=0.36, seed=0, edge=0.10,
               alpha=1.0, boil_fps=0.0):
    """水彩洗染：大色块透明叠色（多遍错位，跨 pass alpha_composite）+ 水痕边。
    吉卜力背景。"""
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    bp = _bp(c, boil_fps)
    rng = random.Random(seed * 2543 + bp)
    a255 = max(0.0, min(1.0, alpha))
    gs, cols, rows = grid_samples(arr, scale, cell, c.width, c.height, 0.3, 0.3)
    npt = 18
    acc = None
    for pasi in range(passes):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        joff = 0.5 * (pasi % 2)
        for j in range(rows):
            for i in range(cols):
                cx = (i - 0.5 + (0.5 if pasi % 2 else 0.0)) * cell + (rng.random() - 0.5) * cell * 0.3
                cy = (j - 0.5 + joff) * cell + (rng.random() - 0.5) * cell * 0.3
                v = gs[min(j + pasi % 2, rows - 1), min(i, cols - 1)]
                r, g, b = int(v[0]), int(v[1]), int(v[2])
                base_r = cell * (0.66 + rng.random() * 0.2)
                pts = []
                for p in range(npt):
                    aa = p / npt * math.pi * 2
                    rr = base_r * (0.82 + rng.random() * 0.36)
                    pts.append(((cx + math.cos(aa) * rr) * c.ss, (cy + math.sin(aa) * rr) * c.ss))
                pa = int(255 * a0 * a255)
                d.polygon(pts, fill=(r, g, b, pa))
                if edge > 0:
                    ea = int(255 * edge * a255)
                    dk = (int(r * 0.62), int(g * 0.62), int(b * 0.66), ea)
                    d.line([pts[-1][0], pts[-1][1]] + [v2 for p in pts for v2 in p],
                           fill=dk, width=max(1, int(2.2 * c.ss)), joint="curve")
        acc = lay if acc is None else Image.alpha_composite(acc, lay)
    c.paste_full(acc, alpha)


# ---------------- 9. VHS 后期（蒸汽波/录像带） ----------------


def post_vhs(img, t, fps=30, shift=3.0, shift_wob=1.5, tear=True, scan=0.22,
             noise=0.07, track_h=70, track_speed=520, chroma=3.5):
    """VHS 录像带后期（huashu 26_vaporwave / sy 12-synthwave 融合）：RGB 通道分离 +
    跟踪噪声带 + 扫描线 + 噪点。确定性（按帧号种子）。

    shift: RGB 错位基础量（px）；shift_wob: 正弦摆幅；chroma: 色度溢出通道错位；
    tear: 跟踪噪声带（下滚撕扯）；scan: 扫描线强度；noise: 噪点强度。
    """
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    # RGB 通道分离（错位量随时间摆动 + 偶发跳变）
    rng = np.random.RandomState(int(t * fps))
    wob = shift + shift_wob * math.sin(7.0 * t)
    if rng.rand() < 0.12:
        wob += 6.0
    ox = int(round(wob))
    r = np.roll(a[..., 0], ox, axis=1)
    b = np.roll(a[..., 2], -ox, axis=1)
    out = np.stack([r, a[..., 1], b], axis=-1)
    # 色度溢出：通道再错位 + 水平糊（亮度保持锐利）
    if chroma > 0:
        cx = int(round(chroma))
        cr = np.roll(out[..., 0], cx, axis=1)
        cb = np.roll(out[..., 2], -cx, axis=1)
        out = np.stack([cr, out[..., 1], cb], axis=-1)
        im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        im = im.filter(ImageFilter.GaussianBlur(3.0))
        out = out * 0.65 + np.asarray(im, dtype=np.float32) * 0.35
    # 跟踪噪声带（下滚撕扯）
    if tear:
        band_y = (track_speed * t + 200) % (h + 160) - 80
        band = np.exp(-(((yy - band_y) / (track_h * 0.5)) ** 2))
        xs = np.clip(xx - (np.sin(np.pi * (yy - band_y) / track_h) * 30 * band).astype(np.int32),
                     0, w - 1)
        out = np.take_along_axis(out, xs[..., None].repeat(3, axis=2), axis=1)
        out += band[..., None] * (rng.rand(h, w, 1).astype(np.float32) - 0.5) * 90
    # 扫描线
    if scan > 0:
        sl = np.where(yy % 4 == 0, 1.0 - scan, np.where(yy % 4 == 2, 1.0 - scan * 0.45, 1.0))
        out *= sl[..., None]
    # 噪点
    if noise > 0:
        out += (rng.rand(h, w, 1).astype(np.float32) - 0.5) * 255 * noise
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------- 10. 泛光 bloom ----------------


def post_bloom(img, strength=0.6, threshold=0.75, radius=12.0, second=2.0):
    """泛光（shinkai/synthwave 的 glow）：亮部提取 → 两级高斯 → screen 回叠。

    strength: 辉光强度；threshold: 亮度阈值（0-1）；radius/second: 两级模糊半径。
    """
    a = np.asarray(img).astype(np.float32) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bright = np.clip((lum - threshold) / max(0.05, 1.0 - threshold), 0.0, 1.0)
    src = Image.fromarray((np.clip(a * bright[..., None], 0, 1) * 255).astype(np.uint8))
    b1 = np.asarray(src.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0
    b2 = np.asarray(src.filter(ImageFilter.GaussianBlur(radius * second)), dtype=np.float32) / 255.0
    glow = (b1 * 0.55 + b2 * 0.8) * strength
    out = 1.0 - (1.0 - np.clip(a, 0, 1)) * (1.0 - np.clip(glow, 0, 1))   # screen
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


# ---------------- 11. flowLines 流场长笔（蒙克/梵高） ----------------


def flowlines(c, arr, scale, cell=24.0, steps=26, step=7.0, width=9.0, a=0.78,
              field=None, classify=None, params=None, outline=0.0,
              outline_col=(58, 46, 102), mix=0.0, palette=None,
              seed=0, boil_fps=8.0, alpha=1.0):
    """流场长笔（huashu munch/postimp）：抖动网格种子沿方向场积分成 200-300px 长笔，
    越出本区域即停（区域边界干净），8fps 沸腾换种子。

    蒙克=薄涂不描边（outline=0，a 0.5-0.8；底下先铺同色系平涂，笔缝露出来的是同色）；
    梵高=厚涂描边（outline 0.8-0.9，笔色混 40% 深蓝）。
    field: f(x, y, t)->弧度（默认 0.55·sin(x·.011+y·.018-2.4t) 水平扭动）；
    classify: f(x, y)->区域 key 或 None（None 跳过该笔）；
    params: {key: dict(steps=, step=, width=, a=, field=, palette=)}——墙/地/其余必须分遍参数，
    全图同参数会糊成地毯（postimp 坑）；palette 可按区域给不同色板（区域色板十几种色相才有梵高味）；
    小物件拆到道具层单独画，别被大笔打碎。
    """
    t = getattr(getattr(c, "ctx", None), "time", 0.0) or 0.0
    rng = random.Random(bp_seed(seed, boil_fps, c))
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    if field is None:
        field = lambda x, y, tt: 0.55 * math.sin(x * 0.011 + y * 0.018 - 2.4 * tt)
    cols = int(c.width / cell) + 2
    rows = int(c.height / cell) + 2
    k = c.ss
    pms = params or {}
    for j in range(rows):
        for i in range(cols):
            x = (i + 0.5 + (rng.random() - 0.5) * 0.9) * cell
            y = (j + 0.5 + (rng.random() - 0.5) * 0.9) * cell
            if classify is not None:
                key = classify(x, y)
                if key is None:
                    continue
                p = pms.get(key, {})
            else:
                p = {}
            st = p.get("steps", steps)
            sp = p.get("step", step)
            wd = p.get("width", width)
            av = p.get("a", a)
            fld = p.get("field", field)
            pal = p.get("palette", palette)
            if isinstance(pal, dict):
                pal = pal.get(key)
            if pal and isinstance(pal[0], str):
                pal = [parse_color(v) for v in pal]
            r, g, b = sample(arr, scale, x, y)
            if mix > 0 and pal:
                pr, pg, pb = pal[rng.randrange(len(pal))]
                mm = min(1.0, mix * (0.7 + 0.6 * rng.random()))
                r, g, b = int(r + (pr - r) * mm), int(g + (pg - g) * mm), int(b + (pb - b) * mm)
            pts = [(x, y)]
            cx, cy = x, y
            for _ in range(st + rng.randint(0, 8)):
                av2 = fld(cx, cy, t)
                cx += math.cos(av2) * sp
                cy += math.sin(av2) * sp
                if cx < -cell or cy < -cell or cx > c.width + cell or cy > c.height + cell:
                    break
                if classify is not None and classify(cx, cy) != key:
                    break
                pts.append((cx, cy))
            pix = [(px * k, py * k) for px, py in pts]
            wpx = max(1, int(round(wd * k)))
            al = int(255 * min(1.0, av) * min(1.0, alpha))
            if outline > 0:
                oc = (int(r * (1.0 - outline) + outline_col[0] * outline),
                      int(g * (1.0 - outline) + outline_col[1] * outline),
                      int(b * (1.0 - outline) + outline_col[2] * outline))
                d.line(pix, fill=oc + (al,), width=wpx + max(2, int(2 * k)), joint="curve")
            d.line(pix, fill=(r, g, b, al), width=wpx, joint="curve")
    c.paste_full(im)


# ---------------- 12. 整幅行列位移（蒙克「整个世界在流动」） ----------------


def post_warp(img, t, row_amp=(9.0, 4.0), row_f=(0.012, 0.031), col_amp=6.0,
              col_f=0.009, speed=1.0):
    """整幅行列正弦位移（huashu munch）：按行水平位移 + 按列竖直位移，
    人、猫、桌都会一起晃，比单独画摇摆的线便宜得多。接 film.post。

    行位移基准配方 9·sin(y·.012+4.2t)+4·sin(y·.031-6t)，列位移 6·sin(x·.009-3.6t)；
    row_amp/row_f/col_amp/col_f 可调；speed: 时间倍率。
    边缘钳位拉伸（每行多出来的量由边缘像素补），位移后不露黑边。
    """
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    ys = np.arange(h, dtype=np.float32)
    xs = np.arange(w, dtype=np.float32)
    dx = (row_amp[0] * np.sin(ys * row_f[0] + 4.2 * speed * t)
          + row_amp[1] * np.sin(ys * row_f[1] - 6.0 * speed * t))
    xi = np.clip(np.round(xs[None, :] + dx[:, None]), 0, w - 1).astype(np.int32)
    out = a[np.arange(h)[:, None], xi]
    dy = col_amp * np.sin(xs * col_f - 3.6 * speed * t)
    yi = np.clip(np.round(ys[:, None] + dy[None, :]), 0, h - 1).astype(np.int32)
    out = out[yi, np.arange(w)[None, :]]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------- 13. 金色度遮罩（哥特泥金/克里姆特） ----------------

_GOLD_CACHE = {"key": None, "fbm": None, "pol": None}


def post_gold(img, t, recolor=0.0, sweep=0.0, sweep_t0=0.0, sweep_dur=1.15,
              mask=None, bright=0.0, lo=(156, 106, 26), mid=(217, 166, 58),
              hi=(248, 222, 134), glint=0, seed=0, ang=0.45, band_w=0.18,
              band_a=0.62):
    """金色度遮罩（huashu gothic/klimt）：逐像素识别金色——
    clamp((r-b-70)/50)·clamp((g-b-30)/40)·clamp((r-140)/40) 连乘当 alpha，
    羊皮纸 r-b 只有 42 自动排除；凡金色的地方都会自动被高光扫到，不用再画金色形状。接 film.post。

    recolor: 金箔重着色强度（f = 0.42 + fbm·0.5 + 横向打磨纹·0.45，lo/mid/hi 三色插值，
             打磨纹 y 频率是 x 的 20 倍以上 = 横向金属拉丝）；
    sweep: 斜向匀速扫光强度（斜率 ang，sweep_t0 起 sweep_dur 秒从左扫到右——
           inOut 缓动会提前扫出金区，必须匀速）；band_w: 带宽（归一）；band_a: 峰值强度。
    mask: 显式遮罩 (h,w) 0..1；bright>0 时改用亮度阈值遮罩（亮部当金）。
    glint: 遮罩内四角星闪烁数量（klimt 金粉；星星半径别超过 s·(0.6+1.1a)，太大会像圣诞装饰）。
    """
    a = np.asarray(img).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    r8, g8, b8 = a[..., 0], a[..., 1], a[..., 2]
    if mask is not None:
        m = np.asarray(mask, dtype=np.float32)
        if m.shape != (h, w):
            m = np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))
                           .resize((w, h), Image.BILINEAR), dtype=np.float32) / 255.0
        m = np.clip(m, 0.0, 1.0)
    elif bright > 0:
        lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        m = np.clip((lum - bright) / max(0.05, 1.0 - bright), 0.0, 1.0)
    else:
        m = (np.clip((r8 - b8) * 255.0 - 70.0, 0.0, 50.0) / 50.0
             * np.clip((g8 - b8) * 255.0 - 30.0, 0.0, 40.0) / 40.0
             * np.clip(r8 * 255.0 - 140.0, 0.0, 40.0) / 40.0)
    if recolor > 0:
        key = (h, w, seed)
        if _GOLD_CACHE["key"] != key:
            _GOLD_CACHE["key"] = key
            _GOLD_CACHE["fbm"] = _fbm(h, w, seed + 11)
            rs = np.random.RandomState(seed + 23)
            pol = Image.fromarray((rs.rand(h, max(2, w // 24)) * 255).astype(np.uint8))
            _GOLD_CACHE["pol"] = np.asarray(pol.resize((w, h), Image.BILINEAR),
                                            dtype=np.float32) / 255.0
        f = np.clip(0.42 + (_GOLD_CACHE["fbm"] - 0.5) * 0.5
                    + (_GOLD_CACHE["pol"] - 0.5) * 0.45, 0.0, 1.0)
        loa = np.asarray(lo, dtype=np.float32) / 255.0
        mia = np.asarray(mid, dtype=np.float32) / 255.0
        hia = np.asarray(hi, dtype=np.float32) / 255.0
        c1 = loa[None, None, :] + (mia - loa)[None, None, :] * np.clip(f / 0.5, 0, 1)[..., None]
        c2 = mia[None, None, :] + (hia - mia)[None, None, :] * np.clip((f - 0.5) / 0.5, 0, 1)[..., None]
        gold_rgb = np.where((f < 0.5)[..., None], c1, c2)
        mm = m * recolor
        a = a * (1.0 - mm)[..., None] + gold_rgb * mm[..., None]
    if sweep > 0:
        u = min(1.0, max(0.0, (t - sweep_t0) / max(0.01, sweep_dur)))
        span = w * ang + h
        s = (np.arange(w, dtype=np.float32)[None, :] * ang
             + np.arange(h, dtype=np.float32)[:, None]) / span
        cpos = -0.15 + u * 1.3
        g = np.exp(-(((s - cpos) / max(0.02, band_w * 0.5)) ** 2))
        a = a + (g * m * sweep * band_a)[..., None] * np.array([1.0, 0.93, 0.72], dtype=np.float32)
    out = Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8))
    if glint > 0:
        rng = np.random.RandomState(seed + 77)
        pts = []
        tries = 0
        while len(pts) < glint and tries < glint * 30:
            tries += 1
            x = int(rng.randint(0, w))
            y = int(rng.randint(0, h))
            if m[y, x] > 0.3:
                pts.append((x, y, rng.rand() * 6.283, 7.0 + rng.rand() * 12.0))
        ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for x, y, ph, s_ in pts:
            pu = max(0.0, math.sin(6.283 * t * 0.85 + ph))
            al = pu ** 3
            if al < 0.06:
                continue
            col = (255, 244, 200, int(230 * al))
            d.line([x - s_, y, x + s_, y], fill=col, width=1)
            d.line([x, y - s_, x, y + s_], fill=col, width=1)
            d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=col)
        out = Image.alpha_composite(out.convert("RGBA"), ov).convert("RGB")
    return out


# ---------------- 14. 皮影皮件（刻纹 + 印染透光） ----------------


def _erode_mask(im, px):
    px = max(1, int(round(px)))
    if px >= 12:
        small = im.resize((max(2, im.width // 4), max(2, im.height // 4)), Image.BILINEAR)
        small = small.filter(ImageFilter.MinFilter(min(31, max(3, px // 4)) | 1))
        return small.resize(im.size, Image.BILINEAR)
    return im.filter(ImageFilter.MinFilter(px | 1))


def _dilate_mask(im, px):
    px = max(1, int(round(px)))
    if px >= 12:
        small = im.resize((max(2, im.width // 4), max(2, im.height // 4)), Image.BILINEAR)
        small = small.filter(ImageFilter.MaxFilter(min(31, max(3, px // 4)) | 1))
        return small.resize(im.size, Image.BILINEAR)
    return im.filter(ImageFilter.MaxFilter(px | 1))


def leather(c, shape, col, carve=None, edge=6.0, border=(58, 22, 10), bw=2.6,
            shadow=(0.28, 6.0, (7.0, 5.0))):
    """皮影皮件（huashu shadowpuppet）：剪影 → 刻纹（离皮边 2×edge 自动护住，刻不穿外轮廓）
    → 深褐描边 → 偏移软影 + multiply 印染到幕布（透光 = 幕布色 × 皮色，重叠皮件自然变深）。

    shape: f(d, k) 在透明离屏画白色剪影（d=ImageDraw，设计坐标乘 k=c.ss）；
    carve: f(d, k) 画刻纹（白色=刻掉：鱼子纹 dots/团花 flowers/云纹螺旋/方格 lattice/刻线 lines）；
    col: 皮色（印染色）；edge: 刻纹离皮边距离（设计 px）；bw: 深褐描边宽；
    shadow: (强度, 模糊, 偏移) 幕布上的虚影——皮件没完全贴紧幕布。
    坑：multiply 重叠变深是对的，但别把重叠放在视觉焦点上（桌腿压裙子=黑块）；
    白色部位（白胸/白爪）= 整块镂空只留皮边，另起一件 carve 全刻。
    """
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    k = c.ss
    sil = Image.new("L", (W, H), 0)
    shape(ImageDraw.Draw(sil), k)
    sil = sil.filter(ImageFilter.GaussianBlur(0.6))
    sil_a = np.asarray(sil, dtype=np.float32) / 255.0
    if sil_a.max() < 0.01:
        return
    sil_im = Image.fromarray((sil_a * 255).astype(np.uint8))
    dye = np.asarray(col, dtype=np.float32) / 255.0
    if carve is not None:
        cav = Image.new("L", (W, H), 0)
        carve(ImageDraw.Draw(cav), k)
        cav_a = np.asarray(cav.filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32) / 255.0
        keep = np.asarray(_erode_mask(sil_im, 2.0 * edge * k), dtype=np.float32) / 255.0
        piece_a = np.clip(sil_a * (1.0 - cav_a * keep), 0.0, 1.0)
    else:
        piece_a = sil_a
    bwp = max(1.5, bw * k)
    outer = np.asarray(_dilate_mask(sil_im, bwp * 0.5), dtype=np.float32) / 255.0
    inner = np.asarray(_erode_mask(sil_im, bwp * 0.5), dtype=np.float32) / 255.0
    ring = np.clip(outer - inner, 0.0, 1.0)
    A = np.maximum(piece_a, ring)
    bcol = np.asarray(border, dtype=np.float32) / 255.0
    mixr = np.clip(ring / np.maximum(A, 1e-5), 0.0, 1.0)[..., None]
    rgb = dye[None, None, :] * (1.0 - mixr) + bcol[None, None, :] * mixr
    bg = np.asarray(c.img).astype(np.float32) / 255.0
    if shadow is not None:
        sk, sblur, (sdx, sdy) = shadow
        shim = Image.fromarray((np.roll(np.roll(piece_a, int(sdy * k), axis=0),
                                        int(sdx * k), axis=1) * 255).astype(np.uint8))
        sh_a = np.asarray(shim.filter(ImageFilter.GaussianBlur(max(0.5, sblur * k))),
                          dtype=np.float32) / 255.0
        bg = bg * (1.0 - (sk * sh_a * 0.88)[..., None])
    mp = A[..., None]
    bg = bg * (1.0 - mp) + bg * rgb * mp
    c.img.paste(Image.fromarray(np.clip(bg * 255.0, 0, 255).astype(np.uint8)), (0, 0))


# ---------------- 15. 达利软钟 + 剪切仿射长影 ----------------


def softclock(c, cx, cy, r=88.0, sag=0.8, fold=-34.0, flare=-0.12, t=None,
              hand_speed=5.0, frame_col=(240, 210, 124), face_col=(246, 239, 214),
              mark_col=(154, 116, 38), alpha=1.0):
    """软钟（huashu dali《记忆的永恒》）：圆盘局部坐标 (u,v) 沿映射采样到屏幕——
    v<=fold 躺在台面上（y 压缩 0.30），v>fold 垂下：X 外摊（flare<0 像软布往外摊开，
    正值收成冰淇淋筒）、中央下垂高斯 + sin 波纹。外框、表盘、刻度、指针、折线高光都走同一个映射。

    cx/cy: 钟挂在边沿的接触点（局部原点）；r: 半径；sag: 下垂程度（1.2s 内 0.1→1.4 才看得出淌）；
    fold: 折叠位置（负值=大部分垂下）；t: 指针时刻（默认画布时间）；hand_speed: 分针 rad/s。
    """
    tt = t if t is not None else getattr(getattr(c, "ctx", None), "time", 0.0) or 0.0

    def mp(u, v):
        if v <= fold:
            return (cx + u, cy + v * 0.30)
        d = v - fold
        q = min(1.0, d / (2.0 * r))
        grow = 1.0 - flare * q
        settle = min(1.0, d / max(1.0, r))
        x = cx + u * grow
        y = (cy + fold * 0.30 + d * (0.62 + 0.30 * sag)
             + r * 0.5 * sag * math.exp(-(u / (r * 0.55)) ** 2) * settle
             + r * 0.05 * math.sin(u / r * 2.4 + sag * 2.5) * settle)
        return (x, y)

    ring = [mp(r * math.cos(a2), r * math.sin(a2)) for a2 in
            [i / 36.0 * 6.2832 for i in range(37)]]
    face = [mp(r * 0.80 * math.cos(a2), r * 0.80 * math.sin(a2)) for a2 in
            [i / 28.0 * 6.2832 for i in range(29)]]
    c.polygon(ring, fill=frame_col, alpha=alpha)
    c.polygon(face, fill=face_col, alpha=alpha)
    for i in range(12):
        a2 = i / 12.0 * 6.2832
        p1 = mp(r * 0.58 * math.cos(a2), r * 0.58 * math.sin(a2))
        p2 = mp(r * 0.72 * math.cos(a2), r * 0.72 * math.sin(a2))
        c.line(p1[0], p1[1], p2[0], p2[1], color=mark_col,
               width=max(1.5, r * 0.045), alpha=alpha)
    for a2, ln in ((tt * hand_speed, 0.52), (tt * hand_speed / 12.0, 0.36)):
        pts = []
        for s in range(9):
            u = math.cos(a2) * r * ln * s / 8.0
            v = math.sin(a2) * r * ln * s / 8.0
            pts.append(mp(u, v))
        c.lines(pts, color=mark_col, width=max(2.0, r * 0.06), alpha=alpha)
    hl = [mp(-r * 0.62 + r * 1.24 * i / 6.0, fold + r * 0.06) for i in range(7)]
    c.lines(hl, color=(255, 246, 200), width=max(1.5, r * 0.035), alpha=alpha * 0.7)


def longshadow(c, sils, yg, kx=0.85, ky=0.55, alpha=0.55, blur=1.5,
               horizon=None, col=(15, 18, 30)):
    """剪切仿射长影（huashu dali）：物体剪影投到着地线 yg——
    x' = x + kx·(yg-y)，y' = yg - ky·(yg-y)（影子往右后方躺，压向地面透视）。

    sils: f(d, k) 或 [f(d, k), ...]，在离屏画白色剪影（同一张离屏，重叠处不加深）；
    yg: 着地线（设计 px，墙 0.65h、桌 0.84h、人 0.86h 一类）；horizon: 只留 y>horizon 的地面部分；
    kx: 剪切（0.85+0.6·easeInOut(lt/1.2) 影子在 1.2s 里明显变长）；ky: 纵向压缩（<1）。
    坑：影子往观众方向投（ky>0 向下拉伸）全被画框底边吃掉——太阳放左前方低空，往右后方躺。
    """
    if callable(sils):
        sils = [sils]
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    k = c.ss
    sil = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(sil)
    for fn in sils:
        fn(d, k)
    ygp = yg * k
    a, b = 1.0, kx / ky
    cc_, dd, e, f = -(kx / ky) * ygp, 0.0, 1.0 / ky, ygp * (1.0 - 1.0 / ky)
    warped = sil.transform((W, H), Image.AFFINE, (a, b, cc_, dd, e, f), resample=Image.BILINEAR)
    if blur > 0:
        warped = warped.filter(ImageFilter.GaussianBlur(blur * k))
    sh = np.asarray(warped, dtype=np.float32) / 255.0
    if horizon is not None:
        hp = max(0, min(H, int(horizon * k)))
        sh[:hp, :] = 0.0
    aa = alpha * sh
    bg = np.asarray(c.img).astype(np.float32) / 255.0
    colv = np.asarray(col, dtype=np.float32) / 255.0
    out = bg * (1.0 - aa[..., None]) + colv[None, None, :] * aa[..., None]
    c.img.paste(Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8)), (0, 0))


# ---------------- 16. 庞贝马赛克（Hausner 简化版） ----------------


def roman(c, arr, scale, cell=12.0, grout=(112, 103, 92), edge_thresh=34.0,
          small=0.5, jitter=0.06, bevel=2.2, seed=0, alpha=1.0, edge_cap=3500):
    """庞贝马赛克（huashu 04_roman，Hausner 2001 简化版）：灰浆打底 → 半错位网格旋转方块石
    （四条半边独立 0.94-1.06 抖动 + 旋转 ±0.06rad，缝宽 g..g+0.12s 不规则）→
    沿轮廓小石行（底稿相邻 RGB 差 > edge_thresh 的边缘上铺 small 倍小石，朝向沿等值线切向）
    → 斜面明暗（上左亮 +16%/下右暗 -16%，离边 2.2px）。

    底稿要平涂+粗描边；石块颜色取自底稿（±8% 乘性抖动 + 7% 压暗 + 9% 偏暖 + 7% 偏冷 + ±7 加性灰）。
    坑：马赛克文字/脸=等宽粗笔画（每笔约 2 块石头宽），Cinzel 细横笔在 7px 石块下会断；
    小于 3 块石头宽的道具在固定布局里读不出来，做成随手移动的嵌片。
    """
    rng = random.Random(seed * 977 + 41)
    W = max(1, int(round(c.width * c.ss)))
    H = max(1, int(round(c.height * c.ss)))
    k = c.ss
    s = cell * k
    g = min(1.25, max(0.75, 0.1 * cell)) * k
    lay = Image.new("RGBA", (W, H), tuple(grout) + (int(255 * min(1.0, alpha)),))
    d = ImageDraw.Draw(lay, "RGBA")
    grout_n = (rng.randint(-8, 8), rng.randint(-8, 8), rng.randint(-8, 8))
    gc = tuple(max(0, min(255, grout[i] + grout_n[i])) for i in range(3))

    def stone(cx, cy, half_base, rot, colv):
        ca, sa = math.cos(rot), math.sin(rot)
        hs = []
        pts = []
        for i2, (ux, uy) in enumerate(((1, -1), (1, 1), (-1, 1), (-1, -1))):
            h = half_base[i2]
            lx, ly = ux * h, uy * h
            pts.append((cx + (lx * ca - ly * sa), cy + (lx * sa + ly * ca)))
        d.polygon(pts, fill=colv)
        if bevel > 0 and half_base[0] > 4.0:
            bw = max(1, int(round(bevel * k)))
            lit = tuple(min(255, int(v * 1.16)) for v in colv[:3]) + (colv[3],)
            dkb = tuple(int(v * 0.84) for v in colv[:3]) + (colv[3],)
            d.line([pts[0], pts[1]], fill=lit, width=bw)
            d.line([pts[3], pts[0]], fill=lit, width=bw)
            d.line([pts[1], pts[2]], fill=dkb, width=bw)
            d.line([pts[2], pts[3]], fill=dkb, width=bw)

    cols = int(math.ceil(W / s)) + 1
    rows = int(math.ceil(H / s)) + 1
    for j in range(rows):
        off = 0.5 * s if j % 2 else 0.0
        for i in range(cols):
            cx = (i + 0.5) * s + off + (rng.random() - 0.5) * s * 0.18
            cy = (j + 0.5) * s + (rng.random() - 0.5) * s * 0.10
            hb = tuple((0.47 + 0.06 * rng.random()) * s - g * 0.5 for _ in range(4))
            rot = (rng.random() - 0.5) * jitter * 2.0
            r0, g0, b0 = sample(arr, scale, cx / k, cy / k)
            f = 1.0 + (rng.random() - 0.5) * 0.16
            if rng.random() < 0.07:
                f *= 0.88
            dr, dg, db = 0, 0, 0
            if rng.random() < 0.09:
                dr, dg, db = 12, 4, -8
            elif rng.random() < 0.07:
                dr, dg, db = -6, 0, 9
            ad = (rng.random() - 0.5) * 14
            colv = (max(0, min(255, int(r0 * f + dr + ad))),
                    max(0, min(255, int(g0 * f + dg + ad))),
                    max(0, min(255, int(b0 * f + db + ad))), 255)
            stone(cx, cy, hb, rot, colv)
    # 沿轮廓小石行
    e = arr.astype(np.int16)
    dxm = np.abs(e[:, 1:, :] - e[:, :-1, :]).sum(axis=2)
    dym = np.abs(e[1:, :, :] - e[:-1, :, :]).sum(axis=2)
    ed = np.zeros(arr.shape[:2], dtype=np.float32)
    ed[:, 1:] += dxm
    ed[1:, :] += dym
    ys, xs = np.where(ed[: ed.shape[0] - 1, : ed.shape[1] - 1] > edge_thresh)
    if len(ys) > 0:
        n = min(edge_cap, len(ys))
        idx = np.random.RandomState(seed + 5).choice(len(ys), size=n, replace=False)
        s2 = s * small
        g2 = g * 0.7
        gys = np.gradient(ed, axis=0)
        gxs = np.gradient(ed, axis=1)
        for ii in idx:
            py, px = float(ys[ii]) / scale, float(xs[ii]) / scale
            cx, cy = px * k + (rng.random() - 0.5) * s2 * 0.3, py * k + (rng.random() - 0.5) * s2 * 0.3
            gyv = gys[min(ys[ii], ed.shape[0] - 2), min(xs[ii], ed.shape[1] - 2)]
            gxv = gxs[min(ys[ii], ed.shape[0] - 2), min(xs[ii], ed.shape[1] - 2)]
            rot = math.atan2(gyv, gxv) + math.pi * 0.5 + (rng.random() - 0.5) * 0.2
            hb = tuple((0.47 + 0.06 * rng.random()) * s2 - g2 * 0.5 for _ in range(4))
            r0, g0, b0 = sample(arr, scale, px, py)
            f = 1.0 + (rng.random() - 0.5) * 0.10
            colv = (max(0, min(255, int(r0 * f))), max(0, min(255, int(g0 * f))),
                    max(0, min(255, int(b0 * f))), 255)
            stone(cx, cy, hb, rot, colv)
    c.paste_full(lay)
