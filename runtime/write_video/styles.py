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

from .canvas import Canvas

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


def pixel8(c, arr, scale, cw=200, palette=None, alpha=1.0, dither=0.0, dither_mode="random"):
    """8-bit：底稿降采样 + 最近色板量化 + 最近邻放大（240×135 情怀）。

    距离在 int32 里算：int16 平方会溢出回绕成负数，argmin 选中垃圾颜色。
    dither: 抖动强度（0-1）；dither_mode: "random"（随机去色带）/"ordered"（Bayer 有序，像素风渐变）。
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
