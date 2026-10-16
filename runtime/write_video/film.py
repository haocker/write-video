# -*- coding: utf-8 -*-
"""write-video — 影片模型：场景、元素、入场预设、自动排版、lint、逐帧渲染。

全局时钟：脚本里的数字就是成片秒数（报告、联系表、节拍都用同一个数）。
"""
import difflib
import math
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import canvas as _cv
from . import fonts as _fonts
from . import icons as _icons
from .canvas import Canvas, ease, rand, spring, decay, wiggle, parse_color, clamp, lerp

# ================================================================ 常量

STYLE_SIZES = {"hero": 120, "title": 72, "subtitle": 48, "body": 40, "caption": 30}
STYLE_ENTER = {"hero": "pop", "title": "rise", "subtitle": "fade", "body": "fade", "caption": "fade"}
STYLE_BOLD = {"hero": True, "title": True, "subtitle": False, "body": False, "caption": False}
STYLE_COLOR = {"hero": "fg", "title": "fg", "subtitle": "fg", "body": "fg", "caption": "soft"}

THEMES = {
    "midnight": {
        "colors": {"fg": "#EAF2FF", "soft": "#A9B7CF", "dim": "#5E6C86", "accent": "#64F4DC",
                   "emph": "#FFD166", "panel": "#121A2E", "line": "#26324E", "bg": "#0A0E1A",
                   "white": "#FFFFFF", "dark": "#05070C"},
        "onAccent": {"fg": "#0B1218", "soft": "#2E3D48", "dim": "#5A6B76", "accent": "#0B1218",
                     "emph": "#7A3E00"},
        "bg": {"type": "gradient", "top": "#101A33", "bottom": "#070A12"},
    },
    "punch": {
        "colors": {"fg": "#FFFFFF", "soft": "#C9C9CE", "dim": "#6E6E76", "accent": "#FFD400",
                   "emph": "#FF5A36", "panel": "#151519", "line": "#2C2C31", "bg": "#0A0A0C",
                   "white": "#FFFFFF", "dark": "#000000"},
        "onAccent": {"fg": "#161300", "soft": "#4A4630", "dim": "#7A7554", "accent": "#161300",
                     "emph": "#8A2B12"},
        "bg": {"type": "gradient", "top": "#141416", "bottom": "#060607"},
    },
    "light": {
        "colors": {"fg": "#18202E", "soft": "#4E5A70", "dim": "#93A0B6", "accent": "#2E6BFF",
                   "emph": "#FF5A5F", "panel": "#FFFFFF", "line": "#D9E1ED", "bg": "#F4F7FB",
                   "white": "#FFFFFF", "dark": "#10141C"},
        "onAccent": {"fg": "#FFFFFF", "soft": "#DCE6FF", "dim": "#A9BCE8", "accent": "#FFFFFF",
                     "emph": "#FFE08A"},
        "bg": {"type": "gradient", "top": "#F8FBFF", "bottom": "#E7EDF6"},
    },
}

TRANS_DUR = {"cut": 0.0, "fade": 0.5, "flash": 0.4, "wipe": 0.5, "push": 0.5, "zoom": 0.5}

ENTER_DUR = {"fade": 0.5, "rise": 0.6, "slide": 0.5, "pop": 0.5,
             "punch": 0.35, "slam": 0.30, "type": 0.0}

SFX_AUTO = {
    "pop": ("pop", 0.0, 0.0),
    "rise": ("swish", 0.0, -9.0),
    "slide": ("swish", 0.0, -9.0),
    "punch": ("impact", 0.0, -11.0),
    "slam": ("impact", 0.0, -2.0),
}

ICON_GLYPHS = {
    "check": "\u2713", "circle-check": "\u2714", "star": "\u2605", "rocket": "\u2192",
    "arrow": "\u2192", "dot": "\u2022", "warn": "\u26A0", "heart": "\u2665",
    "plus": "+", "cross": "\u2715", "spark": "\u2726",
}

_EMPH_RE = re.compile(r"\*\*(.+?)\*\*")


def _icon_glyph(icon):
    """icon 选项解析 -> (字符, 是否 tabler 图标字体)。

    内置字形名(check/cross/...) -> 内置字符；"tabler:名字" 或已知 tabler 图标名
    -> Tabler 字符；单字符按字面量；其余按原字符串（调用方决定是否 lint）。
    """
    if icon in ICON_GLYPHS:
        return ICON_GLYPHS[icon], False
    name = icon[7:] if icon.startswith("tabler:") else icon
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) and _icons.has(name):
        return _icons.char(name), True
    return icon, False

_BASE_OPTS = {"at", "out", "style", "enter", "size", "color", "bold", "font", "x", "y",
              "pos", "opacity", "sfx", "align", "line_gap"}
_KIND_OPTS = {
    "text": {"split", "stagger", "max_width"},
    "list": {"icon", "stagger", "gap"},
    "counter": {"format", "dur"},
    "image": {"width", "height", "radius", "title", "caption", "shadow", "zoom", "bg", "border"},
    "draw": {"width", "height", "bg", "border", "radius", "title", "caption"},
    "burst": {"on", "radius", "behind"},
    "audio": {"on", "gain", "text", "words", "name"},
}


def _runs(line):
    """把一行文本按 **强调** 切分为 [(文本, fg|emph), ...]。"""
    runs = []
    pos = 0
    for m in _EMPH_RE.finditer(line):
        if m.start() > pos:
            runs.append((line[pos:m.start()], "fg"))
        runs.append((m.group(1), "emph"))
        pos = m.end()
    if pos < len(line):
        runs.append((line[pos:], "fg"))
    return runs or [("", "fg")]


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")


def _split_words(text):
    """把一行拆成词序列（空白片段保留、供光标推进；标点并入前一个词）。
    拉丁词按字母/数字连写、CJK 逐字；无词典也稳。
    """
    out = []
    buf = []
    for ch in text:
        if ch in " \t\u3000":
            if buf:
                out.append("".join(buf))
                buf = []
            out.append(ch)
        elif _CJK_RE.match(ch):
            if buf:
                out.append("".join(buf))
                buf = []
            out.append(ch)
        elif ch.isalnum() or (buf and ch in "'\u2019_-."):
            buf.append(ch)
        else:  # 标点：并入前一个词
            if buf:
                buf.append(ch)
            elif out and out[-1].strip():
                out[-1] += ch
            else:
                out.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def _mix_rgb(c1, c2, k):
    return tuple(int(round(c1[i] * (1.0 - k) + c2[i] * k)) for i in range(3))


def _transparent_corners(im):
    """源图四角是否透明（PNG 图标类：默认不投影）。"""
    try:
        if im is None or im.mode != "RGBA":
            return False
        W, H = im.size
        for x, y in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
            if im.getpixel((x, y))[3] > 24:
                return False
        return True
    except Exception:
        return False


def _find_nth(s, sub, n=1):
    pos = -1
    for _ in range(max(1, int(n))):
        pos = s.find(sub, pos + 1)
        if pos < 0:
            return None
    return pos


def _default_styles():
    out = {}
    for n in STYLE_SIZES:
        out[n] = {"size": STYLE_SIZES[n], "bold": STYLE_BOLD[n], "enter": STYLE_ENTER[n], "color": STYLE_COLOR[n]}
    return out


def make_theme(spec):
    """主题：名称或覆盖表（base/colors/styles/bg/onAccent）。"""
    if isinstance(spec, dict):
        base = THEMES.get(spec.get("base", "midnight"), THEMES["midnight"])
        th = {"colors": dict(base["colors"]), "onAccent": dict(base.get("onAccent", {})),
              "bg": dict(base["bg"]) if isinstance(base["bg"], dict) else base["bg"],
              "styles": _default_styles()}
        th["colors"].update(spec.get("colors", {}))
        th["onAccent"].update(spec.get("onAccent", {}))
        if "bg" in spec:
            th["bg"] = spec["bg"]
        for k, v in (spec.get("styles") or {}).items():
            st = th["styles"].get(k, dict(th["styles"].get("body", {})))
            st.update(v)
            th["styles"][k] = st
        return th
    base = THEMES.get(spec, THEMES["midnight"])
    return {"colors": dict(base["colors"]), "onAccent": dict(base.get("onAccent", {})),
            "bg": dict(base["bg"]) if isinstance(base["bg"], dict) else base["bg"],
            "styles": _default_styles()}


class DrawCtx(object):
    """自绘回调的上下文（c.ctx）。"""
    __slots__ = ("palette", "seed", "t", "time", "_film", "elem")

    def __init__(self, palette, seed, t, time, film, elem):
        self.palette = palette
        self.seed = seed
        self.t = t
        self.time = time
        self._film = film
        self.elem = elem

    def box(self, el, piece=None):
        if el is None:
            return None
        return el.box()


# ================================================================ 元素

class Elem(object):
    def __init__(self, film, kind, content, opt=None, scene=None, internal=False):
        opt = dict(opt or {})
        self.film = film
        self.kind = kind
        self.content = content
        self.scene = scene
        self.internal = internal
        self.parent = None
        self.children = []
        film._elem_seq += 1
        self.seed = film.seed * 1000 + film._elem_seq
        base = scene.start if scene is not None else 0.0
        self.at = float(opt.get("at", base))
        self.out = opt.get("out")
        if self.out is not None:
            self.out = float(self.out)
        self.style = opt.get("style")
        st = film.style(self.style) if self.style else film.style("body")
        self.size = float(opt.get("size", st["size"]))
        self.bold = bool(opt.get("bold", st["bold"]))
        en = opt.get("enter", st["enter"])
        self.enter = None if en in (None, "none") else en
        self._default_enter = st["enter"]
        self.color = opt.get("color", st["color"])
        self.font = opt.get("font")
        self.align = opt.get("align", "center")
        self.line_gap = float(opt.get("line_gap", 1.35))
        self.x = opt.get("x")
        self.y = opt.get("y")
        self.pos = opt.get("pos") or ""
        self.opacity = float(opt.get("opacity", 1.0))
        self.sfx_opt = opt.get("sfx", True)
        self.done = None
        self.mw = 0.0
        self.mh = 0.0
        self.cx = None
        self.cy = None
        self._rasters = {}
        self._icon = None
        self._off = (0.0, 0.0)
        # 选项白名单
        if not internal:
            allowed = _BASE_OPTS | _KIND_OPTS.get(kind, set())
            unknown = [k for k in opt if k not in allowed]
            for k in unknown:
                near = difflib.get_close_matches(k, sorted(allowed), n=1)
                film._lint_add("warn", self.at, "%s 元素选项 %r 未识别%s" % (
                    kind, k, ("（是否想写 %r？）" % near[0]) if near else ""))
        # 分类初始化
        getattr(self, "_init_" + kind)(opt)

    # ---------------- 初始化 ----------------
    def _init_text(self, opt):
        txt = str(self.content).replace("\r", "")
        self.lines = txt.split("\n")
        self.mw, self.mh = self._measure_lines(self.lines, self.size)
        # 超宽自动缩小：显式 max_width，或 hero/title 超出安全区
        limit = opt.get("max_width")
        if limit is None and self.style in ("hero", "title"):
            limit = self.film.width - 2 * self.film.margin
        if limit and self.mw > limit > 0:
            k = float(limit) / self.mw * 0.98
            self.size = max(8.0, self.size * k)
            self.mw, self.mh = self._measure_lines(self.lines, self.size)
            self.film._lint_add("info", self.at, "文字超宽，字号自动缩小到 %.0f" % self.size)
        split = opt.get("split")
        if split in ("char", "line", "word"):
            self._make_children(opt, split)
        elif self.enter == "type":
            self.done = self.at + len("".join(self.lines)) * 0.045

    def _init_list(self, opt):
        self.items = [str(x) for x in self.content]
        self._icon = opt.get("icon")
        icon = self._icon
        gap = float(opt.get("gap", 0.55))
        # gap < 1.0 按字号比例；>= 1.0 视为像素间距
        row_gap = self.size * gap if gap < 1.0 else gap
        rows_wh = []
        glyph_pad = 0.0
        if icon:
            glyph, is_t = _icon_glyph(icon)
            f = (_icons.font(int(self.size)) if is_t else
                 _fonts.load(self.font or ("sans_bold" if self.bold else "sans"),
                             max(1, int(self.size))))
            glyph_pad = f.getlength(glyph) + self.size * 0.55
            if not is_t and icon not in ICON_GLYPHS:
                self.film._lint_add("warn", self.at,
                                    "未知图标 %r（内置字形名或 tabler:名字，tabler 共 %d 个）"
                                    % (icon, len(_icons.names())))
        for it in self.items:
            w, h = self._measure_lines([it], self.size)
            rows_wh.append((w + glyph_pad, h))
        self._rows = rows_wh
        self._row_gap = row_gap
        self.mw = max([r[0] for r in rows_wh] or [0.0])
        self.mh = sum(r[1] for r in rows_wh) + row_gap * max(0, len(rows_wh) - 1)
        self._make_list_children(opt)

    def _init_counter(self, opt):
        self.frm = float(self.content[0])
        self.to = float(self.content[1])
        self.fmt = opt.get("format", "%d")
        self.dur = float(opt.get("dur", 1.0))
        self.done = self.at + self.dur
        w1, h1 = self._measure_lines([self._fmt_value(self.frm)], self.size)
        w2, h2 = self._measure_lines([self._fmt_value(self.to)], self.size)
        self.mw, self.mh = max(w1, w2), max(h1, h2)

    def _init_image(self, opt):
        self.path = str(self.content)
        self.title = opt.get("title")
        self.caption = opt.get("caption")
        self.bg = opt.get("bg")
        self.border = opt.get("border")
        self._card = bool(self.title or self.bg or self.border)
        if self.title and self.bg is None:
            self.bg = True
        if self.title and self.border is None:
            self.border = True
        self.radius = float(opt.get("radius", 18 if self._card else 0))
        self._w = opt.get("width")
        self._h = opt.get("height")
        src = None
        w = h = 80.0
        if os.path.exists(self.path):
            src = _cv.load_image(self.path)
            w, h = float(src.width), float(src.height)
        elif self.scene is not None:
            self.film._lint_add("error", self.at, "找不到图片：%s" % self.path)
        if self._w and self._h:
            w, h = float(self._w), float(self._h)
        elif self._w:
            h = h * float(self._w) / w
            w = float(self._w)
        elif self._h:
            w = w * float(self._h) / h
            h = float(self._h)
        # 卡片几何（与字号同一坐标空间：像素）
        self.pad = 14.0 if self._card else 0.0
        self.bar_h = 44.0 if self.title else 0.0
        self.inner_w, self.inner_h = w, h
        card_w = w + 2 * self.pad
        card_h = h + 2 * self.pad + self.bar_h
        # 卡外说明文字（caption 样式）
        cap_st = self.film.style("caption")
        self._cap_size = float(cap_st["size"])
        self._cap_color = cap_st["color"]
        self._cap_h = 0.0
        cap_w = 0.0
        if self.caption:
            f = _fonts.load("sans", max(1, int(round(self._cap_size))))
            self._cap_h = float(sum(f.getmetrics()))
            cap_w = f.getlength(str(self.caption))
        self._cap_gap = 10.0 if self.caption else 0.0
        self.mw = max(card_w, cap_w)
        self.mh = card_h + (self._cap_h + self._cap_gap if self.caption else 0.0)
        # 投影：卡片默认；非全屏图片默认；源图四角透明或占满全屏时默认关闭
        shadow = opt.get("shadow")
        if shadow is None:
            full = (w * h) >= 0.95 * self.film.width * self.film.height
            shadow = bool(self._card) or (not full and not _transparent_corners(src))
        self.shadow = bool(shadow)
        # zoom（卡内推近）与自动 Ken Burns
        zoom = opt.get("zoom")
        self.zoom = None
        self._kb = None
        self._end_default = None
        if zoom is not None:
            if isinstance(zoom, (int, float)):
                self.zoom = ("static", float(zoom))
            else:
                kf = []
                for it in zoom:
                    kf.append((float(it[0]), float(it[1]),
                               float(it[2]) if len(it) > 2 else 0.5,
                               float(it[3]) if len(it) > 3 else 0.5,
                               str(it[4]) if len(it) > 4 else "easeInOutSine"))
                kf.sort(key=lambda x: x[0])
                self.zoom = ("keys", kf)

    def _init_draw(self, opt):
        self.fn = self.content
        self.w = opt.get("width")
        self.h = opt.get("height")
        self.bg = opt.get("bg")
        self.border = opt.get("border")
        self.radius = float(opt.get("radius", 18))
        if self.w and self.h:
            self.mw, self.mh = float(self.w), float(self.h)
            if self.y is None and self.x is not None:
                pass
        else:
            self.mw, self.mh = float(self.film.width), float(self.film.height)
            if self.x is not None or self.y is not None:
                self.film._lint_add("warn", self.at, "整屏自绘不接受 x/y（不参与排版）")
                self.x = self.y = None
        for k in ("title", "caption"):
            if opt.get(k):
                self.film._lint_add("warn", self.at, "draw 的 %s 选项在通用版 v1 暂未支持" % k)

    def _init_burst(self, opt):
        self.target = opt.get("on")
        self.radius = opt.get("radius")
        if "at" not in opt and self.target is not None:
            self.at = getattr(self.target, "at", self.at) + 0.45
        self.mw = self.mh = 0.0

    def _init_audio(self, opt):
        src = self.content
        if isinstance(src, dict):
            path = src.get("path") or src.get("file")
            self.text = src.get("text", opt.get("text"))
            self.words = src.get("words", opt.get("words"))
            self.name = src.get("name", opt.get("name"))
        else:
            path = src
            self.text = opt.get("text")
            self.words = opt.get("words")
            self.name = opt.get("name")
        self.path = str(path)
        self.gain = float(opt.get("gain", 0.0))
        self.mw = self.mh = 0.0
        self.buf = None
        self._lead = 0.0
        self.duration = 0.0
        self.done = self.at
        self._err = None
        if "on" in opt and "at" not in opt:
            self.at = float(getattr(opt["on"], "at", self.at))
        if self.words:
            wl = []
            for w in self.words:
                if isinstance(w, dict):
                    wl.append({"text": str(w.get("text", "")), "at": float(w.get("at", 0.0)),
                               "dur": float(w.get("dur", 0.1))})
                else:
                    wl.append({"text": str(w[0]), "at": float(w[1]),
                               "dur": float(w[2]) if len(w) > 2 else 0.1})
            self.words = wl
        if not os.path.exists(self.path):
            self._err = "找不到声音文件：%s" % self.path
            return
        from . import audio as _audio
        try:
            self.buf, self._lead = _audio.prepare_voice(self.path, gain_db=self.gain)
        except Exception as e:
            self._err = "读不出声音：%s（%s）" % (self.path, e)
            return
        if self.buf is None or len(self.buf) == 0:
            self._err = "声音为空或整段静音：%s" % self.path
            return
        self.duration = len(self.buf) / float(_audio.SR)
        self.done = self.at + self.duration
        # 词时间以文件开头为参照；这里补偿被裁掉的头部静音
        if self.words and self._lead > 0:
            for it in self.words:
                it["at"] = max(0.0, it["at"] - self._lead)

    def word(self, w, n=1):
        """audio 元素：说到第 n 次出现的词 w 的成片秒（写进画面 at 对齐）。"""
        if self.kind != "audio":
            raise TypeError("word() 只用于 audio 元素")
        if self.text is None:
            raise ValueError("这段声音没有台词文本（text）")
        txt = str(self.text)
        key = str(w)
        if self.words:
            k = 0
            for it in self.words:
                if key in it["text"]:
                    k += 1
                    if k >= n:
                        return self.at + it["at"]
        else:
            pos = _find_nth(txt, key, n)
            if pos is not None:
                a = pos / max(1, len(txt))
                b = (pos + len(key)) / max(1, len(txt))
                return self.at + (a + b) / 2.0 * max(0.0, self.duration)
        self.film._lint_add("error", self.at, "台词里找不到词 %r：%s" % (key, txt[:24]))
        return self.at

    # ---------------- 量测 ----------------
    def _font_at(self, size, ss=1.0):
        kind = self.font or ("sans_bold" if self.bold else "sans")
        return _fonts.load(kind, max(1, int(round(size * ss))))

    def _measure_lines(self, lines, size):
        f = self._font_at(size, 1.0)
        lh = float(sum(f.getmetrics()))
        step = max(lh, size * self.line_gap)
        widths = []
        for ln in lines:
            w = 0.0
            for txt, ck in _runs(ln):
                w += f.getlength(txt)
            widths.append(w)
        w = max(widths or [0.0])
        h = (len(lines) - 1) * step + lh
        return w, h

    # ---------------- 子元素（逐字 / 逐行 / 清单行） ----------------
    def _make_children(self, opt, split):
        co = {k: opt[k] for k in ("style", "size", "color", "bold", "font", "line_gap", "opacity") if k in opt}
        stagger = opt.get("stagger")
        units = []
        f = self._font_at(self.size, 1.0)
        lh = float(sum(f.getmetrics()))
        step = max(lh, self.size * self.line_gap)
        idx = 0
        for i, ln in enumerate(self.lines):
            if split == "line":
                w, h = self._measure_lines([ln], self.size)
                lx = 0.0 if self.align == "left" else (self.mw - w if self.align == "right" else (self.mw - w) / 2)
                units.append((lx, i * step, ln, idx))
                idx += 1
            else:
                runs = _runs(ln)
                plain = "".join(t for t, c in runs)
                lw = sum(f.getlength(t) for t, c in runs)
                lx = 0.0 if self.align == "left" else (self.mw - lw if self.align == "right" else (self.mw - lw) / 2)
                cursor = lx
                seq = _split_words(plain) if split == "word" else list(plain)
                for unit in seq:
                    cw = f.getlength(unit)
                    if unit.strip():
                        units.append((cursor, i * step, unit, idx))
                    cursor += cw
                    idx += 1
        self.children = []
        for (lx, ly, txt, i) in units:
            ch = Elem(self.film, "text", txt, co, self.scene, internal=True)
            ch.parent = self
            ch.enter = self.enter or self._default_enter
            if ch.enter == "none":
                ch.enter = None
            ch.out = self.out
            if isinstance(stagger, (list, tuple)):
                st = float(stagger[min(i, len(stagger) - 1)]) if stagger else 0.0
            else:
                st = float(stagger) if stagger is not None else (
                    0.045 if split == "char" else (0.07 if split == "word" else 0.12))
            ch.at = self.at + i * st
            ch._off = (lx, ly)
            ch.opacity = self.opacity
            self.children.append(ch)
        eff_enter = self.enter or self._default_enter
        if split in ("char", "word"):
            self.done = self.at + max(0, idx - 1) * (
                stagger if isinstance(stagger, (int, float)) else (0.045 if split == "char" else 0.07)) \
                + ENTER_DUR.get(eff_enter, 0.0)
        self.enter = None

    def _make_list_children(self, opt):
        co = {k: opt[k] for k in ("style", "size", "color", "bold", "font", "line_gap", "opacity") if k in opt}
        stagger = opt.get("stagger")
        self.children = []
        y = 0.0
        icon = self._icon
        f = self._font_at(self.size, 1.0)
        glyph_pad = 0.0
        if icon:
            glyph, is_t = _icon_glyph(icon)
            glyph_pad = ((_icons.font(int(self.size)) if is_t else f)
                         .getlength(glyph) + self.size * 0.55)
        for i, it in enumerate(self.items):
            ch = Elem(self.film, "text", it, co, self.scene, internal=True)
            ch.parent = self
            ch._icon = icon
            ch.enter = self.enter or "slide"
            if ch.enter == "none":
                ch.enter = None
            ch.out = self.out
            if isinstance(stagger, (list, tuple)):
                st = float(stagger[min(i, len(stagger) - 1)])
            else:
                st = float(stagger) if stagger is not None else 0.3
            ch.at = self.at + i * st
            ch._off = (0.0, y)
            y += self._rows[i][1] + self._row_gap
            self.children.append(ch)
        # 清单行需要带图标重测（含图标宽度）
        for i, ch in enumerate(self.children):
            if icon:
                w, h = self._measure_lines([ch.content], self.size)
                ch.mw = w + glyph_pad
                ch.mh = h
        eff_enter = self.enter or "slide"
        if self.children:
            self.done = self.children[-1].at + ENTER_DUR.get(eff_enter, 0.0)
        self.enter = None

    # ---------------- 入场 / 退场 ----------------
    def enter_state(self, t):
        en = self.enter
        if en is None:
            return {"a": 1.0, "dx": 0.0, "dy": 0.0, "s": 1.0}
        if en == "fade":
            if t < 0:
                return None
            p = min(1.0, t / 0.5)
            return {"a": ease("easeOutCubic", p), "dx": 0.0, "dy": 0.0, "s": 1.0}
        if en == "rise":
            if t < 0:
                return None
            p = min(1.0, t / 0.6)
            e = ease("easeOutCubic", p)
            return {"a": e, "dx": 0.0, "dy": 36 * (1 - e), "s": 0.965 + 0.035 * min(1.0, p)}
        if en == "slide":
            if t < 0:
                return None
            p = min(1.0, t / 0.5)
            e = ease("easeOutCubic", p)
            return {"a": min(1.0, p * 1.8), "dx": -88 * (1 - e), "dy": 0.0, "s": 1.0}
        if en == "pop":
            if t < 0:
                return None
            p = min(1.0, t / 0.5)
            return {"a": min(1.0, t / 0.14), "dx": 0.0, "dy": 0.0, "s": 0.55 + 0.45 * ease("easeOutBack", p)}
        if en == "punch":
            if t < 0:
                return None
            p = min(1.0, t / 0.35)
            return {"a": 1.0, "dx": 0.0, "dy": 0.0, "s": 1.0 + 0.30 * (1 - ease("easeOutCubic", p))}
        if en == "slam":
            if t < -0.30:
                return None
            # 起始倍率按文本宽度封顶：宽文本落定前横向不出画幅，窄文本保持 2.6 倍砸落
            s0 = 2.6
            if self.mw:
                s0 = min(s0, self.film.width * 0.92 / self.mw)
            s0 = max(1.0, s0)
            if t < 0:
                p = (t + 0.30) / 0.30
                return {"a": min(1.0, p * 5), "dx": 0.0, "dy": 0.0, "s": lerp(s0, 1.0, ease("easeInCubic", p))}
            k = 0.16 * decay(t, 3.4, 8.5)
            return {"a": 1.0, "dx": 0.0, "dy": 0.0, "s": 1.0, "sx": 1.0 + k, "sy": 1.0 - k}
        if en == "type":
            return {"a": 1.0, "dx": 0.0, "dy": 0.0, "s": 1.0}
        return {"a": 1.0, "dx": 0.0, "dy": 0.0, "s": 1.0}

    def out_alpha(self, t):
        if self.out is None:
            return 1.0
        if t >= self.out:
            return 0.0
        k = (self.out - t) / 0.35
        if k >= 1.0:
            return 1.0
        return ease("easeInCubic", max(0.0, k))

    def end_time(self, end_default):
        return self.out if self.out is not None else end_default

    def box(self):
        if self.cx is None or self.cy is None:
            return None
        return (self.cx - self.mw / 2, self.cy - self.mh / 2, self.mw, self.mh)

    def local_time(self, t):
        return t - self.at

    def _guess_cx(self, film):
        if self.x is not None:
            return float(self.x)
        pos = self.pos or ""
        if "left" in pos:
            return film.margin + self.mw / 2
        if "right" in pos:
            return film.width - film.margin - self.mw / 2
        return film.width / 2

    # ---------------- 文字光栅 ----------------
    def _text_raster(self, ss, lines=None, size=None, icon=None, cache_key=None, color=None):
        lines = lines if lines is not None else getattr(self, "lines", [str(self.content)])
        size = size if size is not None else self.size
        key = cache_key if cache_key is not None else ("t", round(ss, 3), len(lines), id(lines))
        r = self._rasters.get(key)
        pal = self.film.palette
        col_fg = parse_color(self.color if color is None else color, pal)
        col_emph = parse_color("emph", pal)
        col_accent = parse_color("accent", pal)
        glyph = None
        is_t = False
        if icon:
            glyph, is_t = _icon_glyph(icon)
        if r is None:
            px = max(1, int(round(size * ss)))
            kind = self.font or ("sans_bold" if self.bold else "sans")
            f = _fonts.load(kind, px)
            gf = _icons.font(px) if is_t else f
            lh = float(sum(f.getmetrics()))
            step = max(lh, px * self.line_gap)
            pad = max(3.0, size * 0.24) * ss
            runs_lines = [_runs(ln) for ln in lines]
            widths = []
            glyph_w = 0.0
            if glyph:
                glyph_w = gf.getlength(glyph) + size * 0.55 * ss
            for i, runs in enumerate(runs_lines):
                w = sum(f.getlength(txt) for txt, ck in runs)
                if i == 0 and glyph:
                    w += glyph_w
                widths.append(w)
            mw = max(widths or [0.0])
            h = (len(lines) - 1) * step + lh
            W = int(math.ceil(mw + 2 * pad))
            H = int(math.ceil(h + 2 * pad))
            img = Image.new("RGBA", (max(1, W), max(1, H)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img, "RGBA")
            for i, runs in enumerate(runs_lines):
                x = pad
                if self.align == "center":
                    x += (mw - widths[i]) / 2
                elif self.align == "right":
                    x += mw - widths[i]
                y = pad + i * step
                if i == 0 and glyph:
                    d.text((int(round(x)), int(round(y))), glyph, font=gf, fill=col_accent + (255,))
                    x += glyph_w
                for txt, ck in runs:
                    if not txt:
                        continue
                    d.text((int(round(x)), int(round(y))), txt, font=f,
                           fill=(col_emph if ck == "emph" else col_fg) + (255,))
                    x += f.getlength(txt)
            r = (img, pad, mw, h)
            self._rasters[key] = r
        return r

    def _reveal_chars(self, t):
        """typewriter：已显示字符数。"""
        pts = getattr(self, "lines", [""])
        plain = "".join(pts) if isinstance(pts, list) else str(pts)
        n = len(plain)
        return int(clamp(t / 0.045, 0, n))

    def _reveal_px(self, k, ss):
        lines = getattr(self, "lines", [str(self.content)])
        f = self._font_at(self.size, ss)
        cnt = 0
        w = 0.0
        for ln in lines:
            for ch in ln:
                if cnt >= k:
                    return w
                w += f.getlength(ch)
                cnt += 1
        return w

    # ---------------- 绘制 ----------------
    def draw(self, img, t, ss, palette, extra_dy=0.0, extra_a=1.0):
        if self.kind == "audio":
            return
        lt = t - self.at  # 元素本地秒（入场/打字/自绘都按本地时间）
        st = self.enter_state(lt)
        if st is None:
            return
        a = st["a"] * self.out_alpha(t) * self.opacity * extra_a
        if a <= 0.004:
            return
        dx = st["dx"]
        dy = st["dy"] + extra_dy
        sx = st.get("sx", st["s"])
        sy = st.get("sy", st["s"])
        if self.style == "hero" and self.enter in ("pop", "punch", "slam"):
            t0 = {"pop": 0.5, "punch": 0.35, "slam": 0.35}[self.enter]
            if lt > t0:
                w = 1 + 0.006 * math.sin(2 * math.pi * 0.32 * (lt - t0))
                sx *= w
                sy *= w
        if self.kind in ("text", "counter"):
            if not self.children:
                self._draw_text(img, lt, ss, a, dx, dy, sx, sy)
        elif self.kind == "image":
            self._draw_image(img, lt, ss, a, dx, dy, sx, sy)
        elif self.kind == "draw":
            self._draw_custom(img, lt, ss, palette, a, dx, dy, sx, sy)
        elif self.kind == "burst":
            self._draw_burst(img, lt, ss, palette, a, dx, dy)
        for ch in self.children:
            ch.draw(img, t, ss, palette, extra_dy=extra_dy, extra_a=a)

    def _paste(self, img, ss, rgba, cx, cy, a, sx, sy):
        if sx != 1.0 or sy != 1.0:
            w2 = max(1, int(round(rgba.width * sx)))
            h2 = max(1, int(round(rgba.height * sy)))
            key = (id(rgba), w2, h2)
            rr = self.film._paste_cache.get(key)
            if rr is None:
                rr = rgba.resize((w2, h2), Image.BILINEAR)
                self.film._paste_cache.put(key, rr)
            rgba = rr
        if a < 0.996:
            key2 = (id(rgba), int(a * 32))
            rr = self.film._paste_cache.get(key2)
            if rr is None:
                alpha = rgba.getchannel("A").point(lambda v: int(v * a))
                rr = rgba.copy()
                rr.putalpha(alpha)
                self.film._paste_cache.put(key2, rr)
            rgba = rr
        px = int(round(cx * ss - rgba.width / 2))
        py = int(round(cy * ss - rgba.height / 2))
        img.paste(rgba, (px, py), rgba)

    def _text_left(self, dx=0.0):
        """文本 raster 左缘的成片 x（align 感知：left=锚点，right=锚点-宽，center=锚点-半宽）。"""
        if self.align == "left":
            return self.cx + dx
        if self.align == "right":
            return self.cx + dx - self.mw
        return self.cx + dx - self.mw / 2

    def _draw_text(self, img, t, ss, a, dx, dy, sx, sy):
        if self.kind == "counter":
            txt = self._fmt_value(self._counter_value(t))
            key = ("c", round(ss, 3), txt)
            r = self._rasters.get(key)
            if r is None:
                r = self._text_raster(ss, lines=[txt], cache_key=key)
            rgba, pad_px, mw_px, mh_px = r
            self._paste(img, ss, rgba, self._text_left(dx) + self.mw / 2, self.cy + dy, a, sx, sy)
            return
        icon = getattr(self, "_icon", None)
        rgba, pad_px, mw_px, mh_px = self._text_raster(ss, icon=icon)
        if self.enter == "type":
            k = self._reveal_chars(t)
            plain_len = len("".join(self.lines))
            if k < plain_len:
                rw = self._reveal_px(k, ss)
                rgba = rgba.crop((0, 0, min(rgba.width, int(math.ceil(self._text_raster_pad(ss) + rw))), rgba.height))
                # 打字中从左缘固定位置揭示（不平移），位置按 align 算
                px = int(round(self._text_left(dx) * ss - self._text_raster_pad(ss)))
                py = int(round((self.cy + dy) * ss - rgba.height / 2))
                if a < 0.996:
                    key2 = (id(rgba), int(a * 32))
                    rr = self.film._paste_cache.get(key2)
                    if rr is None:
                        alpha = rgba.getchannel("A").point(lambda v: int(v * a))
                        rr = rgba.copy()
                        rr.putalpha(alpha)
                        self.film._paste_cache.put(key2, rr)
                    rgba = rr
                img.paste(rgba, (px, py), rgba)
                # 光标
                cur_x = self._text_left(dx) + rw / ss
                if (t * 2.0) % 1.0 < 0.55:
                    c2 = Canvas(img, ss=ss, width=self.film.width, height=self.film.height)
                    c2.rect(cur_x, self.cy + dy - self.size * 0.48, max(2.0, 3.0), self.size * 0.96,
                            fill="accent", alpha=a * 0.9)
                    if hasattr(c2, "flush"):
                        c2.flush()
                return
        self._paste(img, ss, rgba, self._text_left(dx) + self.mw / 2, self.cy + dy, a, sx, sy)

    def _text_raster_pad(self, ss):
        return max(3.0, self.size * 0.24) * ss

    def _draw_image(self, img, t, ss, a, dx, dy, sx, sy):
        if not os.path.exists(self.path):
            return
        self._ensure_kb()
        cx = self.cx + dx
        cy = self.cy + dy
        plain = (not self._card and not self.caption and not self.shadow
                 and self.zoom is None and self._kb is None)
        if plain:
            # 快速路径：无卡片/投影/推近（与 v1 行为一致）
            w = max(1, int(round(self.mw * sx * ss)))
            h = max(1, int(round(self.mh * sy * ss)))
            spr = _cv.image_sprite(self.path, w, h, self.radius * ss, a)
            px = int(round(cx * ss - w / 2))
            py = int(round(cy * ss - h / 2))
            img.paste(spr, (px, py), spr)
            return
        card_w = (self.inner_w + 2 * self.pad) * sx
        card_h = (self.inner_h + 2 * self.pad + self.bar_h) * sy
        total_w = self.mw * sx
        total_h = self.mh * sy
        card_x = cx - total_w / 2 + (total_w - card_w) / 2
        card_y = cy - total_h / 2
        if self.shadow:
            spr, pad_px = self._card_shadow_sprite(card_w * ss, card_h * ss, self.radius * ss)
            spr = self._with_alpha(spr, a)
            img.paste(spr, (int(round(card_x * ss)) - pad_px, int(round(card_y * ss)) - pad_px), spr)
        if self._card:
            spr = self._card_bg_sprite(card_w * ss, card_h * ss, self.radius * ss)
            spr = self._with_alpha(spr, a)
            img.paste(spr, (int(round(card_x * ss)), int(round(card_y * ss))), spr)
        # 卡内画面（含 zoom / Ken Burns）
        f, zx, zy = self._zoom_at(t)
        iw = max(1, int(round(self.inner_w * sx * ss)))
        ih = max(1, int(round(self.inner_h * sy * ss)))
        inner = self._inner_sprite(iw, ih, f, zx, zy)
        if inner is not None:
            r = max(0.0, self.radius - self.pad) if self._card else self.radius
            if r > 0.5:
                inner = self._round_sprite(inner, r * ss)
            inner = self._with_alpha(inner, a)
            ix = card_x + self.pad * sx
            iy = card_y + (self.pad + self.bar_h) * sy
            img.paste(inner, (int(round(ix * ss)), int(round(iy * ss))), inner)
        if self._card:
            spr = self._card_front_sprite(card_w * ss, card_h * ss, self.radius * ss)
            spr = self._with_alpha(spr, a)
            img.paste(spr, (int(round(card_x * ss)), int(round(card_y * ss))), spr)
        if self.caption:
            rgba, pad_px, mw_px, mh_px = self._text_raster(
                ss, lines=[str(self.caption)], size=self._cap_size,
                cache_key=("cap", round(ss, 3)), color=self._cap_color)
            rgba = self._with_alpha(rgba, a)
            img.paste(rgba, (int(round(card_x * ss - pad_px)),
                             int(round((card_y + card_h + self._cap_gap) * ss))), rgba)

    # ---------------- 卡片贴片 / 推近（image） ----------------
    def _ensure_kb(self):
        if self.kind != "image" or self.zoom is not None or self._kb is not None:
            return
        t_end = getattr(self, "_end_default", None)
        if t_end is None:
            return
        stay = float(t_end) - self.at
        if self.inner_w * self.inner_h >= 0.40 * self.film.width * self.film.height and stay >= 3.0:
            d = (rand(self.seed, 5) - 0.5) * 0.10
            e = (rand(self.seed, 9) - 0.5) * 0.08
            self._kb = (self.at + 0.4, float(t_end), 1.0, 1.07, 0.5 + d, 0.5 + e)

    def _zoom_at(self, t):
        """返回卡内画面的 (倍数, 中心x01, 中心y01)。"""
        if self.zoom is None and self._kb is None:
            return 1.0, 0.5, 0.5
        if self.zoom is not None:
            if self.zoom[0] == "static":
                return self.zoom[1], 0.5, 0.5
            kf = self.zoom[1]
            lt = t - self.at
            if lt <= kf[0][0]:
                return kf[0][1], kf[0][2], kf[0][3]
            for i in range(1, len(kf)):
                if lt <= kf[i][0]:
                    a, b = kf[i - 1], kf[i]
                    p = 1.0 if b[0] - a[0] <= 1e-6 else (lt - a[0]) / (b[0] - a[0])
                    e = ease(b[4], clamp(p, 0.0, 1.0))
                    return (lerp(a[1], b[1], e), lerp(a[2], b[2], e), lerp(a[3], b[3], e))
            return kf[-1][1], kf[-1][2], kf[-1][3]
        t0, t1, f0, f1, zx, zy = self._kb
        p = clamp((t - t0) / max(0.001, t1 - t0), 0.0, 1.0)
        e = ease("easeInOutSine", p)
        return lerp(f0, f1, e), zx, zy

    def _inner_sprite(self, iw, ih, f, zx, zy):
        src = _cv.load_image(self.path)
        W, H = float(src.width), float(src.height)
        vw = max(1.0, W / max(1.0, f))
        vh = max(1.0, H / max(1.0, f))
        ox = clamp(zx * W - vw / 2.0, 0.0, max(0.0, W - vw))
        oy = clamp(zy * H - vh / 2.0, 0.0, max(0.0, H - vh))
        key = ("zin", self.path, iw, ih, round(f, 3), int(ox), int(oy))
        out = self.film._zoom_cache.get(key)
        if out is None:
            crop = src.crop((int(round(ox)), int(round(oy)),
                             int(round(ox + vw)), int(round(oy + vh))))
            rs = Image.LANCZOS if abs(f - 1.0) < 1e-6 else Image.BILINEAR
            out = crop.resize((iw, ih), rs)
            self.film._zoom_cache.put(key, out)
        return out

    def _with_alpha(self, spr, a):
        if a >= 0.996:
            return spr
        key = ("wa", id(spr), int(a * 32))
        rr = self.film._paste_cache.get(key)
        if rr is None:
            alpha = spr.getchannel("A").point(lambda v: int(v * a))
            rr = spr.copy()
            rr.putalpha(alpha)
            self.film._paste_cache.put(key, rr)
        return rr

    def _round_sprite(self, spr, r_px):
        key = ("rs", id(spr), int(round(r_px)))
        out = self.film._paste_cache.get(key)
        if out is None:
            mask = _cv._rounded_mask(spr.size, r_px)
            out = Image.new("RGBA", spr.size, (0, 0, 0, 0))
            out.paste(spr, (0, 0), mask)
            self.film._paste_cache.put(key, out)
        return out

    def _card_bg_sprite(self, w_px, h_px, r_px):
        w = max(2, int(round(w_px)))
        h = max(2, int(round(h_px)))
        r = max(0, int(round(r_px)))
        pal = self.film._frame_palette
        col = parse_color("panel" if self.bg is True else self.bg, pal)
        key = ("cbg", w, h, r, col)
        spr = self.film._card_sprites.get(key)
        if spr is None:
            spr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(spr)
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=col + (255,))
            self.film._card_sprites[key] = spr
        return spr

    def _card_front_sprite(self, w_px, h_px, r_px):
        w = max(2, int(round(w_px)))
        h = max(2, int(round(h_px)))
        r = max(0, int(round(r_px)))
        pal = self.film._frame_palette
        panel = parse_color("panel" if self.bg is True else self.bg, pal)
        fg = parse_color("fg", pal)
        line = parse_color("line" if self.border is True else self.border, pal)
        bar_h = max(0, int(round(self.bar_h)))
        title = str(self.title) if self.title else ""
        key = ("cfr", w, h, r, bar_h, title, panel, fg, line, round(self._cap_size, 1))
        spr = self.film._card_sprites.get(key)
        if spr is None:
            spr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(spr)
            bar_col = _mix_rgb(panel, fg, 0.10)
            if bar_h > 1:
                mask = _cv._rounded_mask((w, h), r)
                bar = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                db = ImageDraw.Draw(bar)
                db.rectangle([0, 0, w - 1, bar_h - 1], fill=bar_col + (255,))
                spr.paste(bar, (0, 0), mask)
                if title:
                    size = max(10, int(round(min(self._cap_size, bar_h * 0.56))))
                    f = _fonts.load("sans", size)
                    tw = f.getlength(title)
                    d.text(((w - tw) / 2.0, (bar_h - size) / 2.0 - size * 0.10), title,
                           font=f, fill=_mix_rgb(bar_col, fg, 0.58) + (255,))
                dot = max(2.0, bar_h * 0.10)
                for i in range(3):
                    x = dot * 3.0 + i * dot * 2.4
                    d.ellipse([x - dot, bar_h / 2.0 - dot, x + dot, bar_h / 2.0 + dot],
                              fill=_mix_rgb(bar_col, fg, 0.30) + (255,))
                d.line([1, bar_h, w - 2, bar_h], fill=_mix_rgb(panel, fg, 0.16) + (255,), width=1)
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, outline=line + (255,), width=2)
            self.film._card_sprites[key] = spr
        return spr

    def _card_shadow_sprite(self, w_px, h_px, r_px):
        w = max(2, int(round(w_px)))
        h = max(2, int(round(h_px)))
        r = max(0, int(round(r_px)))
        key = ("csh", w, h, r)
        hit = self.film._card_sprites.get(key)
        if hit is not None:
            return hit
        blur = max(4, int(round(min(w, h) * 0.05)))
        pad = blur * 3
        mask = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
        dm = ImageDraw.Draw(mask)
        dm.rounded_rectangle([pad, pad + blur // 2, pad + w - 1, pad + h - 1 + blur // 2],
                             radius=r, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
        alpha = mask.point(lambda v: v * 100 // 255)
        spr = Image.new("RGBA", mask.size, (0, 0, 0, 255))
        spr.putalpha(alpha)
        self.film._card_sprites[key] = (spr, pad)
        return spr, pad

    def _draw_custom(self, img, t, ss, palette, a, dx, dy, sx, sy):
        ctx = DrawCtx(palette, self.seed, t, self.film._cur_time, self.film, self)
        if self.w and self.h:
            lw = max(2, int(round(self.w * ss)))
            lh = max(2, int(round(self.h * ss)))
            layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
            bx = self.cx - self.w / 2
            by = self.cy - self.h / 2
            c = Canvas(layer, ss=ss, width=self.w, height=self.h, ctx=ctx, box_origin=(bx, by))
            if self.bg:
                c.rect(0, 0, self.w, self.h, fill=("panel" if self.bg is True else self.bg), radius=self.radius)
            if self.border:
                c.rect(0, 0, self.w, self.h, outline=("line" if self.border is True else self.border),
                       width=2, radius=self.radius)
            self.fn(c, t)
            if hasattr(c, "flush"):
                c.flush()
            if sx != 1.0 or sy != 1.0:
                w2 = max(1, int(round(layer.width * sx)))
                h2 = max(1, int(round(layer.height * sy)))
                layer = layer.resize((w2, h2), Image.BILINEAR)
            if a < 0.996:
                alpha = layer.getchannel("A").point(lambda v: int(v * a))
                layer = layer.copy()
                layer.putalpha(alpha)
            px = int(round((self.cx + dx) * ss - layer.width / 2))
            py = int(round((self.cy + dy) * ss - layer.height / 2))
            img.paste(layer, (px, py), layer)
            return
        # 整屏自绘
        if a >= 0.996 and sx == 1.0 and sy == 1.0:
            c = Canvas(img, ss=ss, width=self.film.width, height=self.film.height, ctx=ctx,
                       ox=dx, oy=dy)
            self.fn(c, t)
            if hasattr(c, "flush"):
                c.flush()
            return
        # 整屏自绘（带元素透明度 / 缩放）：在当前帧的不透明副本上绘制，
        # 内部半透明 ink 以帧内容为底正常混合；再与原帧按元素透明度 a 混合。
        # （此前用透明 RGBA 层起步，半透明 ink 会被"预乘黑"压暗：淡出期间
        #   光环变深环、蒸汽变灰、淡色笔触发闷。）
        layer = img.copy().convert("RGBA")
        c = Canvas(layer, ss=ss, width=self.film.width, height=self.film.height, ctx=ctx)
        self.fn(c, t)
        if hasattr(c, "flush"):
            c.flush()
        if sx != 1.0 or sy != 1.0:
            w2 = max(1, int(round(layer.width * sx)))
            h2 = max(1, int(round(layer.height * sy)))
            layer = layer.resize((w2, h2), Image.BILINEAR)
        base = img.copy().convert("RGBA")
        if base.size != layer.size:
            base = base.resize(layer.size, Image.BILINEAR)
        blended = Image.blend(base, layer, clamp(a, 0.0, 1.0))
        px = int(round(dx * ss - (layer.width - img.width) / 2))
        py = int(round(dy * ss - (layer.height - img.height) / 2))
        img.paste(blended.convert(img.mode), (px, py))

    def _draw_burst(self, img, t, ss, palette, a, dx, dy):
        age = t - 0.0
        if age < 0 or age > 0.8:
            return
        cx = cy = None
        if self.target is not None:
            b = self.target.box()
            if b:
                cx = b[0] + b[2] / 2
                cy = b[1] + b[3] / 2
            else:
                cx, cy = self.film.width / 2, self.film.height / 2
        if cx is None:
            cx, cy = self.film.width / 2, self.film.height / 2
        fade = 1 - age / 0.8
        c = Canvas(img, ss=ss, width=self.film.width, height=self.film.height)
        acc = parse_color("accent", palette)
        emph = parse_color("emph", palette)
        # 冲击环
        r0 = 24 + 110 * ease("easeOutCubic", age / 0.8)
        c.circle(cx + dx, cy + dy, r0, outline="accent", width=3, alpha=0.55 * fade * a)
        if self.content == "confetti":
            for i in range(26):
                ang = rand(self.seed, i) * 2 * math.pi
                sp = 60 + 380 * rand(self.seed, i + 40)
                px = cx + dx + math.cos(ang) * sp * age
                py = cy + dy + math.sin(ang) * sp * age + 300 * age * age
                col = acc if i % 2 else emph
                c.rect(px - 4, py - 4, 9, 9, fill=col, alpha=0.85 * fade * a)
            return
        # sparkle
        c.glow(cx + dx, cy + dy, 130 * fade, "accent", 0.45 * fade * a)
        for i in range(22):
            ang = rand(self.seed, i) * 2 * math.pi
            d = (36 + 210 * rand(self.seed, i + 50)) * (1 - math.exp(-5.5 * age))
            x = cx + dx + math.cos(ang) * d
            y = cy + dy + math.sin(ang) * d
            ln = 18 * fade
            c.line(x, y, x - math.cos(ang) * ln, y - math.sin(ang) * ln, color="accent", width=3,
                   alpha=0.9 * fade * a)
            c.circle(x, y, 2.2, fill="fg", alpha=0.9 * fade * a)

    # ---------------- 计数器 ----------------
    def _counter_value(self, t):
        # t 是元素本地秒（draw 传入的已是本地时间 t - at）
        p = clamp(t / max(0.001, self.dur), 0, 1)
        return self.frm + (self.to - self.frm) * ease("easeOutCubic", p)

    def _fmt_value(self, v):
        if "%d" in self.fmt:
            return self.fmt % int(round(v))
        return self.fmt % v


# ================================================================ 场景

class Scene(object):
    def __init__(self, film, start, end, transition="cut", bg=None, name=None):
        self.film = film
        self.start = float(start)
        self.end = float(end)
        self.transition = transition
        self.bg = bg
        self.name = name
        self.index = 0
        self.prev = None
        self.elements = []

    def _add(self, kind, content, opt):
        el = Elem(self.film, kind, content, opt, self)
        if not el.internal:
            self.elements.append(el)
        self.film._prepared = False
        return el

    def text(self, s, **opt):
        return self._add("text", s, opt)

    def list(self, items, **opt):
        return self._add("list", items, opt)

    def counter(self, frm, to, **opt):
        return self._add("counter", (frm, to), opt)

    def image(self, path, **opt):
        return self._add("image", path, opt)

    def draw(self, fn, **opt):
        return self._add("draw", fn, opt)

    def burst(self, kind="sparkle", **opt):
        return self._add("burst", kind, opt)

    def audio(self, src, **opt):
        """放一段外部声音（配音/旁白/录音）：文件路径或 {path;text;words} 表。"""
        return self._add("audio", src, opt)

    def sfx(self, name, at, gain=0.0, dur=None, pitch=0.0):
        """在（全局）at 秒放一个音效。"""
        self.film.sfx(name, at, gain=gain, dur=dur, pitch=pitch)


# ================================================================ 影片

class Film(object):
    def __init__(self, width=1920, height=1080, duration=None, fps=30, ss=2,
                 theme="midnight", bpm=120, music=None, seed=1, grain=True, name="film",
                 frame_key=None, post=None):
        """music 配乐来源，二选一：
             * 乐谱 Song 对象（`wv.wa.Song(...)`，乐谱自己写）；
             * 现成音频文件路径（循环铺满全片）；
             * 或 dict：{"score": <Song>} / {"file": <路径>}，可带 "gain"（dB）。
        """
        self.width = float(width)
        self.height = float(height)
        self.fps = int(fps)
        self.ss = int(ss)
        self.seed = int(seed)
        self.grain = bool(grain)
        self.name = name
        self.bpm = bpm
        self.frame_key = frame_key   # 定格动画帧去重：fn(t) → 可哈希 key，key 相同的帧只渲染一次
        self.post = post             # 成片后处理钩子：fn(img, t) → img（暗角/颗粒/调色/色散）
        self._duration = float(duration) if duration is not None else None
        self.theme = make_theme(theme)
        self.palette = self.theme["colors"]
        self.scale = min(self.width, self.height) / 1080.0
        self.margin = round(0.085 * min(self.width, self.height))
        self.music = music
        self.scenes = []
        self.elements = []
        self._elem_seq = 0
        self._lint = []
        self._prepared = False
        self._shake = []
        self._sfx_user = []
        self._sfx_all = []
        self._shake_user = []
        self._flicker_ex = []
        self._bg_cache = {}
        self._paste_cache = _cv._DictCap(512)
        self._zoom_cache = _cv._DictCap(48)
        self._card_sprites = {}
        self._voices = []
        self._frame_palette = self.palette
        self._cur_time = 0.0

    # ---------------- 场景 / 元素 ----------------
    @property
    def duration(self):
        d = 0.0
        for s in self.scenes:
            d = max(d, s.end)
        if self._duration is not None:
            d = max(d, self._duration)
        return d

    def scene(self, start, end, transition="cut", bg=None, name=None):
        sc = Scene(self, start, end, transition=transition, bg=bg, name=name)
        self.scenes.append(sc)
        self._prepared = False
        return sc

    def _add(self, kind, content, opt):
        el = Elem(self, kind, content, opt, None)
        if not el.internal:
            self.elements.append(el)
        self._prepared = False
        return el

    def text(self, s, **opt):
        return self._add("text", s, opt)

    def list(self, items, **opt):
        return self._add("list", items, opt)

    def counter(self, frm, to, **opt):
        return self._add("counter", (frm, to), opt)

    def image(self, path, **opt):
        return self._add("image", path, opt)

    def draw(self, fn, **opt):
        return self._add("draw", fn, opt)

    def burst(self, kind="sparkle", **opt):
        return self._add("burst", kind, opt)

    def audio(self, src, **opt):
        """放一段外部声音（配音/旁白/录音）：文件路径或 {path;text;words} 表。"""
        return self._add("audio", src, opt)

    def sfx(self, name, at, gain=0.0, dur=None, pitch=0.0):
        self._sfx_user.append((float(at), str(name), float(gain), dur, float(pitch)))
        self._prepared = False

    def shake(self, at, dur=0.25, amp=6.0):
        self._shake_user.append((float(at), float(dur), float(amp)))
        self._prepared = False

    def flicker_exclude(self, t0, t1, x=None, y=None, w=None, h=None):
        """声明"有意急变"窗口：闪烁检测跳过（高速平移物体、设计阶跃等）。
        只给时间 → 全帧排除；给 x/y/w/h → 仅排除该区域。"""
        if x is None:
            self._flicker_ex.append((float(t0), float(t1)))
        else:
            self._flicker_ex.append({"t0": float(t0), "t1": float(t1), "x": float(x),
                                     "y": float(y), "w": float(w), "h": float(h)})
        self._prepared = False

    # ---------------- 样式 / lint ----------------
    def style(self, name):
        st = self.theme["styles"].get(name)
        if st is None:
            self._lint_add("warn", 0.0, "未知样式 %r（可用：hero/title/subtitle/body/caption）" % name)
            return self.theme["styles"]["body"]
        return st

    def _lint_add(self, level, t, msg):
        for it in self._lint:
            if it["level"] == level and abs(it["t"] - float(t)) < 1e-6 and it["msg"] == msg:
                return
        self._lint.append({"level": level, "t": float(t), "msg": msg})

    def lint(self):
        self._prepare()
        return sorted(self._lint, key=lambda it: (it["t"], it["level"]))

    def print_lint(self):
        for it in self.lint():
            print("[%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))

    # ---------------- 准备 ----------------
    def _auto_extend_scenes(self):
        """场景自动拉到内容播完，后续场景/元素/音效整体顺延。

        场景时长自动覆盖配音与打字/计数动画的完成时间（done+0.15s 收尾），
        后续场景 start/end、场景内元素 at、全局手动 sfx/shake 时间全部平移，
        保持相对时间轴，避免配音剪断、打字没打完或互相重叠。"""
        pad = 0.15
        for i, sc in enumerate(self.scenes):
            done = max((e.done for e in sc.elements
                        if e.done is not None and e.out is None), default=None)
            if done is None:
                continue
            need = done + pad
            if need <= sc.end + 1e-6:
                continue
            shift = need - sc.end
            threshold = sc.end
            sc.end = need
            for nxt in self.scenes[i + 1:]:
                nxt.start += shift
                nxt.end += shift
                for e in nxt.elements:
                    if e.at >= threshold - 1e-6:
                        e.at += shift
                        if e.done is not None:
                            e.done += shift
                        for ch in e.children:
                            ch.at += shift
                            if ch.done is not None:
                                ch.done += shift
            for j, it in enumerate(self._sfx_user):
                if it[0] >= threshold - 1e-6:
                    self._sfx_user[j] = (it[0] + shift, it[1], it[2], it[3], it[4])
            for j, it in enumerate(self._shake_user):
                if it[0] >= threshold - 1e-6:
                    self._shake_user[j] = (it[0] + shift, it[1], it[2])

    def _prepare(self):
        if self._prepared:
            return
        self.scenes.sort(key=lambda s: s.start)
        self._auto_extend_scenes()
        prev = None
        for i, sc in enumerate(self.scenes):
            sc.index = i
            sc.prev = prev
            prev = sc
        for i in range(1, len(self.scenes)):
            a, b = self.scenes[i - 1], self.scenes[i]
            if b.start < a.end - 1e-6:
                self._lint_add("warn", b.start, "场景重叠：%.2f 与 %.2f" % (a.start, b.start))
        for sc in self.scenes:
            self._layout_group(sc.elements, sc.end)
            for el in sc.elements:
                self._lint_elem(el, sc.end)
        for sc in self.scenes:
            ats = [el.at for el in sc.elements
                   if el.kind in ("text", "counter", "list", "image", "draw")]
            if ats:
                gap = min(ats) - sc.start
                if gap > 1.0:
                    self._lint_add("warn", sc.start,
                                   "场景开头空白 %.1f 秒（首个画面元素 %.2fs 才出现）："
                                   "把结构性锚点（标题/步骤号）落在场景开头 0.5s 内，"
                                   "词对齐元素不承担开场" % (gap, min(ats)))
        self._layout_group(self.elements, self.duration)
        for el in self.elements:
            self._lint_elem(el, self.duration)
        self._voices = [el for sc in self.scenes for el in sc.elements if el.kind == "audio"]
        self._voices += [el for el in self.elements if el.kind == "audio"]
        self._lint_audio()
        self._collect_sfx()
        self._prepared = True

    def _layout_group(self, elements, end_default):
        for e in elements:
            if e.kind == "image":
                e._end_default = end_default
                e._ensure_kb()
        free = []
        for e in elements:
            if e.kind in ("burst", "audio") or (e.kind == "draw" and not e.w) or e.parent is not None:
                continue
            if e.y is not None:
                e.cy = e.y
                if e.x is not None:
                    e.cx = e.x
            else:
                e.t0 = e.at - (0.30 if e.enter == "slam" else 0.0)
                e.t1 = e.end_time(end_default)
                free.append(e)
        regions = {"top": [], "center": [], "bottom": []}
        for e in free:
            pos = e.pos or ""
            r = "top" if "top" in pos else ("bottom" if "bottom" in pos else "center")
            regions[r].append(e)
        for rname, group in regions.items():
            clusters = []
            for e in group:
                ex = e._guess_cx(self)
                placed = False
                for cl in clusters:
                    if cl["t0"] < e.t1 and e.t0 < cl["t1"]:
                        for m in cl["items"]:
                            if abs(ex - m._guess_cx(self)) < (e.mw + m.mw) * 0.5 * 0.85:
                                cl["items"].append(e)
                                cl["t0"] = min(cl["t0"], e.t0)
                                cl["t1"] = max(cl["t1"], e.t1)
                                placed = True
                                break
                    if placed:
                        break
                if not placed:
                    clusters.append({"items": [e], "t0": e.t0, "t1": e.t1})
            for cl in clusters:
                self._stack(cl["items"], rname)
        for e in elements:
            if e.kind in ("burst", "audio") or (e.kind == "draw" and not e.w) or e.parent is not None:
                continue
            if e.cx is None:
                e.cx = self.width / 2
            if e.cy is None:
                e.cy = self.height / 2
        for e in elements:
            if e.children:
                bx = e.cx - e.mw / 2
                by = e.cy - e.mh / 2
                for ch in e.children:
                    ch.cx = bx + ch._off[0] + ch.mw / 2
                    ch.cy = by + ch._off[1] + ch.mh / 2

    def _stack(self, items, region):
        gap = 26 * self.scale
        total = sum(i.mh for i in items) + gap * max(0, len(items) - 1)
        if region == "top":
            y = self.margin
        elif region == "bottom":
            y = self.height - self.margin - total
        else:
            y = self.height / 2 - total / 2
        for e in items:
            e.cy = y + e.mh / 2
            e.cx = e.x if e.x is not None else e._guess_cx(self)
            y += e.mh + gap

    def _lint_elem(self, el, end_default):
        b = el.box()
        if b and el.kind in ("text", "counter", "list", "image") or (b and el.kind == "draw" and el.w):
            x, y, w, h = b
            if x < -2 or y < -2 or x + w > self.width + 2 or y + h > self.height + 2:
                self._lint_add("warn", el.at, "%s 元素超出画面（%.0f,%.0f %.0fx%.0f）" % (el.kind, x, y, w, h))
        if el.kind in ("text", "list") and not el.children:
            units = 0
            texts = el.lines if el.kind == "text" else [str(i) for i in el.content]
            for txt in texts:
                txt = _EMPH_RE.sub(r"\1", str(txt))
                units += len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", txt))
                units += 2 * len(re.findall(r"[A-Za-z]+", txt))
            stay = (el.out if el.out is not None else end_default) - max(0.0, el.at)
            if stay > 0 and units / stay > 8.0:
                self._lint_add("info", el.at, "阅读时间不足：%d 字 / %.2f 秒" % (units, stay))
        if isinstance(el.sfx_opt, (list, tuple)):
            for it in el.sfx_opt:
                if not isinstance(it, (list, tuple)) or len(it) < 2:
                    self._lint_add("warn", el.at, "sfx 列表项应为 (相对秒, 音效名[, gain])：%r" % (it,))

    def _style_adj(self, el):
        return -6.0 if el.style in ("subtitle", "body", "caption") else 0.0

    def _lint_audio(self):
        vs = sorted(self._voices, key=lambda v: v.at)
        for i, v in enumerate(vs):
            base = os.path.basename(v.path)
            if v._err:
                self._lint_add("error", v.at, v._err)
                continue
            if v.done > self.duration + 0.02:
                self._lint_add("warn", v.at, "声音超出影片结尾：%s" % base)
            if v.scene is not None and v.done > v.scene.end + 0.02:
                self._lint_add("info", v.at, "声音越过场景结尾：%s（旁白跨镜头是正常用法）" % base)
            if i + 1 < len(vs):
                w = vs[i + 1]
                if w._err is None and w.at < v.done - 0.02:
                    self._lint_add("warn", w.at, "两段声音重叠：%s 与 %s"
                                   % (base, os.path.basename(w.path)))
            if v.text and not v.words:
                self._lint_add("info", v.at, "声音没有词时间，word() 按字数估算：%s" % base)

    def _collect_sfx(self):
        self._shake = []
        auto = []
        for sc in self.scenes:
            for el in sc.elements:
                self._emit_auto_sfx(el, auto, sc.end)
        for el in self.elements:
            self._emit_auto_sfx(el, auto, self.duration)
        allx = list(self._sfx_user) + auto
        allx.sort(key=lambda x: x[0])
        dedup = []
        for item in allx:
            t, name = item[0], item[1]
            clash = False
            for d in dedup:
                if d[1] == name and abs(d[0] - t) < 0.06:
                    clash = True
                    break
            if not clash:
                dedup.append(item)
        self._sfx_all = dedup
        # 音效密度（数字滚动的 tick 不计）
        dens = [x for x in dedup if x[1] != "tick"]
        for i, item in enumerate(dens):
            n = 0
            for j in range(i, len(dens)):
                if dens[j][0] - item[0] <= 0.5:
                    n += 1
                else:
                    break
            if n > 6:
                self._lint_add("warn", item[0], "音效过密：0.5 秒内 %d 个" % n)
                break

    def _emit_auto_sfx(self, el, out, end_default):
        if el.sfx_opt is False:
            return
        adj = self._style_adj(el)
        if isinstance(el.sfx_opt, (list, tuple)) and len(el.sfx_opt) > 0:
            for it in el.sfx_opt:
                if not isinstance(it, (list, tuple)) or len(it) < 2:
                    continue
                dt, name = float(it[0]), str(it[1])
                gain = float(it[2]) if len(it) > 2 else 0.0
                out.append((el.at + dt, name, gain, None, 0.0))
            return
        if el.kind == "burst":
            out.append((el.at, "sparkle", -6.0, None, 0.0))
        enter = el.enter or (el._default_enter if el.children else None)
        src_el = el
        if enter in SFX_AUTO:
            name, off, g = SFX_AUTO[enter]
            out.append((src_el.at + off, name, g + adj, None, 0.0))
        if enter == "type":
            n = len("".join(getattr(el, "lines", [str(el.content)])))
            out.append((el.at, "typing", -8.0 + adj, n * 0.045 + 0.3, 0.0))
        if el.kind == "counter":
            frm, to = el.frm, el.to
            span = abs(to - frm)
            step = max(1, int(math.ceil(span / 14.0)))
            k = int(math.ceil(frm / step)) * step
            while k <= to and span > 0:
                tt = el.at + (k - frm) / (to - frm) * el.dur
                if el.at <= tt <= el.at + el.dur:
                    out.append((tt, "tick", -15.0 + adj, None, 0.0))
                k += step
            out.append((el.at + el.dur, "ding", -9.0 + adj, None, 0.0))
        if el.enter == "slam":
            self.shake(el.at, 0.28, 7.0 * self.scale)

    def _layout_film_elements(self):
        pass

    # ---------------- 背景 ----------------
    def _norm_bg(self, spec):
        if spec is None:
            return self.theme["bg"]
        if isinstance(spec, dict):
            if "image" in spec:
                return {"type": "image", "path": spec["image"], "grain": spec.get("grain")}
            return spec
        if spec == "accent":
            return {"type": "accent"}
        if spec == "dark":
            return self.theme["bg"]
        if isinstance(spec, str) and (spec.startswith("#") or "." in spec or "/" in spec or "\\" in spec):
            if spec.startswith("#"):
                return {"type": "solid", "color": spec}
            return {"type": "image", "path": spec}
        return self.theme["bg"]

    def palette_for(self, bg):
        bg = self._norm_bg(bg)
        if isinstance(bg, dict) and bg.get("type") == "accent":
            pal = dict(self.theme["colors"])
            pal.update(self.theme.get("onAccent", {}))
            return pal
        return self.theme["colors"]

    def _bg_image(self, bg, ss):
        bg = self._norm_bg(bg)
        key = (repr(bg), ss)
        im = self._bg_cache.get(key)
        if im is not None:
            return im
        W = max(1, int(round(self.width * ss)))
        H = max(1, int(round(self.height * ss)))
        typ = bg.get("type", "gradient") if isinstance(bg, dict) else "gradient"
        arr = None
        if typ == "image":
            path = bg.get("path")
            if path and os.path.exists(path):
                src = _cv.load_image(path).convert("RGB")
                sc = max(W / src.width, H / src.height)
                nw, nh = max(1, int(src.width * sc + 0.5)), max(1, int(src.height * sc + 0.5))
                src = src.resize((nw, nh), Image.LANCZOS)
                ox = (nw - W) // 2
                oy = (nh - H) // 2
                im = src.crop((ox, oy, ox + W, oy + H))
                if bg.get("grain") or self.grain:
                    a = np.asarray(im, dtype=np.int16)
                    rng = np.random.RandomState(self.seed)
                    a = np.clip(a + rng.randint(-3, 4, size=(H, W, 1)), 0, 255).astype(np.uint8)
                    im = Image.fromarray(a, "RGB")
                self._bg_cache[key] = im
                return im
            typ = "gradient"
        if typ == "accent":
            c = parse_color(self.theme["colors"]["accent"], self.palette)
            arr = np.zeros((H, W, 3), dtype=np.float32)
            arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = c[0], c[1], c[2]
        elif typ == "solid":
            c = parse_color(bg.get("color", "#000000"), self.palette)
            arr = np.zeros((H, W, 3), dtype=np.float32)
            arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = c[0], c[1], c[2]
        else:
            top = np.array(parse_color(bg.get("top", "#101A33"), self.palette), dtype=np.float32)
            bot = np.array(parse_color(bg.get("bottom", "#070A12"), self.palette), dtype=np.float32)
            yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
            col = top[None, :] * (1 - yy) + bot[None, :] * yy
            arr = np.repeat(col[:, None, :], W, axis=1)
            # 轻微暗角
            yv, xv = np.mgrid[0:H, 0:W].astype(np.float32)
            dx = (xv - (W - 1) / 2.0) / (W * 0.62)
            dy = (yv - (H - 1) / 2.0) / (H * 0.62)
            v = np.clip(1.0 - 0.16 * (dx * dx + dy * dy), 0, 1)[:, :, None]
            arr = arr * v
        if self.grain:
            rng = np.random.RandomState(self.seed)
            arr = arr + rng.randint(-3, 4, size=(H, W, 1))
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        im = Image.fromarray(arr, "RGB")
        if len(self._bg_cache) > 8:
            self._bg_cache.clear()
        self._bg_cache[key] = im
        return im

    # ---------------- 震动 / 帧状态 ----------------
    def _shake_dy(self, t):
        dy = 0.0
        for (t0, dur, amp) in (self._shake + self._shake_user):
            if t0 <= t <= t0 + dur:
                dt = t - t0
                dy += amp * math.exp(-9.0 * dt) * math.sin(2 * math.pi * 7.0 * dt)
        return dy

    def _scene_state(self, t):
        sc = None
        for s in self.scenes:
            if s.start <= t + 1e-9:
                sc = s
        if sc is None:
            return (None, "none", 0.0)
        D = TRANS_DUR.get(sc.transition, 0.0)
        if sc.prev is not None and D > 0 and t < sc.start + D:
            p = clamp((t - sc.start) / D, 0.0, 1.0)
            return (sc, "transition", p)
        return (sc, "none", 0.0)

    def _scene_layer(self, sc, t_eval, ss, pal, dy):
        layer = Image.new("RGBA", (max(1, int(round(self.width * ss))), max(1, int(round(self.height * ss)))), (0, 0, 0, 0))
        for el in sc.elements:
            el.draw(layer, t_eval, ss, pal, extra_dy=dy)
        return layer

    def _paste_layer(self, img, layer, a):
        if a <= 0.004:
            return
        if a < 0.996:
            alpha = layer.getchannel("A").point(lambda v: int(v * a))
            layer = layer.copy()
            layer.putalpha(alpha)
        img.paste(layer, (0, 0), layer)

    def _draw_transition(self, img, sc, t, ss, pal, dy, mode, p):
        prev = sc.prev
        t_prev = max(prev.start, prev.end - 1e-3)
        lay_old = self._scene_layer(prev, t_prev, ss, self.palette_for(prev.bg), dy)
        lay_new = self._scene_layer(sc, t, ss, pal, dy)
        if mode == "fade":
            e = ease("easeInOutSine", p)
            self._paste_layer(img, lay_old, 1.0 - e)
            self._paste_layer(img, lay_new, e)
        elif mode == "flash":
            if p < 0.5:
                self._paste_layer(img, lay_old, 1.0)
            else:
                self._paste_layer(img, lay_new, 1.0)
            wv = math.sin(math.pi * clamp(p, 0.0, 1.0)) * 0.95
            if wv > 0.02:
                white = Image.new("RGB", img.size, (255, 255, 255))
                mask = Image.new("L", img.size, int(wv * 255))
                img.paste(white, (0, 0), mask)
        elif mode == "wipe":
            base = img.copy()
            self._paste_layer(base, lay_old, 1.0)
            edge = img.width * p
            soft = max(6.0, 30 * ss)
            xx = np.arange(img.width, dtype=np.float32)
            m = np.clip((edge + soft / 2 - xx) / soft, 0, 1)
            mask = Image.fromarray((np.tile(m, (img.height, 1)) * 255).astype(np.uint8), "L")
            out = Image.composite(lay_new, base, mask)
            img.paste(out, (0, 0))
            c = Canvas(img, ss=ss, width=self.width, height=self.height)
            c.line(edge / ss - 1.5, 0, edge / ss + 1.5, self.height, color="accent", width=3, alpha=0.9)
        elif mode == "push":
            e = ease("easeInOutCubic", p)
            off = img.width * e
            img.paste(lay_old, (int(round(-off)), 0), lay_old)
            img.paste(lay_new, (int(round(img.width - off)), 0), lay_new)
        elif mode == "zoom":
            e = ease("easeInOutCubic", p)
            lay_old = self._zoom_layer(lay_old, 1.0 + 0.15 * e)
            self._paste_layer(img, lay_old, 1.0 - e)
            lay_new2 = self._zoom_layer(lay_new, 0.92 + 0.08 * e)
            self._paste_layer(img, lay_new2, e)
        else:
            self._paste_layer(img, lay_new, 1.0)

    def _zoom_layer(self, layer, k):
        w2 = max(1, int(round(layer.width * k)))
        h2 = max(1, int(round(layer.height * k)))
        big = layer.resize((w2, h2), Image.BILINEAR)
        out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        ox = (w2 - layer.width) // 2
        oy = (h2 - layer.height) // 2
        out.paste(big, (-ox, -oy))
        return out

    # ---------------- 渲染 ----------------
    def render_frame(self, t, ss=None, out_scale=1.0):
        self._prepare()
        self._cur_time = t
        ss = float(ss if ss is not None else self.ss)
        W = max(1, int(round(self.width * ss)))
        H = max(1, int(round(self.height * ss)))
        img = Image.new("RGB", (W, H), (0, 0, 0))
        sc, mode, p = self._scene_state(t)
        bg = sc.bg if sc is not None else None
        pal = self.palette_for(bg)
        self._frame_palette = pal
        bgimg = self._bg_image(bg, ss)
        img.paste(bgimg, (0, 0))
        dy = self._shake_dy(t)
        if sc is not None:
            if mode == "transition" and sc.prev is not None:
                self._draw_transition(img, sc, t, ss, pal, dy, sc.transition, p)
            else:
                for el in sc.elements:
                    el.draw(img, t, ss, pal, extra_dy=dy)
        for el in self.elements:
            el.draw(img, t, ss, pal, extra_dy=dy)
        k = ss / float(out_scale)
        if abs(k - 2.0) < 1e-6:
            out = img.reduce(2)
        elif abs(k - 1.0) < 1e-6:
            out = img
        else:
            out = img.resize((max(1, int(round(self.width * out_scale))),
                              max(1, int(round(self.height * out_scale)))), Image.BILINEAR)
        if self.post is not None:
            out = self.post(out, t)
        return out

    def frame(self, t, path=None):
        im = self.render_frame(t, ss=self.ss, out_scale=1.0)
        if path:
            d = os.path.dirname(os.path.abspath(path))
            if d and not os.path.isdir(d):
                os.makedirs(d)
            im.save(path, compress_level=1)
            return path
        return im

    def sheet(self, path=None, times=None, n=16, cols=4):
        self._prepare()
        dur = self.duration
        if not times:
            times = [round(0.12 + i * max(0.01, (dur - 0.24)) / max(1, n - 1), 2) for i in range(n)]
        thumbs = []
        for t in times:
            thumbs.append((t, self.render_frame(t, ss=self.ss, out_scale=0.5)))
        cw = thumbs[0][1].width
        ch = thumbs[0][1].height
        rows = (len(thumbs) + cols - 1) // cols
        f = _fonts.load("sans", 22)
        sheet = Image.new("RGB", (cw * cols, (ch + 34) * rows), (8, 10, 16))
        d = ImageDraw.Draw(sheet)
        for i, (t, im) in enumerate(thumbs):
            x = (i % cols) * cw
            y = (i // cols) * (ch + 34)
            sheet.paste(im, (x, y))
            d.text((x + 10, y + ch + 6), "%.2fs" % t, font=f, fill=(200, 210, 225))
        if path:
            d2 = os.path.dirname(os.path.abspath(path))
            if d2 and not os.path.isdir(d2):
                os.makedirs(d2)
            sheet.save(path, compress_level=1)
            return path
        return sheet

    def render(self, path=None, **kw):
        from . import render as _render
        return _render.render_film(self, path, **kw)

    def report(self, extra=None):
        self._prepare()
        data = {
            "name": self.name, "width": self.width, "height": self.height, "fps": self.fps,
            "duration": round(self.duration, 3),
            "scenes": [{
                "name": s.name, "start": s.start, "end": s.end, "transition": s.transition,
                "elements": [{"kind": e.kind, "at": e.at, "out": e.out,
                              "enter": e.enter, "style": e.style,
                              "text": (str(e.content)[:24] if e.kind in ("text", "counter") else None)}
                             for e in s.elements],
            } for s in self.scenes],
            "sfx": [{"t": round(x[0], 3), "name": x[1], "gain": x[2]} for x in self._sfx_all],
            "lint": self.lint(),
        }
        if extra:
            data.update(extra)
        return data
