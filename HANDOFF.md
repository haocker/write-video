# HANDOFF — write-video（通用版）

> 项目状态文件：新会话先读这里。主记忆里只存索引行。

## 状态

- 阶段：**v0.4.0（更名为 write-video / write_video；配乐改为纯渲染，去掉全部风格模板）**。
  - **v0.4.0（本次）**：项目由 `codingfilm` 更名为 **`write-video`**（Python 包 `codingfilm` → `write_video`，
    运行时目录 `runtime/codingfilm/` → `runtime/write_video/`，脚本 `import codingfilm as cf` → `import write_video as cf`）。
    环境变量统一前缀：`CODINGFILM_RUNTIME`→`WRITE_VIDEO_RUNTIME`、`CF_FFMPEG`→`WV_FFMPEG`、
    `CF_FONT_*`→`WV_FONT_*`；临时文件前缀改 `write_video_*`；控制台标签改 `[write-video]`。
    重命名后示例片重渲结果与原版**完全一致**（0 闪烁 / lint 0-0-0 / -16.0 LUFS / TP -2.2 dB）。
  - **v1.3**：配乐从"audio.py 内 numpy 现场合成 + 内置风格模板"改为**可替换的渲染模块**，
    并**抛弃全部内置风格模板**（tech/upbeat/ambient/lofi 及 `build_music` 的自动编曲逻辑全部删除）——
    渲染模块只负责渲染，曲式/和弦/旋律/配器/音量全部由 AI 在影片脚本里用乐谱显式写出（无随机预设）。
    `audio.py` 删除原合成器实现（约 360 行：`_i_*` 音型、`build_music` 骨架、音阶/音名工具），
    改为导出 `render_score(score, duration, gain_db=, lufs=)` 纯渲染函数 + `_read_wav_mono()` 解码助手；
    `mix_tracks()` 的配乐分支改为：`film.music` 是 `write_audio.Song` → `render_score()`，
    是文件路径 → 解码循环铺满。当前渲染实现以源码放在 `runtime/write_video/write_audio/`，**可整体替换**
    （换实现只需替换该目录 + 调整 `write_video/__init__.py` 的导出）。
    `write_video/__init__.py` 导出 `write_audio` 与别名 `wa`（脚本里写 `cf.wa.Song(...)`）。
  - **零回归项**：音效合成（19 种）、配音（edge-tts / 外部音频）、配乐闪避、混音、响度归一全部未动。
  - 验证：示例片《Hello, World!》20s 重渲（乐谱：C 大调 I–V–vi–IV，pad/arp/bass 三声部）——
    **0 闪烁 / lint 0-0-0 / -16.0 LUFS / 真峰值 -2.2 dBTP**；`render_score` 单独验证峰值 0.850、无 nan/inf。
  - v1.1 新增**自定义配乐**（调性/音阶/和弦进行/音型/主旋律）；
  - v1.2 新增第一批**内容通道**：`s.audio` 外部音频/配音（配乐自动闪避 + 逐词对齐 + `cf.voice.tts()` edge-tts 助手）、image 卡片（`title` 窗口框 / `caption` 说明 / `shadow` 投影 / `zoom` 卡内推近）、自动 Ken Burns、`split="word"` 逐词入场。
- 位置：`./`（仓库根目录）
- 验证记录：
  - 示例片《Hello, World!》20s / 1920x1080 / 30fps：渲染 61.5s，**0 闪烁事件、lint 0/0/0、-16.0 LUFS / -2.9 dBTP**；
  - 成片回读扫描（`checks.scan_video`）0 事件；编码质量（qsv q21）与源帧 mean-abs-diff = 1.48/255；
  - 闪烁检测器标定（`_dev/mini5.py`）：平滑运动不误报、单帧闪烁/帧丢失必报、区域排除精确；
  - 关键帧 OCR 验收：文案/位置全部正确（发现并修复计数器双重减 `at` 的 bug）。
  - v1.1 自定义配乐：`_dev/_mtest.py` 35 项断言全通过（默认输出与基线逐字节一致、显式默认参数 == 默认、旋律音高经探针精确命中、端到端 -16.0 LUFS）；`_dev/mini11.py` 真渲染 5s 自定义配乐 dict（0 闪烁 / lint 0 error / -16.0 LUFS）。
  - v1.2 第一批：`_dev/mini12.py` **46 项断言全通过**（拆词/卡片几何/标题栏亮点/阴影变暗/zoom 像素探针/KB 条件/词时间补偿/闪避包络/混音隔离/端到端 draft 0 闪烁）；`_dev/mini13.py` **19 项断言全通过**（edge-tts 真实合成+缓存+词时间、word() 对齐、两段配音端到端 -16.0 LUFS / 0 闪烁）；**零回归**：音频混音与基线逐字节一致，基线 7 帧中 4 帧逐像素一致、3 帧（含图）差异定位为“图片周围投影环，内部 0 差异”。

## 环境事实（本机）

- Python 3.8.5（`C:\Users\10086\AppData\Local\Programs\Python\Python38\python.exe`）
- Pillow 9.3 / numpy 1.24；FFmpeg：`D:\tools\ffmpeg\bin\ffmpeg.exe`（无 libx264；可用 `h264_qsv` / `h264_mf` / `libopenh264`）
- 测试运行器：`_dev/pyrun.bat`（chcp 65001 + PYTHONUTF8=1）；工具调用用 `process_popen` + codepage=65001 + 命令 `/c pyrun.bat <脚本>`

## 结构

- `runtime/write_video/`：`film.py`（模型/预设/排版/lint）· `canvas.py`（画布/缓动/颜色）· `audio.py`（音效/配乐渲染/响度）· `write_audio/`（配乐渲染模块，可替换）· `render.py`（编码管线/报告/条带）· `checks.py`（闪烁检测）· `fonts.py`
- `knowledge/planning.md` · `knowledge/compose.md`；`SKILL.md` · `README.md`
- `examples/hello-world/film.py`（可运行示例片）；`_dev/`（开发测试脚本，可删）

## 已验证的设计要点（改动前先读）

- 超采样 `ss=2` + `Image.reduce(2)` 降采样（LANCZOS 4K 降采样 170ms/帧太慢，reduce=14ms）
- 元素光栅缓存 + 量化 alpha/scale 变换缓存；PNG 存盘必须 `compress_level=1`（默认 798ms → 170ms）
- 动画全靠本地时间（`draw()` 里 `lt = t - at`；**所有子函数接收本地时间**——计数器曾在双重减法上翻车）
- 闪烁检测：320x176 缩略 + 16px 块 + 尖峰判定 + 平移复核（±20px）；排除清单支持全局窗口与区域窗口（转场/slam/punch）
- 音频：ffmpeg `loudnorm` 测响度 → 增益 → tanh 软限幅（ceiling 0.82）→ 再测；-16 LUFS 达标
- 编码器自动探测（libx264→nvenc→qsv→amf→mf→openh264），结果缓存在临时目录
- 配乐：**渲染模块只渲染**，无风格模板。AI 在脚本里用 `cf.wa`（`Song`/`Track`/`note`/`notes`/`grid`/`hit`/`hits`/`sidechain`/`fade`/`length`）显式写出乐谱，赋给 `film.music`；
  `audio.py::render_score(score, duration, gain_db=, lufs=-14)` 调 `Song.render(wav=...)` → `_read_wav_mono()`（0.5L+0.5R 安全下混 / 重采样到 48k）→ 裁剪/补零到 `duration+1s` → 峰值归一 0.85；
  `mix_tracks()` 判类型路由：`write_audio.Song` → 渲染，字符串路径 → 解码循环铺满，`{"score"/"file":..., "gain":dB}` → 带增益。
  音高/和声工具在 `cf.wa`（= `cf.wa.theory`）：`midi`/`freq`/`chord`/`scale`/`resolve_scale`/`SCALES`/`parse_note`/`midi_to_freq`/`midi_to_name`
- 混音结构：music / voice / sfx 三条来源；配音段只压配乐（-8dB，0.15s 前压 / 0.25s 保持 / 0.6s 回升 / 间隔 <1s 不回升），音效不受影响；无配音时与 v1 逐字节一致（回归基线 `_dev/_base_frames.py`）
- 配音管线：解码 → 去首尾静音（-50dB, 0.03s pad）→ 每段响度对齐 -16 LUFS → 边缘 12ms 淡化；**词时间以文件开头为参照，s.audio 自动补偿头部裁剪**（`prepare_voice` 返回 `(buf, lead)`）
- edge-tts（7.x）：`Communicate(..., boundary="WordBoundary")` 才给逐词事件（默认 Sentence）；事件 offset/duration 单位 100ns；Windows 上用 SelectorEventLoop 避免 Proactor 关闭噪音；合成结果缓存 `<path>.json`（key = 文本+音色+参数 md5）
- image 卡片：标题栏 44px / 内边距 14px / 圆角默认 18（与字号同为绝对像素）；投影 = 圆角矩形高斯模糊贴片（黑 α≈100，缓存）；标题栏/边框/说明分层缓存贴片；`zoom` 关键帧用元素本地秒；自动 Ken Burns 条件 = 面积 ≥40% 画面且停留 ≥3s（1.0→1.07，排版期 `_ensure_kb()` 确定）
- 卡内画面（zoom）走独立缓存 `film._zoom_cache`（48 条）避免污染 `_paste_cache`；投影/卡面/前板贴片在 `film._card_sprites`（不随帧清理）

## 路线图

- 下一批：`clip` 序列帧 + 视频取帧（复用 ffmpeg 抽帧，闪烁检测需排除素材区域）、`code`/`chat` 专用元素、方框自绘（draw）的卡片词
- `burst` 的 `behind` 参数未实现（白名单接受但忽略）；`zoom`/`push` 转场代价高（全帧缩放）可优化
- 配音增强：`on=` 收起式跟随、`words` 手工表 lint 校验、长旁白分句助手
- 可考虑：`_dev` 转为正式的 `tests/`（pytest 风格）；打包发布（zip / GitHub）

## 运行方式

```
python examples/hello-world/film.py     # 示例片（~1 分钟）
python _dev/mini5.py                    # 闪烁检测器标定（秒级）
python _dev/mini12.py [--render]        # 第一批：拆词/卡片/推近/配音单测（秒级；--render 加端到端）
python _dev/mini13.py                   # edge-tts 配音集成（需联网，秒级）
python _dev/_base_frames.py save before # 画面/音频零回归基线（改动渲染或混音前先跑）
```
