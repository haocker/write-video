# -*- coding: utf-8 -*-
"""write-video — 渲染管线：编码器探测、帧管道、混音、联系表、闪烁条带、报告。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw

from . import checks
from . import fonts as _fonts


def find_ffmpeg():
    p = os.environ.get("WV_FFMPEG")
    if p and os.path.exists(p):
        return p
    p = shutil.which("ffmpeg")
    if p:
        return p
    cands = []
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        cands.append(os.path.join(la, "Microsoft", "WinGet", "Links", "ffmpeg.exe"))
        cands.append(r"C:\ffmpeg\bin\ffmpeg.exe")
    else:
        cands += ["/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise RuntimeError("找不到 ffmpeg。安装：Windows `winget install ffmpeg`；macOS `brew install ffmpeg`；Linux `apt install ffmpeg`；"
                       "或用环境变量 WV_FFMPEG 指定完整路径。")


_ENCODERS = (
    ("libx264", ["-c:v", "libx264", "-crf", "19", "-preset", "medium"]),
    ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "20"]),
    ("h264_qsv", ["-c:v", "h264_qsv", "-global_quality", "21"]),
    ("h264_amf", ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22"]),
    ("h264_mf", ["-c:v", "h264_mf", "-b:v", "14M"]),
    ("libopenh264", ["-c:v", "libopenh264", "-rc_mode", "quality", "-q", "22"]),
)


def _apply_quality(enc_args, quality):
    """把 quality（数值越小质量越高）套到编码器的质量参数上。"""
    args = []
    i = 0
    while i < len(enc_args):
        a = enc_args[i]
        if a in ("-crf", "-cq", "-global_quality", "-q") and i + 1 < len(enc_args):
            args += [a, str(int(quality))]
            i += 2
        elif a == "-qp_i" and i + 1 < len(enc_args):
            args += [a, str(int(quality))]
            i += 2
        elif a == "-qp_p" and i + 1 < len(enc_args):
            args += [a, str(int(quality) + 2)]
            i += 2
        else:
            args.append(a)
            i += 1
    return args


def pick_encoder(ffmpeg, verbose=False):
    """探测本机可用的 H.264 编码器（结果按 ffmpeg 路径缓存）。"""
    cache_path = os.path.join(tempfile.gettempdir(), "write_video_encoder.json")
    try:
        key = "%s|%.0f" % (ffmpeg, os.path.getmtime(ffmpeg))
    except Exception:
        key = ffmpeg
    if os.path.exists(cache_path):
        try:
            data = json.load(open(cache_path, "r", encoding="utf-8"))
            if data.get("key") == key:
                for name, args in _ENCODERS:
                    if name == data.get("enc"):
                        return name, list(args)
        except Exception:
            pass
    for name, args in _ENCODERS:
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
               "-i", "testsrc2=size=320x240:rate=30", "-frames:v", "5"] + list(args) + [
              "-pix_fmt", "yuv420p", "-f", "null", "-"]
        ok = False
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            ok = r.returncode == 0
        except Exception:
            ok = False
        if verbose:
            print("[write-video] 编码器 %s: %s" % (name, "可用" if ok else "不可用"))
        if ok:
            try:
                json.dump({"key": key, "enc": name}, open(cache_path, "w", encoding="utf-8"))
            except Exception:
                pass
            return name, list(args)
    raise RuntimeError("找不到可用的 H.264 编码器（试过 libx264/nvenc/qsv/amf/mf/openh264）。")


def film_exclusions(film):
    """闪烁检测的排除清单：全局时间窗口 + 元素区域快速窗口（slam 起跳急缩 / punch 命中急缩）。
    场景边界（含 cut 切镜）是合法的全帧/局部变化，排除切换后 1 帧 + 过渡时长。"""
    from .film import TRANS_DUR
    ex = []
    step = 1.0 / max(film.fps, 1)
    for sc in film.scenes:
        if sc.prev is not None:
            D = max(TRANS_DUR.get(sc.transition, 0.0), step)
            ex.append((sc.start, sc.start + D + 0.05))
    for item in (film._shake + film._shake_user):
        ex.append((item[0], item[0] + item[1] + 0.08))
    ex.extend(getattr(film, "_flicker_ex", []))
    for sc in film.scenes:
        for el in sc.elements:
            if el.parent is not None or el.kind == "burst":
                continue
            b = el.box()
            if not b:
                continue
            cx = b[0] + b[2] / 2.0
            cy = b[1] + b[3] / 2.0
            if el.enter == "slam":
                k = 2.9
                ex.append({"t0": el.at - 0.35, "t1": el.at + 0.36,
                           "x": cx - b[2] * k / 2, "y": cy - b[3] * k / 2,
                           "w": b[2] * k, "h": b[3] * k})
            elif el.enter == "punch":
                k = 1.5
                ex.append({"t0": el.at - 0.02, "t1": el.at + 0.42,
                           "x": cx - b[2] * k / 2, "y": cy - b[3] * k / 2,
                           "w": b[2] * k, "h": b[3] * k})
    return ex


def render_film(film, path=None, draft=False, sheet=True, flicker=True, progress=True, quality=None):
    t_start = time.time()
    timings = {}
    film._prepare()
    lint = film.lint()
    errs = [it for it in lint if it["level"] == "error"]
    if errs:
        for it in errs:
            print("[error] %.2fs %s" % (it["t"], it["msg"]))
        raise RuntimeError("存在 error 级问题，停止渲染（先修复再渲染）")
    ffmpeg = find_ffmpeg()
    t0 = time.time()
    enc_name, enc_args = pick_encoder(ffmpeg, verbose=progress)
    if quality is not None:
        enc_args = _apply_quality(enc_args, quality)
    timings["prepare"] = time.time() - t0
    out = path or (film.name + ".mp4")
    if not os.path.isabs(out):
        out = os.path.abspath(out)
    out_dir = os.path.dirname(out)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    tmp_video = out + ".rendering.mp4"
    fps = film.fps
    total = max(1, int(round(film.duration * fps)))
    if draft:
        ss = 1.0
        out_scale = 0.5
    else:
        ss = float(film.ss)
        out_scale = 1.0
    Wout = max(1, int(round(film.width * out_scale)))
    Hout = max(1, int(round(film.height * out_scale)))
    an = checks.FlickerAnalyzer(Wout, Hout, fps, exclusions=film_exclusions(film)) if flicker else None
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (Wout, Hout), "-r", str(fps), "-i", "-"] + enc_args + [
          "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp_video]
    if progress:
        print("[write-video] 开始渲染 %s（%d 帧 %dx%d，编码器 %s）" % (film.name, total, Wout, Hout, enc_name))
        sys.stdout.flush()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_frames0 = time.time()
    try:
        for i in range(total):
            t = i / float(fps)
            frame = film.render_frame(t, ss=ss, out_scale=out_scale)
            proc.stdin.write(frame.tobytes())
            if an is not None:
                an.push(frame)
            if progress and i % 60 == 0 and i > 0:
                el = time.time() - t_frames0
                eta = el / i * (total - i)
                print("[write-video] 帧 %d/%d (%.0f%%) 已用 %.0fs，预计还需 %.0fs" % (i, total, 100.0 * i / total, el, eta))
                sys.stdout.flush()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        raise
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    proc.wait()
    timings["frames"] = time.time() - t_frames0
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg 编码失败（exit=%d），临时文件保留：%s" % (proc.returncode, tmp_video))
    t0 = time.time()
    fl = an.finish() if an is not None else {"events": [], "maxScore": 0.0}
    timings["flicker"] = time.time() - t0
    for ev in fl.get("events", []):
        film._lint_add("warn", ev["t"], "疑似单帧闪烁（第 %d 帧，强度 %.2f）位置约 (%d,%d)"
                       % (ev["frame"], ev["score"], ev["x"], ev["y"]))
    t0 = time.time()
    from . import audio as _audio
    audio_stats = _audio.build_audio_track(film, tmp_video + ".wav", ffmpeg)
    timings["audio"] = time.time() - t0
    t0 = time.time()
    final_tmp = tmp_video + ".mux.mp4"
    cmd2 = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp_video, "-i", tmp_video + ".wav",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final_tmp]
    r = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 合流失败：" + r.stderr.decode("utf-8", "ignore")[-400:])
    timings["mux"] = time.time() - t0
    if os.path.exists(out):
        os.remove(out)
    os.replace(final_tmp, out)
    for f in (tmp_video, tmp_video + ".wav"):
        try:
            os.remove(f)
        except Exception:
            pass
    if sheet:
        t0 = time.time()
        sheet_path = os.path.splitext(out)[0] + ".sheet.png"
        film.sheet(sheet_path)
        timings["sheet"] = time.time() - t0
    if an is not None and fl.get("events"):
        strip = os.path.splitext(out)[0] + ".flicker.png"
        try:
            save_flicker_strip(film, fl["events"], strip, ss=ss, out_scale=out_scale)
        except Exception as e:
            print("[write-video] 闪烁条带生成失败: %r" % (e,))
    size = os.path.getsize(out)
    dur_out = total / float(fps)
    report = {
        "path": out, "frames": total, "duration": round(dur_out, 3), "fps": fps,
        "size": size, "mbps": round(size * 8 / 1e6 / max(0.001, dur_out), 2),
        "seconds": round(time.time() - t_start, 1),
        "timings": dict((k, round(v, 2)) for k, v in timings.items()),
        "encoder": enc_name,
        "audio": audio_stats,
        "flicker": fl,
        "lint": film.lint(),
        "draft": bool(draft),
    }
    print_report(report)
    try:
        save_report(report, os.path.splitext(out)[0] + ".report.txt")
    except Exception:
        pass
    return report


def print_report(r):
    print("")
    print("[write-video] 渲染完成：%s" % r["path"])
    print("  时长   %.2f 秒  %d 帧 @%dfps" % (r["duration"], r["frames"], r["fps"]))
    print("  文件   %.2f MB  %.2f Mbps  编码器 %s" % (r["size"] / 1e6, r["mbps"], r["encoder"]))
    tm = r["timings"]
    print("  耗时   共 %.1f 秒（画帧 %.1f / 音频 %.1f / 闪烁 %.1f / 联系表 %.1f）" % (
        r["seconds"], tm.get("frames", 0), tm.get("audio", 0), tm.get("flicker", 0), tm.get("sheet", 0)))
    au = r["audio"]
    extra = ("，配音 %d 段" % au["voices"]) if au.get("voices") else ""
    print("  音频   %.1f LUFS  真峰值 %.1f dB  音效 %d 个%s"
          % (au.get("lufs", -200), au.get("tp", -200), au.get("count", 0), extra))
    fl = r["flicker"]
    print("  闪烁   %d 事件%s" % (len(fl.get("events", [])),
          ("（最高强度 %.2f）" % fl["maxScore"]) if fl.get("events") else ""))
    lv = {"error": 0, "warn": 0, "info": 0}
    for it in r["lint"]:
        lv[it["level"]] = lv.get(it["level"], 0) + 1
    print("  lint   error %d / warn %d / info %d" % (lv.get("error", 0), lv.get("warn", 0), lv.get("info", 0)))
    for it in r["lint"][:24]:
        print("    [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    print("")
    sys.stdout.flush()


def save_report(report, path):
    lines = ["write-video 渲染报告", "文件: %s" % report["path"],
             "时长: %.2fs  %d 帧 %dx%d@%d" % (report["duration"], report["frames"], 0, 0, report["fps"]),
             "大小: %.2f MB  %.2f Mbps" % (report["size"] / 1e6, report["mbps"]),
             "编码器: %s" % report["encoder"], "", "lint:"]
    for it in report["lint"]:
        lines.append("  [%s] %.2fs %s" % (it["level"], it["t"], it["msg"]))
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def save_flicker_strip(film, events, path, ss=2.0, out_scale=1.0):
    evs = list(events)[:8]
    rows = []
    for ev in evs:
        frames = []
        for k in range(-2, 3):
            t = max(0.0, ev["t"] + k / float(film.fps))
            frames.append(film.render_frame(t, ss=ss, out_scale=out_scale))
        rows.append((ev, frames))
    if not rows:
        return None
    cw, ch = rows[0][1][0].size
    cell_w = max(120, cw // 3)
    cell_h = max(80, ch // 3)
    pad = 6
    label_h = 24
    strip = Image.new("RGB", ((cell_w + pad) * 5 + pad, (cell_h + label_h + pad) * len(rows) + pad), (10, 12, 18))
    d = ImageDraw.Draw(strip)
    fnt = _fonts.load("sans", 16)
    for ri, (ev, frames) in enumerate(rows):
        y = pad + ri * (cell_h + label_h + pad)
        cx = int(ev["x"] * 1.0)
        cy = int(ev["y"] * 1.0)
        bx = max(0, min(max(0, cw - cell_w), cx - cell_w // 2))
        by = max(0, min(max(0, ch - cell_h), cy - cell_h // 2))
        for ci, im in enumerate(frames):
            cell = im.crop((bx, by, min(cw, bx + cell_w), min(ch, by + cell_h)))
            x = pad + ci * (cell_w + pad)
            strip.paste(cell, (x, y))
            if ci == 2:
                d.rectangle([x, y, x + cell.width - 1, y + cell.height - 1], outline=(255, 60, 60), width=3)
        d.text((pad, y + cell_h + 4), "t=%.2fs score=%.2f 第%d帧" % (ev["t"], ev["score"], ev["frame"]),
               font=fnt, fill=(230, 235, 245))
    strip.save(path, compress_level=1)
    return path
