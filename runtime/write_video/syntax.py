# -*- coding: utf-8 -*-
"""解说动画语法层（移植自 huashu-art-motion 8 支示范片 + lib/motion.js + lib/camera.js）。

三层：
1. Cam 世界相机 + cam_track 镜头动作表 + 视差/漂移——图元级矢量重画（缩放转场不放大位图）。
2. 转场（帧级离屏合成）：cut/cross/push/bands/smash/zoom/lens。
3. 8 种语法 scaffold（每段一块全屏画面）：y1_scale / y2_desk / y3_board / y4_story /
   y5_type / t1_math / t2_keynote / t3_chart——用法与坑见 recipes/syntax/。
"""
import math

import numpy as np
from PIL import Image

from . import motion as mo
from .canvas import Canvas, parse_color


# ============================================================
# Cam · 世界相机
# ============================================================


class Cam(object):
    """相机画布包装：图元级矢量重画。

    cam = (x, y, z, r)：世界点 (x,y) 落在画面中心；z>1 推近；r 弧度绕中心旋转。
    变换与 huashu CAM.apply 一致：translate(W/2,H/2)→rotate→scale→translate(-x,-y)。
    所有图元先变换点/尺寸再交给真实画布——缩放永远矢量重画。
    """

    def __init__(self, c, x=960.0, y=540.0, z=1.0, r=0.0):
        self.c = c
        self.x, self.y, self.z, self.r = float(x), float(y), float(z), float(r)
        self.W = float(getattr(c, "width", 1920.0))
        self.H = float(getattr(c, "height", 1080.0))

    # ---------- 变换 ----------

    def pt(self, px, py):
        dx, dy = px - self.x, py - self.y
        zx, zy = dx * self.z, dy * self.z
        if self.r:
            cr, sr = math.cos(self.r), math.sin(self.r)
            zx, zy = zx * cr - zy * sr, zx * sr + zy * cr
        return (self.W / 2.0 + zx, self.H / 2.0 + zy)

    def to_screen(self, px, py):
        return self.pt(px, py)

    def to_world(self, sx, sy):
        dx, dy = sx - self.W / 2.0, sy - self.H / 2.0
        if self.r:
            cr, sr = math.cos(-self.r), math.sin(-self.r)
            dx, dy = dx * cr - dy * sr, dx * sr + dy * cr
        return (self.x + dx / self.z, self.y + dy / self.z)

    def pts(self, pl):
        return [self.pt(p[0], p[1]) for p in pl]

    def layer(self, d):
        """视差层：远层位移按 d 线性、缩放按 z^d（深推时远景几乎不动）。"""
        return Cam(self.c, lerp2(self.W / 2.0, self.x, d), lerp2(self.H / 2.0, self.y, d),
                   self.z ** d, self.r)

    # ---------- 图元 ----------

    def rect(self, x, y, w, h, fill=None, outline=None, width=2.0, alpha=1.0,
             jitter=0.0, seed=0, smooth=False):
        p = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        self.c.polygon(self.pts(p), fill=fill, outline=outline,
                       width=width * self.z, alpha=alpha, jitter=jitter, seed=seed,
                       smooth=smooth)

    def polygon(self, pts, fill=None, outline=None, width=2.0, alpha=1.0,
                jitter=0.0, seed=0, smooth=False):
        self.c.polygon(self.pts(pts), fill=fill, outline=outline,
                       width=width * self.z, alpha=alpha, jitter=jitter, seed=seed,
                       smooth=smooth)

    def lines(self, pts, color="fg", width=2.0, alpha=1.0, curve=False,
              jitter=0.0, seed=0, smooth=None):
        self.c.lines(self.pts(pts), color=color, width=width * self.z, alpha=alpha,
                     curve=curve, jitter=jitter, seed=seed, smooth=smooth)

    def circle(self, x, y, r, fill=None, outline=None, width=2.0, alpha=1.0):
        sx, sy = self.pt(x, y)
        self.c.circle(sx, sy, max(0.5, r * self.z), fill=fill, outline=outline,
                      width=width * self.z, alpha=alpha)

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, width=2.0, alpha=1.0):
        sx, sy = self.pt(x, y)
        self.c.ellipse(sx, sy, rx * self.z, ry * self.z, fill=fill, outline=outline,
                       width=width * self.z, alpha=alpha)

    def arc(self, x, y, r, start, end, color="fg", width=3.0, alpha=1.0):
        sx, sy = self.pt(x, y)
        self.c.arc(sx, sy, max(0.5, r * self.z), start, end, color=color,
                   width=width * self.z, alpha=alpha)

    def glow(self, x, y, r, color=(255, 214, 130), alpha=0.4):
        sx, sy = self.pt(x, y)
        self.c.glow(sx, sy, r * self.z, color=color, alpha=alpha)

    def text(self, s, x, y, size=48, color="fg", bold=False, align="center",
             valign="center", alpha=1.0, font=None, line_gap=1.35):
        sx, sy = self.pt(x, y)
        self.c.text(s, sx, sy, size=max(4, int(round(size * self.z))), color=color,
                    bold=bold, align=align, valign=valign, alpha=alpha, font=font,
                    line_gap=line_gap)


def lerp2(a, b, u):
    return a + (b - a) * u


def cam_at(x=960.0, y=540.0, z=1.0, r=0.0):
    return {"x": float(x), "y": float(y), "z": float(z), "r": float(r)}


def cam_zlerp(z0, z1, e):
    """对数缩放：每帧放大同样倍数，尺度穿行才是匀速。线性插值禁用。"""
    if z0 <= 1e-6:
        return z1
    return z0 * (z1 / z0) ** e


def cam_cover(r, w=1920.0, h=1080.0):
    """钻进半径 r 的开口且盖满屏的最小倍数：中心开口 ≈ 1101/r。"""
    cx, cy = w / 2.0, h / 2.0
    return max(math.hypot(cx, cy), math.hypot(w - cx, cy),
               math.hypot(cx, h - cy), math.hypot(w - cx, h - cy)) / max(1e-4, r)


def cam_anchor(wx, wy, z, sx, sy, w=1920.0, h=1080.0):
    """让世界点在缩放 z 下出现在屏幕 (sx, sy)。"""
    return {"x": wx - (sx - w / 2.0) / z, "y": wy - (sy - h / 2.0) / z, "z": z, "r": 0.0}


def cam_push_to(base, wx, wy, Z, e, k=None, to=(960.0, 540.0)):
    """推进世界点：缩放按对数插值到 Z（进度 e），该点在屏幕上从原位置移向 to（进度 k）。"""
    s0 = Cam(_DummyC(), **_camdict(base)).pt(wx, wy) if not isinstance(base, Cam) else base.pt(wx, wy)
    if isinstance(base, Cam):
        z0 = base.z
        w0, h0 = base.W, base.H
    else:
        z0 = base.get("z", 1.0)
        w0, h0 = 1920.0, 1080.0
    k = e if k is None else k
    z = cam_zlerp(z0, Z, mo.clamp(e))
    return cam_anchor(wx, wy, z, lerp2(s0[0], to[0], mo.clamp(k)),
                      lerp2(s0[1], to[1], mo.clamp(k)), w0, h0)


class _DummyC(object):
    width = 1920.0
    height = 1080.0


def _camdict(c):
    if isinstance(c, Cam):
        return {"x": c.x, "y": c.y, "z": c.z, "r": c.r}
    return {"x": c.get("x", 960.0), "y": c.get("y", 540.0),
            "z": c.get("z", 1.0), "r": c.get("r", 0.0)}


def cam_track(base, events, t):
    """镜头动作表：相机只由 t 算出（确定性）。每个动作从上一动作结束时的相机出发，
    at+dur 落定；两动作挨太近时下一个从上一个此刻位置接着走。

    events: [{"at": s, "kind": "push|pull|glide|to|punch|pan|slam|shake|cut",
              "x": wx, "y": wy, "z": z, "k": 幅度, "dur": s, "ease": f, "amp": px, "from": z0}]
    """
    cam = cam_at(**_camdict(base))
    shake = 0.0
    for ev in sorted(events, key=lambda e: e.get("at", 0.0)):
        kind = ev.get("kind", "push")
        dur = ev.get("dur", mo.PULSE.get({"push": "push", "glide": "glide", "pull": "pull",
                                          "punch": "punch", "pan": "pan", "slam": "slam",
                                          "to": "push"}.get(kind, "push"), 0.9))
        at_ = ev.get("at", 0.0)
        if kind == "cut":
            if t >= at_:
                cam = cam_at(ev.get("x", cam["x"]), ev.get("y", cam["y"]),
                             ev.get("z", cam["z"]), cam["r"])
            continue
        if kind == "slam":
            if t >= at_:
                cam["z"] *= mo.slam_k((t - at_) / dur, ev.get("from", 1.55))
            continue
        if kind == "shake":
            if at_ <= t < at_ + 0.13:
                k = (t - at_) / 0.13
                shake = (ev.get("amp", 14.0)) * math.sin(k * math.pi * 4.0) * (1.0 - k) / cam["z"]
            continue
        if t <= at_:
            continue
        ease = ev.get("ease")
        if ease is None:
            ease = mo.cubic_in_out if (kind in ("punch", "pan") or dur <= 0.35) else mo.sine_in_out
        p = ease(mo.clamp((t - at_) / dur))
        if kind in ("push", "pull", "punch"):
            k = ev.get("k", 0.2 if kind == "push" else (-1.0 / 6.0 if kind == "pull" else mo.PULSE["k"]))
            tz = cam["z"] * (1.0 + k)
            tx, ty = (ev.get("x", cam["x"]), ev.get("y", cam["y"]))
        elif kind in ("glide", "pan"):
            tz = cam["z"]
            tx, ty = (ev.get("x", cam["x"]), ev.get("y", cam["y"]))
        else:  # to
            tz = ev.get("z", cam["z"])
            tx, ty = (ev.get("x", cam["x"]), ev.get("y", cam["y"]))
        cam = cam_at(lerp2(cam["x"], tx, p), lerp2(cam["y"], ty, p),
                     cam_zlerp(cam["z"], tz, p), cam["r"])
    cam["y"] += shake
    return cam


def cam_drift(t, amp=6.0, seed=0.0):
    """手持微漂（只给艺术画面/纯氛围镜头；解说镜头停住时就停）。"""
    return (amp * math.sin(t * 0.9 + seed) + amp * 0.4 * math.sin(t * 2.3 + seed * 2.0),
            amp * 0.7 * math.sin(t * 1.1 + seed * 3.0))


# ============================================================
# 转场（帧级离屏合成）
# ============================================================


def _offscreen(c):
    img = Image.new("RGBA", (int(round(c.width * c.ss)), int(round(c.height * c.ss))),
                    (0, 0, 0, 0))
    return img, Canvas(img, ss=c.ss, width=c.width, height=c.height)


def _zoom_crop(img, s, cx, cy):
    """位图近似缩放（转场窗口内 0.2-0.6s 的近似；长推请用 Cam 矢量重画）。"""
    if s <= 1.001:
        return img
    w, h = img.size
    cw, ch = w / s, h / s
    box = (max(0, int(cx - cw / 2)), max(0, int(cy - ch / 2)),
           min(w, int(cx + cw / 2)), min(h, int(cy + ch / 2)))
    crop = img.crop(box)
    return crop.resize((w, h), Image.BILINEAR)


def _blend(a_img, b_img, u):
    a = np.asarray(a_img, dtype=np.float32)
    b = np.asarray(b_img, dtype=np.float32)
    if a_img.mode != "RGBA":
        a = np.dstack([a, np.full(a.shape[:2] + (1,), 255.0)])
    if b_img.mode != "RGBA":
        b = np.dstack([b, np.full(b.shape[:2] + (1,), 255.0)])
    al = (b[..., 3:4] / 255.0) * mo.clamp(u)
    out = a.copy()
    out[..., :3] = a[..., :3] * (1.0 - al) + b[..., :3] * al
    out[..., 3:4] = a[..., 3:4] * (1.0 - al) + b[..., 3:4] * al
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def _mask_paste(base, top, mask):
    base.paste(top, (0, 0), mask)
    return base


def _circle_mask(c, r, cx, cy):
    m = Image.new("L", (int(round(c.width * c.ss)), int(round(c.height * c.ss))), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(m)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return m


def transition(c, kind, fa, fb, lt_a, lt_b, u, arg=None):
    """帧级转场合成。fa/fb: fn(cv, local_t)；u: 转场进度 0..1。

    kind: cut / cross / push / bands / smash / zoom / lens
      - zoom（fillZoom/zoomThrough 近似）：冲进 arg["at"]=(wx,wy) 点，倍数 arg.get("z", 6)，
        中点后 B 溶入（matchCut 近似；lens 用 arg["r0"] 圆形开口 + 双光环）
      - smash：B 以弹簧缩回（1+0.22·(1−springHz)），前 2 帧 55% 白闪
    """
    if kind == "cut" or u <= 0:
        fa(c, lt_a)
        return
    if u >= 1.0:
        fb(c, lt_b)
        return
    W, H = c.width, c.height
    if kind == "cross":
        ia, ca = _offscreen(c)
        fa(ca, lt_a)
        ib, cb = _offscreen(c)
        fb(cb, lt_b)
        out = _blend(ia, ib, u)
        if c.img.mode == "RGBA":
            c.img.alpha_composite(out)
        else:
            c.img.paste(out, (0, 0))
        return
    if kind == "push":
        e = mo.expo_in_out(u)
        ia, ca = _offscreen(c)
        fa(ca, lt_a)
        ib, cb = _offscreen(c)
        fb(cb, lt_b)
        out = Image.new("RGBA", ia.size, (0, 0, 0, 0))
        out.paste(ia, (-int(e * W * c.ss), 0), ia)
        out.paste(ib, (int((1.0 - e) * W * c.ss), 0), ib)
        if c.img.mode == "RGBA":
            c.img.alpha_composite(out)
        else:
            c.img.paste(out, (0, 0))
        return
    if kind == "bands":
        ia, ca = _offscreen(c)
        fa(ca, lt_a)
        if c.img.mode == "RGBA":
            c.img.alpha_composite(ia)
        else:
            c.img.paste(ia, (0, 0))
        ib, cb = _offscreen(c)
        fb(cb, lt_b)
        sk = H * 0.35 * c.ss
        x = mo.lerp(-sk - 40.0, W * c.ss + sk + 40.0, mo.expo_in_out(u))
        m = Image.new("L", ib.size, 0)
        from PIL import ImageDraw
        dm = ImageDraw.Draw(m)
        dm.polygon([(-sk - 60, 0), (x + sk, 0), (x, ib.size[1]), (-sk - 60, ib.size[1])], fill=255)
        _mask_paste(c.img, ib, m)
        return
    if kind == "smash":
        ia, ca = _offscreen(c)
        fa(ca, lt_a)
        if c.img.mode == "RGBA":
            c.img.alpha_composite(ia)
        else:
            c.img.paste(ia, (0, 0))
        ib, cb = _offscreen(c)
        fb(cb, lt_b)
        s = max(1.0, 1.0 + 0.22 * (1.0 - mo.spring_hz(u * 0.2, 3.0, 11.0)))
        zb = _zoom_crop(ib, s, W * c.ss / 2.0, H * c.ss / 2.0)
        if c.img.mode == "RGBA":
            c.img.alpha_composite(zb)
        else:
            c.img.paste(zb, (0, 0))
        if u < 2.0 / 30.0:
            fl = Image.new("RGBA", ib.size, (255, 255, 255, 140))
            if c.img.mode == "RGBA":
                c.img.alpha_composite(fl)
            else:
                c.img.paste(fl, (0, 0))
        return
    # zoom / lens：A 位图冲进点，B 圆口溶入
    at_pt = (arg or {}).get("at", (W / 2.0, H / 2.0))
    Z = (arg or {}).get("z", 6.0)
    r0 = (arg or {}).get("r0", 60.0)
    e = mo.smooth(u)
    sA = cam_zlerp(1.0, Z, e)
    ia, ca = _offscreen(c)
    fa(ca, lt_a)
    cx, cy = at_pt[0] * c.ss, at_pt[1] * c.ss
    za = _zoom_crop(ia, sA, cx, cy)
    if kind == "lens":
        if c.img.mode == "RGBA":
            c.img.alpha_composite(za)
        else:
            c.img.paste(za, (0, 0))
        ib, cb = _offscreen(c)
        fb(cb, lt_b)
        rr = r0 * sA * c.ss
        if rr > 2.0:
            m = _circle_mask(c, rr, cx, cy)
            _mask_paste(c.img, ib, m)
            from PIL import ImageDraw
            ov = Image.new("RGBA", ib.size, (0, 0, 0, 0))
            do = ImageDraw.Draw(ov)
            do.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                       outline=(120, 240, 255, 216), width=max(2, int(rr * 0.06)))
            do.ellipse([cx - rr * 1.06, cy - rr * 1.06, cx + rr * 1.06, cy + rr * 1.06],
                       outline=(70, 230, 255, 64), width=max(2, int(rr * 0.18)))
            if c.img.mode == "RGBA":
                c.img.alpha_composite(ov)
            else:
                c.img.paste(ov, (0, 0))
        return
    # zoom（fillZoom/matchCut 近似）：A 冲进满屏色 → B 溶入
    if c.img.mode == "RGBA":
        c.img.alpha_composite(za)
    else:
        c.img.paste(za, (0, 0))
    q2 = mo.clamp((u - 0.45) / 0.55)
    if q2 > 0:
        ib, cb = _offscreen(c)
        fb(cb, lt_b)
        out = _blend(za, ib, q2)
        if c.img.mode == "RGBA":
            c.img.alpha_composite(out)
        else:
            c.img.paste(out, (0, 0))
    return


def seq_scene(seqs):
    """多段语法合成 scene_fn。

    seqs: [{"t0": s, "dur": s, "fn": fn(cv, local_t), "trans": kind, "trans_dur": 0.45, "arg": {...}}]
    转场从本段 t0 起 trans_dur 秒；A/B 都按各自时间全量矢量重画（live），
    仅 zoom/smash 的 settle 用位图近似。
    """
    def fn(c, t):
        cur = None
        prev = None
        for i, sq in enumerate(seqs):
            if t >= sq["t0"]:
                cur = sq
                prev = seqs[i - 1] if i > 0 else None
        if cur is None:
            return
        kind = cur.get("trans", "cut")
        td = cur.get("trans_dur", 0.45)
        if kind != "cut" and prev is not None and t < cur["t0"] + td:
            lt_a = t - prev["t0"]
            lt_b = t - cur["t0"]
            u = mo.clamp((t - cur["t0"]) / td)
            transition(c, kind, lambda cv, lt: prev["fn"](cv, lt),
                       lambda cv, lt: cur["fn"](cv, lt), lt_a, lt_b, u, cur.get("arg"))
            return
        cur["fn"](c, t - cur["t0"])
    return fn


# ============================================================
# 共用小工具
# ============================================================


def _fnv(name):
    h = 2166136261
    for ch in str(name):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def _saturate(rgb, s=1.5):
    """manim 色值 ×1.5 饱和（CSS saturate 矩阵）。照原值用会发灰。"""
    r, g, b = rgb
    r2 = (0.213 + 0.787 * s) * r + (0.715 - 0.715 * s) * g + (0.072 - 0.072 * s) * b
    g2 = (0.213 - 0.213 * s) * r + (0.715 + 0.285 * s) * g + (0.072 - 0.072 * s) * b
    b2 = (0.213 - 0.213 * s) * r + (0.715 - 0.715 * s) * g + (0.072 + 0.928 * s) * b
    return (int(max(0, min(255, r2))), int(max(0, min(255, g2))),
            int(max(0, min(255, b2))))


def _poly_upto(pts, d):
    """折线按累计弧长描前 d 长，返回 (点列, 笔尖)。"""
    if d <= 0 or len(pts) < 2:
        return ([pts[0]] if pts else []), (pts[0] if pts else (0.0, 0.0))
    total = 0.0
    for i in range(len(pts) - 1):
        seg_len = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if total + seg_len >= d:
            u = (d - total) / max(1e-6, seg_len)
            tip = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u,
                   pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u)
            return pts[:i + 1] + [tip], tip
        total += seg_len
    return pts, pts[-1]


def _cum_lens(pts):
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.hypot(pts[i + 1][0] - pts[i][0],
                                        pts[i + 1][1] - pts[i][1]))
    return cum


def _string_pts(a, b, sag=0.06, n=48):
    """红线索绳：二次贝塞尔，中点下垂 dist·sag。"""
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0 + dist * sag
    return [((1 - q) ** 2 * a[0] + 2 * (1 - q) * q * mx + q * q * b[0],
             (1 - q) ** 2 * a[1] + 2 * (1 - q) * q * my + q * q * b[1])
            for q in (i / (n - 1.0) for i in range(n))]


def _ellipse_pts(cx, cy, rx, ry, a0=-2.6, a1=1.08 * 2 * math.pi, n=44):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / (n - 1.0)),
             cy + ry * math.sin(a0 + (a1 - a0) * i / (n - 1.0))) for i in range(n)]


def _wobble(pts, amp, seed, freq=0.035):
    """手绘抖动：等距重采样近似（直接逐点加低频噪声）。"""
    return [(p[0] + math.sin(i * 2.7 + seed * 13.7) * amp,
             p[1] + math.cos(i * 1.9 + seed * 7.3) * amp) for i, p in enumerate(pts)]


def _ticks(lo, hi):
    """1/2/2.5/5×10ᵏ 刻度 + pad 8%；返回 (刻度值列表, 小数位)。"""
    span = max(1e-9, hi - lo)
    raw = span / 5.0
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= m * mag:
            stepv = m * mag
            break
    start = math.floor(lo / stepv) * stepv
    vals = []
    v = start
    while v <= hi + stepv * 0.5:
        vals.append(round(v, 10))
        v += stepv
    tdec = 0
    while tdec < 6 and abs(stepv * (10.0 ** tdec) - round(stepv * (10.0 ** tdec))) > 1e-9:
        tdec += 1
    while tdec < 6 and abs(round(stepv, tdec) - stepv) > 1e-9:
        tdec += 1
    return vals, tdec


def _fmt_num(v, dec=0):
    if dec <= 0:
        return "{:,}".format(int(round(v)))
    return "{:,}".format(round(v, dec))


def _img_cache():
    global _IMG_CACHE
    if "_IMG_CACHE" not in globals():
        _IMG_CACHE = {}
    return _IMG_CACHE


def paste_img(cv, path, sx, sy, w, h):
    """把用户图贴到屏幕 (sx,sy)（左上角），目标 w×h 设计像素。"""
    cache = _img_cache()
    if path not in cache:
        cache[path] = Image.open(path).convert("RGBA")
    src = cache[path]
    pw = max(1, int(round(w * cv.ss)))
    ph = max(1, int(round(h * cv.ss)))
    im = src.resize((pw, ph), Image.BILINEAR)
    if hasattr(cv.img, "alpha_composite"):
        cv.img.alpha_composite(im, (int(sx * cv.ss), int(sy * cv.ss)))
    else:
        cv.img.paste(im, (int(sx * cv.ss), int(sy * cv.ss)), im)


# ============================================================
# y1 · Kurzgesagt 扁平科普（尺度穿行）
# ============================================================

_Y1_BG = "#0F1114"
_Y1_ACC = ["#32BAEE", "#FACC12", "#E07A3F", "#5CD0B3", "#FC6255", "#A3B84B"]
_Y1_STAR = "#F2EFE8"


def _y1_shape(cv, k, name, cx, cy, R, col, l, v, w, outline=False):
    """双色分面形状：填充阴影色→偏移填高光色→偏移填本色（TOON.flat 等价）。"""
    h = _fnv(name)
    shape = ("circle", "rounded", "hex")[h % 3]
    base = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
    dark = tuple(int(c * 0.72) for c in base)
    light = tuple(int(c + (255 - c) * 0.4) for c in base)
    pts = []
    if shape == "circle":
        pts = [(cx + R * math.cos(a), cy + R * math.sin(a))
               for a in [i / 48.0 * 2 * math.pi for i in range(49)]]
    elif shape == "rounded":
        r2 = R * 0.92
        rad = R * 0.36
        pts = []
        for (bx, by, dx, dy) in ((-1, -1, 1, 0), (1, -1, 0, 1), (1, 1, -1, 0), (-1, 1, 0, -1)):
            cxx, cyy = cx + bx * (r2 - rad), cy + by * (r2 - rad)
            a0 = {(-1, -1): math.pi, (1, -1): 1.5 * math.pi,
                  (1, 1): 0.0, (-1, 1): 0.5 * math.pi}[(bx, by)]
            for q in range(13):
                a = a0 + q / 12.0 * 0.5 * math.pi
                pts.append((cxx + rad * math.cos(a), cyy + rad * math.sin(a)))
    else:
        pts = [(cx + R * 1.06 * math.cos(math.pi / 6 + i / 6.0 * 2 * math.pi),
                cy + R * 1.06 * math.sin(math.pi / 6 + i / 6.0 * 2 * math.pi))
               for i in range(7)]
    for fill, off in ((dark, (0.0, 0.0)), (light, v), (base, w)):
        moved = [(p[0] + off[0], p[1] + off[1]) for p in pts]
        k.polygon(moved, fill=fill, alpha=mo.clamp(l))


def y1_scale(cv, lt, spec):
    """y1 Kurzgesagt：中心物 + 卫星节点 + 尺度穿行。spec:
    {"title", "node", "sats": [...], "cam_events"?: [...], "node_pos"?: (x,y)}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    cv.rect(0, 0, W, H, fill=_Y1_BG)
    events = spec.get("cam_events", [])
    cam = cam_track(cam_at(W / 2, H / 2, 1.0), events, lt) if events else cam_at(W / 2, H / 2, 1.0)
    k = Cam(cv, **cam)
    cx = spec.get("node_pos", (W / 2.0, H / 2.0 + 30.0 * u))[0]
    cy = spec.get("node_pos", (W / 2.0, H / 2.0 + 30.0 * u))[1]
    R = 140.0 * u
    # 星（视差 d=0.05）
    ks = k.layer(0.05)
    for i in range(160):
        r1 = mo.clamp((i * 2654435761 % 1000) / 1000.0)
        r2 = mo.clamp((i * 40503 % 1000) / 1000.0)
        sx = -0.2 * W + r1 * 1.4 * W
        sy = -0.2 * H + r2 * 1.4 * H
        sp = 1.0 + r2 * 2.5
        a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(lt * sp + i * 1.7))
        ks.circle(sx, sy, (0.8 + r1 * r1 * 3.0) * u, fill=_Y1_STAR, alpha=0.7 * a)
    # 中心物辉光 + 双色分面
    k.glow(cx, cy, R * 2.4, color=(53, 186, 238), alpha=0.28)
    col = _Y1_ACC[_fnv(spec.get("node", "n")) % 6]
    _y1_shape(cv, k, spec.get("node", "n"), cx, cy, R, col, 1.0, (-18.0 * u, 14.0 * u),
              (-6.0 * u, 5.0 * u))
    name = spec.get("node", "")
    if name:
        k.text(name, cx, cy, size=56.0 * u, color="#FFFFFF", bold=True)
    # 卫星节点 + 连线 + 标签
    sats = spec.get("sats", [])[:4]
    n = len(sats)
    rx = min(W * 0.32, 640.0 * u)
    ry = H * 0.36
    for i, sn in enumerate(sats):
        l = mo.clamp((lt - 1.0 - i * 0.3) / 1.0)
        if l <= 0:
            continue
        ang = math.pi + (i + 0.5) / max(1, n) * math.pi if n < 4 else math.pi + i / n * 2 * math.pi
        nx, ny = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
        lq = mo.back_out(l / 0.5 if l < 0.5 else 1.0, 1.1)
        # 连线（0.4s 长到节点）
        lp = mo.cubic_out(mo.clamp(l / 0.4))
        end = (cx + (nx - cx) * lp, cy + (ny - cy) * lp)
        k.lines([_y1_lp(cx, cy, R, nx, ny), end], color="#7DD3DC", width=4.0 * u,
                alpha=0.35)
        for kk in range(3):
            q = (lt * 0.7 - i * 0.33 + kk / 3.0) % 1.0
            px = cx + (nx - cx) * q
            py = cy + (ny - cy) * q
            k.circle(px, py, 5.0 * u, fill="#32BAEE", alpha=0.9 * lp)
        scol = _Y1_ACC[(i + 2) % 6]
        _y1_shape(cv, k, sn, nx, ny, 46.0 * u * lq, scol, lq, (-8.0 * u, -8.0 * u),
                  (-3.0 * u, -3.0 * u))
        # 标签胶囊
        lbn = sn
        lw_ = max(120.0 * u, (len(lbn) * 30.0 + 56.0) * u)
        lq2 = mo.back_out(mo.clamp((l - 0.15) / 0.5), 1.1)
        k.polygon([(nx - lw_ / 2 * lq2, ny + 70.0 * u - 35.0 * u * lq2),
                   (nx + lw_ / 2 * lq2, ny + 70.0 * u - 35.0 * u * lq2),
                   (nx + lw_ / 2 * lq2, ny + 70.0 * u + 35.0 * u * lq2),
                   (nx - lw_ / 2 * lq2, ny + 70.0 * u + 35.0 * u * lq2)],
                  fill="#FFFFFF", alpha=0.95 * lq, smooth=False)
        k.text(lbn, nx, ny + 70.0 * u, size=38.0 * u, color="#1B1A17", alpha=lq2)
    # 标题（逐字）
    title = spec.get("title", "")
    if title:
        shown = int(mo.clamp((lt - 0.2) / 0.5) * len(title))
        a0 = mo.clamp((lt - 0.2) / 0.5)
        if events:
            fade = 1.0 - mo.sine_in_out(mo.clamp((lt - events[0].get("at", 1e9)) / 0.5))
        else:
            fade = 1.0
        if shown > 0 and fade > 0.01:
            k.text(title[:shown], W / 2, 130.0 * u, size=76.0 * u, color="#FFFFFF",
                   bold=True, alpha=fade * mo.clamp(a0 * 2.2))
    # 高光变暗（cam_events 有 push 时其余元素变暗）
    if events:
        dim = mo.smooth(mo.clamp((lt - events[0].get("at", 1e9)) / 0.6))
        if dim > 0:
            cv.rect(0, 0, W, H, fill="#0F1114", alpha=0.4 * dim)


def _y1_lp(cx, cy, R, nx, ny):
    """连线起点：中心物圆周。"""
    d = math.hypot(nx - cx, ny - cy) or 1.0
    return (cx + R * 0.9 * (nx - cx) / d, cy + R * 0.9 * (ny - cy) / d)


# ============================================================
# y2 · Vox 拼贴（真实材料桌面）
# ============================================================

_Y2_DESK = "#e4ddcf"
_Y2_RED = "#b8433f"
_Y2_CARD = "#f6f4ee"
_Y2_INK = "#171716"
_Y2_HL = (218, 207, 8)


def _vignette_plate(cv, col=(40, 30, 20), a_max=0.30):
    """径向暗角（中心干净，四角压暗；缓存成图）。"""
    cache = _img_cache()
    key = ("vig", int(cv.width * cv.ss), int(cv.height * cv.ss), col, a_max)
    if key in cache:
        return cache[key]
    W, H = int(cv.width * cv.ss), int(cv.height * cv.ss)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W / 2.0, H / 2.0
    d = np.sqrt(((xx - cx) / (W * 0.62)) ** 2 + ((yy - cy) / (H * 0.62)) ** 2)
    a = np.clip(d - 0.55, 0.0, 1.0) / 0.45 * a_max
    layer = np.zeros((H, W, 4), np.float32)
    layer[..., 0], layer[..., 1], layer[..., 2] = col
    layer[..., 3] = a * 255.0
    img = Image.fromarray(np.clip(layer, 0, 255).astype(np.uint8), "RGBA")
    cache[key] = img
    return img


def y2_desk(cv, lt, spec):
    """y2 Vox：桌面拼贴。spec:
    {"items": [{"kind":"photo"|"text", "x","y","w","h", "at", "img"?, "lines"?: [str...]}...],
     "threads": [(a, b)...], "hl"?: {"item": i, "line": k, "at": t},
     "circle"?: {"item": i, "at": t}, "cam_events"?: [...]}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    events = spec.get("cam_events", [])
    cam = cam_track(cam_at(W / 2, H / 2, 1.0), events, lt) if events else cam_at(W / 2, H / 2, 1.0)
    k = Cam(cv, **cam)
    # 桌面（世界坐标大平面 + 纤维，静态）
    k.rect(-2600, -1600, 7600, 4600, fill=_Y2_DESK)
    for i in range(220):
        r1 = mo.clamp((i * 48271 % 997) / 997.0)
        r2 = mo.clamp((i * 7919 % 991) / 991.0)
        fx, fy = -2600 + r1 * 7600, -1600 + r2 * 4600
        ln = 14.0 + r2 * 26.0
        k.lines([(fx, fy), (fx + ln * math.cos(r1 * 6.28), fy + ln * 0.4 * math.sin(r2 * 6.28))],
                color=(110, 95, 70), width=1.2 * u, alpha=0.16)
    items = spec.get("items", [])
    # 红线（先画，被卡片压住钉点）
    for ti, (ia, ib) in enumerate(spec.get("threads", [])):
        if ia >= len(items) or ib >= len(items):
            continue
        A, B = items[ia], items[ib]
        at_ = max(A.get("at", 0.0), B.get("at", 0.0)) + 0.4
        q = mo.step(mo.clamp((lt - at_) / 0.7), 12)
        if q <= 0:
            continue
        a = (A["x"] + A["w"] / 2 - 30.0 * u, A["y"] + A["h"] * 0.25)
        b = (B["x"] - B["w"] / 2 + 30.0 * u, B["y"] + B["h"] * 0.25)
        pts = _string_pts(a, b, 0.06, 48)
        seg_pts, tip = _poly_upto(pts, math.hypot(b[0] - a[0], b[1] - a[1]) * 1.15
                                  * mo.sine_in_out(q))
        if len(seg_pts) > 1:
            k.lines(_wobble(seg_pts, 1.2 * u, ti), color=_Y2_RED, width=5.0 * u)
            k.lines(_wobble(seg_pts, 1.2 * u, ti), color=(0, 0, 0), width=5.0 * u,
                    alpha=0.12)
        if q >= 1.0:
            for p in (a, b):
                k.circle(p[0], p[1], 12.0 * u, fill=_Y2_RED)
                k.circle(p[0] - 4.0 * u, p[1] - 4.0 * u, 4.0 * u, fill="#FFFFFF", alpha=0.8)
    # 卡片（12fps 从 at 起算）
    for idx, it in enumerate(items):
        ls = mo.step(lt - it.get("at", 0.0) + 1e-6, 12) + 1.0 / 12.0
        if ls <= 0:
            continue
        x, y, w, h = it["x"], it["y"], it["w"], it["h"]
        k.rect(x - 16.0 * u, y - 16.0 * u, w + 32.0 * u, h + 32.0 * u, fill="#FFFFFF",
               alpha=0.95 * min(1.0, ls))
        if it.get("img"):
            sx, sy = k.pt(x, y)
            paste_img(cv, it["img"], sx, sy, w * k.z, h * k.z)
        else:
            k.rect(x, y, w, h, fill=it.get("tint", "#C8C2B4"), alpha=0.9 * min(1.0, ls))
        if it.get("kind") == "text":
            k.rect(x, y, w, h, fill=_Y2_CARD, alpha=min(1.0, ls))
            lines_ = it.get("lines", [""])
            fs = 48.0 * u
            for li, ln in enumerate(lines_):
                shown = int(mo.clamp((ls - li * 0.12) / 0.3) * len(ln))
                if shown <= 0:
                    continue
                k.text(ln[:shown], x + 40.0 * u, y + 90.0 * u + li * fs * 1.45, size=fs,
                       color=_Y2_INK, align="left")
            k.lines([(x + 20.0 * u, y + 56.0 * u), (x + w - 20.0 * u, y + 56.0 * u)],
                    color=(80, 140, 200), width=2.0 * u, alpha=0.3)
    # 荧光笔（斜切平行四边形，sineInOut 扫）
    hl = spec.get("hl")
    if hl and hl.get("item", -1) < len(items):
        it = items[hl["item"]]
        ls = mo.step(lt - hl.get("at", 0.0), 12) + 1.0 / 12.0
        p = mo.sine_in_out(mo.clamp(ls / 0.6))
        if p > 0:
            fs = 48.0 * u
            ly = it["y"] + 90.0 * u + hl.get("line", 0) * fs * 1.45
            x0 = it["x"] + 40.0 * u
            ww = (it["w"] - 80.0 * u) * p
            k.polygon([(x0 + 14.0 * u, ly - fs * 0.62), (x0 + ww + 20.0 * u, ly - fs * 0.62),
                       (x0 + ww, ly + fs * 0.55), (x0, ly + fs * 0.55)],
                      fill=_Y2_HL + (128,), alpha=0.55, smooth=False)
    # 红圈
    ci = spec.get("circle")
    if ci and ci.get("item", -1) < len(items):
        it = items[ci["item"]]
        ls = mo.step(lt - ci.get("at", 0.0), 12) + 1.0 / 12.0
        p = mo.cubic_out(mo.clamp((ls - 0.5) / 0.6))
        if p > 0:
            cx2 = it["x"] + it["w"] / 2
            cy2 = it["y"] + it["h"] / 2
            pts = _ellipse_pts(cx2, cy2, it["w"] * 0.42, it["h"] * 0.5, -2.6, 1.08 * 2 * math.pi)
            total = _cum_lens(pts)[-1]
            seg_pts, _ = _poly_upto(pts, total * p)
            k.lines(_wobble(seg_pts, 2.2 * u, 7), color=_Y2_RED, width=7.0 * u)
    # 暗角（径向，屏幕层）
    if cv.img.mode == "RGBA":
        cv.img.alpha_composite(_vignette_plate(cv))
    else:
        cv.img.paste(_vignette_plate(cv), (0, 0), _vignette_plate(cv))


# ============================================================
# y3 · 白板手绘（RSA）
# ============================================================

_Y3_BOARD = "#FBFBFB"
_Y3_INK = "#0A0503"


def _y3_timeline(spec):
    """笔画时间线（确定性）：每块 cue 排出 [start, end, kind, payload]。"""
    u = 1920.0 / 1920.0
    strokes = []
    for bi, b in enumerate(spec.get("blocks", [])):
        at_ = b.get("at", 0.0)
        y = 260.0 + bi * 300.0
        if b.get("text"):
            rate = 7.5 if bi == 0 else 16.0
            dur = len(b["text"]) / rate
            strokes.append({"t0": at_, "t1": at_ + dur, "kind": "text", "y": y,
                            "text": b["text"], "x": 150.0, "rate": rate})
            at_ += dur + 0.03
        for li, raw in enumerate(b.get("lines", [])):
            pts = [(p[0], p[1] + y - 150.0) for p in raw]
            total = _cum_lens(pts)[-1]
            dur = max(0.04, total / 2600.0)
            strokes.append({"t0": at_, "t1": at_ + dur, "kind": "line", "pts": pts,
                            "total": total})
            at_ += dur + 0.02
    return strokes


def y3_board(cv, lt, spec):
    """y3 白板：说一句写一句，相机跟论证走，最后拉远。spec:
    {"blocks": [{"at", "text"?/ "lines"?: [[(x,y)...], ...], "img"?}...],
     "accent"?: "#EF7226"}；返回时间线。"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    accent = spec.get("accent", "#EF7226")
    strokes = _y3_timeline(spec)
    last_end = max([s["t1"] for s in strokes], default=2.0)
    # 相机：内容超带下移 0.6s；收尾拉远
    band_top, band_bot = 140.0, H - 140.0
    cy0, z0 = H / 2.0, 1.0
    need = 0.0
    for s in strokes:
        if s.get("y", 0) + 70.0 > band_bot and s["t0"] > lt - 0.6:
            pass
    cur_y = 0.0
    for s in strokes:
        if s.get("y", 0) + 70.0 > band_bot:
            cur_y = max(cur_y, s["y"] + 70.0 - band_bot)
    pull = mo.sine_in_out(mo.clamp((lt - last_end - 0.1) / 0.8))
    z = cam_zlerp(1.0, min(0.94, (band_bot - band_top) / max(1.0, (cur_y + H)) * 0.96), pull)
    cy = lerp2(cy0 + cur_y * 0.5, H / 2.0 - (cur_y / 2.0) * z, pull) + cur_y * (1.0 - pull) * 0.5
    cam = cam_at(W / 2.0, cy0 + cur_y * 0.5 * (1.0 - pull), z)
    k = Cam(cv, **cam)
    cv.rect(0, 0, W, H, fill=_Y3_BOARD)
    if pull > 0:
        cv.rect(0, 0, W, H, fill="#EEEEEC", alpha=0.85 * pull)
    # 笔画
    tip = None
    drawing = False
    for s in strokes:
        if lt < s["t0"] or lt > s["t1"] + 0.02:
            if lt > s["t1"]:
                if s["kind"] == "text":
                    k.text(s["text"], s["x"] * u, s["y"], size=54.0 * u, color=_Y3_INK,
                           align="left")
                else:
                    k.lines(_wobble(s["pts"], 1.4 * u, 3.1), color=_Y3_INK, width=6.5 * u)
            continue
        drawing = True
        if s["kind"] == "text":
            n_shown = int(mo.clamp((lt - s["t0"]) / max(1e-6, s["t1"] - s["t0"]))
                          * len(s["text"]) + 0.999)
            k.text(s["text"][:n_shown], s["x"] * u, s["y"], size=54.0 * u, color=_Y3_INK,
                   align="left")
            cw = 54.0 * u
            tip = (s["x"] * u + n_shown * cw, s["y"])
        else:
            q = mo.sine_in_out(mo.clamp((lt - s["t0"]) / (s["t1"] - s["t0"])))
            seg_pts, tp = _poly_upto(_wobble(s["pts"], 1.4 * u, 3.1), s["total"] * q)
            if len(seg_pts) > 1:
                k.lines(seg_pts, color=_Y3_INK, width=6.5 * u)
            tip = tp
    # 马克笔（画时入画；tip 世界坐标 → 屏幕坐标）
    if drawing and tip is not None and lt < last_end:
        stp = k.pt(tip[0], tip[1])
        _marker(cv, stp[0] + 26.0 * u * k.z, stp[1], accent)
    return {"strokes": strokes, "last_end": last_end}


def _marker(cv, x, y, col):
    """马克笔（屏幕空间，笔尖在 (x,y)，rotate -0.72）。"""
    ca, sa = math.cos(-0.72), math.sin(-0.72)

    def pf(lx, ly):
        return (x + lx * ca - ly * sa, y + lx * sa + ly * ca)

    cv.polygon([pf(30, 14), pf(280, 14), pf(280, 48), pf(30, 48)],
                 fill=(0, 0, 0), alpha=0.12)
    cv.polygon([pf(0, 0), pf(26, -8), pf(26, 8)], fill=col)
    cv.polygon([pf(24, -12), pf(26, 24), pf(30, 24), pf(28, -12)], fill="#e8e8e4")
    cv.polygon([pf(48, -17), pf(48, 17), pf(238, 17), pf(238, -17)], fill="#26262a")
    cv.polygon([pf(212, -18), pf(212, 18), pf(258, 18), pf(258, -18)], fill=col)
    cv.polygon([pf(60, -12), pf(60, -5), pf(200, -5), pf(200, -12)],
                 fill=(255, 255, 255), alpha=0.22)


# ============================================================
# y4 · 故事型简笔角色（storytime）
# ============================================================

_Y4_POSES = {"rest": [(-0.95, 1.05), (0.95, 1.05)],
             "talk": [(-0.95, 1.05), (1.05, 0.55)],
             "point": [(-0.95, 1.05), (1.75, -0.15)],
             "type": [(-0.55, 0.62), (0.55, 0.62)],
             "shrug": [(-1.45, -0.05), (1.45, -0.05)],
             "stiff": [(-0.78, 1.25), (0.78, 1.25)]}


def _bean(cv, x, y_foot, R, pose_l, pose_r, mouth, brow=(0.0, 0.0), sweat=0.0, t=0.0):
    """程序化豆子角色（lean 版）：全圆全钝，线随镜头缩放。"""
    skin = "#FFE2CC"
    ink = "#1B1B1F"
    lw = max(4.0, R * 0.05)
    body_top = -R * 1.32
    # 腿 + 鞋
    for s in (-1, 1):
        cv.rect(x + s * R * 0.2 - R * 0.09, y_foot - R * 0.44, R * 0.18, R * 0.22,
                fill=skin, outline=ink, width=lw, smooth=False)
        cv.ellipse(x + s * R * 0.22, y_foot - R * 0.04, R * 0.17, R * 0.08,
                   fill=ink, outline=ink, width=lw * 0.5)
    # 身体（豆子：贝塞尔近似为圆角胶囊）
    by = y_foot + body_top
    bh = R * 1.32
    cv.polygon([(x - R * 0.5, y_foot - R * 0.2), (x - R * 0.62, y_foot - bh * 0.6),
                (x - R * 0.3, by + R * 0.05), (x + R * 0.3, by + R * 0.05),
                (x + R * 0.62, y_foot - bh * 0.6), (x + R * 0.5, y_foot - R * 0.2),
                (x, y_foot - R * 0.1)], fill="#FFFFFF", outline=ink, width=lw)
    # 短裤
    cv.rect(x - R * 0.55, y_foot - R * 0.44, R * 1.1, R * 0.22, fill="#CDBB97",
            outline=None, smooth=False)
    # 手臂（肩到手，管子双描边）
    sh_l = (x - R * 0.42, by + R * 0.32)
    sh_r = (x + R * 0.42, by + R * 0.32)
    for (sh, pose) in ((sh_l, pose_l), (sh_r, pose_r)):
        hand = (sh[0] + pose[0] * R * 0.62, sh[1] + pose[1] * R * 0.62)
        mid = ((sh[0] + hand[0]) / 2.0 + R * 0.08, max(sh[1], hand[1]) + R * 0.12)
        cv.lines([sh, mid, hand], color=ink, width=R * 0.17 + lw)
        cv.lines([sh, mid, hand], color=skin, width=R * 0.17)
        cv.circle(hand[0], hand[1], R * 0.13, fill=skin, outline=ink, width=lw * 0.6)
    # 头
    hy = by - R * 0.78
    cv.ellipse(x, hy, R, R * 0.93, fill=skin, outline=ink, width=lw)
    # 帽
    cv.polygon([(x - R * 0.78, hy - R * 0.42), (x - R * 0.8, hy - R * 1.25),
                (x + R * 0.8, hy - R * 1.25), (x + R * 0.78, hy - R * 0.42)],
               fill="#FFFFFF", outline=ink, width=lw)
    cv.rect(x - R, hy - R * 0.62, R * 2.0, R * 0.18, fill="#E4E4E8")
    # 眉（表情主载体）
    for s in (-1, 1):
        b0 = -R * 0.13 + brow[0] * R
        inner = b0 - brow[1] * R * s
        cv.lines([(x + s * R * 0.52, b0), (x + s * R * 0.2, inner)], color=ink,
                   width=lw * 1.4)
    # 眼（镜片圆 + 瞳孔 + 高光）
    for s in (-1, 1):
        ex = x + s * R * 0.37
        cv.circle(ex, hy + R * 0.2, R * 0.27, fill="#FFFFFF", outline=ink, width=lw * 1.5)
        cv.circle(ex, hy + R * 0.2, R * 0.075, fill=ink)
        cv.circle(ex - R * 0.027, hy + R * 0.2 - R * 0.034, R * 0.024, fill="#FFFFFF")
    # 鼻梁
    cv.lines([(x, hy + R * 0.05), (x - R * 0.03, hy + R * 0.2)], color=ink, width=lw * 0.8)
    # 嘴
    my = hy + R * 0.6
    if mouth <= 0:
        cv.lines([(x - R * 0.13, my - R * 0.02), (x, my + R * 0.1), (x + R * 0.13, my - R * 0.02)],
                   color=ink, width=lw)
    else:
        mh = R * (0.1 if mouth == 1 else 0.2)
        mw = R * (0.14 if mouth == 1 else 0.18)
        cv.ellipse(x, my + mh * 0.4, mw, mh, fill="#6E2430", outline=ink, width=lw * 0.7)
        cv.ellipse(x + mw * 0.25, my + mh * 0.75, mw * 0.4, mh * 0.3, fill="#F07B7B")
    # 腮红
    for s in (-1, 1):
        cv.ellipse(x + s * R * 0.68, hy + R * 0.5, R * 0.11, R * 0.06,
                   fill=(255, 140, 120), alpha=0.35)
    # 汗滴
    if sweat > 0:
        sxx = x + R * 0.88
        syy = hy - R * 0.1 + sweat * R * 1.2
        rr = R * 0.09
        cv.polygon([(sxx, syy - rr * 1.5), (sxx + rr * 1.05, syy + rr * 0.1),
                    (sxx, syy + rr), (sxx - rr * 1.05, syy + rr * 0.1)],
                   fill="#9ED8F5", outline=None, alpha=mo.expo_out(mo.clamp(sweat)) * 0.9)


def y4_story(cv, lt, spec):
    """y4 storytime：姿势 0.1s 快切后定住，反应特写闭嘴。spec:
    {"shots": [{"kind":"mid|insert|react|wide|close", "at", "dur", "say"?,
                "pose"?, "mark"?}...]}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    shots = spec.get("shots", [])
    cur = None
    for s in shots:
        if lt >= s.get("at", 0.0):
            cur = s
    if cur is None:
        return
    lt_s = lt - cur.get("at", 0.0)
    kind = cur.get("kind", "mid")
    # 相机：mid z1.0 / wide 0.53 / close 1.9 / insert zoom 1.06 / react 特写
    zmap = {"mid": 1.0, "wide": 0.53, "close": 1.9, "insert": 1.06, "react": 1.9}
    z = zmap.get(kind, 1.0)
    if kind == "insert":
        z = 1.06 - 0.06 * mo.expo_out(mo.clamp(lt_s / 0.25))
        shake = mo.settle(lt_s, 14.0 * u, 9.0, 14.0) if lt_s < 0.3 else 0.0
        cam = cam_at(W / 2.0 + shake, H / 2.0 - shake * 0.5, z)
    elif kind == "react":
        spring = 1.0 + 0.15 * max(0.0, 1.0 - mo.spring_hz(lt_s, 3.0, 11.0))
        cam = cam_at(W * 0.3, H * 1.02 - 215.0 * u * 2.2, z * spring)
    else:
        cam = cam_at(W / 2.0, H / 2.0, z)
    k = Cam(cv, **cam)
    # 房间（世界坐标）
    k.rect(-1600, -1200, 5200, 3600, fill="#DCE9EC")
    k.rect(-1600, H * 1.02 - 40.0 * u, 5200, 800.0 * u, fill="#E8DCC8")
    # 窗 + 云
    wx, wy, ww, wh = W * 0.05, H * 0.12, W * 0.17, W * 0.17 * 0.7
    k.rect(wx, wy, ww, wh, fill="#FFFFFF", outline="#5B6470", width=3.0 * u, smooth=False)
    k.rect(wx + ww / 2 - 2.0 * u, wy, 4.0 * u, wh, fill="#5B6470", smooth=False)
    k.rect(wx, wy + wh / 2 - 2.0 * u, ww, 4.0 * u, fill="#5B6470", smooth=False)
    for ci, sp in ((0, 18.0), (1, 12.0)):
        cxx = wx + ((lt * sp + ci * 90.0) % (ww + 120.0 * u)) - 60.0 * u
        cyy = wy + 20.0 * u + ci * 26.0 * u
        for dx, dy, rr in ((0, 0, 22.0 * u), (-20.0 * u, 6.0 * u, 16.0 * u),
                           (20.0 * u, 6.0 * u, 16.0 * u)):
            k.ellipse(cxx + dx, cyy + dy, rr, rr * 0.7, fill="#FFFFFF", alpha=0.9)
    # 桌
    dy = H * 1.02 - 215.0 * u * 0.55
    k.rect(-200.0 * u, dy, W + 400.0 * u, 40.0 * u, fill="#E2C29B", smooth=False)
    k.rect(-200.0 * u, dy + 40.0 * u, W + 400.0 * u, 200.0 * u, fill="#CDA97F", smooth=False)
    # 角色
    pose = cur.get("pose", "rest")
    pl, pr = _Y4_POSES.get(pose, _Y4_POSES["rest"])
    squash = 1.0 + mo.settle(lt_s, -0.07, 3.5, 9.0) if lt_s < 0.35 else 1.0
    saying = cur.get("say") and lt_s < len(cur["say"]) / 6.5 + 0.6
    mouth = 0
    if saying:
        mouth = [1, 2, 1, 0, 2, 1][int(mo.step(lt_s, 12) * 12) % 6]
    if kind == "react":
        cv.rect(0, 0, W, H, fill="#3D405B")
        sweat = mo.clamp((lt_s - 0.3) / 0.9) if lt_s > 0.3 else 0.0
        _bean(k, W * 0.3, H * 1.02, 215.0 * u, pl, pr, 0,
              brow=(-0.02, -0.11), sweat=sweat, t=lt)
    elif kind == "insert":
        cv.rect(0, 0, W, H, fill="#15161C")
        # 代码墙（种子确定性 token 块）
        for i in range(24):
            r1 = mo.clamp((i * 69119 % 997) / 997.0)
            r2 = mo.clamp((i * 6337 % 991) / 991.0)
            shown = mo.clamp((lt_s - 0.05 - min(i, 12) * 0.03) / 0.05)
            if shown <= 0:
                continue
            cols = ["#E06C75", "#5FB3A1", "#C3E88D", "#F78C6C", "#89DDFF", "#FFCB6B"]
            bx = W * 0.1 + (r2 * 0.55) * W * 0.8
            by = 120.0 * u + i * 46.0 * u - (lt_s * 60.0 * u) % (24 * 46.0 * u)
            bw2 = (30.0 + r1 * 150.0) * u
            cv.rect(bx, by, bw2, 20.0 * u, fill=cols[i % 6], alpha=0.9 * shown)
        # 打字气泡
        bx, by2 = W * 0.16, H * 0.62
        cv.rect(bx, by2, W * 0.3, 90.0 * u, fill="#2F3342")
        msg = cur.get("say", "")
        nsh = int(mo.clamp(lt_s / 0.5) * 13)
        cv.text(msg[:nsh] + ("|" if int(lt * 4) % 2 else ""), bx + 20.0 * u,
                  by2 + 45.0 * u, size=36.0 * u, color="#FFFFFF", align="left")
    else:
        kx, ky = W * 0.3, H * 1.02
        _bean(k, kx, ky, 215.0 * u, pl, pr, mouth,
              brow=((0.0, 0.0) if mouth else (-0.05, 0.03)), t=lt)
    # 气泡（屏幕层）
    if cur.get("say") and kind != "insert":
        bw0 = W * 0.42
        bx = W * 0.5
        by = H * 0.09
        lines_ = [cur["say"][i:i + 12] for i in range(0, len(cur["say"]), 12)]
        bh = len(lines_) * 44.0 * u * 1.3 + 56.0 * u
        cv.rect(bx - bw0 / 2, by, bw0, bh, fill="#FFFFFF", outline="#1B1B1F",
                width=4.0 * u)
        cv.polygon([(bx + 70.0 * u, by + bh), (bx + 110.0 * u, by + bh),
                    (bx + 90.0 * u, by + bh + 60.0 * u)], fill="#FFFFFF",
                   outline="#1B1B1F")
        for i, ln in enumerate(lines_):
            nsh = int(mo.clamp((lt_s - 0.2 - i * 0.3) / 0.4) * len(ln))
            if nsh > 0:
                cv.text(ln[:nsh], bx, by + 40.0 * u + (i + 0.8) * 44.0 * u, size=44.0 * u,
                        color="#1B1B1F")
    # 「？」
    if cur.get("mark") and lt_s > cur.get("mark_at", 0.6):
        mp = mo.back_out(mo.clamp((lt_s - cur.get("mark_at", 0.6)) / 0.26), 3.0)
        cv.text(cur["mark"], W * 0.3 + 215.0 * u * 1.35, H * 1.02 - 215.0 * u * 3.0,
                size=int(130.0 * u * mp), color="#FFFFFF", alpha=mo.clamp(mp))


# ============================================================
# y5 · 动态文字（kinetic type）
# ============================================================


def y5_type(cv, lt, spec):
    """y5 动态文字：主词砸入+辅句槽升起+荧光笔+ghost 数字。spec（单页）:
    {"bg","ink","main","sub"?: [行...], "tag"?, "ghost"?, "at", "accent"?}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    at_ = spec.get("at", 0.0)
    l = lt - at_
    if l < 0:
        cv.rect(0, 0, W, H, fill=spec.get("bg", "#111111"))
        return
    # 镜头微漂 + 拍点微冲
    bump = 1.0 + 0.015 * math.exp(-max(0.0, l) * 22.0)
    dx = 5.0 * u * math.sin(lt * 0.9) + 2.0 * u * math.sin(lt * 2.3)
    dyy = 3.5 * u * math.sin(lt * 1.1)
    k = Cam(cv, W / 2.0 + dx, H / 2.0 + dyy, bump)
    cv.rect(0, 0, W, H, fill=spec.get("bg", "#111111"))
    # 背景点阵（斜向平移）
    ink = spec.get("ink", "#FFFFFF")
    for gy in range(0, int(H / (64.0 * u)) + 2):
        for gx in range(0, int(W / (64.0 * u)) + 2):
            px = gx * 64.0 * u + (lt * 36.0 * u) % (64.0 * u)
            py = gy * 64.0 * u + (lt * 18.0 * u) % (64.0 * u)
            k.circle(px, py, 4.0 * u, fill=ink, alpha=0.07)
    # ghost 巨型数字
    ghost = spec.get("ghost")
    if ghost:
        gq = mo.spring_hz(l, 2.0, 8.0)
        gs = lerp2(1.35, 1.0, gq)
        k.text(ghost, W - 60.0 * u + l * 14.0 * u, H - 100.0 * u - l * 10.0 * u,
               size=int(900.0 * u * gs), color=ink, alpha=0.12 * mo.clamp(l / 0.08))
    # 主词砸入（缩放轴在字上方）
    main = spec.get("main", "")
    if main:
        q = mo.spring_hz(l, 2.2, 10.0)
        sc = lerp2(1.7, 1.0, q)
        a = mo.clamp(l / 0.06)
        oy = H * 0.42 - 300.0 * u * 0.36
        size = int(300.0 * u * sc)
        k.text(main, W / 2.0, oy + (H * 0.42 - oy) * sc / max(0.01, sc), size=size,
               color=ink, bold=True, alpha=a)
        # 荧光笔（重音拍后）
        hl_at = spec.get("hl_at", 2.0)
        hp = mo.expo_out(mo.clamp((l - hl_at) / 0.3))
        if hp > 0:
            acc = spec.get("accent", "#FFD23F")
            ww = (len(main) * 300.0 * u * 0.62) * hp
            base = tuple(int(ink[i:i + 2], 16) for i in (1, 3, 5)) if ink.startswith("#") else (255, 255, 255)
            hl_col = tuple(int(acc[i:i + 2], 16) for i in (1, 3, 5)) if acc.startswith("#") else (255, 210, 63)
            if base == hl_col:
                k.polygon([(W / 2.0 - ww / 2 + 12.0 * u, H * 0.42 - 300.0 * u * 0.86),
                           (W / 2.0 + ww / 2 + 24.0 * u, H * 0.42 - 300.0 * u * 0.86),
                           (W / 2.0 + ww / 2, H * 0.42 + 300.0 * u * 0.14),
                           (W / 2.0 - ww / 2, H * 0.42 + 300.0 * u * 0.14)],
                          fill=spec.get("bg", "#111111"), alpha=0.9, smooth=False)
            else:
                k.polygon([(W / 2.0 - ww / 2 + 12.0 * u, H * 0.42 - 300.0 * u * 0.86),
                           (W / 2.0 + ww / 2 + 24.0 * u, H * 0.42 - 300.0 * u * 0.86),
                           (W / 2.0 + ww / 2, H * 0.42 + 300.0 * u * 0.14),
                           (W / 2.0 - ww / 2, H * 0.42 + 300.0 * u * 0.14)],
                          fill=hl_col, alpha=0.9, smooth=False)
    # 辅句槽升起
    subs = spec.get("sub", [])
    for i, ln in enumerate(subs):
        e = mo.expo_out(mo.clamp((l - 0.35 - i * 0.08) / 0.35))
        if e <= 0:
            continue
        k.text(ln, W / 2.0, H * 0.62 + i * 96.0 * u, size=96.0 * u, color=ink,
               alpha=mo.clamp(e))
    # 标签
    tag = spec.get("tag")
    if tag:
        tp = mo.expo_out(mo.clamp(l / 0.3))
        k.text(tag, 130.0 * u, 110.0 * u, size=40.0 * u, color=ink,
               alpha=0.8 * tp, align="left")


# ============================================================
# t1 · 3Blue1Brown（数学可视化）
# ============================================================

_T1_MANIM = {
    "blue": _saturate((0x58, 0xC4, 0xDD)), "red": _saturate((0xFC, 0x62, 0x55)),
    "yellow": _saturate((0xFF, 0xFF, 0x00)), "teal": _saturate((0x5C, 0xD0, 0xB3)),
    "green": _saturate((0x83, 0xC1, 0x67)), "grey": _saturate((0x88, 0x88, 0x88)),
    "gold": _saturate((0xF0, 0xAC, 0x5F)), "purple": _saturate((0x9A, 0x72, 0xAC)),
}


def _t1_rect_pts(cx, cy, w, h, n=64):
    """周长均分，左上角起顺时针。"""
    per = 2.0 * (w + h)
    pts = []
    for i in range(n):
        d = i / float(n) * per
        if d < w:
            pts.append((cx - w / 2 + d, cy - h / 2))
        elif d < w + h:
            pts.append((cx + w / 2, cy - h / 2 + (d - w)))
        elif d < 2 * w + h:
            pts.append((cx + w / 2 - (d - w - h), cy + h / 2))
        else:
            pts.append((cx - w / 2, cy + h / 2 - (d - 2 * w - h)))
    return pts


def _t1_circle_pts(cx, cy, r, n=64):
    return [(cx + r * math.cos(-3 * math.pi / 4 + i / float(n) * 2 * math.pi),
             cy + r * math.sin(-3 * math.pi / 4 + i / float(n) * 2 * math.pi))
            for i in range(n)]


def _t1_morph(A, B, p):
    return [(a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)
            for a, b in zip(A, B)]


def t1_math(cv, lt, spec):
    """t1 3b1b：纯黑底 + Write/Transform/神经元/Indicate。spec:
    {"title"?, "concepts": [{"kind":"write"|"morph"|"neurons"|"grid"|"indicate", ...}]}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    U = H / 8.0
    cv.rect(0, 0, W, H, fill="#000000")
    title = spec.get("title", "")
    if title:
        tp = mo.clamp((lt - 0.2) / 0.8)
        cv.text(title, W / 2.0, 140.0 * u, size=66.0 * u, color="#FFFFFF", alpha=tp)
    cy0 = H * 0.55
    for ci, cpt in enumerate(spec.get("concepts", [])):
        at_ = cpt.get("at", 0.0)
        dur = cpt.get("dur", 1.5)
        kind = cpt.get("kind", "write")
        if kind == "grid":
            gq = mo.smooth(mo.clamp((lt - at_) / 0.8))
            if gq <= 0:
                continue
            for gi in range(9):
                p = mo.lagged(gi, 9, gq, 0.1)
                y = cy0 - U * 2 + gi * (U * 4 / 8.0)
                cv.lines([(W * 0.3, y), (W * 0.3 + W * 0.4 * p, y)], color="#FFFFFF",
                         width=2.0, alpha=0.25)
            for gi in range(9):
                p = mo.lagged(gi, 9, gq, 0.1)
                x = W * 0.3 + gi * (W * 0.4 / 8.0)
                cv.lines([(x, cy0 - U * 2), (x, cy0 - U * 2 + U * 4 * p)], color="#FFFFFF",
                         width=2.0, alpha=0.25)
        elif kind == "write":
            wq = mo.clamp((lt - at_) / dur)
            if wq <= 0:
                continue
            txt = cpt.get("text", "")
            n = len(txt)
            shown = int(mo.lagged(0, 1, wq, 0.0) * n + 0.999)
            cv.text(txt[:shown], W / 2.0, cy0 - U * 2.6, size=66.0 * u,
                    color=cpt.get("col", "#FFFFFF"), alpha=mo.clamp(wq * 2.2))
        elif kind == "morph":
            mq = mo.smooth(mo.clamp((lt - at_) / dur))
            if mq <= 0:
                continue
            cx2 = W / 2.0
            a_shape, b_shape = cpt.get("a", "rect"), cpt.get("b", "circle")
            A = _t1_rect_pts(cx2, cy0, U * 2.4, U * 2.4) if a_shape == "rect" \
                else _t1_circle_pts(cx2, cy0, U * 1.4)
            B = _t1_rect_pts(cx2, cy0, U * 2.4, U * 2.4) if b_shape == "rect" \
                else _t1_circle_pts(cx2, cy0, U * 1.4)
            pts = _t1_morph(A, B, mq)
            col = _t1_manim_mix(cpt.get("ca", "blue"), cpt.get("cb", "teal"), mq)
            cv.polygon(pts + [pts[0]], fill=col, alpha=0.18 * mq)
            cv.polygon(pts + [pts[0]], outline=col, width=4.0)
            lbl_a = cpt.get("la", "")
            lbl_b = cpt.get("lb", "")
            if lbl_a or lbl_b:
                cv.text(lbl_b if mq > 0.5 else lbl_a, cx2, cy0 + U * 2.2, size=50.0 * u,
                        color=col, alpha=mo.clamp(mq * 2 if mq > 0.5 else (1 - mq * 2)))
        elif kind == "neurons":
            nq = mo.clamp((lt - at_) / dur)
            if nq <= 0:
                continue
            layers = cpt.get("layers", [3, 4, 2])
            xs = [W * 0.32 + i * W * 0.18 for i in range(len(layers))]
            pos = []
            for li, cnt in enumerate(layers):
                col_y = [cy0 - (cnt - 1) * U * 0.55 + j * U * 1.1 for j in range(cnt)]
                pos.append([(xs[li], y) for y in col_y])
            # 连线（圆周到圆周：两端沿连线方向回退神经元半径）
            for li in range(len(layers) - 1):
                ei = mo.lagged(li, len(layers) - 1, nq, 0.2)
                for ai, A in enumerate(pos[li]):
                    for bi, B in enumerate(pos[li + 1]):
                        wgt = cpt.get("weights", lambda a, b, l2: math.sin(a * 3.1 + b * 1.7 + l2))(
                            ai, bi, li)
                        lw2 = 0.6 + 3.2 * abs(wgt) ** 3
                        col = _T1_MANIM["blue"] if wgt > 0 else _T1_MANIM["red"]
                        if ei > 0.05:
                            dx2, dy2 = B[0] - A[0], B[1] - A[1]
                            dl = math.hypot(dx2, dy2) or 1.0
                            r_n = U * 0.15
                            a2 = (A[0] + dx2 / dl * r_n, A[1] + dy2 / dl * r_n)
                            b2 = (B[0] - dx2 / dl * r_n, B[1] - dy2 / dl * r_n)
                            cv.lines([a2, b2], color=col, width=lw2, alpha=0.7 * mo.clamp(ei))
            # 神经元（填充不透明度=激活值）
            for li, layer in enumerate(pos):
                ni = mo.lagged(li, len(layers), nq, 0.12)
                for ai, A in enumerate(layer):
                    act = cpt.get("acts", lambda l2, a: 0.35 + 0.55 * math.sin(l2 * 2.1 + a * 1.3) * 0.5 + 0.3)(
                        li, ai)
                    cv.circle(A[0], A[1], U * 0.15,
                              fill=(255, 255, 255), alpha=mo.clamp(abs(act)) * mo.clamp(ni),
                              outline="#FFFFFF", width=2.0)
        elif kind == "indicate":
            iq = mo.clamp((lt - at_) / 0.8)
            if iq <= 0 or iq >= 1:
                continue
            tgt = cpt.get("target", (W / 2.0, cy0))
            s = 1.0 + 0.2 * mo.there_and_back(iq)
            cv.ellipse(tgt[0], tgt[1], U * 0.3 * s, U * 0.3 * s, outline=_T1_MANIM["yellow"],
                       width=4.0)


def _t1_manim_mix(ka, kb, p):
    ca = _T1_MANIM.get(ka, (255, 255, 255))
    cb = _T1_MANIM.get(kb, (255, 255, 255))
    return (int(ca[0] + (cb[0] - ca[0]) * p), int(ca[1] + (cb[1] - ca[1]) * p),
            int(ca[2] + (cb[2] - ca[2]) * p))


# ============================================================
# t2 · 发布会界面（keynote UI）
# ============================================================

_T2_BLOBS = [(150, 90, 238), (56, 104, 255), (120, 214, 255), (255, 96, 84)]


def _t2_blob_plate(cv):
    """4 团径向渐变光斑底（缓存成图）。"""
    cache = _img_cache()
    key = ("t2blob", int(cv.width * cv.ss), int(cv.height * cv.ss))
    if key in cache:
        return cache[key]
    W, H = int(cv.width * cv.ss), int(cv.height * cv.ss)
    img = Image.new("RGBA", (W, H), (5, 5, 8, 255))
    import numpy as np2
    yy, xx = np2.mgrid[0:H, 0:W].astype(np.float32)
    for bi, (r, g, b) in enumerate(_T2_BLOBS):
        bx = (0.25 + 0.5 * (bi % 2)) * W
        by = (0.3 + 0.4 * ((bi // 2) % 2)) * H
        d2 = ((xx - bx) ** 2 + (yy - by) ** 2) / (0.42 * W) ** 2
        a = np.clip(1.0 - d2, 0.0, 1.0) ** 2 * 0.5
        layer = np.zeros((H, W, 4), np.float32)
        layer[..., 0], layer[..., 1], layer[..., 2] = r, g, b
        layer[..., 3] = a * 255.0
        base = np.asarray(img, np.float32)
        al = layer[..., 3:4] / 255.0
        base[..., :3] = base[..., :3] * (1 - al) + layer[..., :3] * al
        img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
    cache[key] = img
    return img


def t2_keynote(cv, lt, spec):
    """t2 发布会：一屏一件事，光斑底+大数字/截图卡。spec:
    {"eyebrow"?, "title", "subtitle"?, "block": {"kind":"title"|"number"|"shot",
     "at", "value"?, "unit"?, "label"?, "shot_text"?}, "cam"?: "smooth"|"snap"}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    plate = _t2_blob_plate(cv)
    if cv.img.mode == "RGBA":
        cv.img.alpha_composite(plate)
    else:
        cv.img.paste(plate, (0, 0))
    blk = spec.get("block", {"kind": "title", "at": 0.0})
    at_ = blk.get("at", 0.0)
    l = lt - at_
    # 光斑漂移（整盘轻移）
    dxx = 40.0 * u * math.sin(lt * 0.55)
    dyy = 30.0 * u * math.cos(lt * 0.42)
    kind = blk.get("kind", "title")
    if kind == "title":
        eb = spec.get("eyebrow", "")
        if eb:
            p = mo.clamp(l / 0.7)
            cv.text(eb, W / 2.0, H * 0.3 - 16.0 * u * p, size=40.0 * u,
                    color="#a7a7b4", alpha=p)
        title = spec.get("title", "")
        tl = title.split("\n") if title else []
        for i, ln in enumerate(tl):
            p = mo.clamp((l - 0.15 - i * 0.12) / 1.0)
            if p <= 0:
                continue
            cv.text(ln, W / 2.0, H * 0.42 + i * 130.0 * u - 40.0 * u * p, size=110.0 * u,
                    color="#f5f3ff", bold=True, alpha=p)
        sub = spec.get("subtitle", "")
        if sub:
            p = mo.clamp((l - 0.5) / 0.9)
            if p > 0:
                cv.text(sub, W / 2.0, H * 0.62 - 22.0 * u * p, size=52.0 * u,
                        color="#c9c9d4", alpha=p)
    elif kind == "number":
        val = blk.get("value", 0.0)
        unit = blk.get("unit", "")
        k = mo.expo_out(mo.clamp((l - 0.35) / 0.9))
        shown = val * k
        dec = 1 if val < 100 else 0
        s = mo.slam_k(mo.clamp(l / 0.17), 1.35, 0.96) if l < 0.17 * 1.0 + 0.01 else 1.0
        cv.text(_fmt_num(shown, dec) + (" " + unit if unit else ""), W / 2.0,
                H * 0.5 / s, size=int(240.0 * u * s), color="#f5f3ff", bold=True,
                max_width=W * 0.86)
        lab = blk.get("label", "")
        if lab:
            lp = mo.clamp((l - 1.1) / 0.5)
            if lp > 0:
                cv.text(lab, W / 2.0, H * 0.68, size=48.0 * u, color="#c9c9d4", alpha=lp)
    elif kind == "shot":
        # 截图卡（满幅）+ highlight 框 + 撕边标签
        sx, sw, sh = W * 0.1, W * 0.8, H * 0.72
        sy = H * 0.16
        if blk.get("img"):
            paste_img(cv, blk["img"], sx, sy, sw, sh)
        else:
            cv.rect(sx, sy, sw, sh, fill=blk.get("tint", "#1B2030"))
            st = blk.get("shot_text", "")
            if st:
                cv.text(st, sx + sw / 2, sy + sh / 2, size=72.0 * u, color="#E8E8F0")
        cv.rect(sx, sy, sw, sh, outline=(255, 255, 255), width=1.5 * u, alpha=0.22,
                smooth=False)
        hp = mo.spring_hz(mo.clamp((l - 0.5) / 1.0) * 1.0, 2.5, 6.0)
        hq = mo.clamp((l - 0.5) / 0.45)
        if hq > 0:
            hx, hy2, hw, hh = sx + sw * 0.18, sy + sh * 0.3, sw * 0.4, sh * 0.32
            e = 8.0 * u * (1.0 - hq)
            cv.rect(hx - e, hy2 - e, hw + 2 * e, hh + 2 * e, outline="#3d6bff",
                    width=5.0 * u, alpha=0.95 * hq)
            lab = blk.get("label", "")
            if lab:
                nsh = int(mo.step(l - 0.7, 12) * 12 * 1.1 * len(lab))
                if nsh > 0:
                    cv.rect(hx, hy2 + hh + 14.0 * u, max(140.0 * u, len(lab) * 26.0 * u),
                            52.0 * u, fill="#171716")
                    cv.text(lab[:nsh], hx + 14.0 * u, hy2 + hh + 40.0 * u, size=30.0 * u,
                            color="#eeedeb", align="left")


# ============================================================
# t3 · 财经图表（finance chart）
# ============================================================


def t3_chart(cv, lt, spec):
    """t3 财经图表：先坐标系、数据长出来、只标一件事。spec:
    {"title", "subtitle"?, "source"?, "paper"?: "white"|"ft",
     "chart": {"kind":"bar"|"line", "data": [...], "labels": [...], "unit"?,
               "event"?: {"i": idx, "text": str}, "number"?: {"value","at"}}}"""
    W, H = cv.width, cv.height
    u = W / 1920.0
    paper = spec.get("paper", "white")
    bg = "#FFF1E5" if paper == "ft" else "#FFFFFF"
    ink = "#0C0C0C"
    sub = "#4F5B61"
    red = "#E3120B"
    bar_col = "#006BA2"
    dim = "#C6D2D8"
    cv.rect(0, 0, W, H, fill=bg)
    m = 90.0 * u
    top = H * 0.16
    # 版式（0.5s）
    p0 = mo.clamp(lt / 0.5)
    cv.rect(0, 0, W, 8.0 * u, fill=red, alpha=p0)
    cv.rect(m, H * 0.06, 96.0 * u, 22.0 * u, fill=red, alpha=p0)
    if p0 > 0:
        cv.text(spec.get("title", ""), m, top - 60.0 * u, size=46.0 * u, color=ink,
                bold=True, align="left", alpha=p0)
        if spec.get("subtitle"):
            cv.text(spec.get("subtitle"), m, top - 16.0 * u, size=30.0 * u, color=sub,
                    align="left", alpha=p0)
    ch = spec.get("chart", {})
    data = ch.get("data", [])
    labels = ch.get("labels", [])
    n = len(data)
    if n == 0:
        return
    F = (m + 20.0 * u, top + 40.0 * u, W - 2 * m - 40.0 * u, H - top - 40.0 * u - 190.0 * u)
    fx, fy, fw, fh = F
    hi = max(max(data), 0.0)
    lo = min(min(data), 0.0)
    kind = ch.get("kind", "bar")
    zero_based = kind == "bar" or lo <= 0 or (hi - lo) / max(1e-9, hi) > 0.6
    lo2 = 0.0 if zero_based else lo
    vals, tdec = _ticks(lo2 - (hi - lo2) * 0.08, hi + (hi - lo2) * 0.08)
    vmin, vmax = min(vals), max(vals)

    def yv(v):
        return fy + fh - (v - vmin) / max(1e-9, vmax - vmin) * fh

    gq = mo.clamp((lt - 0.5) / 0.8)
    # 网格（逐条 lag 0.12 quintOut）
    for gi, v in enumerate(vals):
        p = mo.quint_out(mo.lagged(gi, len(vals), gq, 0.12))
        if p <= 0:
            continue
        y = fy + fh - (v - vmin) / max(1e-9, vmax - vmin) * fh * p
        cv.lines([(fx, y), (fx + fw * mo.clamp(gq * 1.4), y)], color=(12, 12, 12),
                 width=1.5, alpha=0.13)
        if v > vmin:
            cv.text(_fmt_num(v, tdec), fx + fw + 10.0 * u, y - 10.0 * u, size=24.0 * u,
                    color="#5b666b", align="left", alpha=p)
    # 零基线
    if zero_based and gq > 0.2:
        cv.lines([(fx, yv(0)), (fx + fw, yv(0))], color=ink, width=3.0)
    dq = mo.clamp((lt - 1.3) / ch.get("dur", 1.6))
    if kind == "bar":
        for i, v in enumerate(data):
            p = mo.quint_out(mo.lagged(i, n, dq, min(0.22, 2.0 / n)))
            if p <= 0:
                continue
            slot = fw / n
            bw2 = min(150.0 * u, slot * 0.62)
            bx = fx + slot * (i + 0.5) - bw2 / 2
            hero = (ch.get("event", {}).get("i") == i) or i == n - 1 and not ch.get("event")
            col = red if hero else (bar_col if i == n - 1 else dim)
            y0b, y1b = yv(0), yv(v * p)
            cv.rect(bx, min(y0b, y1b), bw2, abs(y1b - y0b), fill=col)
            if labels and i < len(labels):
                cv.text(labels[i], bx + bw2 / 2, fy + fh + 40.0 * u, size=26.0 * u,
                        color="#3a4246", alpha=mo.clamp(p * 2))
    else:
        # 折线按 x smooth 推进
        xs = [fx + fw * i / max(1, n - 1) for i in range(n)]
        pts = [(xs[i], yv(data[i])) for i in range(n)]
        cur_x = fx + fw * dq
        vis = [p for p in pts if p[0] <= cur_x]
        if pts and cur_x > fx and cur_x < xs[-1]:
            for i in range(len(pts) - 1):
                if pts[i][0] <= cur_x < pts[i + 1][0]:
                    uu = (cur_x - pts[i][0]) / max(1e-6, pts[i + 1][0] - pts[i][0])
                    vis.append((cur_x, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * uu))
                    break
        if len(vis) > 1:
            cv.lines(vis, color=red, width=5.0)
            tip = vis[-1]
            cv.circle(tip[0], tip[1], 9.0 * u, fill=red)
            # 价格标签
            val_tip = vmin + (fy + fh - tip[1]) / fh * (vmax - vmin)
            cv.text(_fmt_num(val_tip, tdec), tip[0] - 14.0 * u, tip[1] - 34.0 * u,
                    size=28.0 * u, color=red, bold=True, align="right")
        # 面积渐变
        if dq >= 1.0:
            area = vis + [(vis[-1][0], fy + fh), (vis[0][0], fy + fh)]
            cv.polygon(area, fill=red, alpha=0.10)
    # 标注只标一件事（线头经过事件点才触发）
    ev = ch.get("event")
    if ev and kind == "line":
        xi = ev["i"]
        frac = xi / max(1, n - 1)
        t_hit = 1.3 + ch.get("dur", 1.6) * mo.invert(mo.smooth, frac)
        hq = mo.spring_hz(lt - t_hit, 2.5, 6.0)
        if lt > t_hit:
            pt = (xs[xi], yv(data[xi]))
            cv.circle(pt[0], pt[1], 9.0 * u, fill=red)
            lp = mo.quint_out(mo.clamp((lt - t_hit - 0.12) / 0.33))
            if lp > 0:
                ty2 = pt[1] - 60.0 * u - (1 - lp) * 12.0 * u
                cv.lines([(pt[0], pt[1] - 12.0 * u), (pt[0], ty2 + 20.0 * u)],
                         color=ink, width=2.0, alpha=lp)
                tp = mo.clamp((lt - t_hit - 0.3) / 0.4)
                if tp > 0:
                    cv.text(ev.get("text", ""), pt[0], ty2, size=30.0 * u, color=ink,
                            alpha=tp)
    elif ev and kind == "bar":
        xi = ev["i"]
        t_hit = 1.3 + ch.get("dur", 1.6) * mo.invert(mo.smooth, (xi + 0.5) / n)
        if lt > t_hit:
            slot = fw / n
            pt = (fx + slot * (xi + 0.5), yv(data[xi]) - 30.0 * u)
            cv.lines([(pt[0], yv(data[xi]) - 8.0 * u), (pt[0], pt[1] + 16.0 * u)],
                     color=ink, width=2.0)
            cv.text(ev.get("text", ""), pt[0], pt[1] - 24.0 * u, size=30.0 * u, color=ink)
    # 大数字（提前 0.9s 滚动，at=落定）
    nm = ch.get("number")
    if nm:
        k2 = mo.expo_out(mo.clamp((lt - (nm["at"] - 0.9)) / 0.9))
        if k2 > 0:
            cv.text(_fmt_num(nm["value"] * k2, 1) + " " + nm.get("unit", ""), fx + fw,
                    fy - 62.0 * u, size=120.0 * u, color=red, bold=True, align="right")
    # 来源
    if spec.get("source"):
        cv.text(spec.get("source"), m, H - 60.0 * u, size=22.0 * u, color="#7c868b",
                align="left", alpha=p0)
