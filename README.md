# write-video

> 用代码编排短视频 / MP4（code-to-video）：策划分镜 → 写 Python 影片脚本 → 渲染带配乐与音效的成片。

用代码编排影片：写一个 Python 脚本，声明场景与元素（文字、清单、数字、图片卡片、自绘、配音），
合成配乐与音效，渲染出带声 MP4，并自动做 lint、单帧闪烁检测与响度检查。

- **画面是时间的纯函数**：任意帧可单独渲染；同样的脚本、素材与种子得到相同画面。
- **配乐引擎只负责渲染**：曲式/和弦/旋律/配器全部由乐谱显式写出，**没有风格模板、没有随机预设**；乐谱用 `cf.wa` 在脚本里直接写。
- **自动检查**：lint、单帧闪烁检测（源帧 + 成片回读）、混音响度与真峰值。

只需要 **Python 3.8+** 与 **FFmpeg**，纯 Python 实现、零外部素材。

## 安装

1. Python 3.8+（含 pip）
2. 依赖：`pip install pillow numpy`
   - 要生成配音再加 `pip install edge-tts`（可选；配音也支持任何现成音频文件）
3. FFmpeg：
   - Windows：`winget install ffmpeg`
   - macOS：`brew install ffmpeg`
   - Linux：`apt install ffmpeg`
   - 找不到时用环境变量指定：`WV_FFMPEG=D:\tools\ffmpeg\bin\ffmpeg.exe`

中文字体会自动发现（微软雅黑/苹方/Noto CJK）；找不到时用 `WV_FONT_SANS` / `WV_FONT_SANS_BOLD` / `WV_FONT_MONO` 指定字体文件路径。

## 快速开始

```python
# film.py — 放在任意目录
import sys
sys.path.insert(0, r"<本技能目录>/runtime")   # 或设置环境变量 WRITE_VIDEO_RUNTIME
import write_video as cf

film = cf.Film(1920, 1080, theme="midnight", bpm=120)
s = film.scene(0, 6)
s.text("你好，世界", at=0.6, style="hero", enter="slam")
s.text("一句代码，一支短片", at=1.6, style="subtitle", split="char")

# 配乐：乐谱自己写，引擎只负责渲染（无风格模板）
score = cf.wa.Song(bpm=120)
score.track("pad",  gain_db=-16).notes([(0, "C4", 4.0, 0.5), (0, "E4", 4.0, 0.5), (0, "G4", 4.0, 0.5)])
score.track("bass", gain_db=-9).note(0, "C2", 3.6, 0.75)
score.track("pluck", gain_db=-11).grid(0, 0.5, ["C5", "E5", "G5", "E5"], dur=0.55, vel=0.5)
score.length(beats=24)
film.music = score

film.render("artifacts/demo.mp4")
```

运行 `python film.py`，产物在 `artifacts/`：
MP4 + 联系表（`*.sheet.png`）+ 报告（`*.report.txt`，含 lint / 闪烁 / 响度）。

配乐由运行时内置的渲染模块（`runtime/write_video/write_audio/`）负责，**它只负责渲染**：
曲式、和弦、旋律、配器、音量全部由乐谱显式写出——没有内置风格模板、也没有随机预设，编曲完全由你自己写。
乐谱用 `cf.wa` 构造：`Song` / `Track` / `note` / `notes` / `grid` / `hit` / `hits` / `sidechain` / `fade` / `length`；音高与和声工具在 `cf.wa.theory`（`midi` / `freq` / `chord` / `scale` / `SCALES`）。
该模块是可替换的：换一套渲染实现，只需替换 `runtime/write_video/write_audio/` 并调整 `__init__.py` 的导出。
也可直接给音频文件路径：`film.music = "res/bgm.mp3"`（循环铺满全片）。详见 `knowledge/compose.md`。

配音（edge-tts，需联网）：

```python
v = cf.voice.tts("只用一句话，能做视频吗？", "res/voice/q1.mp3")   # 返回 {path;text;words}
q = s.audio(v, at=0.8)                        # 摆放：自动去静音、响度对齐、配乐闪避
s.text(v["text"], at=q.at, style="subtitle")  # 台词长在画面里
s.text("落版", at=q.word("视频"))              # 精确到词（词时间来自合成）
```

图片卡片：`s.image("res/shot.png", title="真实界面", caption="图 1", width=1180)`
——窗口标题栏 + 卡外说明 + 柔和投影；大图默认 Ken Burns 慢推，`zoom=[(0,1.0,0.5,0.5),(1.6,1.3,0.5,0.45)]` 可自定义推近。

## 示例片

`examples/hello-world/film.py` — 20 秒 1920x1080 完整示例（打字代码卡、slam、逐字浮现、清单、计数器、招牌星海自绘、全片层光尘、配乐与音效对齐）：

```
cd examples/hello-world
python film.py
```

## 两个阶段

1. **策划**：读 `knowledge/planning.md`，把分镜写进项目的 `HANDOFF.md`；
2. **编排**：读 `knowledge/compose.md`，写 `film.py` → 渲染 → 检查 → 交付。

## 目录

- `SKILL.md` — 技能包说明（给 AI 智能体）
- `knowledge/planning.md` — 策划指南
- `knowledge/compose.md` — 编排指南（API 速查 + 自绘菜单 + 常见坑）
- `runtime/write_video/` — 运行时：`film.py` 模型 / `canvas.py` 画布 / `audio.py` 音效 + 配乐渲染 + 混音 / `write_audio/` 配乐渲染模块（可替换） / `voice.py` 配音（edge-tts）/ `render.py` 管线 / `checks.py` 闪烁检测 / `fonts.py` 字体
- `examples/hello-world/` — 示例片

## 常见问题

- **找不到 ffmpeg**：安装或 `WV_FFMPEG` 指定；首次渲染会自动探测可用编码器（结果缓存在临时目录）。
- **配乐报错**：`film.music` 只接受乐谱 `Song` 对象或音频文件路径；报 `render_score 需要 … Song 对象` 说明赋错了类型（正确写法 `film.music = cf.wa.Song(...)`）。
- **找不到可用字体**：安装中文字体或用 `WV_FONT_SANS` 指定。
- **渲染很慢**：先用 `draft=True`（半分辨率）迭代；正式渲染 1080p 约 40~100ms/帧（看内容）。
- **中文输出乱码**：Windows 终端执行 `chcp 65001`；或设 `PYTHONUTF8=1`。

## 尚未支持（路线图）

clip 序列帧与视频取帧、code/chat 专用元素、方框自绘的卡片词、`burst` 的 `behind` 参数。

已补齐（相对初版）：配音与外部音频 `s.audio`（含配乐自动闪避、逐词对齐、edge-tts 助手）、
image 卡片（忠实的窗口框 `title` / 说明 `caption` / 投影 `shadow` / 卡内推近 `zoom`）、
自动 Ken Burns 慢推、`split="word"` 逐词入场。
