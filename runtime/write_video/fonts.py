# -*- coding: utf-8 -*-
"""write-video — 捆绑字体发现与缓存。

仅收录 SIL OFL / GPL+font-exception 无版权可商用字体，全部随技能捆绑
（不依赖系统安装字体）。需要覆盖时用环境变量指定，优先级最高：

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
    """检测字体是否含真实 CJK 字形（排除 .notdef 豆腐块）。

    优先 fontTools 查 cmap（准确，能识别宽拉丁设计的展示字体）；
    无 fontTools 时退回宽度启发式：真实 CJK 字形宽度约为拉丁的 1.5~1.7 倍。
    """
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(path, fontNumber=0, lazy=True)
        return 0x4E2D in f.getBestCmap()  # "中"
    except ImportError:
        pass
    except Exception:
        pass
    try:
        f = ImageFont.truetype(path, 48)
        m_latin = f.getmask(_LATIN_CHAR)
        if m_latin.size[0] <= 1 or m_latin.size[1] <= 1:
            return False
        m_cjk = f.getmask(_CJK_CHAR)
        if m_cjk.size[0] <= 2 or m_cjk.size[1] <= 2:
            return False
        return m_cjk.size[0] / m_latin.size[0] > 1.3
    except Exception:
        return False


# 候选字体表：字符串为路径（index=0），元组为 (路径, TTC_face_index)
# 仅收录开源无版权可商用字体。

# 捆绑字体目录（相对于 fonts.py 的 ../../../fonts）
_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.normpath(os.path.join(_HERE, "..", "..", "fonts"))


def _bundled(name):
    return os.path.join(_BUNDLED, name)


_CANDIDATES = {
    "sans": [
        _bundled("站酷庆科黄油体.ttf"),
        _bundled("站酷文艺体.ttf"),
        _bundled("站酷快乐体 开源版.ttf"),
        _bundled("站酷高端黑.ttf"),
        _bundled("站酷酷黑体.ttf"),
        _bundled("站酷小薇LOGO体.otf"),
    ],
    "sans_bold": [
        _bundled("站酷高端黑.ttf"),
        _bundled("站酷庆科黄油体.ttf"),
        _bundled("站酷酷黑体.ttf"),
    ],
    "mono": [
        _bundled("WenQuanYiMicroHeiMono.ttf"),  # 文泉驿等宽微米黑（CJK 等宽，20932 字形）
    ],
    "mono_bold": [
        _bundled("WenQuanYiMicroHeiMono.ttf"),  # 同 mono；粗细由描边承担
    ],
}

_ENV = {
    "sans": "WV_FONT_SANS",
    "sans_bold": "WV_FONT_SANS_BOLD",
    "mono": "WV_FONT_MONO",
    "mono_bold": "WV_FONT_MONO_BOLD",
}

_FONT_EXT = (".ttf", ".ttc", ".otf")

# 所有类别都优先选含中文的字体（用于中文影片场景）
_NEEDS_CJK = {"sans", "sans_bold", "mono", "mono_bold"}


def _is_font_path(v):
    return isinstance(v, str) and os.path.splitext(v)[1].lower() in _FONT_EXT


def _resolve(candidate):
    """将候选条目解析为 (path, index)。"""
    if isinstance(candidate, (list, tuple)):
        return candidate[0], candidate[1] if len(candidate) > 1 else 0
    return candidate, 0


def _exists(path_idx):
    path, _ = path_idx
    return os.path.exists(path)


def _supports_cjk_path(path_idx):
    path, _ = path_idx
    return _supports_cjk(path)


def _needs_cjk(kind):
    return kind in _NEEDS_CJK


@lru_cache(maxsize=32)
def find(kind="sans"):
    """返回 (文件路径, TTC face_index)。kind: sans / sans_bold / mono / mono_bold"""
    candidates = _CANDIDATES.get(kind, [])

    # 1) 环境变量（跳过 CJK 检测，用户显式指定的优先级最高）
    env = os.environ.get(_ENV.get(kind, ""), "")
    if env and os.path.exists(env):
        return (env, 0)

    # 2) 优先 CJK 候选
    for c in candidates:
        path, idx = _resolve(c)
        if os.path.exists(path):
            if not _needs_cjk(kind) or _supports_cjk(path):
                return (path, idx)

    # 3) 降级：选任意存在的
    for c in candidates:
        path, idx = _resolve(c)
        if os.path.exists(path):
            return (path, idx)

    # 4) 跨类别降级：粗体/等宽回退到 sans
    if kind in ("sans_bold", "mono_bold", "mono"):
        fallback = find("sans")
        if fallback:
            return fallback

    return None


@lru_cache(maxsize=512)
def load(kind="sans", size=48, index=0):
    """取字体对象（带缓存）。kind 可以是种类名或直接的字体文件路径。"""
    if _is_font_path(kind):
        path = kind
    else:
        result = find(kind)
        if result is None:
            raise RuntimeError(
                "找不到可用字体（kind=%r）。请安装字体或用 WV_FONT_SANS 等环境变量指定。" % (kind,)
            )
        path, index = result
    return ImageFont.truetype(path, max(1, int(size)), index=index)


def describe():
    """报告用：返回各类字体实际解析到的路径。"""
    return dict((k, find(k)) for k in _CANDIDATES)