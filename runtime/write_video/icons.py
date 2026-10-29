# -*- coding: utf-8 -*-
"""write-video — Tabler 图标注册表（MIT，5070 个，名字 -> 字符）。

用法：
    import write_video as wv
    wv.icons.char("brand-github")   # 字符（s.text/s.list 直接可用）
    wv.icons.has("brand-github")    # 存在性
    list icon 选项：icon="tabler:brand-github" 或直接 icon="brand-github"
    （后者先查内置字形表，再查 tabler，都未命中按原字符画）

    也可 font="tabler" 后直接写图标字符。
"""
import json
import os
from functools import lru_cache

from PIL import ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
_TTF = os.path.normpath(os.path.join(_HERE, "..", "..", "fonts", "TablerIcons.ttf"))
_JSON = os.path.normpath(os.path.join(_HERE, "..", "..", "fonts", "tabler-names.json"))

with open(_JSON) as _f:
    _NAMES = json.load(_f)          # 图标名 -> 码位(int)


def has(name):
    return name in _NAMES


def char(name):
    """图标名 -> 字符；未知名字返回 None。"""
    cp = _NAMES.get(name)
    return chr(cp) if cp is not None else None


def codepoint(name):
    return _NAMES.get(name)


@lru_cache(maxsize=16)
def font(px):
    """图标字体对象。必须用 BASIC 布局引擎（raqm 对 PUA 码位会崩）。"""
    return ImageFont.truetype(_TTF, max(1, int(px)),
                              layout_engine=ImageFont.Layout.BASIC)


def names():
    return sorted(_NAMES)
