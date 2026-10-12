# -*- coding: utf-8 -*-
"""write_audio.theory — 乐理工具（纯函数，全部确定性）。

音名 / MIDI / 频率互转；和弦名解析；音阶。供写乐谱时构造音高用。

    import write_audio as ca
    ca.midi("A3")            # 57
    ca.freq("A3")            # 220.0
    ca.freq(57)              # 220.0
    ca.chord("Am7", 3)       # [57, 60, 64, 67]  (MIDI，升序)
    ca.chord("C/E", 3)       # 低音 E 在下方
    ca.scale("A", "minor", 3)  # [57, 59, 60, 62, 64, 65, 67, 69]
"""
import math

# ================================================================ 音名 / MIDI / 频率

NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def parse_note(v, default_band=(57, 68)):
    """音名或 MIDI 数值 → MIDI 音高。

    'A3' / 'F#2' / 'Bb' / 57。
    省略八度时（如 'F#'）取 default_band 内同一音名的最近值。
    """
    if v is None or isinstance(v, bool):
        raise ValueError("无效的音高值 %r" % (v,))
    if isinstance(v, (int, float)):
        return int(round(float(v)))
    s = str(v).strip()
    pc = _NOTE_PC.get(s[:1].upper()) if s else None
    if pc is None:
        raise ValueError("无法识别的音高 %r（示例：'A3'、'F#'、'Bb2' 或 MIDI 数值 57）" % (v,))
    i = 1
    while i < len(s) and s[i] in "#b":
        pc += 1 if s[i] == "#" else -1
        i += 1
    tail = s[i:].strip()
    if tail:
        try:
            octave = int(tail)
        except ValueError:
            raise ValueError("无法识别的音高 %r（八度部分 %r 不是数字）" % (v, tail))
        return 12 * (octave + 1) + pc
    m = pc
    while m < default_band[0]:
        m += 12
    while m > default_band[1]:
        m -= 12
    return m


_NOTE_PC = NOTE_PC  # 兼容别名


def midi_to_freq(m):
    """MIDI 音高 → 频率（Hz）。"""
    return 440.0 * (2.0 ** ((float(m) - 69.0) / 12.0))


def freq(v):
    """音名或 MIDI → 频率（Hz）。ca.freq('A3') → 220.0"""
    return midi_to_freq(parse_note(v))


# ================================================================ 音阶

SCALES = {
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "major": (0, 2, 4, 5, 7, 9, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "harmonicminor": (0, 2, 3, 5, 7, 8, 11),
    "melodicminor": (0, 2, 3, 5, 7, 9, 11),
    "minorpentatonic": (0, 3, 5, 7, 10),
    "majorpentatonic": (0, 2, 4, 7, 9),
    "blues": (0, 3, 5, 6, 7, 10),
}
_SCALE_ALIASES = {"aeolian": "minor", "ionian": "major", "naturalminor": "minor"}


def resolve_scale(name):
    """音阶名或半音偏移序列 → 偏移元组。

    音阶名忽略大小写与 '-'/'_'/空格（如 'minor pentatonic' / 'MinorPentatonic' / 'harmonic-minor'）。
    也可直接给半音偏移序列，如 (0, 3, 5, 7, 10)。
    """
    if isinstance(name, str):
        key = name.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        key = _SCALE_ALIASES.get(key, key)
        if key not in SCALES:
            raise ValueError("未知音阶 %r（可用：%s；或直接给半音偏移序列）"
                             % (name, "/".join(sorted(SCALES))))
        return SCALES[key]
    seq = tuple(int(x) for x in name)
    if len(seq) < 3:
        raise ValueError("自定义音阶至少需要 3 个半音偏移：%r" % (name,))
    return seq


def scale(root, name="minor", octave=3, count=None):
    """音阶 → MIDI 音高列表。

    root: 'A' / 'A3' / MIDI。'A' 时用 octave 参数（默认 3）确定八度。
    count: 取前 count 个音（默认 音阶音数+1，即含高八度主音）。
    """
    iv = resolve_scale(name)
    if isinstance(root, (int, float)) and not isinstance(root, bool):
        r = int(root)
    else:
        s = str(root).strip()
        if s and s[-1].isdigit():
            r = parse_note(s)
        else:
            r = parse_note(s, default_band=(12 * (octave + 1), 12 * (octave + 2) - 1))
    k = len(iv)
    if count is None:
        count = k + 1
    return [r + iv[i % k] + 12 * (i // k) for i in range(int(count))]


# ================================================================ 和弦

_CHORD_INTERVALS = {
    "": (0, 4, 7),                    # 大三
    "M": (0, 4, 7),
    "maj": (0, 4, 7),
    "m": (0, 3, 7),                   # 小三
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "o": (0, 3, 6),
    "aug": (0, 4, 8),
    "+": (0, 4, 8),
    "5": (0, 7),                      # 强力和弦
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "sus": (0, 5, 7),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "7": (0, 4, 7, 10),               # 属七
    "maj7": (0, 4, 7, 11),
    "M7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "min7": (0, 3, 7, 10),
    "mmaj7": (0, 3, 7, 11),
    "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "7sus4": (0, 5, 7, 10),
    "9": (0, 4, 7, 10, 14),
    "maj9": (0, 4, 7, 11, 14),
    "m9": (0, 3, 7, 10, 14),
    "add9": (0, 4, 7, 14),
    "madd9": (0, 3, 7, 14),
    "11": (0, 4, 7, 10, 14, 17),
    "m11": (0, 3, 7, 10, 14, 17),
    "13": (0, 4, 7, 10, 14, 21),
    "m13": (0, 3, 7, 10, 14, 21),
}
_CHORD_NORMALIZE = [("Maj", "maj"), ("MAJ", "maj"), ("Min", "min"), ("MIN", "min"),
                    ("SUS", "sus"), ("ADD", "add"), ("DIM", "dim"), ("AUG", "aug"),
                    ("\u0394", "maj")]


def _suffix_intervals(sfx):
    if sfx in _CHORD_INTERVALS:
        return _CHORD_INTERVALS[sfx]
    t = sfx
    for a, b in _CHORD_NORMALIZE:
        t = t.replace(a, b)
    if t in _CHORD_INTERVALS:
        return _CHORD_INTERVALS[t]
    raise ValueError("无法识别的和弦后缀 %r（如 m / 7 / maj7 / m7 / sus4 / add9 / dim / aug ...）" % (sfx,))


def chord(name, octave=3):
    """和弦名 → MIDI 音高列表（升序）。

    支持：'Am' / 'C' / 'F#m7' / 'Cmaj7' / 'Bb7' / 'G7sus4' / 'Dm7b5' / 'C/E'（斜杠低音）等。
    octave 决定根音所在八度（默认 3）。
    """
    s = str(name).strip()
    bass = None
    if "/" in s:
        s, _, b = s.partition("/")
        bass = b.strip()
    s = s.strip()
    if not s:
        raise ValueError("和弦名不能为空")
    letter = s[0].upper()
    if letter not in NOTE_PC:
        raise ValueError("无法识别的和弦根音 %r（应以 A-G 开头）" % (name,))
    pc = NOTE_PC[letter]
    i = 1
    while i < len(s) and s[i] in "#b\u266f\u266d":
        if s[i] in "#\u266f":
            pc += 1
        else:
            pc -= 1
        i += 1
    iv = _suffix_intervals(s[i:].strip())
    root_midi = 12 * (int(octave) + 1) + pc
    out = [root_midi + x for x in iv]
    if bass:
        bm = parse_note(bass, (out[0] - 6, out[0] + 6))
        while bm >= out[0]:
            bm -= 12
        out = [bm] + out
    return out


def chord_freqs(name, octave=3):
    """和弦名 → 频率列表（Hz）。"""
    return [midi_to_freq(m) for m in chord(name, octave)]
