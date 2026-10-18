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
                po = out[b.parent][0]
                pa = out[b.parent][2]
                origin = (po[0] + b.off_w[0], po[1] + b.off_w[1])
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
