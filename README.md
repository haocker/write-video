# write-video

> 用代码编排短视频 / MP4（code-to-video）：策划分镜 → 写 Python 影片脚本 → 渲染带配乐与音效的成片。

写一个 Python 脚本，声明场景与元素（文字、清单、数字、图片卡片、自绘、配音），
合成配乐与音效，一次 `render` 生成带声 MP4 —— 无需剪辑软件、无需手工对轨。

## 为什么用它

- **画面是时间的纯函数**：任何一帧都能单独渲染；同样的脚本、素材与种子，永远得到同样的画面。可复现、可 diff、可版本管理。
- **一套脚本 = 一支成片**：文案、节奏、动效、配乐、音效全部写在代码里，改一行就改一版，再也不用在时间轴上挪来挪去。
- **招牌画面信手拈来**：`s.draw(fn)` 用画布 API 直接画（光晕、弧线、火花、弹簧、粒子…），给出这支片独有的视觉，而不是套模板。
- **音效自动跟着命中点**：入场预设自带音效；关键事件用一张时刻表，让画面与声音共用同一份时间。
- **配乐完全由你掌控**：引擎只负责渲染，曲式/和弦/旋律/配器/音量全部由乐谱显式写出——没有风格模板、没有随机预设，同一份乐谱逐样本可复现。
- **配音与旁白一条通道**：`wv.voice.tts()` 生成或任何现成音频文件，摆放时自动去首尾静音、响度对齐，说话时配乐自动闪避。
- **交付前自动体检**：lint（越界/阅读时间/拼写）、单帧闪烁检测（源帧 + 成片回读）、混音响度与真峰值，一次渲染全给你。

只需要 **Python 3.8+** 与 **FFmpeg**；纯 Python 实现，零外部素材依赖。

## 安装

1. Python 3.8+（含 pip）
2. 依赖：`pip install pillow numpy`
   - 要生成配音再加 `pip install edge-tts`（可选；配音也支持任何现成音频文件）
3. FFmpeg：Windows `winget install ffmpeg` · macOS `brew install ffmpeg` · Linux `apt install ffmpeg`
   - 找不到时用环境变量指定：`WV_FFMPEG=D:\tools\ffmpeg\bin\ffmpeg.exe`

中文字体自动发现（微软雅黑 / 苹方 / Noto CJK）；也可用 `WV_FONT_SANS` / `WV_FONT_SANS_BOLD` / `WV_FONT_MONO` 指定字体文件。

## 快速开始

```python
# film.py — 放在任意目录
import sys
sys.path.insert(0, r"<本技能目录>/runtime")   # 或设置环境变量 WRITE_VIDEO_RUNTIME
import write_video as wv

film = wv.Film(1920, 1080, theme="midnight", bpm=120)
s = film.scene(0, 6)
s.text("你好，世界", at=0.6, style="hero", enter="slam")        # 砸下 + 自动 impact
s.text("一句代码，一支短片", at=1.6, style="subtitle", split="char")

# 配乐：乐谱自己写（AI 生成），引擎只负责渲染
score = wv.wa.Song(bpm=120)
score.track("pad",   gain_db=-16).notes([(0, "C4", 4.0, 0.5), (0, "E4", 4.0, 0.5), (0, "G4", 4.0, 0.5)])
score.track("bass",  gain_db=-9).note(0, "C2", 3.6, 0.75)
score.track("pluck", gain_db=-11).grid(0, 0.5, ["C5", "E5", "G5", "E5"], dur=0.55, vel=0.5)
score.length(beats=24)
film.music = score

film.render("artifacts/demo.mp4")
```

运行 `python film.py`，产物在 `artifacts/`：**MP4 + 联系表（`*.sheet.png`）+ 报告（`*.report.txt`，含 lint / 闪烁 / 响度）**。

## 配乐

默认渲染模块在 `runtime/write_video/write_audio/`，**只做渲染**：曲式、和弦、旋律、配器、音量全部由乐谱显式写出——
乐谱自己写（AI 生成），引擎不编曲、不预设、不随机。
乐谱用 `wv.wa` 构造：`Song` / `Track` / `note` / `notes` / `grid` / `hit` / `hits` / `sidechain` / `fade` / `length`；
音高与和声工具在 `wv.wa.theory`（`midi` / `freq` / `chord` / `scale` / `SCALES`）。
也可以直接给音频文件路径：`film.music = "res/bgm.mp3"`（循环铺满全片）。详见 `knowledge/compose.md`。

### 想用真实采样音源？（换成 write-audio-pro）

默认模块是纯合成（零依赖，装好 pillow/numpy 即可）。想要钢琴/弦乐/管弦这类**真实采样**音色，
可把渲染模块整体换成 [write-audio-pro](https://github.com/haocker/write-audio-pro)。步骤：

```bash
# 1) 装依赖：pro 走 FluidSynth + SoundFont，另需 pretty_midi / mido
pip install numpy pretty_midi mido
sudo apt install fluidsynth musescore-general-soundfont   # macOS: brew install fluid-synth
#  Win: 装 FluidSynth + 下载 FluidR3_GM.sf2 / MuseScore_General.sf3

# 2) 用 pro 的运行时内容替换默认渲染模块（目录名保持 write_audio 不变）
cd runtime/write_video
mv write_audio write_audio.simple                                  # 先备份原实现
cp -r /path/to/write-audio-pro-skill/runtime/write_audio_pro/. write_audio/
```

就这两步——目录名仍是 `write_audio`，包内是 pro 的实现，`wv.wa` 自动指向 pro，**无需改任何代码**。
（想切回来：`rm -rf write_audio && mv write_audio.simple write_audio`。）

影片脚本只要换掉乐谱写法即可（`film.music` 接口不变）：

```python
score = wv.wa.Song(bpm=66)                                  # 同样的 Song 入口
score.track("piano",   gain_db=0) .notes([(0, "A4", 2, 80), (2, "C5", 2, 80)])
score.track("strings", gain_db=-6).notes([(0, "A3", 4, 70), (4, "F3", 4, 70)])
score.length(bars=8)
film.music = score
```

**换 pro 时乐谱要改的地方**：乐器名用 GM 真实乐器（`piano` / `strings` / `cello` …，见 pro 的 `GM` / `ENSEMBLES`），
不是合成版的 `pad` / `pluck` / `bass`；`note` 的力度是 **0–127**（不是 0–1）；`grid` / `hit` / `sidechain` 是合成版专有，
pro 里用 `notes` + 声部编排代替。混音链、响度归一、配音闪避都不用动——
`render_score()` 按 `Song.render(wav=...)` 读回音频，对两个模块都兼容。

## 配音

```python
v = wv.voice.tts("只用一句话，能做视频吗？", "res/voice/q1.mp3")   # edge-tts，返回 {path;text;words}
q = s.audio(v, at=0.8)                        # 自动去静音、响度对齐、配乐闪避
s.text(v["text"], at=q.at, style="subtitle")  # 台词长在画面里
s.text("落版", at=q.word("视频"))              # 精确到词（词时间来自合成）
```

## 图片卡片

```python
s.image("res/shot.png", title="真实界面", caption="图 1", width=1180)
```

窗口标题栏 + 卡外说明 + 柔和投影；大图默认 Ken Burns 慢推，也可自定义推近：
`zoom=[(0, 1.0, 0.5, 0.5), (1.6, 1.3, 0.5, 0.45)]`。

## 示例片

`examples/hello-world/film.py` — 20 秒 1920x1080 完整示例：打字代码卡、slam、逐字浮现、清单、计数器、
招牌星海自绘、全片层光尘、配乐与音效对齐。

```
cd examples/hello-world
python film.py
```

## 用法

两个阶段，分开做：

1. **策划**：读 `knowledge/planning.md`，把分镜写进项目 `HANDOFF.md`；
2. **编排**：读 `knowledge/compose.md`，写 `film.py` → 渲染 → 检查 → 交付。

## 目录

- `SKILL.md` — 技能包说明（给 AI 智能体）
- `knowledge/planning.md` — 策划指南
- `knowledge/compose.md` — 编排指南（API 速查 + 自绘菜单 + 常见坑）
- `runtime/write_video/` — 运行时：`film.py` 模型 / `canvas.py` 画布 / `audio.py` 音效 + 配乐渲染 + 混音 / `write_audio/` 配乐渲染模块（可替换） / `voice.py` 配音 / `render.py` 管线 / `checks.py` 闪烁检测 / `fonts.py` 字体
- `examples/hello-world/` — 示例片

## 常见问题

- **找不到 ffmpeg**：安装后用 `WV_FFMPEG` 指定；首次渲染会自动探测可用编码器（结果缓存在临时目录）。
- **配乐报错**：`film.music` 只接受乐谱 `Song` 对象或音频文件路径（正确写法 `film.music = wv.wa.Song(...)`）。
- **找不到可用字体**：安装中文字体，或用 `WV_FONT_SANS` 指定字体文件。
- **想更快迭代**：用 `draft=True`（半分辨率）；正式渲染 1080p 约 40~100ms/帧（看内容）。
- **中文输出乱码**：Windows 终端执行 `chcp 65001`，或设 `PYTHONUTF8=1`。
