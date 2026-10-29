# -*- coding: utf-8 -*-
"""write_audio — 用代码写乐谱 → 渲染完整音乐（3 分钟级）。

引擎只做渲染：曲式、和弦、旋律、织体全部由你在乐谱里显式给出。
没有随机预设、没有自动作曲；同一乐谱 → 逐样本可复现。

快速上手：
    import write_audio as ca

    s = ca.Song(bpm=124)
    kick = s.track("kick")
    kick.grid("x...x...x...x...", step=0.25)
    bass = s.track("bass", gain_db=-4)
    bass.notes([(0, "A1", 1), (1, "A1", 0.5), (1.5, "C2", 0.5)])
    s.sidechain("kick", "bass")
    s.length(bars=4)
    s.render("out.mp3")

乐理工具：
    ca.midi("A3") -> 57          ca.freq("A3") -> 220.0
    ca.chord("Am7", 3)           ca.scale("A", "minor", 3)

命令行：
    python -m write_audio <song.py> [--out x.mp3] [--stems dir] [--check]
"""
from . import audio, mix, song, theory
from .song import Song, Track
from .theory import (SCALES, chord, chord_freqs, freq, midi_to_freq, parse_note,
                     resolve_scale, scale)
from .audio import INST, SFX, SR, synth_sfx

# 简名别名：ca.midi("A3") -> 57
midi = parse_note

__version__ = "0.2.0"
__all__ = ["Song", "Track", "midi", "freq", "midi_to_freq", "parse_note",
           "chord", "chord_freqs", "scale", "resolve_scale", "SCALES",
           "INST", "SFX", "SR", "synth_sfx",
           "audio", "mix", "song", "theory"]
