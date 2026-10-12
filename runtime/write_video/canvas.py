# -*- coding: utf-8 -*-
"""write-video — 画布、缓动与颜色工具（自绘用）。

画布坐标为设计像素（与 Film 的 width/height 同一坐标系），
内部自动按超采样倍率 ss 映射到位图像素；ox/oy 为整帧震动等全局偏移。

自绘回调签名：fn(c, t)，t 为元素本地秒（= 全局秒 - 元素 at）。
"""
import math

import numpy as np
from PIL import Image, ImageDraw

from . import fonts as _fonts

# ---------------------------------------------------------------- 缓动

def _clamp01(t):
    return 0.0 if t < 0 else (1.0 if t > 1 else float(t))


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, t):
    return a + (b - a) * t


def _ease_in_out_back(t):
    c2 = 1.70158 * 1.525
    if t < 0.5:
        u = 2 * t
        return (u * u * ((c2 + 1) * u - c2)) / 2
    u = 2 * t - 2
    return (u * u * ((c2 + 1) * u + c2) + 2) / 2


_EASES = {
    "linear": lambda t: t,
    "easeInQuad": lambda t: t * t,
    "easeOutQuad": lambda t: 1 - (1 - t) ** 2,
    "easeInOutQuad": lambda t: 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2,
    "easeInCubic": lambda t: t ** 3,
    "easeOutCubic": lambda t: 1 - (1 - t) ** 3,
    "easeInOutCubic": lambda t: 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,
    "easeInSine": lambda t: 1 - math.cos(t * math.pi / 2),
    "easeOutSine": lambda t: math.sin(t * math.pi / 2),
    "easeInOutSine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "easeInExpo": lambda t: 0.0 if t <= 0 else 2 ** (10 * t - 10),
    "easeOutExpo": lambda t: 1.0 if t >= 1 else 1 - 2 ** (-10 * t),
    "easeInBack": lambda t: 2.70158 * t ** 3 - 1.70158 * t * t,
    "easeOutBack": lambda t: 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
    "easeInOutBack": _ease_in_out_back,
}

_EASE_LOOKUP = dict((k.lower(), k) for k in _EASES)
_EASE_LOOKUP.update({
    "inquad": "easeInQuad", "outquad": "easeOutQuad", "inoutquad": "easeInOutQuad",
    "incubic": "easeInCubic", "outcubic": "easeOutCubic", "inoutcubic": "easeInOutCubic",
    "insine": "easeInSine", "outsine": "easeOutSine", "inoutsine": "easeInOutSine",
    "inexpo": "easeInExpo", "outexpo": "easeOutExpo",
    "inback": "easeInBack", "outback": "easeOutBack", "inoutback": "easeInOutBack",
})


def ease(name, t):
    """t∈[0,1] 求缓动值。name 可为缓动名或函数。"""
    t = _clamp01(t)
    if callable(name):
        return float(name(t))
    s = str(name).lower()
    key = _EASE_LOOKUP.get(s) or _EASE_LOOKUP.get(s.replace("_", "").replace("-", ""))
    if key is None:
        key = "linear"
    return float(_EASES[key](t))


# ------------------------------------------------- 解析式运动 / 确定性随机

def rand(seed, i=0):
    """确定性伪随机 [0,1)：同 seed、i 恒等。"""
    h = (int(seed) * 374761393 + int(i) * 668265263 + 2147483647) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFF) / 16777215.0


def spring(t, damping=6.0, freq=2.2):
    """弹簧过冲：从 0 出发、以 1 为中心衰减振荡（t<0 返回 0）。"""
    if t < 0:
        return 0.0
    return 1.0 - math.exp(-damping * t) * math.cos(2 * math.pi * freq * t)


def decay(t, freq=3.0, damp=9.0):
    """衰减振荡（t<0 返回 0）。"""
    if t < 0:
        return 0.0
    return math.exp(-damp * t) * math.sin(2 * math.pi * freq * t)


def wiggle(t, freq=1.0, amp=1.0, seed=1):
    """平滑抖动：多个正弦叠加。"""
    v = 0.0
    ws = (1.0, 0.55, 0.3, 0.15)
    for k in range(4):
        ph = rand(seed, k) * 2 * math.pi
        v += math.sin(2 * math.pi * freq * (1.0 + k * 1.7) * t + ph) * ws[k]
    return v * amp / 2.0


# ---------------------------------------------------------------- 颜色

DEFAULT_PALETTE = {
    "fg": "#EAF2FF", "soft": "#A8B6CC", "dim": "#5C6A82",
    "accent": "#64F4DC", "emph": "#FFD166",
    "panel": "#121A2B", "line": "#24304A", "bg": "#0A0E1A",
    "dark": "#000000", "white": "#FFFFFF",
}


def parse_color(v, palette=None):
    """颜色 → (r,g,b)。支持 '#RRGGBB'、调色板名、0xRRGGBB、(r,g,b)。"""
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        return (int(v[0]), int(v[1]), int(v[2]))
    if isinstance(v, int):
        return ((v >> 16) & 255, (v >> 8) & 255, v & 255)
    s = str(v).strip()
    if palette and s in palette:
        return parse_color(palette[s], palette)
    if s in DEFAULT_PALETTE:
        return parse_color(DEFAULT_PALETTE[s], palette)
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = h[0] * 2 + h[1] * 2 + h[2] * 2
        if len(h) >= 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    raise ValueError("无法识别的颜色: %r" % (v,))


# ------------------------------------------------------------ 位图缓存

class _DictCap(dict):
    def __init__(self, cap=256):
        dict.__init__(self)
        self.cap = cap

    def put(self, k, v):
        if len(self) >= self.cap:
            self.pop(next(iter(self)))
        self[k] = v
        return v


_IMG_CACHE = _DictCap(64)      # 原始图片
_SPR_CACHE = _DictCap(512)     # 缩放/圆角/透明度后的图片贴片
_GLOW_MASK = {}
_GLOW_SPR = _DictCap(512)


def load_image(path):
    im = _IMG_CACHE.get(path)
    if im is None:
        im = Image.open(path)
        im.load()
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        _IMG_CACHE.put(path, im)
    return im


def _rounded_mask(size, radius):
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=max(0, int(round(radius))), fill=255)
    return m


def image_sprite(path, w, h, radius=0, alpha=1.0):
    """图片贴片：目标位图尺寸 w×h（含超采样），圆角与透明度预先应用，带缓存。"""
    a = int(round(clamp(alpha, 0.0, 1.0) * 32))
    key = (path, int(w), int(h), int(round(radius)), a)
    spr = _SPR_CACHE.get(key)
    if spr is not None:
        return spr
    im = load_image(path)
    if (im.width, im.height) != (int(w), int(h)):
        rsz = im.resize((max(1, int(w)), max(1, int(h))), Image.LANCZOS)
    else:
        rsz = im
    if radius and radius > 0:
        mask = _rounded_mask(rsz.size, radius)
        out = Image.new("RGBA", rsz.size, (0, 0, 0, 0))
        out.paste(rsz, (0, 0), mask)
        rsz = out
    if a < 32:
        rr, gg, bb, aa = rsz.split()
        aa = aa.point(lambda v: (v * a) // 32)
        rsz = Image.merge("RGBA", (rr, gg, bb, aa))
    return _SPR_CACHE.put(key, rsz)


def glow_sprite(color, alpha, size=512, power=2.0):
    """柔和光晕贴片（径向渐变），按颜色与透明度分级缓存。"""
    key0 = (size, power)
    mask = _GLOW_MASK.get(key0)
    if mask is None:
        c = (size - 1) / 2.0
        y, x = np.mgrid[0:size, 0:size].astype(np.float32)
        d = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
        mask = (np.clip(1 - d, 0, 1) ** power * 255).astype(np.uint8)
        _GLOW_MASK[key0] = mask
    a = int(round(clamp(alpha, 0.0, 1.0) * 24))
    key = (color, a, size, power)
    spr = _GLOW_SPR.get(key)
    if spr is None:
        m = Image.fromarray(mask, "L").point(lambda v: v * a // 24)
        spr = Image.new("RGBA", (size, size), tuple(color) + (255,))
        spr.putalpha(m)
        _GLOW_SPR.put(key, spr)
    return spr


def scale_sprite(spr, d):
    """把贴片缩放到 d×d（尺寸取 2px 分档缓存）。"""
    d = max(2, int(round(d / 2.0)) * 2)
    if spr.width == d:
        return spr
    key = (id(spr), d)
    out = _SPR_CACHE.get(key)
    if out is None:
        out = spr.resize((d, d), Image.BILINEAR)
        _SPR_CACHE.put(key, out)
    return out


# ---------------------------------------------------------------- 画布

def text_size(s, size=48, bold=False, font=None, line_gap=1.35, ss=1.0):
    """量文字排版尺寸（设计像素）。不画。"""
    s = str(s).replace("\r", "")
    lines = s.split("\n")
    px = max(1, int(round(size * ss)))
    f = _fonts.load(font or ("sans_bold" if bold else "sans"), px)
    line_h = float(sum(f.getmetrics()))
    step = max(line_h, px * float(line_gap))
    w = max([f.getlength(ln) for ln in lines] or [0.0])
    h = (len(lines) - 1) * step + line_h
    return (w / ss, h / ss)


class Canvas(object):
    """绘图画布。坐标为设计像素；ox/oy 为全局偏移（设计像素）。

    颜色：'#RRGGBB'、调色板名（fg/soft/dim/accent/emph/panel/line/bg）、(r,g,b)。
    """

    def __init__(self, img, ss=1.0, width=None, height=None, ctx=None,
                 box_origin=(0.0, 0.0), ox=0.0, oy=0.0, draw=None):
        self.img = img
        self.ss = float(ss)
        self.width = float(width) if width is not None else img.width / self.ss
        self.height = float(height) if height is not None else img.height / self.ss
        self.ctx = ctx
        self._origin = box_origin
        self.ox = float(ox)
        self.oy = float(oy)
        self._d = draw if draw is not None else ImageDraw.Draw(img, "RGBA")

    # ---------- 内部 ----------
    def _palette(self):
        return getattr(self.ctx, "palette", None) if self.ctx is not None else None

    def _fill(self, c, alpha=1.0):
        if c is None:
            return None
        r, g, b = parse_color(c, self._palette())
        a = int(round(clamp(alpha, 0.0, 1.0) * 255))
        return (r, g, b, a)

    def _ix(self, v):
        return int(round((v + self.ox) * self.ss))

    def _iy(self, v):
        return int(round((v + self.oy) * self.ss))

    def _box2(self, x, y, w, h):
        return [self._ix(x), self._iy(y), self._ix(x + w) - 1, self._iy(y + h) - 1]

    def _lw(self, width):
        return max(1, int(round(width * self.ss)))

    # ---------- 基础图元 ----------
    def rect(self, x, y, w, h, fill=None, outline=None, width=1.0, radius=0, alpha=1.0):
        """矩形（x,y = 左上角）。radius>0 为圆角。"""
        box = self._box2(x, y, w, h)
        f = self._fill(fill, alpha)
        o = self._fill(outline, alpha)
        if radius and radius > 0:
            self._d.rounded_rectangle(box, radius=self._lw(radius), fill=f, outline=o, width=self._lw(width) if o else 1)
        else:
            if f is not None or o is not None:
                self._d.rectangle(box, fill=f, outline=o, width=self._lw(width))

    def line(self, x1, y1, x2, y2, color="fg", width=2.0, alpha=1.0):
        self._d.line([self._ix(x1), self._iy(y1), self._ix(x2), self._iy(y2)], fill=self._fill(color, alpha), width=self._lw(width))

    def lines(self, pts, color="fg", width=2.0, alpha=1.0):
        if len(pts) < 2:
            return
        pix = [(self._ix(px), self._iy(py)) for px, py in pts]
        self._d.line(pix, fill=self._fill(color, alpha), width=self._lw(width), joint="curve")

    def polygon(self, pts, fill=None, outline=None, width=2.0, alpha=1.0):
        if len(pts) < 2:
            return
        pix = [(self._ix(px), self._iy(py)) for px, py in pts]
        f = self._fill(fill, alpha)
        if f is not None and len(pix) >= 3:
            self._d.polygon(pix, fill=f)
        if outline is not None:
            self._d.line(pix + [pix[0]], fill=self._fill(outline, alpha), width=self._lw(width), joint="curve")

    def circle(self, x, y, r, fill=None, outline=None, width=2.0, alpha=1.0):
        self.ellipse(x, y, r, r, fill=fill, outline=outline, width=width, alpha=alpha)

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, width=2.0, alpha=1.0):
        box = [self._ix(x - rx), self._iy(y - ry), self._ix(x + rx) - 1, self._iy(y + ry) - 1]
        f = self._fill(fill, alpha)
        o = self._fill(outline, alpha)
        if f is not None:
            self._d.ellipse(box, fill=f)
        if o is not None:
            self._d.ellipse(box, outline=o, width=self._lw(width))

    def arc(self, x, y, r, start, end, color="fg", width=3.0, alpha=1.0):
        """圆弧：0° = 三点钟方向，角度沿屏幕顺时针增加。"""
        box = [self._ix(x - r), self._iy(y - r), self._ix(x + r) - 1, self._iy(y + r) - 1]
        self._d.arc(box, start, end, fill=self._fill(color, alpha), width=self._lw(width))

    # ---------- 文字 ----------
    def text(self, s, x, y, size=48, color="fg", bold=False, align="center", valign="center",
             alpha=1.0, font=None, line_gap=1.35, max_width=None):
        """文字（可多行，\n 分行）。x,y 锚点：align 决定水平锚（left/center/right）。
        返回排版尺寸 (w,h)（设计像素）。"""
        s = str(s).replace("\r", "")
        lines = s.split("\n")
        px = max(1, int(round(size * self.ss)))
        kind = font or ("sans_bold" if bold else "sans")
        f = _fonts.load(kind, px)
        if max_width:
            w0 = max([f.getlength(ln) for ln in lines] or [0.0])
            if w0 > max_width * self.ss and w0 > 0:
                px = max(1, int(px * max_width * self.ss / w0 * 0.98))
                f = _fonts.load(kind, px)
        line_h = float(sum(f.getmetrics()))
        step = max(line_h, px * float(line_gap))
        widths = [f.getlength(ln) for ln in lines]
        w = max(widths or [0.0])
        h = (len(lines) - 1) * step + line_h
        xi, yi = (x + self.ox) * self.ss, (y + self.oy) * self.ss
        if align == "left":
            bx = xi
        elif align == "right":
            bx = xi - w
        else:
            bx = xi - w / 2
        if valign == "top":
            by = yi
        elif valign == "bottom":
            by = yi - h
        else:
            by = yi - h / 2
        fill = self._fill(color, alpha)
        for i, ln in enumerate(lines):
            if not ln:
                continue
            if align == "left":
                lx = bx
            elif align == "right":
                lx = bx + (w - widths[i])
            else:
                lx = bx + (w - widths[i]) / 2
            self._d.text((int(round(lx)), int(round(by + i * step))), ln, font=f, fill=fill)
        return (w / self.ss, h / self.ss)

    def text_width(self, s, size=48, bold=False, font=None):
        """量一行文字宽度（设计像素）。"""
        f = _fonts.load(font or ("sans_bold" if bold else "sans"), max(1, int(round(size * self.ss))))
        return f.getlength(str(s)) / self.ss

    # ---------- 图片 / 光晕 ----------
    def image(self, path, x, y, w=None, h=None, alpha=1.0, radius=0, anchor="center"):
        """贴图。x,y 默认是中心点（anchor='topleft' 时是左上角）。返回尺寸 (w,h)。"""
        im = load_image(path)
        iw, ih = im.size
        if w is None and h is None:
            tw, th = float(iw), float(ih)
        elif h is None:
            tw = float(w)
            th = ih * tw / iw
        elif w is None:
            th = float(h)
            tw = iw * th / ih
        else:
            tw, th = float(w), float(h)
        spr = image_sprite(path, round(tw * self.ss), round(th * self.ss), radius * self.ss, alpha)
        px = (x - tw / 2) if anchor == "center" else x
        py = (y - th / 2) if anchor == "center" else y
        self.img.paste(spr, (self._ix(px), self._iy(py)), spr)
        return (tw, th)

    def glow(self, x, y, r, color="accent", alpha=0.35):
        col = parse_color(color, self._palette())
        spr = scale_sprite(glow_sprite(col, alpha), round(2 * r * self.ss))
        self.img.paste(spr, (self._ix(x - r), self._iy(y - r)), spr)

    # ---------- 装饰级效果 ----------

    def _gradient_stops(self, colors):
        """colors: [(位置0~1, 颜色名)] → [(位置, (r,g,b))]"""
        pal = self._palette()
        stops = [(0.0, parse_color(colors[0][1], pal))]
        for pos, c in colors:
            stops.append((pos, parse_color(c, pal)))
        if stops[-1][0] < 1.0:
            stops.append((1.0, stops[-1][1]))
        return stops

    def _gradient_at(self, t, stops):
        if t <= stops[0][0]:
            return stops[0][1]
        for i in range(1, len(stops)):
            if t <= stops[i][0]:
                lo, hi = stops[i - 1], stops[i]
                span = hi[0] - lo[0]
                u = (t - lo[0]) / span if span > 0 else 0.5
                return tuple(int(round(lo[1][j] + (hi[1][j] - lo[1][j]) * u)) for j in range(3))
        return stops[-1][1]

    def gradient(self, x=0, y=0, w=None, h=None, colors=None, direction="radial", alpha=1.0):
        """渐变填充矩形区域。
        不传 x/y/w/h 则铺满全画布。
        colors: [(位置0~1, 颜色名), ...]  如 [(0,"bg"), (0.5,"accent"), (1,"bg")]
        direction: "radial" / "vertical" / "horizontal"
        """
        if w is None:
            w = self.width
        if h is None:
            h = self.height
        if colors is None:
            colors = [(0.0, "bg"), (1.0, "accent")]
        w_px = max(1, int(round(w * self.ss)))
        h_px = max(1, int(round(h * self.ss)))
        stops = self._gradient_stops(colors)
        alp_frac = clamp(alpha, 0.0, 1.0)

        if direction == "radial":
            cx, cy = w_px / 2.0, h_px / 2.0
            max_r = math.hypot(cx, cy)
            yy, xx = np.mgrid[0:h_px, 0:w_px]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max_r
            arr = np.zeros((h_px, w_px, 4), dtype=np.uint8)
            for i in range(3):
                arr[:, :, i] = np.uint8(self._gradient_at(0.0, stops)[i])
            for si in range(1, len(stops)):
                lo, hi = stops[si - 1], stops[si]
                mask = (dist >= lo[0]) & (dist < hi[0])
                span = hi[0] - lo[0]
                u = ((dist - lo[0]) / span) if span > 0 else 0.5
                for c in range(3):
                    lo_v, hi_v = lo[1][c], hi[1][c]
                    arr[:, :, c] = np.where(mask,
                                             np.uint8(lo_v + (hi_v - lo_v) * u), arr[:, :, c])
            arr[:, :, 3] = np.uint8(255 * alp_frac)
        else:
            if direction == "vertical":
                t = np.linspace(0, 1, h_px).reshape(-1, 1)
            else:
                t = np.linspace(0, 1, w_px).reshape(1, -1)
            arr = np.zeros((h_px, w_px, 4), dtype=np.uint8)
            for si in range(1, len(stops)):
                lo, hi = stops[si - 1], stops[si]
                span = hi[0] - lo[0]
                u = ((t - lo[0]) / span) if span > 0 else 0.5
                mask = (t >= lo[0]) & (t < hi[0])
                for c in range(3):
                    lo_v, hi_v = lo[1][c], hi[1][c]
                    arr[:, :, c] = np.where(mask,
                                             np.uint8(lo_v + (hi_v - lo_v) * u), arr[:, :, c])
            arr[:, :, 3] = np.uint8(255 * alp_frac)

        grad = Image.fromarray(arr, "RGBA")
        self.img.paste(grad, (self._ix(x), self._iy(y)), grad)

    def vignette(self, radius=0.65, power=1.8, color=(0, 0, 0), alpha=0.55):
        """边缘暗角。radius 暗角起始半径比例，power 衰减指数。"""
        w_px = int(round(self.width * self.ss))
        h_px = int(round(self.height * self.ss))
        cx, cy = w_px / 2.0, h_px / 2.0
        max_r = math.hypot(cx, cy)
        yy, xx = np.mgrid[0:h_px, 0:w_px]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max_r
        t = np.clip((d - radius) / (1.0 - radius), 0, 1)
        t = np.power(t, power)
        a = np.uint8(t * 255 * clamp(alpha, 0, 1))
        c = tuple(int(clamp(v, 0, 255)) for v in color)
        arr = np.dstack([np.full((h_px, w_px), c[0], dtype=np.uint8),
                         np.full((h_px, w_px), c[1], dtype=np.uint8),
                         np.full((h_px, w_px), c[2], dtype=np.uint8),
                         a])
        vit = Image.fromarray(arr, "RGBA")
        self.img.paste(vit, (0, 0), vit)

    def grid(self, spacing=80, color="soft", alpha=0.05, width=1.0):
        """科技网格背景线。"""
        w_px = int(round(self.width * self.ss))
        h_px = int(round(self.height * self.ss))
        sp = max(4, int(round(spacing * self.ss)))
        col = self._fill(color, alpha)
        if col is None:
            return
        ov = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for x in range(0, w_px, sp):
            d.line([(x, 0), (x, h_px)], fill=col, width=max(1, int(round(width * self.ss))))
        for y in range(0, h_px, sp):
            d.line([(0, y), (w_px, y)], fill=col, width=max(1, int(round(width * self.ss))))
        self.img.paste(ov, (0, 0), ov)

    def scanlines(self, spacing=3, alpha=0.08):
        """水平扫描线。"""
        w_px = int(round(self.width * self.ss))
        h_px = int(round(self.height * self.ss))
        sp = max(1, int(round(spacing * self.ss)))
        col = (0, 0, 0, int(255 * clamp(alpha, 0, 1)))
        ov = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for y in range(0, h_px, sp * 2):
            d.rectangle([(0, y), (w_px - 1, y + sp - 1)], fill=col)
        self.img.paste(ov, (0, 0), ov)

    # ---------- 工具 ----------
    def progress(self, a, b, ease_name="linear"):
        t = getattr(self.ctx, "t", 0.0) if self.ctx is not None else 0.0
        if b <= a:
            return 1.0 if t >= b else 0.0
        return ease(ease_name, (t - a) / (b - a))

    def color(self, v, alpha=1.0):
        r, g, b = parse_color(v, self._palette())
        return (r, g, b, int(round(clamp(alpha, 0.0, 1.0) * 255)))

    def box(self, el, piece=None):
        """声明元素的排版矩形 (x,y,w,h)（本画布坐标系），不含入场动作。"""
        if self.ctx is None:
            return None
        r = self.ctx.box(el, piece)
        if not r:
            return None
        return (r[0] - self._origin[0], r[1] - self._origin[1], r[2], r[3])

    def rand(self, i=0):
        return rand(getattr(self.ctx, "seed", 1) if self.ctx is not None else 1, i)

    def lerp(self, a, b, t):
        return lerp(a, b, t)

    def spring(self, t, damping=6.0, freq=2.2):
        return spring(t, damping, freq)

    def decay(self, t, freq=3.0, damp=9.0):
        return decay(t, freq, damp)

    def wiggle(self, t, freq=1.0, amp=1.0, seed=1):
        return wiggle(t, freq, amp, seed)
