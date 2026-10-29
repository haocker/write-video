# -*- coding: utf-8 -*-
"""pagecam · 真实页面 2.5D 推镜 · 把剪辑软件拆成悬浮图层
11 秒 / 1920x1080 / 30fps
运行: python3 film.py

CSS 3D 降级为手写透视投影(F=2200) + 分层 blur 近似景深：
面板 spring 飞入(0.25s 错 0.08) → 拆层 Z={top:30,lib:-70,mon:0,ins:-40,tl:90}·2.2 →
rotateX(8°)/rotateY(-19°) 倾斜 → rack focus(时间线→监视器) → 光标点「AI 一键成片」(3.75s) →
8 条 clip spring 落上时间线 + 波形揭示 + 播放头 → 监视器 15fps 开播 →
6.5s 收回平面推进监视器(scale→1.55) → 8.4s 标题。
全部确定性时间函数（spring/衰减正弦/hash），禁全局随机态。
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("WRITE_VIDEO_RUNTIME", ""),
           "/root/.codingmatrix/project-tpl/.ai-ready/skills/write-video/runtime"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import write_video as wv

W, H = 1920, 1080
OUT = os.path.join(HERE, "artifacts")
SS = 2  # 与 film ss 一致（sprite 超采样）
F = 2200.0  # 透视焦距(px)，对应 CSS perspective:2200


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_io(x):
    x = clamp(x, 0.0, 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def out_cubic(x):
    x = clamp(x, 0.0, 1.0)
    return 1.0 - (1.0 - x) ** 3


def hash1(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


# === 面板定义（基准平面布局 + 深度 Z） ===
PAD = 56  # sprite 阴影外边距(设计px)
PANELS = {
    "top": {"rect": (40, 24, 1840, 64), "z": 30},
    "lib": {"rect": (40, 116, 360, 500), "z": -70},
    "mon": {"rect": (428, 116, 1024, 500), "z": 0},
    "ins": {"rect": (1480, 116, 400, 500), "z": -40},
    "tl": {"rect": (40, 644, 1840, 396), "z": 90},
}
FLY_ORDER = ["top", "mon", "lib", "ins", "tl"]


def spring_in(t, damping, freq):
    """欠阻尼弹簧 0→1（canvas.spring 语义，确定性）。"""
    if t <= 0:
        return 0.0
    return 1.0 - math.exp(-damping * t) * math.cos(2 * math.pi * freq * t)


def cam_params(t):
    """返回 (sep, tx, ty, push)。sep: 拆层 1.2-2.6s；push: 推进监视器 6.5-7.6s。"""
    sep = ease_io((t - 1.2) / 1.4)
    push = ease_io((t - 6.5) / 1.1)
    drift_x = 0.5 * math.sin(t * 0.5 + 1.0) * sep * (1 - push)
    drift_y = 0.4 * math.sin(t * 0.37) * sep * (1 - push)
    tx = (4.0 * sep * (1 - push) + drift_x) * math.pi / 180.0
    ty = (-8.0 * sep * (1 - push) + drift_y) * math.pi / 180.0
    return sep, tx, ty, push


PUSH_DY = 0.0  # 推进期相机下移（每帧由 main_scene 重设，确定性）


def focus_z(t):
    """焦点深度(Z 单位)：2.6-3.3s 到时间线(90)，5.8-6.6s rack focus 回监视器(0)。"""
    f = 90.0 * ease_io((t - 2.6) / 0.7)
    if t > 5.8:
        f *= 1.0 - ease_io((t - 5.8) / 0.8)
    return f


def proj(x, y, d, tx, ty):
    """手写 2.5D 透视：点 (x,y) 在深度 d(朝向相机为正) → 屏幕坐标 + 缩放。"""
    X, Y = x - W / 2.0, y - H / 2.0
    ca, sa = math.cos(tx), math.sin(tx)
    cb, sb = math.cos(ty), math.sin(ty)
    y1 = Y * ca - d * sa
    d1 = Y * sa + d * ca
    x2 = X * cb + d1 * sb
    d2 = -X * sb + d1 * cb
    den = F - d2
    if den < 80:
        return None
    s = F / den
    return (W / 2.0 + s * x2, H / 2.0 + s * y1 + PUSH_DY, s)


# === 面板 sprite（离屏 PIL + wv Canvas 绘制） ===
SPR_CACHE = {}


def _card_chrome(c2, w, h, dots=True):
    """深色圆角卡 + 顶部内描边高光 + 细外描边（局部坐标 0,0 起）。"""
    c2.rect(0, 0, w, h, fill="#10182A", radius=14)
    c2.rect(0, 0, w, h, outline=(255, 255, 255), alpha=16 / 255.0, width=1.5, radius=14)
    c2.line(14, 1.5, w - 14, 1.5, color=(255, 255, 255), alpha=30 / 255.0, width=2)
    if dots:
        for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            c2.circle(22 + i * 20, 20, 5.5, fill=col)


def _shadow_layer(dw, dh, w, h):
    """面板投影（box-shadow 0 40px 90px 近似）。"""
    m = Image.new("RGBA", (int(dw * SS), int(dh * SS)), (0, 0, 0, 0))
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([int((PAD + 4) * SS), int((PAD + 26) * SS),
                         int((PAD + 4 + w) * SS), int((PAD + 26 + h) * SS)],
                        radius=int(16 * SS), fill=(0, 0, 0, 120))
    return m.filter(ImageFilter.GaussianBlur(int(26 * SS)))


def _thumb_scene(idx, dw, dh):
    """监视器预载帧：12 张确定性小场景缩略图。"""
    im = Image.new("RGB", (int(dw * SS), int(dh * SS)), (10, 12, 20))
    d = ImageDraw.Draw(im, "RGBA")
    palettes = [((36, 52, 96), (140, 190, 235)), ((20, 26, 48), (255, 170, 110)),
                ((12, 60, 60), (110, 230, 200)), ((50, 30, 70), (200, 150, 250)),
                ((70, 40, 30), (250, 200, 120)), ((16, 32, 24), (140, 220, 150)),
                ((30, 20, 50), (255, 130, 170)), ((24, 34, 60), (120, 200, 255)),
                ((60, 50, 20), (255, 220, 140)), ((20, 40, 46), (90, 210, 210)),
                ((40, 24, 34), (240, 160, 180)), ((18, 28, 40), (170, 190, 230))]
    c0, c1 = palettes[idx % 12]
    wpx, hpx = im.size
    for yy in range(hpx):
        u = yy / float(hpx)
        col = (int(c0[0] + (c1[0] - c0[0]) * u), int(c0[1] + (c1[1] - c0[1]) * u),
               int(c0[2] + (c1[2] - c0[2]) * u))
        d.line([(0, yy), (wpx, yy)], fill=col)
    kind = idx % 3
    if kind == 0:
        d.ellipse([wpx * 0.68, hpx * 0.14, wpx * 0.8, hpx * 0.34], fill=(255, 240, 200, 230))
        for k in range(4):
            x0 = wpx * (0.05 + 0.24 * k)
            d.polygon([(x0, hpx * 0.92), (x0 + wpx * 0.13, hpx * (0.42 + 0.1 * (k % 2))),
                       (x0 + wpx * 0.26, hpx * 0.92)], fill=(18, 24, 40, 220))
    elif kind == 1:
        for k in range(7):
            bh = hpx * (0.2 + 0.55 * hash1(idx * 31 + k * 7))
            d.rectangle([wpx * (0.06 + 0.13 * k), hpx - bh, wpx * (0.06 + 0.13 * k) + wpx * 0.08,
                         hpx], fill=(230, 240, 255, 160))
    else:
        d.rectangle([0, hpx * 0.8, wpx, hpx], fill=(24, 34, 52, 200))
        for k in range(3):
            yy = hpx * (0.28 + 0.2 * k)
            pts = [(wpx * (0.06 + 0.36 * v / 22.0), yy + 9 * math.sin(v * 1.3 + k * 2 + idx)) for v in range(23)]
            d.line(pts, fill=(240, 250, 255, 150), width=6)
    return im


THUMBS = [_thumb_scene(i, 992, 384) for i in range(12)]


def build_panel_sprite(pid, t):
    """渲染单块面板 sprite（设计坐标，含阴影外边距）。"""
    px, py, pw, ph = PANELS[pid]["rect"]
    dw, dh = pw + 2 * PAD, ph + 2 * PAD
    spr = Image.new("RGBA", (int(dw * SS), int(dh * SS)), (0, 0, 0, 0))
    spr.alpha_composite(_shadow_layer(dw, dh, pw, ph))
    c2 = wv.canvas.Canvas(spr, ss=SS, width=dw, height=dh, ox=PAD, oy=PAD)

    if pid == "top":
        _card_chrome(c2, pw, ph, dots=False)
        for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            c2.circle(24 + i * 21, ph / 2, 5.5, fill=col)
        c2.text("AI STUDIO · 智能剪辑", 92, ph / 2, 21, "#E8F0FC", bold=True, align="left")
        for i in range(3):
            c2.circle(pw - 320 + i * 30, ph / 2, 8, outline=(168, 182, 204), width=2)
        # AI 一键成片按钮（点击 3.75s：scale 0.94 反馈）
        press = 0.0
        if 3.75 <= t <= 4.05:
            press = math.sin(math.pi * clamp((t - 3.75) / 0.24, 0, 1))
        bs = 1.0 - 0.06 * press
        bw, bh = 196, 40
        bx, by = pw - 214 + bw / 2, ph / 2
        x0, y0 = bx - bw / 2 * bs, by - bh / 2 * bs
        c2.rect(x0, y0, bw * bs, bh * bs, fill="#6D4AFF", radius=10 * bs)
        c2.rect(x0, y0, bw * bs, bh * bs * 0.52, fill="#8F72FF", radius=10 * bs, alpha=0.5)
        c2.rect(x0, y0, bw * bs, bh * bs, outline=(255, 255, 255), alpha=60 / 255.0,
                width=1.5, radius=10 * bs)
        c2.polygon([(x0 + 20 * bs, by - 8 * bs), (x0 + 27 * bs, by), (x0 + 20 * bs, by + 8 * bs),
                    (x0 + 24 * bs, by), (x0 + 16 * bs, by)], fill="#FFE08A")
        c2.text("AI 一键成片", bx + 16 * bs, by, 19, "#FFFFFF", bold=True)
    elif pid == "lib":
        _card_chrome(c2, pw, ph)
        c2.text("媒体库", 88, 20, 19, "#DDE7F5", bold=True, align="left")
        c2.line(16, 40, pw - 16, 40, color=(255, 255, 255), alpha=18 / 255.0, width=1.5)
        tiles = [((36, 52, 96), (140, 190, 235)), ((20, 26, 48), (255, 170, 110)),
                 ((12, 60, 60), (110, 230, 200)), ((50, 30, 70), (200, 150, 250)),
                 ((70, 40, 30), (250, 200, 120)), ((16, 32, 24), (140, 220, 150)),
                 ((30, 20, 50), (255, 130, 170)), ((24, 34, 60), (120, 200, 255)),
                 ((60, 50, 20), (255, 220, 140))]
        for r in range(3):
            for q in range(3):
                c0, c1 = tiles[r * 3 + q]
                tx, ty = 20 + q * 110, 58 + r * 118
                tw, th = 102, 72
                c2.rect(tx, ty, tw, th, fill=c0, radius=8)
                c2.rect(tx, ty, tw, th / 2, fill=c1, radius=8, alpha=0.35)
                c2.rect(tx, ty, tw, th, outline=(255, 255, 255), alpha=24 / 255.0, width=1, radius=8)
                c2.circle(tx + tw - 14, ty + 12, 4, fill="#FFD166")
                c2.rect(tx, ty + th + 8, tw * 0.66, 7, fill=(168, 182, 204), alpha=0.63, radius=3)
                c2.rect(tx, ty + th + 21, tw * 0.4, 6, fill=(120, 132, 152), alpha=0.51, radius=3)
        c2.rect(20, ph - 44, pw - 40, 30, fill=(124, 92, 255), alpha=0.27, radius=8,
                outline=(124, 92, 255), width=1.5)
        c2.text("+ 导入素材", pw / 2, ph - 29, 15, "#CBB8FF", bold=True)
    elif pid == "mon":
        _card_chrome(c2, pw, ph)
        c2.text("预览监视器", 88, 20, 19, "#DDE7F5", bold=True, align="left")
        c2.text("1920×1080 · 30FPS", pw - 20, 20, 14, "#7C8AA0", align="right")
        c2.line(16, 40, pw - 16, 40, color=(255, 255, 255), alpha=18 / 255.0, width=1.5)
        sx, sy, sw, sh = 16, 56, pw - 32, ph - 100
        c2.rect(sx, sy, sw, sh, fill="#05070D", radius=10)
        if t >= 5.4:
            tp = t - 5.4
            idx = int(tp * 15) % 12
            th_im = THUMBS[idx].resize((int(sw * SS), int(sh * SS)), Image.BILINEAR)
            spr.paste(th_im, (int((PAD + sx) * SS), int((PAD + sy) * SS)))
            # 时间码 + 进度条（继续用 c2 画回 sprite，保序由 _pil_first 处理）
            c2.rect(sx, sy, sw, sh, outline=(255, 255, 255), alpha=30 / 255.0, width=1.5, radius=10)
            c2.text("00:00:%02d:%02d" % (int(tp) % 60, int(tp % 1.0 * 30)),
                    sx + sw - 16, sy + sh - 18, 15, "#9FE8C8", align="right")
            c2.rect(sx + 16, sy + sh - 26, sw - 32, 5, fill=(255, 255, 255), alpha=0.16, radius=2)
            c2.rect(sx + 16, sy + sh - 26, (sw - 32) * clamp(tp / 5.6, 0, 1), 5,
                    fill="#FF4D6D", radius=2)
        else:
            c2.rect(sx, sy, sw, sh, fill="#05070D", radius=10)
            c2.rect(sx, sy, sw, sh, fill=(0, 0, 0), alpha=0.35, radius=10)
            c2.rect(sx, sy, sw, sh, outline=(255, 255, 255), alpha=20 / 255.0, width=1.5, radius=10)
            c2.polygon([(sx + sw / 2 - 20, sy + sh / 2 - 30), (sx + sw / 2 - 20, sy + sh / 2 + 30),
                        (sx + sw / 2 + 28, sy + sh / 2)], fill=(255, 255, 255), alpha=0.82)
            c2.text("待机 · 等待时间线", sx + sw / 2, sy + sh - 44, 16, (200, 214, 235),
                    alpha=0.59)
    elif pid == "ins":
        _card_chrome(c2, pw, ph)
        c2.text("属性检查器", 88, 20, 19, "#DDE7F5", bold=True, align="left")
        c2.line(16, 40, pw - 16, 40, color=(255, 255, 255), alpha=18 / 255.0, width=1.5)
        labels = ["亮度", "对比度", "饱和度", "色温", "锐化", "降噪"]
        for r, lb in enumerate(labels):
            yy = 68 + r * 56
            v = 0.25 + 0.68 * hash1(r * 7.3 + 2.0)
            c2.text(lb, 20, yy, 16, "#AEBDD4", align="left")
            c2.rect(110, yy - 4, pw - 190, 8, fill=(255, 255, 255), alpha=0.1, radius=4)
            c2.rect(110, yy - 4, (pw - 190) * v, 8, fill="#64F4DC", radius=4)
            c2.circle(110 + (pw - 190) * v, yy, 7, fill="#EAFFF9", outline="#64F4DC", width=2)
            c2.text("%d" % round(v * 100), pw - 20, yy, 15, "#DDE7F5", align="right")
        c2.text("调色预设", 20, ph - 118, 15, "#7C8AA0", align="left")
        for i, col in enumerate(("#FF9F5A", "#64F4DC", "#7C5CFF", "#FF7AA2", "#FFD166")):
            c2.rect(20 + i * 72, ph - 92, 62, 40, fill=col, radius=8, alpha=0.85)
        c2.rect(20, ph - 36, 172, 26, fill=(255, 255, 255), alpha=0.08, radius=7)
        c2.text("导出设置", 106, ph - 23, 14, "#AEBDD4")
    elif pid == "tl":
        _card_chrome(c2, pw, ph, dots=False)
        for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            c2.circle(24 + i * 21, 20, 5, fill=col)
        c2.text("时间线", 92, 20, 18, "#DDE7F5", bold=True, align="left")
        for i in range(6):
            c2.rect(300 + i * 46, 10, 30, 22, fill=(255, 255, 255), alpha=0.09, radius=6)
        c2.text("自动吸附 ON", pw - 24, 21, 14, "#64F4DC", align="right")
        c2.line(16, 40, pw - 16, 40, color=(255, 255, 255), alpha=18 / 255.0, width=1.5)
        for k in range(0, 17):
            xx = 90 + k * 104
            c2.line(xx, 46, xx, 54, color=(168, 182, 204), alpha=0.43, width=1.5)
            if k % 2 == 0:
                c2.text("00:%02d" % (k // 2), xx + 4, 50, 10, (120, 132, 152), align="left")
        for r, nm in enumerate(("视频", "字幕", "音频", "音频 2")):
            yy = 64 + r * 76
            c2.rect(16, yy, pw - 32, 66, fill=(255, 255, 255), alpha=0.05, radius=8)
            c2.text(nm, 26, yy + 33, 14, (140, 152, 172), align="left")
        # 视频轨 8 条 clip：spring(k:180,c:14) 错 0.12 从 (+220,-260) 落下（缩放 .6→1）
        hues = ["#7C5CFF", "#2EC4B6", "#FFD166", "#FF7AA2", "#64A7FF", "#9FE36B",
                "#FF9F5A", "#B78BFA"]
        for i in range(8):
            s_i = spring_in(t - (3.95 + i * 0.12), 7.0, 2.137)
            if s_i <= 0.001:
                continue
            sc = 0.6 + 0.4 * s_i
            cw, chh = 200 * sc, 62 * sc
            cx = 96 + i * 212 + 110 + (1 - s_i) * 220
            cy = 64 + 33 + (1 - s_i) * -260
            a = clamp(s_i * 4, 0, 1)
            hc = wv.canvas.parse_color(hues[i])
            c2.rect(cx - cw / 2, cy - chh / 2, cw, chh, fill=(10, 14, 24), alpha=0.78 * a,
                    outline=hc, width=2, radius=6)
            for k in range(4):
                c2.rect(cx - cw / 2 + 8 + k * (cw - 16) / 4, cy - chh / 2 + 8,
                        (cw - 16) / 4 - 6, chh - 30, fill=hc, alpha=0.5 * a, radius=3)
            c2.rect(cx - cw / 2 + 8, cy + chh / 2 - 16, (cw - 16) * 0.5, 6,
                    fill=(255, 255, 255), alpha=0.27 * a, radius=2)
            c2.text("%.1fs" % (2.0 + 0.4 * (i % 5)), cx + cw / 2 - 8, cy + chh / 2 - 12,
                    11, (230, 240, 255), alpha=0.63 * a, align="right")
        # 字幕轨 2 条字幕条 spring(k:220,c:13) 逐个落下
        for j in range(2):
            s_j = spring_in(t - (4.3 + j * 0.25), 6.5, 2.236)
            if s_j <= 0.001:
                continue
            sc = 0.8 + 0.2 * s_j
            a = clamp(s_j * 4, 0, 1)
            x0 = 96 + j * 560 + (1 - s_j) * 80
            y0 = 64 + 76 + 33 + (1 - s_j) * -120
            c2.rect(x0, y0 - 20 * sc, 500 * sc, 40 * sc, fill=(124, 92, 255), alpha=0.47 * a,
                    outline=(167, 139, 250), width=1.5, radius=6)
            c2.rect(x0 + 12, y0 - 6, (500 * sc - 24) * 0.7, 7, fill=(230, 222, 255),
                    alpha=0.63 * a, radius=3)
        # 音频轨波形：hash 条 + 从左到右揭示
        for r, (yy, amp, base_a) in enumerate(((64 + 2 * 76 + 33, 1.0, 0.7),
                                               (64 + 3 * 76 + 33, 0.55, 0.43))):
            nb = 86
            p = clamp((t - (4.35 + r * 0.15)) / 1.25, 0, 1)
            for j in range(nb):
                a_j = clamp((p * (nb + 8) - j) / 6.0, 0, 1)
                if a_j <= 0:
                    continue
                bh2 = (7 + hash1(j * 3.7 + r * 11 + 1) * 46) * amp
                c2.rect(96 + j * 19.6, yy - bh2 / 2, 13, bh2,
                        fill="#2EC4B6", alpha=a_j * base_a, radius=2)
        # 红色播放头前进
        pp = clamp((t - 4.45) / 5.4, 0, 1)
        if pp > 0:
            hx = 96 + pp * (pw - 140)
            c2.line(hx, 46, hx, ph - 26, color="#FF4D6D", width=3)
            c2.polygon([(hx - 9, 44), (hx + 9, 44), (hx, 58)], fill="#FF4D6D")
    c2.flush()
    return spr


def get_panel_sprite(pid, t):
    if pid == "top":
        press_q = 0 if not (3.75 <= t <= 4.05) else round(
            1 - math.sin(math.pi * clamp((t - 3.75) / 0.24, 0, 1)) * 0.06, 2)
        key = ("top", press_q)
    elif pid == "mon":
        key = ("mon", int(max(0.0, t - 5.4) * 15) % 12 if t >= 5.4 else -1)
    elif pid == "tl":
        return build_panel_sprite(pid, t)  # 播放头/波形每帧变化
    else:
        key = (pid, 0)
    if key not in SPR_CACHE:
        if len(SPR_CACHE) > 48:
            SPR_CACHE.clear()
        SPR_CACHE[key] = build_panel_sprite(pid, t)
    return SPR_CACHE[key]


def quad_paste(base, spr, quad):
    """把 sprite 以任意四边形(屏幕坐标 TL,TR,BR,BL)透视贴到 base。"""
    pts = [(q[0] * SS, q[1] * SS) for q in quad]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(math.floor(min(xs))), int(math.floor(min(ys)))
    x1, y1 = int(math.ceil(max(xs))), int(math.ceil(max(ys)))
    bw, bh = x1 - x0, y1 - y0
    if bw < 4 or bh < 4 or bw * bh > 90_000_000:
        return
    sw, sh = spr.size
    dst = [(p[0] - x0, p[1] - y0) for p in pts]  # 局部坐标（可为负）
    src = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
    import numpy as np
    A, b = [], []
    for (X, Y), (u, v) in zip(dst, src):
        A.append([X, Y, 1, 0, 0, 0, -u * X, -u * Y])
        b.append(u)
        A.append([0, 0, 0, X, Y, 1, -v * X, -v * Y])
        b.append(v)
    try:
        co = np.linalg.solve(np.array(A, dtype=np.float64), np.array(b, dtype=np.float64))
    except Exception:
        return
    out = spr.transform((bw, bh), Image.PERSPECTIVE, data=tuple(co), resample=Image.BILINEAR)
    base.paste(out, (x0, y0), out)


def panel_quad(pid, t, sep, tx, ty, push, mc):
    """面板基准矩形 → 相机投影四边形（含飞入弹簧、推镜缩放、透明度）。"""
    px, py, pw, ph = PANELS[pid]["rect"]
    fi = FLY_ORDER.index(pid)
    s_fly = spring_in(t - (0.25 + fi * 0.08), 8.0, 1.744)
    if s_fly <= 0.001:
        return None, 0.0
    d = PANELS[pid]["z"] * 1.2 * sep * (1 - push)
    if pid == "mon":
        d += 620.0 * push
    cx, cy = px + pw / 2.0, py + ph / 2.0
    corners = [(px, py), (px + pw, py), (px + pw, py + ph), (px, py + ph)]
    quad = []
    for (qx, qy) in corners:
        pr = proj(qx, qy, d, tx, ty)
        if pr is None:
            return None, 0.0
        qx2, qy2, _s = pr
        if sep < 0.02:
            # 飞入：从下方 + 缩放 0.9→1（围绕面板中心）
            fs = 0.9 + 0.1 * clamp(s_fly, 0, 1)
            qx2 = cx + (qx2 - cx) * fs
            qy2 = cy + (qy2 - cy) * fs + (1 - s_fly) * 140
        quad.append((qx2, qy2))
    # 拆层期整体略后缩让层叠入画；推进期绕监视器中心放大
    ps = 0.94 + 0.06 * push
    quad = [(W / 2.0 + (qx - W / 2.0) * ps, H / 2.0 + (qy - H / 2.0) * ps) for qx, qy in quad]
    if push > 0 and mc is not None:
        zx = 1.0 + 0.12 * push
        if pid == "mon":
            zx *= 1.0 + 0.06 * push
        quad = [(mc[0] + (qx - mc[0]) * zx, mc[1] + (qy - mc[1]) * zx) for qx, qy in quad]
    alpha = clamp(s_fly * 3, 0, 1)
    if pid != "mon" and push > 0:
        st = {"tl": 0.0, "top": 0.15, "ins": 0.3, "lib": 0.45}.get(pid, 0.0)
        alpha *= 1.0 - clamp((push - st) / 0.5, 0, 1)
    if alpha <= 0.01:
        return None, 0.0
    return quad, alpha


def blurred(spr, q):
    """按档位缓存的高斯模糊（景深近似）。"""
    if q <= 0:
        return spr
    key = (id(spr), q)
    if key in BLUR_CACHE:
        return BLUR_CACHE[key]
    if len(BLUR_CACHE) > 40:
        BLUR_CACHE.clear()
    im = spr.filter(ImageFilter.GaussianBlur(q * SS))
    BLUR_CACHE[key] = im
    return im


BLUR_CACHE = {}
BLUR_LEVELS = (0, 2, 4, 6, 8, 10, 12, 14)


def main_scene(c, t):
    global PUSH_DY
    sep, tx, ty, push = cam_params(t)
    PUSH_DY = 150.0 * push
    c.gradient(0, 0, W, H, colors=[(0, "#0A0E1A"), (1, "#121A2E")], direction="vertical")
    c.glow(W / 2, H / 2 - 60, 620, "#1C2A4A", 0.4)
    if push > 0:
        c.rect(0, 0, W, H, fill="#000000", alpha=0.42 * push)
    c.flush()

    # 监视器投影中心（推镜缩放锚点）
    mon_c = proj(940, 366, PANELS["mon"]["z"] * 1.2 * sep * (1 - push) + 620 * push, tx, ty)
    mc = (mon_c[0], mon_c[1]) if mon_c else (W / 2, H / 2)

    # 景深：blur = |Z - focus|·0.045，随 sep 渐入；焦点 3-6s 在时间线，5.8s rack focus 到监视器
    fz = focus_z(t)
    sep01 = clamp(sep * 1.15, 0, 1)
    items = []
    for pid in PANELS:
        quad, alpha = panel_quad(pid, t, sep, tx, ty, push, mc)
        if quad is None:
            continue
        blur = min(14.0, abs(PANELS[pid]["z"] - fz) * 0.045) * sep01
        q = min(BLUR_LEVELS, key=lambda v: abs(v - blur)) if blur >= 1 else 0
        d_sort = PANELS[pid]["z"] * 1.2 * (1 - push) + (620 * push if pid == "mon" else 0)
        items.append((d_sort, pid, quad, q))
    items.sort(key=lambda it: it[0])  # 画家算法：远→近
    for (d, pid, quad, q) in items:
        spr = get_panel_sprite(pid, t)
        if q > 0:
            spr = blurred(spr, q)
        quad_paste(c.img, spr, quad)
    c.flush()

    # 光标演示（屏幕空间 UI，不参与相机变换）
    draw_cursor(c, t, tx, ty, sep)
    c.flush()
    c.vignette(radius=0.62, power=1.8, alpha=0.4)


def draw_cursor(c, t, tx, ty, sep):
    a_in = clamp((t - 0.75) / 0.3, 0, 1)
    a_out = 1.0 - clamp((t - 6.35) / 0.5, 0, 1)
    alpha = a_in * a_out
    if alpha <= 0.01:
        return
    btn_c = proj(1712, 58, 30 * 1.2 * sep, tx, ty)
    btn = (btn_c[0], btn_c[1]) if btn_c else (1764, 44)
    tlp_c = proj(850, 760, 90 * 1.2 * sep, tx, ty)
    tlp = (tlp_c[0], tlp_c[1]) if tlp_c else (850, 760)
    p0 = (900, 780)
    if t < 3.95:
        u1 = ease_io((t - 0.9) / 1.9)
        pos = [p0[0] + (btn[0] - p0[0]) * u1, p0[1] + (btn[1] - p0[1]) * u1]
        if t > 2.8:
            pos[0] += 3.0 * math.sin(t * 3.1)
            pos[1] += 2.0 * math.sin(t * 2.3 + 1.0)
    else:
        u2 = ease_io((t - 3.95) / 1.35)
        pos = [btn[0] + (tlp[0] - btn[0]) * u2, btn[1] + (tlp[1] - btn[1]) * u2]
    # 点击：按下缩放 0.85 + 紫色 ring 扩散淡出
    pr = clamp((t - 3.75) / 0.12, 0, 1)
    cs = 1.0 - 0.15 * math.sin(math.pi * pr) if t >= 3.75 else 1.0
    for ri, (rt, rr) in enumerate(((3.75, 130.0), (3.83, 90.0))):
        p = clamp((t - rt) / 0.55, 0, 1)
        if 0 < p < 1:
            c.circle(pos[0], pos[1], rr * out_cubic(p), outline="#A78BFA",
                     width=6 - ri * 2, alpha=0.8 * (1 - p) * alpha)
    if 3.75 <= t <= 4.3:
        gp = clamp((t - 3.75) / 0.55, 0, 1)
        c.glow(btn[0], btn[1], 150 * (1 - gp * 0.4), "#8F72FF", 0.55 * (1 - gp))
    # 箭头（经典指针形状）
    base = [(0, 0), (0, 27), (7.5, 20.5), (12, 31), (16.5, 29), (12, 19), (20, 19)]
    pts = [(pos[0] + vx * 2.0 * cs, pos[1] + vy * 2.0 * cs) for (vx, vy) in base]
    c.polygon([(p[0] + 3, p[1] + 4) for p in pts], fill=(0, 0, 0), alpha=0.43 * alpha)
    c.polygon(pts, fill=(255, 255, 255), alpha=alpha, outline="#1A2230", width=2)


# === 配乐：A 小调 120 BPM，11s = 22 拍 ===
def make_score(duration, bpm):
    wa = wv.wa
    spb = 60.0 / bpm
    total_beats = duration / spb
    PROG = [(57, 60, 64), (53, 57, 60), (60, 64, 67), (55, 59, 62)]
    ROOTS = (33, 29, 36, 31)

    def name(m):
        return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][
            int(m) % 12] + str(int(m) // 12 - 1)

    s = wa.Song(bpm=bpm, beats_per_bar=4, tail=0.6)
    pad = s.track("pad", name="pad", gain_db=-16.0, pan=0.0, seed=1)
    pluck = s.track("pluck", name="arp", gain_db=-12.0, pan=0.12, seed=2)
    bass = s.track("bass", name="bass", gain_db=-9.0, pan=0.0, seed=3)
    hat = s.track("hat", name="tick", gain_db=-22.0, pan=-0.05, seed=4)

    bars = 5
    for bi in range(bars):
        b0 = bi * 4.0
        ch = PROG[bi % 4]
        if bi < bars - 1:
            for m in ch:
                pad.note(b0, name(m), 4.05, 0.5 if bi else 0.32)
        if 1 <= bi < bars - 1:
            bass.note(b0, name(ROOTS[bi % 4]), 1.5, 0.8)
            bass.note(b0 + 2.0, name(ROOTS[bi % 4]), 1.8, 0.6)
        if bi >= 2:
            if bi < bars - 1:
                # 摇摆节奏：附点长音 + 错峰跨小节长音
                SWAY = ((0.0, 2.0, 0), (3.0, 3.5, 2))
                for off, dur_b, idx in SWAY:
                    pluck.note(b0 + off, name(ch[idx] + 12), dur_b,
                               0.42 if off == 0.0 else 0.36)
            for si in range(8):
                hat.note(b0 + si * 0.5, None, None, 0.4 if si % 2 else 0.7)
    end_b = bars * 4.0
    # 渐强 swell（最后 2 拍两个重叠长音）→ 高音主音单音收
    pad.note(end_b - 2.0, name(57), 2.5, 0.5)
    pad.note(end_b - 1.0, name(60), 1.5, 0.75)
    pluck.note(end_b, name(69), 2.0, 0.55)
    s.length(beats=total_beats)
    s.fade(out_seconds=2.0)
    return s


film = wv.Film(W, H, duration=11.0, fps=30, ss=2, theme="midnight",
               bpm=120, name="pagecam")
film.music = make_score(film.duration, film.bpm)

s1 = film.scene(0, 11, transition="cut")
s1.draw(main_scene, at=0, enter="none")
s1.text("AI 一键成片", at=8.4, style="hero", y=170)
s1.text("PAGECAM · 真实页面 2.5D 推镜", at=8.9, style="subtitle", y=262)

# 音效对齐 120BPM 八分网格(0.25s)：whoosh 飞入 / click 钩子 / pop 落 clip / swipe 开播 / chime 收
film.sfx("whoosh", at=0.25, gain=-8)
film.sfx("swish", at=1.5, gain=-12)
film.sfx("click", at=3.75, gain=-6)
film.sfx("sparkle", at=4.0, gain=-12)
for tt in (4.25, 4.5, 4.75, 5.0, 5.25):
    film.sfx("pop", at=tt, gain=-14)
film.sfx("swipe", at=5.5, gain=-12)
film.sfx("whoosh", at=6.5, gain=-8)
film.sfx("chime", at=8.5, gain=-9)

# 闪烁检测排除：clip 落下弹簧(3.9-5.5)与 15fps 监视器播放(5.4-11，含推镜放大区域)均属有意急变
film.flicker_exclude(3.9, 5.5, x=56, y=560, w=1810, h=500)
film.flicker_exclude(5.4, 11.0, x=140, y=40, w=1640, h=660)

if __name__ == "__main__":
    print("lint（渲染前）：")
    for it in film.lint():
        print("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    rep = film.render(os.path.join(OUT, "pagecam.mp4"), sheet=True, flicker=True)
    print("成片：", rep["path"])
    print("联系表：", os.path.join(OUT, "pagecam.sheet.png"))
