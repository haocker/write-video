# -*- coding: utf-8 -*-
"""write-video — 配音（TTS）：用 edge-tts（微软 Edge 神经网络语音）生成配音。

配音只认音频文件：本模块生成的 mp3、真人录音、别人给的音频，都走同一条
`s.audio` / `film.audio` 通道进片；这里只是“生成”这一环的助手：

    import write_video as cf
    v = cf.voice.tts("只用一句话，能做视频吗？", "/res/voice/q1.mp3")
    q = s.audio(v, at=0.8)        # v = {path; text; words; ...}，直接传给 audio
    s.text(v["text"], at=q.at)      # 台词长在画面里
    s.text("品牌名", at=q.done + 0.5, style="hero", enter="slam")

- 词时间：合成时顺便拿到逐词时间（v["words"]，相对文件开头的秒数），
  `word()` 靠它精确到词：`s.text("那句", at=q.word("一句"))`。
- 缓存：同文/同音色的合成结果缓存在 <路径>.json；重复跑片不重新联网。
- 依赖：pip install edge-tts（在线服务，需要联网）。
"""
import asyncio
import hashlib
import json
import os

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

# 中文常用音色速查（也可以用完整音色名；用 cf.voice.list_voices() 看全部）
VOICE_ALIASES = {
    "晓晓": "zh-CN-XiaoxiaoNeural",          # 女声・通用旁白（默认）
    "晓伊": "zh-CN-XiaoyiNeural",            # 女声・活泼
    "云希": "zh-CN-YunxiNeural",             # 男声・年轻
    "云健": "zh-CN-YunjianNeural",           # 男声・浑厚有力
    "云扬": "zh-CN-YunyangNeural",           # 男声・播音腔
    "晓北": "zh-CN-liaoning-XiaobeiNeural",  # 女声・东北话
    "晓妮": "zh-CN-shaanxi-XiaoniNeural",    # 女声・陕西话
    "粤语女": "zh-HK-HiuMaanNeural",
    "粤语男": "zh-HK-WanLungNeural",
    "台湾女": "zh-TW-HsiaoChenNeural",
    "台湾男": "zh-TW-YunJheNeural",
}


def _ensure_edge():
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        raise RuntimeError("配音需要 edge-tts：pip install edge-tts（生成配音需联网）")


def resolve_voice(name):
    """音色别名 → 完整音色名（"晓晓"/"粤语女"…；完整名原样返回）。"""
    if not name:
        return DEFAULT_VOICE
    return VOICE_ALIASES.get(str(name).strip(), str(name).strip())


def _run_async(coro):
    """跑一个协程。Windows 上用 Selector 事件循环（避开 Proactor 关闭噪音）。"""
    if os.name == "nt" and hasattr(asyncio, "SelectorEventLoop"):
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass


def list_voices(language=None):
    """列出可用音色（可指定 language="zh" 过滤）；返回 [{name;gender;locale}]。"""
    _ensure_edge()
    import edge_tts
    vs = _run_async(edge_tts.list_voices())
    out = []
    for v in vs:
        loc = v.get("Locale", "")
        if language and not loc.lower().startswith(str(language).lower()):
            continue
        out.append({"name": v["ShortName"], "gender": v.get("Gender"), "locale": loc})
    return out


def _pct(v, default="+0%"):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return "%+d%%" % int(round(v))
    s = str(v).strip()
    return s if s.endswith("%") else s + "%"


def _hz(v, default="+0Hz"):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return "%+dHz" % int(round(v))
    s = str(v).strip()
    return s if s.lower().endswith("hz") else s + "Hz"


def _hash(text, voice, rate, volume, pitch):
    h = hashlib.md5()
    h.update(("|".join([str(text), voice, rate, volume, pitch])).encode("utf-8"))
    return h.hexdigest()


def _synthesize(text, path, voice, rate, volume, pitch, proxy=None):
    import edge_tts
    words = []

    async def run():
        kw = {"proxy": proxy} if proxy else {}
        cm = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch,
                                  boundary="WordBoundary", **kw)
        with open(path, "wb") as f:
            async for ch in cm.stream():
                t = ch.get("type")
                if t == "audio":
                    f.write(ch["data"])
                elif t == "WordBoundary":
                    words.append([ch["text"],
                                  round(float(ch["offset"]) / 1e7, 3),
                                  round(float(ch["duration"]) / 1e7, 3)])

    _run_async(run())
    return words


def tts(text, path, voice=None, rate=None, volume=None, pitch=None,
        cache=True, proxy=None):
    """把一句台词合成成配音文件（默认 mp3）。

    text    台词（标点会被读出来，但不出现在 words 里）
    path    输出路径（相对路径按当前工作目录；工程里习惯写 "/res/voice/xx.mp3"）
    voice   音色：别名（"晓晓"/"粤语女"…）或完整音色名，默认晓晓
    rate    语速，如 -10 或 "-10%"；volume 音量，如 5 或 "+5%"；pitch 音高，如 "-2Hz"
    返回   {path; text; voice; rate; volume; pitch; words}，可直接传给 s.audio；
           words = [[词, 开头秒, 时长], ...]（相对文件开头）
    """
    _ensure_edge()
    voice = resolve_voice(voice)
    rate_s, vol_s, pitch_s = _pct(rate), _pct(volume), _hz(pitch)
    path = os.path.abspath(path)
    meta_path = path + ".json"
    key = _hash(text, voice, rate_s, vol_s, pitch_s)
    if cache and os.path.exists(path) and os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path, "r", encoding="utf-8"))
            if meta.get("key") == key:
                meta["path"] = path
                meta["text"] = text
                meta["cached"] = True
                return meta
        except (ValueError, OSError):
            pass
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    words = _synthesize(text, path, voice, rate_s, vol_s, pitch_s, proxy=proxy)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError("edge-tts 没有返回音频（检查文字是否为空、网络是否可用）")
    meta = {"path": path, "text": text, "voice": voice, "rate": rate_s, "volume": vol_s,
            "pitch": pitch_s, "words": words, "key": key, "cached": False}
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return meta
