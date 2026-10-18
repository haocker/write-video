# -*- coding: utf-8 -*-
"""write-video 骨骼动画层：骨骼层级 + 前向运动学（FK）+ 关键帧轨道。

骨骼：Bone(name, parent, length, rest, off_w=(0,0), z)
      origin = parent_end + off_w（世界固定偏移，适合躯干基本不转的 Q 版）；
      世界角 = parent_world + rest + pose 偏移；end = origin + length·dir(世界角)。
Rig：Rig((x, y), bones).solve(pose, root=None) → {name: (origin, end, world_deg, z)}
      root 可传 (x, y) 覆盖全局锚点（走路位移/起伏直接动根）。
Track：Track({bone: [(t, deg, ease), ...]}, dur=None, loop=False)
      .at(t) → {bone: deg}；dur+loop 时按周期回绕（尾键→首键自动补一段插值）；
      ease 为 mo 缓动名（"sine"/"linear"/"expo_out"/"back_out"/...，默认 "sine"）。
      多轨叠加：pose = {**idle.at(t), **wave.at(t)}（后者按骨覆盖）。

角度约定：画布 y 向下，度为单位；-90 = 向上，90 = 向下，180/-180 = 向左，0 = 向右。
rest 为相对父骨的静止角（根骨的 rest 即世界角）。
"""
import math

from . import motion as mo


class Bone:
    def __init__(self, name, parent, length, rest, off_w=(0.0, 0.0), z=0.0):
        self.name = name
        self.parent = parent
        self.length = float(length)
        self.rest = float(rest)
        self.off_w = (float(off_w[0]), float(off_w[1]))
        self.z = float(z)


class Rig:
    def __init__(self, root, bones):
        self.root = (float(root[0]), float(root[1]))
        self.bones = dict((b.name, b) for b in bones)
        self.order = []
        seen = set()
        pending = list(bones)
        while pending:
            progressed = False
            for b in list(pending):
                if b.parent is None or b.parent in seen:
                    self.order.append(b.name)
                    seen.add(b.name)
                    pending.remove(b)
                    progressed = True
            if not progressed:
                raise ValueError("骨骼层级有环: %r" % [b.name for b in pending])

    def solve(self, pose, root=None):
        """pose: {bone: 角度偏移(度)} → {bone: (origin, end, world_deg, z)}。"""
        pos = self.root if root is None else (float(root[0]), float(root[1]))
        out = {}
        for name in self.order:
            b = self.bones[name]
            off = float(pose.get(name, 0.0))
            if b.parent is None:
                origin = pos
                world = b.rest + off
            else:
                pe = out[b.parent][1]
                pa = out[b.parent][2]
                origin = (pe[0] + b.off_w[0], pe[1] + b.off_w[1])
                world = pa + b.rest + off
            a = math.radians(world)
            end = (origin[0] + b.length * math.cos(a),
                   origin[1] + b.length * math.sin(a))
            out[name] = (origin, end, world, b.z)
        return out


def _ease(name, p):
    if not name or name in ("linear",):
        return mo.linear(p)
    if name == "sine":
        name = "sine_in_out"
    fn = getattr(mo, name, None)
    if fn is None:
        raise ValueError("未知缓动 %r（mo 缓动名）" % (name,))
    return fn(p)


def _sample(ks, t):
    """关键帧采样：ks=[(t, deg[, ease]), ...] 已按 t 排序。"""
    if t <= ks[0][0]:
        return ks[0][1]
    if t >= ks[-1][0]:
        return ks[-1][1]
    for i in range(len(ks) - 1):
        t0, v0 = ks[i][0], ks[i][1]
        t1, v1 = ks[i + 1][0], ks[i + 1][1]
        if t0 <= t < t1:
            p = (t - t0) / max(1e-9, t1 - t0)
            e = ks[i + 1][2] if len(ks[i + 1]) > 2 else "sine"
            return v0 + (v1 - v0) * _ease(e, p)
    return ks[-1][1]


class Track:
    def __init__(self, keys, dur=None, loop=False):
        self.keys = dict((k, sorted(v, key=lambda it: it[0]))
                         for k, v in keys.items())
        self.dur = float(dur) if dur else None
        self.loop = bool(loop)

    def at(self, t):
        pose = {}
        for bone, ks in self.keys.items():
            if self.loop and self.dur:
                t2 = t % self.dur
                v_end = ks[-1][1]
                v_start = ks[0][1]
                if v_end == v_start and ks[-1][0] >= self.dur - 1e-9:
                    pose[bone] = _sample(ks, t2)
                else:
                    ext = list(ks) + [(self.dur, v_start, "sine")]
                    pose[bone] = _sample(ext, t2)
            else:
                pose[bone] = _sample(ks, t)
        return pose


def capsule(cv, p0, p1, r, col, col_sh=None, col_hi=None):
    """2.5D 胶囊肢体：底线 + 背光暗条 + 受光高光条 + 端头圆帽。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    px, py = dy / L, -dx / L
    cv.lines([p0, p1], color=col, width=2 * r)
    cv.circle(p1[0], p1[1], r * 0.52, fill=col)
    if col_sh:
        cv.lines([(p0[0] + px * r * 0.5, p0[1] + py * r * 0.5),
                  (p1[0] + px * r * 0.5, p1[1] + py * r * 0.5)],
                 color=col_sh, width=2 * r * 0.38, alpha=0.55)
    if col_hi:
        cv.lines([(p0[0] - px * r * 0.42, p0[1] - py * r * 0.42),
                  (p1[0] - px * r * 0.42, p1[1] - py * r * 0.42)],
                 color=col_hi, width=2 * r * 0.3, alpha=0.55)


def xform(pts, center, deg, S=1.0):
    """局部点集 → 世界：先缩放再绕 center 旋转再平移。"""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for p in pts:
        x, y = p[0] * S, p[1] * S
        out.append((center[0] + x * ca - y * sa, center[1] + x * sa + y * ca))
    return out


# ============================================================
# SpriteSkin：PNG 部件挂骨 + 随骨旋转（cutout / 纸片人皮肤）
# ============================================================

class SpriteSkin:
    """把透明 PNG 部件装到骨骼上，每帧按骨骼变换贴图。

    part 规范（局部坐标，原点=骨骼 origin，未旋转）：
      {png, pivot=(px, py), offset=(ox, oy), scale=s, z=层序, flip=False}
      部件图中 (px,py) 那个像素对准骨骼 origin；offset 为部件整体沿骨骼局部
      坐标平移（通常让部件"长在"骨骼方向上）；scale 整体缩放；z 小者先画。
    皮肤随骨旋转：部件图先转 (world_deg + rot_off)，再贴到骨骼 origin。
    rot_off 用于"部件基准方向与骨骼 rest 方向不一致"的校正（如竖直图挂水平骨）。
    """

    def __init__(self, parts, ss=1.0):
        self.parts = list(parts)
        self.ss = float(ss)
        self._cache = {}

    def _img(self, png):
        from PIL import Image
        im = self._cache.get(png)
        if im is None:
            im = Image.open(png).convert("RGBA")
            self._cache[png] = im
        return im

    def draw(self, cv, xf):
        """xf = Rig.solve() 输出 {bone: (origin, end, world_deg, z)}。

        全程按画布设备像素（cv.ss）换算：origin/offset 为设计像素，
        部件图 px 经 scale×ss 缩放后对齐。
        """
        from PIL import Image
        ss = float(getattr(cv, "ss", 1.0))
        for part in sorted(self.parts, key=lambda p: p.get("z", 0)):
            bone = part["bone"]
            if bone not in xf:
                continue
            origin, _end, world, _z = xf[bone]
            im = self._img(part["png"])
            scale = float(part.get("scale", 1.0))
            px, py = part.get("pivot", (0, 0))
            ox, oy = part.get("offset", (0.0, 0.0))
            deg = world + float(part.get("rot_off", 0.0))
            if part.get("flip"):
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
                px = im.width - px
                deg = -deg
            a = math.radians(deg)
            ca, sa = math.cos(a), math.sin(a)
            w, h = im.size
            rot = im.rotate(-deg, resample=Image.BICUBIC, expand=True)
            c, s_ = math.cos(-a), math.sin(-a)
            npx = (px - w / 2.0) * c - (py - h / 2.0) * s_ + rot.width / 2.0
            npy = (px - w / 2.0) * s_ + (py - h / 2.0) * c + rot.height / 2.0
            wox = ox * ca - oy * sa
            woy = ox * sa + oy * ca
            sc = scale * ss
            if abs(sc - 1.0) > 1e-6:
                rot = rot.resize((max(1, int(rot.width * sc)),
                                  max(1, int(rot.height * sc))), Image.LANCZOS)
                npx *= sc
                npy *= sc
            dx = (origin[0] + wox) * ss - npx
            dy = (origin[1] + woy) * ss - npy
            box = (int(round(dx)), int(round(dy)))
            if cv.img.mode == "RGBA":
                cv.img.alpha_composite(rot, box)
            else:
                cv.img.paste(rot, box, rot)


def load_rig(path):
    """从 JSON 装配文件读 (Rig, SpriteSkin, {动作名: Track})。

    JSON 结构：
      {
        "root": [x, y],
        "bones": [{"name", "parent", "length", "rest", "off_w"?, "z"?}, ...],
        "skin": {"base_dir"?, "parts": [{"bone", "png", "pivot"?, "offset"?,
                                          "scale"?, "z"?, "rot_off"?, "flip"?}, ...]},
        "tracks": {"idle": {"dur"?, "loop"?, keys: {bone: [[t, deg, ease]?]}}, ...}
      }
    """
    import json
    import os
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    bones = [Bone(b["name"], b.get("parent"), float(b["length"]),
                  float(b.get("rest", 0.0)),
                  tuple(b.get("off_w", (0.0, 0.0))), float(b.get("z", 0.0)))
             for b in data["bones"]]
    rig = Rig(tuple(data.get("root", (0.0, 0.0))), bones)
    skin = None
    if data.get("skin"):
        parts = []
        bdir = data["skin"].get("base_dir", base)
        for p in data["skin"].get("parts", []):
            png = p["png"]
            if not os.path.isabs(png):
                png = os.path.join(bdir, png)
            parts.append(dict(p, png=png))
        skin = SpriteSkin(parts)
    tracks = {}
    for name, tr in (data.get("tracks") or {}).items():
        keys = dict((b, [tuple(k) for k in ks])
                    for b, ks in tr.get("keys", {}).items())
        tracks[name] = Track(keys, dur=tr.get("dur"), loop=tr.get("loop", False))
    return rig, skin, tracks


def save_rig(path, rig, skin=None, tracks=None, base_dir=None):
    """把 Rig/SpriteSkin/Track 写回 JSON 装配文件（与 load_rig 对称）。"""
    import json
    import os
    bones = []
    for name in rig.order:
        b = rig.bones[name]
        bones.append({"name": b.name, "parent": b.parent, "length": b.length,
                      "rest": b.rest, "off_w": list(b.off_w), "z": b.z})
    data = {"root": list(rig.root), "bones": bones}
    if skin is not None:
        parts = []
        for p in skin.parts:
            q = dict(p)
            png = q["png"]
            if base_dir and not os.path.isabs(png):
                q["png"] = os.path.relpath(png, base_dir)
            parts.append(q)
        data["skin"] = {"parts": parts}
    if tracks:
        out = {}
        for name, tr in tracks.items():
            out[name] = {"dur": tr.dur, "loop": tr.loop,
                         "keys": dict((b, [list(k) for k in ks])
                                      for b, ks in tr.keys.items())}
        data["tracks"] = out
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
