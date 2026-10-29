# -*- coding: utf-8 -*-
"""write-video — 画布、缓动与颜色工具（自绘用），skia 后端。

画布坐标为设计像素（与 Film 的 width/height 同一坐标系），
内部自动按超采样倍率 ss 映射到位图像素；ox/oy 为整帧震动等全局偏移。

自绘回调签名：fn(c, t)，t 为元素本地秒（= 全局秒 - 元素 at）。
"""
import math
import os
from functools import lru_cache

import numpy as np
import skia
from PIL import Image

from . import fonts as _fonts

# ---------------------------------------------------------------- 缓动


def _clamp01(t):
    return 0.0 if t < 0 else (1.0 if t > 1 else float(t))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def _ease_in_out_back(t):
    c1, c2, c3 = 1.70158, 1.70158 * 1.525, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


_EASE = {
    "linear": lambda t: t,
    "easeInQuad": lambda t: t * t,
    "easeOutQuad": lambda t: t * (2 - t),
    "easeInOutQuad": lambda t: 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t,
    "easeInCubic": lambda t: t * t * t,
    "easeOutCubic": lambda t: (t - 1) ** 3 + 1,
    "easeInOutCubic": lambda t: 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,
    "easeInSine": lambda t: 1 - math.cos(t * math.pi / 2),
    "easeOutSine": lambda t: math.sin(t * math.pi / 2),
    "easeInOutSine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "easeInExpo": lambda t: 0 if t == 0 else 2 ** (10 * t - 10),
    "easeOutExpo": lambda t: 1 if t == 1 else 1 - 2 ** (-10 * t),
    "easeInBack": _ease_in_out_back,
    "easeOutBack": lambda t: 1 - _ease_in_out_back(1 - t),
    "easeInOutBack": lambda t: 0.5 * _ease_in_out_back(2 * t) if t < 0.5 else 0.5 * (2 - _ease_in_out_back(2 - 2 * t)),
}


def ease(name, t):
    return _EASE.get(name, _EASE["linear"])(_clamp01(t))


def rand(seed, i=0):
    h = seed * 374761393 + i * 668265263
    h = (h ^ (h >> 13)) * 1274126177
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF


def spring(t, damping=6.0, freq=2.2):
    return 1.0 - math.exp(-damping * t) * math.cos(freq * t * math.pi) if t > 0 else 0.0


def decay(t, freq=3.0, damp=9.0):
    return math.exp(-damp * t) * math.cos(freq * t) if t > 0 else 1.0


def wiggle(t, freq=1.0, amp=1.0, seed=1):
    return amp * math.sin(2 * math.pi * freq * t + rand(seed, 0) * 6.2832)


# ---------------------------------------------------------------- 颜色

_PALETTES = {}


def _palette(name):
    if not _PALETTES:
        _PALETTES["midnight"] = {
            "fg": (230, 235, 245), "soft": (168, 178, 200),
            "dim": (96, 106, 130), "accent": (0, 200, 220),
            "emph": (255, 120, 80), "panel": (24, 28, 40),
            "line": (48, 56, 76), "bg": (8, 10, 18),
        }
        _PALETTES["punch"] = {
            "fg": (245, 245, 245), "soft": (200, 200, 210),
            "dim": (110, 110, 120), "accent": (255, 204, 0),
            "emph": (255, 204, 0), "panel": (28, 28, 32),
            "line": (60, 60, 68), "bg": (10, 10, 12),
        }
        _PALETTES["light"] = {
            "fg": (30, 32, 36), "soft": (90, 96, 108),
            "dim": (160, 168, 180), "accent": (0, 112, 232),
            "emph": (0, 180, 100), "panel": (245, 247, 250),
            "line": (216, 220, 228), "bg": (255, 255, 255),
        }
    return _PALETTES.get(name, _PALETTES.get("midnight", {}))


def parse_color(v, palette=None):
    if isinstance(v, (list, tuple)):
        return (int(round(v[0])), int(round(v[1])), int(round(v[2])))
    if isinstance(v, str) and v.startswith("#"):
        h = v.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    if isinstance(v, str) and palette:
        p = palette.get(v)
        if p:
            # 主题表存的是 hex 字符串，继续解析成 RGB（原样返回会让解包崩溃）
            return parse_color(p) if isinstance(p, str) else p
    return (200, 200, 200)


# ---------------------------------------------------------------- 缓存

_GLOW_CACHE = {}
_IMG_CACHE = {}


class _DictCap:
    def __init__(self, cap=256):
        self._cap = cap
        self._d = {}

    def put(self, k, v):
        if len(self._d) >= self._cap:
            self._d.clear()
        self._d[k] = v

    def get(self, k):
        return self._d.get(k)

    def __contains__(self, k):
        return k in self._d


def load_image(path):
    path = os.path.abspath(path)
    if path not in _IMG_CACHE:
        _IMG_CACHE[path] = Image.open(path).convert("RGBA")
    return _IMG_CACHE[path]


def image_sprite(path, w, h, radius=0, alpha=1.0):
    key = (path, w, h, radius, round(alpha, 2))
    if key not in _GLOW_CACHE:
        src = load_image(path)
        if radius:
            from PIL import ImageDraw
            m = Image.new("L", (w, h), 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
            spr = Image.new("RGBA", (w, h))
            spr.paste(src.resize((w, h), Image.LANCZOS), (0, 0), m)
        else:
            spr = src.resize((w, h), Image.LANCZOS)
        if alpha < 1.0:
            if spr.mode == "RGBA":
                r, g, b, a = spr.split()
                a = a.point(lambda v: int(v * alpha))
                spr = Image.merge("RGBA", (r, g, b, a))
        _GLOW_CACHE[key] = spr
    return _GLOW_CACHE[key]


def glow_sprite(color, alpha, size=512, power=2.0):
    key = (color, round(alpha, 2), size, round(power, 1))
    if key not in _GLOW_CACHE:
        c = tuple(clamp(v, 0, 255) for v in color)
        arr = np.zeros((size, size, 4), dtype=np.uint8)
        cx = cy = size / 2.0
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (size / 2.0)
        a = np.clip((1.0 - d ** power) * alpha * 255, 0, 255).astype(np.uint8)
        arr[:, :, :3] = c
        arr[:, :, 3] = a
        _GLOW_CACHE[key] = Image.fromarray(arr, "RGBA")
    return _GLOW_CACHE[key]


def scale_sprite(spr, d):
    if d == spr.width:
        return spr
    key = (id(spr), d)
    if key not in _GLOW_CACHE:
        _GLOW_CACHE[key] = spr.resize((d, d), Image.LANCZOS)
    return _GLOW_CACHE[key]


def text_size(s, size=48, bold=False, font=None, line_gap=1.35, ss=1.0):
    """返回 (文本宽度, 行高) 设计像素。"""
    return _text_size_skia(s, size, bold, font, line_gap, ss)


def _text_size_skia(s, size, bold, font, line_gap, ss):
    if isinstance(font, str):
        path = font
    else:
        path = _fonts.find(font or "sans")
        if isinstance(path, (list, tuple)):
            path = path[0]
    tf = skia.Typeface.MakeFromFile(path) if path and os.path.exists(path) else skia.Typeface.MakeDefault()
    f = skia.Font(tf, max(1, int(round(size * ss))))
    w = f.measureText(s) if s else 0
    h = f.getSpacing()
    return w / ss, h / ss


# ---------------------------------------------------------------- Fonts Cache

_SKIA_FONTS = {}


def _get_skia_typeface(kind_or_path, size, bold=False, ss=1.0):
    """返回 (skia.Font, font_path)。"""
    if _is_font_path(kind_or_path):
        path = kind_or_path
    else:
        kind = kind_or_path if kind_or_path else "sans"
        if bold and kind == "sans":
            kind = "sans_bold"
        elif bold and kind == "mono":
            kind = "mono_bold"
        result = _fonts.find(kind)
        path = result[0] if result else None
    if not path or not os.path.exists(path):
        return skia.Font(skia.Typeface.MakeDefault(), max(1, int(round(size * ss)))), None
    key = (path, int(size * ss))
    if key not in _SKIA_FONTS:
        tf = skia.Typeface.MakeFromFile(path)
        _SKIA_FONTS[key] = tf
    return skia.Font(_SKIA_FONTS[key], max(1, int(round(size * ss)))), path


def _is_font_path(v):
    if not isinstance(v, str):
        return False
    return v.endswith((".ttf", ".ttc", ".otf"))


# ---------------------------------------------------------------- 图片缓存（skia）

_SKIA_IMAGES = {}


def _load_skia_image(path):
    if path not in _SKIA_IMAGES:
        pil = load_image(path)
        arr = np.asarray(pil)
        info = skia.ImageInfo.Make(pil.width, pil.height, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
        _SKIA_IMAGES[path] = skia.Image.MakeRaster(info, arr, arr.strides[0])
    return _SKIA_IMAGES[path]


def _pil_to_skia(pil_img):
    arr = np.asarray(pil_img)
    info = skia.ImageInfo.Make(pil_img.width, pil_img.height, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
    return skia.Image.MakeRaster(info, arr, arr.strides[0])


# ---------------------------------------------------------------- 画布核心

class Canvas:
    """绘图画布（skia 后端）。坐标为设计像素；ox/oy 为全局偏移（设计像素）。

    颜色：'#RRGGBB'、调色板名（fg/soft/dim/accent/emph/panel/line/bg）、(r,g,b)。
    """

    def __init__(self, img, ss=1.0, width=None, height=None, ctx=None,
                 box_origin=(0.0, 0.0), ox=0.0, oy=0.0, draw=None):
        self.ss = float(ss)
        self.width = float(width) if width is not None else (img.width / self.ss if img else 0)
        self.height = float(height) if height is not None else (img.height / self.ss if img else 0)
        self.ctx = ctx
        self._origin = box_origin
        self.ox = float(ox)
        self.oy = float(oy)
        # 创建 skia 表面
        w_px = max(1, int(round(self.width * self.ss)))
        h_px = max(1, int(round(self.height * self.ss)))
        info = skia.ImageInfo.Make(w_px, h_px, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
        self._arr = np.zeros((h_px, w_px, 4), dtype=np.uint8)
        self._surface = skia.Surface.MakeRasterDirect(info, self._arr, self._arr.strides[0])
        self._canvas = self._surface.getCanvas()
        # 复制传入图片的内容
        if img is not None and isinstance(img, Image.Image):
            img_arr = np.asarray(img)
            if img_arr.shape == self._arr.shape:
                self._arr[:] = img_arr
        # PIL 引用（供外部读取渲染结果）
        self.img = Image.frombuffer("RGBA", (w_px, h_px), self._arr, "raw", "RGBA", 0, 1)

    def _flush(self):
        """将 skia 表面刷新到 PIL Image（self.img）。"""
        if not hasattr(self, "_arr") or self._arr.size == 0:
            return
        self.img = Image.frombuffer("RGBA",
                                     (int(round(self.width * self.ss)), int(round(self.height * self.ss))),
                                     self._arr, "raw", "RGBA", 0, 1)

    # ---------- 内部 ----------
    def _palette(self):
        return getattr(self.ctx, "palette", None) if self.ctx is not None else None

    def _fill(self, c, alpha=1.0):
        if c is None:
            return None
        r, g, b = parse_color(c, self._palette())
        a = int(round(clamp(alpha, 0.0, 1.0) * 255))
        return skia.Color(r, g, b, a)

    def _fill4f(self, c, alpha=1.0):
        if c is None:
            return None
        r, g, b = parse_color(c, self._palette())
        a = clamp(alpha, 0.0, 1.0)
        return skia.Color4f(r / 255.0, g / 255.0, b / 255.0, a)

    def _paint(self, color=None, alpha=1.0, width=1.0, style="fill"):
        p = skia.Paint()
        if color is not None:
            c4f = self._fill4f(color, alpha)
            if c4f:
                p.setColor4f(c4f)
        if style == "stroke":
            p.setStyle(skia.Paint.kStroke_Style)
            p.setStrokeWidth(max(0.5, width * self.ss))
        p.setAntiAlias(True)
        return p

    def _ix(self, v):
        return int(round((v + self.ox) * self.ss))

    def _iy(self, v):
        return int(round((v + self.oy) * self.ss))

    def _lw(self, width):
        return max(1, int(round(width * self.ss)))

    def _pts_to_path(self, pts):
        """点数组 → skia Path"""
        path = skia.Path()
        if not pts:
            return path
        path.moveTo(self._ix(pts[0][0]), self._iy(pts[0][1]))
        for p in pts[1:]:
            path.lineTo(self._ix(p[0]), self._iy(p[1]))
        return path

    # ---------- 基础图元 ----------

    def rect(self, x, y, w, h, fill=None, outline=None, width=1.0, radius=0, alpha=1.0):
        box = skia.Rect.MakeXYWH(self._ix(x), self._iy(y), max(1, int(round(w * self.ss))), max(1, int(round(h * self.ss))))
        if radius > 0:
            r = self._lw(radius)
            if fill is not None:
                fp = self._paint(fill, alpha)
                self._canvas.drawRoundRect(box, r, r, fp)
            if outline is not None:
                op = self._paint(outline, alpha, width, "stroke")
                self._canvas.drawRoundRect(box, r, r, op)
        else:
            if fill is not None:
                fp = self._paint(fill, alpha)
                self._canvas.drawRect(box, fp)
            if outline is not None:
                op = self._paint(outline, alpha, width, "stroke")
                self._canvas.drawRect(box, op)

    def line(self, x1, y1, x2, y2, color="fg", width=2.0, alpha=1.0):
        p = self._paint(color, alpha, width, "stroke")
        self._canvas.drawLine(self._ix(x1), self._iy(y1), self._ix(x2), self._iy(y2), p)

    def lines(self, pts, color="fg", width=2.0, alpha=1.0):
        if len(pts) < 2:
            return
        path = self._pts_to_path(pts)
        p = self._paint(color, alpha, width, "stroke")
        self._canvas.drawPath(path, p)

    def polygon(self, pts, fill=None, outline=None, width=2.0, alpha=1.0):
        if len(pts) < 3:
            return
        path = skia.Path()
        path.moveTo(self._ix(pts[0][0]), self._iy(pts[0][1]))
        for p in pts[1:]:
            path.lineTo(self._ix(p[0]), self._iy(p[1]))
        path.close()
        if fill is not None:
            fp = self._paint(fill, alpha)
            self._canvas.drawPath(path, fp)
        if outline is not None:
            op = self._paint(outline, alpha, width, "stroke")
            self._canvas.drawPath(path, op)

    def circle(self, x, y, r, fill=None, outline=None, width=2.0, alpha=1.0):
        cx, cy = self._ix(x), self._iy(y)
        cr = max(0.5, r * self.ss)
        if fill is not None:
            fp = self._paint(fill, alpha)
            self._canvas.drawCircle(cx, cy, cr, fp)
        if outline is not None:
            op = self._paint(outline, alpha, width, "stroke")
            self._canvas.drawCircle(cx, cy, cr, op)

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, width=2.0, alpha=1.0):
        box = skia.Rect.MakeXYWH(
            self._ix(x - rx), self._iy(y - ry),
            max(1, int(round(rx * 2 * self.ss))), max(1, int(round(ry * 2 * self.ss))))
        if fill is not None:
            fp = self._paint(fill, alpha)
            self._canvas.drawOval(box, fp)
        if outline is not None:
            op = self._paint(outline, alpha, width, "stroke")
            self._canvas.drawOval(box, op)

    def arc(self, x, y, r, start, end, color="fg", width=3.0, alpha=1.0):
        box = skia.Rect.MakeXYWH(
            self._ix(x - r), self._iy(y - r),
            max(1, int(round(r * 2 * self.ss))), max(1, int(round(r * 2 * self.ss))))
        start_deg = math.degrees(start)
        sweep_deg = math.degrees(end - start)
        p = self._paint(color, alpha, width, "stroke")
        self._canvas.drawArc(box, start_deg, sweep_deg, False, p)

    def text(self, s, x, y, size=48, color="fg", bold=False, align="center", valign="center",
             alpha=1.0, font=None, line_gap=1.35):
        if not s:
            return
        size_px = max(1, int(round(size * self.ss)))
        skia_font, font_path = _get_skia_typeface(font or "sans", size, bold, self.ss)
        skia_font.setSize(size_px)
        tw = skia_font.measureText(s)
        th = skia_font.getSpacing()
        px = self._ix(x)
        py = self._iy(y)
        if align == "center":
            px -= int(tw / 2)
        elif align == "right":
            px -= int(tw)
        if valign == "center":
            py += int(th / 2)
        elif valign == "bottom":
            py += int(th - skia_font.getSize() * 0.2)
        p = self._paint(color, alpha)
        self._canvas.drawString(s, px, py, skia_font, p)

    def text_width(self, s, size=48, bold=False, font=None):
        if not s:
            return 0
        skia_font, _ = _get_skia_typeface(font or "sans", size, bold, 1.0)
        return skia_font.measureText(s)

    def image(self, path, x, y, w=None, h=None, alpha=1.0, radius=0, anchor="center"):
        if not os.path.exists(path):
            return
        sk_img = _load_skia_image(path)
        sw, sh = sk_img.width(), sk_img.height()
        if w is None and h is None:
            tw, th = float(sw) / self.ss, float(sh) / self.ss
        elif w is not None and h is None:
            tw, th = w, w * sh / sw
        elif h is not None and w is None:
            th, tw = h, h * sw / sh
        else:
            tw, th = w, h
        tw_px = int(round(tw * self.ss))
        th_px = int(round(th * self.ss))
        if tw_px <= 0 or th_px <= 0:
            return
        # Scale image using skia
        info = skia.ImageInfo.Make(tw_px, th_px, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
        surf = skia.Surface.MakeRaster(info)
        s_canv = surf.getCanvas()
        s_rect = skia.Rect.MakeXYWH(0, 0, tw_px, th_px)
        p = skia.Paint()
        p.setAntiAlias(True)
        if alpha < 1.0:
            p.setAlpha(int(round(alpha * 255)))
        s_canv.drawImageRect(sk_img, s_rect, p)
        if radius:
            path = skia.Path()
            path.addRoundRect(s_rect, radius * self.ss, radius * self.ss)
            s_canv.clipPath(path, skia.ClipOp.kIntersect, True)
            s_canv.drawImageRect(sk_img, s_rect, p)
        result = surf.makeImageSnapshot()
        px = (x - tw / 2) if anchor == "center" else x
        py = (y - th / 2) if anchor == "center" else y
        dst_r = skia.Rect.MakeXYWH(self._ix(px), self._iy(py), tw_px, th_px)
        self._canvas.drawImageRect(result, dst_r, skia.SamplingOptions(), None,
                                    skia.PaintFlag.kNone)

    def glow(self, x, y, r, color="accent", alpha=0.35):
        col = parse_color(color, self._palette())
        spr = scale_sprite(glow_sprite(col, alpha), round(2 * r * self.ss))
        sk_img = _pil_to_skia(spr)
        r_px = round(r * self.ss)
        dst_r = skia.Rect.MakeXYWH(self._ix(x - r), self._iy(y - r), r_px * 2, r_px * 2)
        p = skia.Paint()
        p.setAntiAlias(True)
        # 使用 skia 的 BlurMaskFilter 替代 PIL 方法
        blur = skia.MaskFilter.MakeBlur(skia.BlurStyle.kNormal, r_px * 0.3)
        p.setMaskFilter(blur)
        self._canvas.drawImageRect(sk_img, dst_r, skia.SamplingOptions(), p)

    # ---------- 装饰级效果 ----------

    def _gradient_stops(self, colors):
        pal = self._palette()
        stops = [(0.0, parse_color(colors[0][1], pal))]
        for pos, c in colors:
            stops.append((pos, parse_color(c, pal)))
        if stops[-1][0] < 1.0:
            stops.append((1.0, stops[-1][1]))
        return stops

    def gradient(self, x=0, y=0, w=None, h=None, colors=None, direction="radial", alpha=1.0):
        if w is None:
            w = self.width
        if h is None:
            h = self.height
        if colors is None:
            colors = [(0.0, "accent"), (1.0, "bg")]
        w_px = max(1, int(round(w * self.ss)))
        h_px = max(1, int(round(h * self.ss)))
        stops = self._gradient_stops(colors)
        sk_colors = [skia.Color4f(r / 255.0, g / 255.0, b / 255.0, clamp(alpha, 0, 1))
                     for _, (r, g, b) in stops]
        sk_pos = [s[0] for s in stops]
        rect = skia.Rect.MakeXYWH(self._ix(x), self._iy(y), w_px, h_px)
        if direction == "radial":
            cx, cy = self._ix(x + w / 2), self._iy(y + h / 2)
            max_r = max(1, math.hypot(w_px, h_px) / 2)
            shader = skia.GradientShader.MakeRadial(
                skia.Point(cx, cy), max_r, sk_colors, sk_pos, skia.TileMode.kClamp)
        elif direction == "vertical":
            shader = skia.GradientShader.MakeLinear(
                skia.Point(rect.x(), rect.y()), skia.Point(rect.x(), rect.y() + h_px),
                sk_colors, sk_pos, skia.TileMode.kClamp)
        else:
            shader = skia.GradientShader.MakeLinear(
                skia.Point(rect.x(), rect.y()), skia.Point(rect.x() + w_px, rect.y()),
                sk_colors, sk_pos, skia.TileMode.kClamp)
        p = skia.Paint()
        p.setShader(shader)
        self._canvas.drawRect(rect, p)

    def vignette(self, radius=0.65, power=1.8, color=(0, 0, 0), alpha=0.55):
        w_px = max(1, int(round(self.width * self.ss)))
        h_px = max(1, int(round(self.height * self.ss)))
        cx, cy = w_px / 2.0, h_px / 2.0
        max_r = math.hypot(cx, cy)
        # 使用径向渐变实现暗角
        c = tuple(clamp(v, 0, 255) for v in color)
        inner = skia.Color4f(0, 0, 0, 0)
        outer = skia.Color4f(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0, clamp(alpha, 0, 1))
        shader = skia.GradientShader.MakeRadial(
            skia.Point(cx, cy), max_r,
            [inner, outer],
            [clamp(radius, 0, 0.999), 1.0],
            skia.TileMode.kClamp,
        )
        p = skia.Paint()
        p.setShader(shader)
        rect = skia.Rect.MakeXYWH(0, 0, w_px, h_px)
        self._canvas.drawRect(rect, p)

    def grid(self, spacing=80, color="soft", alpha=0.05, width=1.0):
        w_px = max(1, int(round(self.width * self.ss)))
        h_px = max(1, int(round(self.height * self.ss)))
        sp = max(4, int(round(spacing * self.ss)))
        p = self._paint(color, alpha, width, "stroke")
        for x in range(0, w_px, sp):
            self._canvas.drawLine(x, 0, x, h_px, p)
        for y in range(0, h_px, sp):
            self._canvas.drawLine(0, y, w_px, y, p)

    def scanlines(self, spacing=3, alpha=0.08):
        w_px = max(1, int(round(self.width * self.ss)))
        h_px = max(1, int(round(self.height * self.ss)))
        sp = max(1, int(round(spacing * self.ss)))
        p = self._paint((0, 0, 0), alpha)
        for y in range(0, h_px, sp * 2):
            rect = skia.Rect.MakeXYWH(0, y, w_px, min(sp, h_px - y))
            self._canvas.drawRect(rect, p)

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