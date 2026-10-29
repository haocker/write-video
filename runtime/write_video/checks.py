# -*- coding: utf-8 -*-
"""write-video — 闪烁（单帧闪现）检测。

原理：把画面缩成小块灰度，找“某一帧局部突然比前后两帧都强/弱、下一帧又退回去”的
尖峰；再用平移复核排除“高速运动”造成的伪事件。

事件 = {t, frame, score, x, y, w, h}
"""
import subprocess

import numpy as np
from PIL import Image

THUMB = (320, 180)
BLOCK = 16
THR = 10.0
TW = (THUMB[0] // BLOCK) * BLOCK   # 320
TH = (THUMB[1] // BLOCK) * BLOCK   # 176（裁到块尺寸整数倍）


def _luma(img):
    """PIL RGB → 缩略灰度 ndarray（裁剪到块尺寸整数倍）。"""
    if img.size != THUMB:
        img = img.resize(THUMB, Image.BOX)
    if img.mode != "L":
        img = img.convert("L")
    return np.asarray(img, dtype=np.uint8)[:TH, :TW]


class FlickerAnalyzer(object):
    """逐帧喂图，finish() 给出事件。

    exclusions: [(t0, t1), ...] 有意急变窗口（转场、落地震动），窗口内不报。
    """

    def __init__(self, width, height, fps, exclusions=None):
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)
        self.exclusions = list(exclusions or [])
        self.frames = []

    def push(self, frame):
        self.frames.append(_luma(frame))

    def _excluded(self, t, x=None, y=None, w=0, h=0):
        """排除有意急变：全局时间窗口 (t0,t1) 或带区域的时间窗口 dict。"""
        for ex in self.exclusions:
            if isinstance(ex, dict):
                if (ex["t0"] - 1e-6 <= t <= ex["t1"] + 1e-6) and x is not None:
                    if (x < ex["x"] + ex["w"] and ex["x"] < x + w
                            and y < ex["y"] + ex["h"] and ex["y"] < y + h):
                        return True
            else:
                t0, t1 = ex
                if t0 - 1e-6 <= t <= t1 + 1e-6:
                    return True
        return False

    # ---- 平移复核：帧 i 的局部内容是否能在前后帧里找到一致的平移 ----
    def _motion_explained(self, fi, bx, by):
        if fi < 1 or fi + 1 >= len(self.frames):
            return False
        b = BLOCK
        cx = int(bx * b + b / 2)
        cy = int(by * b + b / 2)
        half = 24
        x0, y0 = cx - half, cy - half
        tw, th = TW, TH
        if x0 < 0 or y0 < 0 or x0 + 2 * half > tw or y0 + 2 * half > th:
            return False
        P = self.frames[fi][y0:y0 + 2 * half, x0:x0 + 2 * half].astype(np.float32)
        best = []
        for src in (fi - 1, fi + 1):
            F = self.frames[src].astype(np.float32)
            bd, bdx, bdy = None, 0, 0
            for dy in range(-20, 21, 2):
                for dx in range(-20, 21, 2):
                    xx, yy = x0 + dx, y0 + dy
                    if xx < 0 or yy < 0 or xx + 2 * half > tw or yy + 2 * half > th:
                        continue
                    Q = F[yy:yy + 2 * half, xx:xx + 2 * half]
                    d = float(np.mean(np.abs(P - Q)))
                    if bd is None or d < bd:
                        bd, bdx, bdy = d, dx, dy
            best.append((bd, bdx, bdy))
        if None in [x[0] for x in best]:
            return False
        ok1 = best[0][0] < 6.5 and best[1][0] < 6.5
        opposite = (best[0][1] + best[1][1]) <= 4 and (best[0][2] + best[1][2]) <= 4
        close = abs(best[0][1] + best[1][1]) <= 5 and abs(best[0][2] + best[1][2]) <= 5
        return ok1 and (opposite or close)

    def finish(self, merge=True):
        n = len(self.frames)
        if n < 3:
            return {"events": [], "maxScore": 0.0, "count": n}
        F = np.stack(self.frames).astype(np.float32)
        by = TH // BLOCK
        bx = TW // BLOCK
        blocks = F.reshape(n, by, BLOCK, bx, BLOCK).mean(axis=(2, 4))
        d1 = np.abs(blocks[1:-1] - blocks[:-2])
        d2 = np.abs(blocks[2:] - blocks[1:-1])
        net = np.abs(blocks[2:] - blocks[:-2])
        cand = (d1 > THR) & (d2 > THR) & (net < 0.55 * np.minimum(d1, d2))
        raw = []
        sx = self.width / float(TW)
        sy = self.height / float(TH)
        idxs = np.argwhere(cand)
        for i, yy, xx in idxs:
            fi = int(i) + 1
            t = fi / self.fps
            x = int(xx * BLOCK * sx - 16)
            y = int(yy * BLOCK * sy - 16)
            w = int(64 * sx)
            h = int(64 * sy)
            if self._excluded(t, x, y, w, h):
                continue
            score = float(min(d1[i, yy, xx], d2[i, yy, xx]) / THR)
            raw.append((fi, int(xx), int(yy), score, x, y, w, h))
        events = []
        for fi, xx, yy, score, x, y, w, h in sorted(raw, key=lambda r: (r[0], -r[3])):
            merged = False
            for ev in events:
                if ev["_fi"] == fi and abs(ev["_bx"] - xx) <= 2 and abs(ev["_by"] - yy) <= 2:
                    merged = True
                    if score > ev["score"]:
                        ev["score"] = score
                    break
            if merged:
                continue
            if self._motion_explained(fi, xx, yy):
                continue
            events.append({
                "_fi": fi, "_bx": xx, "_by": yy,
                "t": fi / self.fps,
                "frame": fi,
                "score": round(score, 2),
                "x": x, "y": y, "w": w, "h": h,
            })
        for ev in events:
            ev.pop("_fi", None)
            ev.pop("_bx", None)
            ev.pop("_by", None)
        mx = max([e["score"] for e in events] or [0.0])
        return {"events": events, "maxScore": round(mx, 2), "count": n}


def scan_video(path, ffmpeg, width=None, height=None, fps=None, exclusions=None, max_frames=None):
    """回读 MP4 做闪烁扫描（独立于影片模型）。"""
    import json
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path, "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = probe.stderr.decode("utf-8", "ignore")
    # 用 ffprobe 更可靠：没有 ffprobe 时退回默认
    fps = fps or 30.0
    width = width or 1920
    height = height or 1080
    try:
        import re
        m = re.search(r"(\d+)x(\d+)", info)
        if m:
            width, height = int(m.group(1)), int(m.group(2))
        m = re.search(r"(\d+(?:\.\d+)?)\s*fps", info)
        if m:
            fps = float(m.group(1))
    except Exception:
        pass
    an = FlickerAnalyzer(width, height, fps, exclusions)
    proc = subprocess.Popen(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", path,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    nbytes = width * height * 3
    count = 0
    try:
        while True:
            buf = proc.stdout.read(nbytes)
            if not buf or len(buf) < nbytes:
                break
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)
            an.push(Image.fromarray(arr, "RGB"))
            count += 1
            if max_frames and count >= max_frames:
                break
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        proc.wait()
    return an.finish()
