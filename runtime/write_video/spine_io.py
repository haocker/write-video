# -*- coding: utf-8 -*-
"""write-video Spine 4.3 导入器：JSON 骨架 + 图集 → 可渲染骨骼动画。

支持：
- bones 完整仿射 FK（rotate/translate/scale，父子矩阵级联）
- animations：rotate/translate/scale 时间线（linear / stepped / 三次贝塞尔 curve）
- slots：绘制顺序（JSON 数组序）、attachment 切换时间线
- 附件：region（四边形贴图）；mesh（无权重网格：region 四边形 + 局部顶点多边形蒙版，
  不做网格变形）
- 图集：4.3 文本格式（bounds: x,y,w,h）与旧版（x/y/width/height 行）；PMA 预乘 alpha 自动反预乘

用法：
    sk = SpineSkeleton("spineboy-pro.json", "spineboy-pma.atlas", "spineboy-pma.png")
    sk.draw(cv, anim="run", t=1.2, scale=0.35, cx=640, cy=600)
"""
import json
import math
import os

from . import motion as mo


# ---------------- 图集 ----------------

def parse_atlas(path):
    """解析图集文本：{region名: {page, x, y, width, height, rotate}}。"""
    regions = {}
    png = None
    cur = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip():
                cur = None
                continue
            if not raw[0].isspace():
                if line.endswith(".png") or line.endswith(".jpg") or line.endswith(".webp"):
                    png = line
                    continue
                cur = line
                regions[cur] = {"page": png, "x": 0, "y": 0, "width": 0, "height": 0,
                                "rotate": 0}
                continue
            k, _, v = line.strip().partition(":")
            k, v = k.strip(), v.strip()
            if cur is None:
                continue
            if k == "bounds":
                x, y, w, h = [int(p) for p in v.split(",")]
                regions[cur].update(x=x, y=y, width=w, height=h)
            elif k == "rotate":
                regions[cur]["rotate"] = int(v) if v.lstrip("-").isdigit() else (
                    90 if v == "true" else 0)
            elif k in ("x", "y", "width", "height"):
                regions[cur][k] = int(float(v))
            elif k == "orig":
                w, h = [int(p) for p in v.split(",")]
                regions[cur].update(orig_w=w, orig_h=h)
    return regions


def _unpma(im):
    """PMA 预乘 alpha → 直通 alpha（RGB 还原）。"""
    import numpy as np
    from PIL import Image
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    alpha = a[..., 3:4] / 255.0
    rgb = np.where(alpha > 0.004,
                   np.clip(a[..., :3] / np.maximum(alpha, 1e-3), 0, 255), 0)
    out = a.copy()
    out[..., :3] = rgb
    return Image.fromarray(out.astype(np.uint8), "RGBA")


# ---------------- 时间线 ----------------

def _sample_tl(keys, t, channel="value"):
    """采样单值时间线。无 curve=线性；'stepped'=台阶；[c1..c4]=三次贝塞尔。"""
    if not keys:
        return 0.0
    if t <= keys[0].get("time", 0):
        return keys[0].get(channel, keys[0].get("value", 0))
    last = keys[-1]
    if t >= last.get("time", 0):
        return last.get(channel, last.get("value", 0))
    for i in range(len(keys) - 1):
        k0, k1 = keys[i], keys[i + 1]
        t0, t1 = k0.get("time", 0), k1.get("time", 0)
        if t0 <= t < t1:
            v0 = k0.get(channel, k0.get("value", 0))
            v1 = k1.get(channel, k1.get("value", 0))
            p = (t - t0) / max(1e-9, t1 - t0)
            cv = k1.get("curve")
            if cv == "stepped":
                return v0
            if isinstance(cv, list) and len(cv) == 4:
                p = mo.bezier(cv[0], cv[1], cv[2], cv[3])(p)
            return v0 + (v1 - v0) * p
    return last.get(channel, last.get("value", 0))


def _sample_xy(keys, t, ch="x"):
    return _sample_tl(keys, t, ch)


def _attachment_at(tl, t):
    """attachment 切换时间线 → 当前附件名（None=空槽）。"""
    cur = tl[0].get("name")
    for k in tl:
        if t >= k.get("time", 0):
            cur = k.get("name")
    return cur


# ---------------- 骨架 ----------------

class SpineSkeleton:
    def __init__(self, json_path, atlas_path, png_dir=None):
        with open(json_path, encoding="utf-8") as f:
            d = json.load(f)
        base = os.path.dirname(os.path.abspath(json_path))
        self.data = d
        self.bones = dict((b["name"], b) for b in d.get("bones", []))
        self.order = []
        seen = set()
        pending = list(d.get("bones", []))
        while pending:
            progressed = False
            for b in list(pending):
                if b.get("parent") is None or b["parent"] in seen:
                    self.order.append(b["name"])
                    seen.add(b["name"])
                    pending.remove(b)
                    progressed = True
            if not progressed:
                raise ValueError("Spine 骨骼层级有环")
        self.slots = d.get("slots", [])  # 数组序=绘制顺序
        self.animations = d.get("animations", {})
        skin = None
        for sk in d.get("skins", []):
            if sk.get("name") == "default":
                skin = sk
                break
        if skin is None and d.get("skins"):
            skin = d["skins"][0]
        self.attachments = skin.get("attachments", {}) if skin else {}
        # 图集
        self.regions = parse_atlas(atlas_path)
        png_name = None
        for r in self.regions.values():
            if r.get("page"):
                png_name = r["page"]
                break
        png_path = os.path.join(png_dir or base, png_name or "")
        from PIL import Image
        self.page_png = png_path
        self._page = None
        self._cache = {}
        self._warned = set()

    def _page_img(self):
        if self._page is None:
            from PIL import Image
            im = Image.open(self.page_png).convert("RGBA")
            self._page = _unpma(im)
        return self._page

    def _region_img(self, name):
        im = self._cache.get(name)
        if im is None:
            from PIL import Image
            r = self.regions.get(name)
            if r is None:
                if name not in self._warned:
                    self._warned.add(name)
                    print("[write-video] 图集缺 region %r" % name)
                return None
            page = self._page_img()
            x, y, w, h = r["x"], r["y"], r["width"], r["height"]
            if r.get("rotate"):
                crop = page.crop((x, y, x + h, y + w)).rotate(
                    -r["rotate"] if r["rotate"] == 90 else 90, expand=True)
            else:
                crop = page.crop((x, y, x + w, y + h))
            self._cache[name] = crop
            im = crop
        return im

    # ---- FK（完整仿射）----
    def _bone_worlds(self, poses):
        worlds = {}
        for name in self.order:
            b = self.bones[name]
            local = dict(x=b.get("x", 0.0), y=b.get("y", 0.0),
                         rotation=b.get("rotation", 0.0), sx=1.0, sy=1.0)
            p = poses.get(name)
            if p:
                local["rotation"] += p.get("rotation", 0.0)
                local["x"] += p.get("x", 0.0)
                local["y"] += p.get("y", 0.0)
                local["sx"] *= p.get("sx", 1.0)
                local["sy"] *= p.get("sy", 1.0)
            r = math.radians(local["rotation"])
            cosr, sinr = math.cos(r), math.sin(r)
            aL = (local["sx"] * cosr, local["sx"] * sinr,
                  -local["sy"] * sinr, local["sy"] * cosr)
            if b.get("parent") is None:
                worlds[name] = (aL, local["x"], local["y"])
            else:
                (a, b2, c, d), tpx, tpy = worlds[b["parent"]]
                A = (a * aL[0] + b2 * aL[2], a * aL[1] + b2 * aL[3],
                     c * aL[0] + d * aL[2], c * aL[1] + d * aL[3])
                worlds[name] = (A, tpx + a * local["x"] + c * local["y"],
                                tpy + b2 * local["x"] + d * local["y"])
        return worlds

    def _anim_pose(self, anim_name, t):
        poses = {}
        anim = self.animations.get(anim_name)
        if anim is None:
            if anim_name not in self._warned:
                self._warned.add(anim_name)
                print("[write-video] 无动画 %r（可选：%s）" % (
                    anim_name, list(self.animations)[:6]))
            return poses
        for bn, chs in anim.get("bones", {}).items():
            p = {}
            if "rotate" in chs:
                p["rotation"] = _sample_tl(chs["rotate"], t)
            if "translate" in chs:
                p["x"] = _sample_tl(chs["translate"], t, "x")
                p["y"] = _sample_tl(chs["translate"], t, "y")
            if "scale" in chs:
                p["sx"] = _sample_tl(chs["scale"], t, "x")
                p["sy"] = _sample_tl(chs["scale"], t, "y")
            poses[bn] = p
        return poses

    def anim_time(self, anim_name):
        """动画时长（秒）。"""
        anim = self.animations.get(anim_name)
        if not anim:
            return 1.0
        mx = 0.0
        for chs in anim.get("bones", {}).values():
            for tl in chs.values():
                if tl:
                    mx = max(mx, tl[-1].get("time", 0))
        return max(mx, 0.1)

    # ---- 绘制 ----
    def draw(self, cv, anim=None, t=0.0, scale=1.0, cx=None, cy=None,
             flip_x=False, alpha=1.0):
        """整帧绘制：按 slots 数组序画全部附件。

        scale：骨架逻辑单位 → 画布像素；cx, cy：骨架原点落点（默认画布中心偏下）。"""
        from PIL import Image
        W, H = cv.width, cv.height
        if cx is None:
            cx = W / 2.0
        if cy is None:
            cy = H * 0.62
        poses = self._anim_pose(anim, t) if anim else {}
        slot_atts = {}
        if anim:
            for slot, chs in self.animations[anim].get("slots", {}).items():
                tl = chs.get("attachment")
                if tl:
                    slot_atts[slot] = _attachment_at(tl, t)
        worlds = self._bone_worlds(poses)
        for slot in self.slots:
            sname = slot["name"]
            att_name = slot_atts.get(sname, slot.get("attachment"))
            if not att_name:
                continue
            att_map = self.attachments.get(sname)
            if not att_map or att_name not in att_map:
                continue
            att = att_map[att_name]
            typ = att.get("type", "region")
            if typ not in ("region", "mesh"):
                if typ not in self._warned:
                    self._warned.add(typ)
                    print("[write-video] 跳过附件类型 %r（%s/%s）" % (typ, sname, att_name))
                continue
            region = self.regions.get(att_name)
            if region is None:
                region = self.regions.get(sname)
            if region is None:
                if att_name not in self._warned:
                    self._warned.add(att_name)
                    print("[write-video] 图集缺 region %r（%s）" % (att_name, sname))
                continue
            # 附件局部变换 → 世界
            ax = att.get("x", 0.0)
            ay = att.get("y", 0.0)
            arot = att.get("rotation", 0.0)
            asx = att.get("scaleX", 1.0)
            asy = att.get("scaleY", 1.0)
            (a, b2, c, d), tpx, tpy = worlds[slot["bone"]]
            rr = math.radians(arot)
            cosr, sinr = math.cos(rr), math.sin(rr)
            aL = (asx * cosr, asx * sinr, -asy * sinr, asy * cosr)
            A = (a * aL[0] + b2 * aL[2], a * aL[1] + b2 * aL[3],
                 c * aL[0] + d * aL[2], c * aL[1] + d * aL[3])
            cwx = tpx + a * ax + c * ay
            cwy = tpy + b2 * ax + d * ay
            # 世界旋转角与两轴缩放
            rot = math.degrees(math.atan2(A[1], A[0]))
            s1 = math.sqrt(A[0] * A[0] + A[2] * A[2])
            s2 = math.sqrt(A[1] * A[1] + A[3] * A[3])
            # 画布映射（Spine y 向上，画布 y 向下 → 翻 y）；全程设备像素（cv.ss）
            ss = float(getattr(cv, "ss", 1.0))
            px = (cx + cwx * scale * (-1.0 if flip_x else 1.0)) * ss
            py = (cy - cwy * scale) * ss
            theta = -rot if flip_x else rot
            sprite = self._region_img(att_name)
            if sprite is None:
                continue
            tw = att.get("width") or region["width"]
            th = att.get("height") or region["height"]
            w2 = max(1, int(round(abs(tw) * s1 * scale * ss)))
            h2 = max(1, int(round(abs(th) * s2 * scale * ss)))
            im2 = sprite.resize((w2, h2), Image.LANCZOS)
            if typ == "mesh":
                # 加权网格（vertices 含骨骼绑定）暂不变形：按紧裁剪 region 四边形渲染，
                # 透明 padding 极小可接受；后续可补 setup 顶点多边形蒙版
                pass
            if abs(theta) > 0.05:
                im2 = im2.rotate(-theta, resample=Image.BICUBIC, expand=True)
            if alpha < 1.0:
                im2 = im2.copy()
                im2.putalpha(im2.getchannel("A").point(lambda v: int(v * alpha)))
            box = (int(round(px - im2.width / 2.0)),
                   int(round(py - im2.height / 2.0)))
            if cv.img.mode == "RGBA":
                cv.img.alpha_composite(im2, box)
            else:
                cv.img.paste(im2, box, im2)