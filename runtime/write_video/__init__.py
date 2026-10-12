# -*- coding: utf-8 -*-
"""write-video — 用代码编排视频（通用版）。

基本用法：
    import write_video as cf

    film = cf.Film(1920, 1080, theme="midnight")
    s = film.scene(0, 4)
    s.text("你好，世界", at=0.6, style="hero", enter="slam")

    # 配乐：用内置的渲染模块自己写乐谱（引擎只做渲染，无风格模板）
    score = cf.wa.Song(bpm=120)
    score.track("pad").notes([(0, "A3", 4, 0.5)])
    score.length(beats=8)
    film.music = score
    film.render("/out.mp4")
"""
from .film import Film, Scene, Elem
from .canvas import Canvas, ease, rand, spring, decay, wiggle, lerp, clamp, parse_color
from . import canvas, fonts, checks, audio, render, voice, write_audio

wa = write_audio

__version__ = "0.4.0"
__all__ = ["Film", "Scene", "Elem", "Canvas", "ease", "rand", "spring", "decay",
           "wiggle", "lerp", "clamp", "parse_color", "voice", "write_audio", "wa"]
