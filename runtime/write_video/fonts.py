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

from PIL import Image, ImageFont

_CJK_CHAR = "中"
_LATIN_CHAR = "A"


def _supports_cjk(path):
    """精确检测字体是否含真实 CJK 字形（排除 .notdef 豆腐块）。

    原理：Latin-only 字体对 CJK 字符只渲染 .notdef 备用字形（豆腐块），
    其宽度与拉丁字符一致；真实 CJK 字形宽度是拉丁的 1.5~1.7 倍。
    """
    try:
        f = ImageFont.truetype(path, 48)
        m_latin = f.getmask(_LATIN_CHAR)
        if m_latin.size[0] <= 1 or m_latin.size[1] <= 1:
            return False
        m_cjk = f.getmask(_CJK_CHAR)
        if m_cjk.size[0] <= 2 or m_cjk.size[1] <= 2:
            return False
        # 真实 CJK 宽度显著大于拉丁；.notdef 与拉丁同宽
        return m_cjk.size[0] / m_latin.size[0] > 1.3
    except Exception:
        return False


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


def _needs_cjk(kind):
    """mono / mono_bold 需要 CJK 支持（代码块可能包含中文注释）。"""
    return kind in ("mono", "mono_bold")


@lru_cache(maxsize=32)
def find(kind="sans"):
    """返回某种类字体的文件路径（找不到返回 None）。kind: sans / sans_bold / mono / mono_bold"""
    env = os.environ.get(_ENV.get(kind, ""), "")
    if env and os.path.exists(env):
        if not _needs_cjk(kind) or _supports_cjk(env):
            return env

    for p in _CANDIDATES.get(kind, []):
        if os.path.exists(p):
            if not _needs_cjk(kind) or _supports_cjk(p):
                return p

    # 降级：mono 无 CJK 字体时用 sans（确保中文可读）
    if kind in ("sans_bold", "mono_bold", "mono") and find("sans"):
        return find("sans")

    # 再次尝试 mono 家族第一个存在的（哪怕无 CJK）
    if _needs_cjk(kind):
        for p in _CANDIDATES.get(kind, []):
            if os.path.exists(p):
                return p

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
