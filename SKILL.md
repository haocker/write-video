---
name: write-video
description: 用代码编排短视频/MP4（code-to-video）的 Skill。策划分镜 → 写 Python 影片脚本 → 渲染带配乐与音效的成片，自动做 lint、单帧闪烁检测与响度检查。适用于宣传片、片头、快剪、数据/产品介绍、动效动画。
---

# write-video — 用代码编排影片（Skill）

> 本文件是技能入口。AI 智能体读它了解能力与流程，再按需读 `knowledge/` 下的指南动手做片。

写一个 Python 脚本：声明场景与元素（文字、清单、数字、图片卡片、自绘、配音），合成配乐与音效，
`render` 一次生成带声 MP4 —— 无需剪辑软件、无需手工对轨，旁边还输出联系表与检查报告。

- **画面是时间的纯函数**：任何一帧都能单独渲染；同样的脚本、素材与种子得到同样的画面，可复现、可 diff。
- **音效跟着画面命中点**：入场预设自带音效；特殊事件用一张时刻表让画面与声音共用。
- **配乐引擎只做渲染**：曲式、和弦、旋律、配器、音量全部由**乐谱显式写出**（乐谱自己写，AI 生成），没有风格模板、没有随机预设。乐谱用 `wv.wa`（`Song`/`Track`）在脚本里直接写，赋给 `film.music` 即可；例如 `s = wv.wa.Song(bpm=120); s.track("pad").notes([...]); film.music = s`。想要真实采样音源（钢琴/弦乐/管弦）可整体换成 write-audio-pro，见 `knowledge/compose.md`。
- **配音有两条通道**：`wv.voice.tts()`（edge-tts，默认晓晓/云希等中文音色，带逐词时间）或任何现成音频文件；`s.audio` 摆放时自动去首尾静音、响度对齐、说话时配乐自动闪避。
- **招牌画面信手拈来**：`s.draw(fn)` 用画布 API 直接画（光晕、弧线、火花、弹簧、粒子…）。
- **自动检查**：lint（越界/阅读时间/选项拼写…）、单帧闪烁检测（源帧 + 成片回读）、混音响度与真峰值。

只需要 Python 3.8+ 与 FFmpeg，纯 Python 实现、零外部素材依赖。

## 环境

- Python 3.8+，`pip install pillow numpy`；生成配音再加 `pip install edge-tts`（可选，需联网）
- FFmpeg：在 PATH 中，或用环境变量 `WV_FFMPEG` 指定完整路径（编码器自动探测：libx264/nvenc/qsv/amf/mf/openh264）
- 中文字体：Win（微软雅黑）/ macOS（苹方）/ Linux（Noto CJK）自动发现；可用 `WV_FONT_SANS`、`WV_FONT_SANS_BOLD`、`WV_FONT_MONO` 覆盖

## 两个阶段，分开做

1. **策划**（读 `knowledge/planning.md`）：对齐目的、观众、规格、风格、文案，写成项目 `HANDOFF.md`（简报 + 分镜）。**用户确认分镜之前不写影片脚本代码。**
2. **编排**（读 `knowledge/compose.md`）：按 HANDOFF 写 `film.py` → 静帧检查 → 草稿 → 整片渲染 → 读报告自检 → 交付 → 按反馈改版。

运行方式：`python film.py`（脚本把本技能 `runtime/` 加进 `sys.path`，或设置环境变量 `WRITE_VIDEO_RUNTIME`）。

## 分工

- 内容型画面（文字、清单、数字、图片卡片、配音）用**声明元素**，一行一个；
- 每支片至少一处**招牌自绘**：`s.draw(fn)`，`fn(c, t)` 用 canvas 绘制（这支片独有的画面）；
- 跨场景的连续世界用**全片层**：`film.draw(fn, at=0)`。

## 交付自检（读渲染报告）

- lint 无 error；每条 warn 要么修，要么在 HANDOFF 写明保留理由；
- 闪烁 0 事件为佳；有事件时看 `*.flicker.png` 条带定位（转场与 slam/punch 的急变已自动排除）；
- 音频目标约 -16 LUFS、真峰值 ≤ -1.5 dBTP；
- 逐行对照分镜：文案逐字、命中时刻、招牌镜头到位。

## 知识路由

| 需要 | 读 |
|---|---|
| 策划：要定的事、分镜写法、镜头菜单、节奏与文案 | `knowledge/planning.md` |
| 编排：脚本约定、API 速查、检查循环、自绘菜单、常见坑 | `knowledge/compose.md` |

## 目录

- `knowledge/` — 策划与编排指南（先读这两个）
- `runtime/write_video/` — 运行时（纯 Python，可读源码学手艺）
  - `audio.py` — 音效合成 / 配音 / 混音 / 响度 / **配乐渲染**（`render_score`，纯渲染不含模板）
  - `write_audio/` — 配乐渲染模块（乐谱 API：`Song`/`Track`/`theory`）。默认纯合成、零依赖；
    要真实采样音色（钢琴/弦乐/管弦）可整体替换为 write-audio-pro，流程见 `knowledge/compose.md`「换成 write-audio-pro」
- `examples/hello-world/` — 示例片（20 秒，含招牌星海自绘）
- `SKILL.md` / `README.md` — 本文件与安装说明
