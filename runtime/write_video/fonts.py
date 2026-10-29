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
        _bundled("ZiTiQuanWeiJunHei.ttf"),   # 字体圈伟君黑 W1（常规黑，正文）
        _bundled("YouSheBiaoTiHei.ttf"),     # 优设标题黑（重标题）
        _bundled("ZiZhiQuXiMaiTi.ttf"),      # 字制区喜脉体（装饰）
    ],
    "sans_bold": [
        _bundled("YouSheBiaoTiHei.ttf"),     # 优设标题黑（重标题）
        _bundled("ZiTiQuanWeiJunHei.ttf"),
        _bundled("ZiZhiQuXiMaiTi.ttf"),
    ],
    "mono": [
        _bundled("WenQuanYiMicroHeiMono.ttf"),  # 文泉驿等宽微米黑（CJK 等宽，20932 字形）
    ],
    "mono_bold": [
        _bundled("WenQuanYiMicroHeiMono.ttf"),  # 同 mono；粗细由描边承担
    ],
    "tabler": [
        _bundled("TablerIcons.ttf"),            # Tabler 图标（PUA 码位，经 icons.py 按名引用）
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


@lru_cache(maxsize=32)
def covered_chars(kind):
    """字体类别（或路径）→ 已覆盖字符集合（fontTools cmap）。

    无 fontTools 时返回 None（跳过覆盖检查）。
    """
    if _is_font_path(kind):
        path = kind
    else:
        result = find(kind)
        if result is None:
            return None
        path = result[0]
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(path, fontNumber=0, lazy=True)
        return frozenset(f.getBestCmap().keys())
    except Exception:
        return None


_WARNED_GLYPHS = set()


def warn_missing_glyphs(s, kind):
    """PIL 对缺字形字符静默渲成空白/豆腐——每字符只告警一次。

    正文字体（伟君黑/标题黑/喜脉体）缺 → ✓ 等符号字形；
    符号/图标应改用 wv.icons.char("arrow-right") 或 font="tabler"。
    """
    chars = covered_chars(kind)
    if chars is None:
        return
    text = str(s)
    missing_cp = sorted({ord(c) for c in text if not c.isspace()} - chars - _WARNED_GLYPHS)
    if not missing_cp:
        return
    _WARNED_GLYPHS.update(missing_cp)
    label = os.path.basename(kind) if _is_font_path(kind) else kind
    print("[write-video] 字体 %s 缺字形（静默渲染成空白）：%s —— "
          "符号/图标请用 wv.icons.char(\"arrow-right\") 或 font=\"tabler\""
          % (label, " ".join(chr(cp) for cp in missing_cp)))