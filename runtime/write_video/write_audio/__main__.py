# -*- coding: utf-8 -*-
"""write_audio 命令行：运行乐谱脚本并渲染。

    python -m write_audio song.py                      # 按脚本内设定渲染
    python -m write_audio song.py --out x.mp3           # 指定输出
    python -m write_audio song.py --stems stems/        # 分轨
    python -m write_audio song.py --lufs -14 --bitrate 192
    python -m write_audio song.py --check               # 只打印乐谱摘要，不渲染

约定：song.py 里定义名为 song 的对象（ca.Song 实例）。
若脚本已自行调用 render（有报告），CLI 直接打印其报告。
"""
import argparse
import os
import runpy
import sys


def _fmt(v):
    return "-" if v is None else ("%g" % v if isinstance(v, float) else str(v))


def _print_stats(song):
    st = song.stats()
    print("%s bpm / %s 拍每小节 — %s 拍 / %s 小节 / %.1f 秒（+尾 %.1f s）"
          % (_fmt(st["bpm"]), st["beats_per_bar"], _fmt(st["beats"]), _fmt(st["bars"]),
             st["seconds"], st["tail"]))
    print("轨道 %d 条：" % len(st["tracks"]))
    for t in st["tracks"]:
        print("  %-10s %-7s %4d 音符  gain %+g dB  pan %+g  拍 [%s .. %s]"
              % (t["name"], t["inst"], t["notes"], t["gain_db"], t["pan"],
                 _fmt(t["first"]), _fmt(t["last"])))
    if st["sidechains"]:
        print("侧链：" + "，".join("%s→%s (%g dB)" % (a, b, d) for (a, b, d, r) in st["sidechains"]))


def _print_report(rep):
    print("")
    print("lufs=%s tp=%s gain=%s dB" % (rep.get("lufs"), rep.get("tp"), rep.get("gain_db")))
    if rep.get("wav"):
        print("wav: %s" % rep["wav"])
    if rep.get("mp3"):
        print("mp3: %s (%.1f MB)" % (rep["mp3"], rep["mp3_bytes"] / 1048576.0))
    if rep.get("mp3_error"):
        print("mp3 ERROR: %s" % rep["mp3_error"])
    if rep.get("stems"):
        print("stems: %d 轨" % len(rep["stems"]))
    print("render %.1fs" % rep["render_seconds"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="write_audio",
                                 description="运行乐谱脚本并渲染完整音乐（MP3/WAV/分轨）。")
    ap.add_argument("script", help="乐谱脚本（*.py，里内定义 song = ca.Song(...)）")
    ap.add_argument("--out", default=None, help="输出 mp3/wav 路径")
    ap.add_argument("--wav", default=None, help="额外输出 wav 路径")
    ap.add_argument("--stems", default=None, help="分轨目录")
    ap.add_argument("--lufs", type=float, default=-14.0, help="响度目标（默认 -14）")
    ap.add_argument("--bitrate", type=int, default=192, help="mp3 码率 kbps")
    ap.add_argument("--fade-in", type=float, default=None, help="整曲渐入（秒）")
    ap.add_argument("--fade-out", type=float, default=None, help="整曲渐出（秒）")
    ap.add_argument("--keep-wav", action="store_true", help="保留中间 wav")
    ap.add_argument("--check", action="store_true", help="只打印乐谱摘要，不渲染")
    args = ap.parse_args(argv)

    script = os.path.abspath(args.script)
    if not os.path.exists(script):
        print("找不到脚本：%s" % script)
        return 2
    d = os.path.dirname(script)
    if d and d not in sys.path:
        sys.path.insert(0, d)

    g = runpy.run_path(script)
    song = g.get("song")
    if song is None or not hasattr(song, "stats"):
        print("脚本里没有定义有效的 song 对象（应为 ca.Song 实例）")
        return 2

    _print_stats(song)
    if args.check:
        return 0
    if getattr(song, "_rendered", False) and getattr(song, "_report", None) is not None:
        _print_report(song._report)
        return 0
    rep = song.render(out=args.out, wav=args.wav, stems=args.stems,
                      lufs=args.lufs, bitrate=args.bitrate,
                      fade_in=args.fade_in, fade_out=args.fade_out,
                      keep_wav=args.keep_wav)
    _print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
