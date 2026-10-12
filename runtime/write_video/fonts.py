# -*- coding: utf-8 -*-
"""write-video — 字体发现与缓存。

优先用环境变量指定，其次按操作系统搜索常见字体：
    WV_FONT_SANS      正文字体（支持中文）
    WV_FONT_SANS_BOLD 粗体
    WV_FONT_MONO      等宽（代码）
    WV_FONT_MONO_BOLD 等宽粗体
"""
import os
from functools import lru_cache

from PIL import ImageFont

_CANDIDATES = {
    "sans": [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "sans_bold": [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\Dengb.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "mono": [
        r"C:\Windows\Fonts\consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansMono-Regular.ttf",
    ],
    "mono_bold": [
        r"C:\Windows\Fonts\consolab.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansMono-Bold.ttf",
    ],
}

_ENV = {
    "sans": "WV_FONT_SANS",
    "sans_bold": "WV_FONT_SANS_BOLD",
    "mono": "WV_FONT_MONO",
    "mono_bold": "WV_FONT_MONO_BOLD",
}

_FONT_EXT = (".ttf", ".ttc", ".otf")


def _is_font_path(v):
    return isinstance(v, str) and os.path.splitext(v)[1].lower() in _FONT_EXT


@lru_cache(maxsize=32)
def find(kind="sans"):
    """返回某种类字体的文件路径（找不到返回 None）。kind: sans / sans_bold / mono / mono_bold"""
    env = os.environ.get(_ENV.get(kind, ""), "")
    if env and os.path.exists(env):
        return env
    for p in _CANDIDATES.get(kind, []):
        if os.path.exists(p):
            return p
    if kind in ("sans_bold", "mono_bold", "mono") and find("sans"):
        return find("sans")
    return None


@lru_cache(maxsize=512)
def load(kind="sans", size=48, index=0):
    """取字体对象（带缓存）。kind 可以是种类名或直接的字体文件路径。"""
    if _is_font_path(kind):
        path = kind
    else:
        path = find(kind)
    if not path:
        raise RuntimeError("找不到可用字体（kind=%r）。请安装字体或用 WV_FONT_SANS 等环境变量指定。" % (kind,))
    return ImageFont.truetype(path, max(1, int(size)), index=index)


def describe():
    """报告用：返回各类字体实际解析到的路径。"""
    return dict((k, find(k)) for k in _CANDIDATES)
