# write-video · 阶段 2：编排影片

## 开工

1. 读项目 HANDOFF.md（简报、分镜、招牌镜头、素材、决定、待定）。涉及核心信息、事实、规格的待定项先问；已确认风格下的版面与动效细节自行判断。
2. 装好环境（Python + pillow/numpy + ffmpeg）；确认影片脚本能 `import write_video`（把本技能 `runtime/` 加进 `sys.path`，或设 `WRITE_VIDEO_RUNTIME` 环境变量）。要配音就再 `pip install edge-tts`（见「配音」）。
3. 检查素材是否齐（背景图/logo 等先准备好，路径用项目内相对路径或绝对路径）。
4. 可先跑一遍 `examples/hello-world/film.py` 熟悉链路与产出。

## 脚本约定

- 分镜一行 ↔ 脚本一段，段首注释写分镜编号和时间；时间用全局秒；文案逐字照抄分镜。
- 共享时刻用变量或元素引用（`brand.at`、`.done`）；招牌画面的事件写成一张表（`beats`），画面和音效都读它。
- 动画就是时间 t 的函数；自绘只依赖 `t` 与固定种子（`c.rand(i)`），**不要累积状态**——否则任意帧渲染与整片不一致，会闪。
- 招牌自绘超过一屏就抽成独立函数，脚本只留编排。

### 骨架

```python
# film.py — <项目名>：分镜见同目录 HANDOFF.md（#编号对应下面各段）
import os, sys
sys.path.insert(0, r"<技能目录>/runtime")     # 或设置环境变量 WRITE_VIDEO_RUNTIME
import write_video as wv

film = wv.Film(1920, 1080, duration=8, theme="midnight", bpm=120)

# #1 0–3 钩子：品牌名砸下（slam 提前 0.3 秒起跳）
s1 = film.scene(0, 3)
brand = s1.text("品牌名", at=1.0, style="hero", enter="slam")
film.sfx("riser", at=0.0, dur=1.0, gain=-8)          # 蓄力，正好结束在落地
s1.text("一句需求，做成片", at=1.7, style="subtitle", split="char")

# #2 3–6 【招牌】光环收拢迸火花（时刻表：画面与音效共用）
beats = {"close": 1.2}
s2 = film.scene(3, 6, transition="wipe")

def shot(c, t):
    p = c.progress(0.1, beats["close"], "easeInOutCubic")
    if p <= 0:
        return
    c.glow(960, 470, 300, "accent", 0.22 * p)
    c.arc(960, 470, 200, -90, -90 + 360 * p, "accent", 8)

s2.draw(shot, at=3.0)
s2.sfx("impact", 3.0 + beats["close"], gain=-6)

# #3 6–8 收尾
film.scene(6, 8, transition="fade").text("行动号召", at=6.3, style="subtitle")

if __name__ == "__main__":
    film.render("artifacts/项目名.mp4")
```

## 分工：声明元素装内容，自绘做招牌

- **内容型用声明元素**：文字、清单、数字、图片——入场、音效、排版、不抖这些手艺已经在库里，不要再手画一遍。
- **独特型用自绘**：这支片才有的画面（示意动画、图表、招牌动效）；`c` 就是画布，`c.box(元素)` 能对准声明元素。
- **全片层**：跨场景不随转场移动的东西（光尘、水印、进度条）挂在 `film.draw(fn, at=0)` 上。

## 声明元素速查

| 方法 | 要点 |
|---|---|
| `s.text(文字, at=, style=, enter=, size=, color=, bold=, font=, x=, y=, pos=, split=, stagger=, line_gap=, align=)` | `**强调**` → 强调色；`\n` 分行；`font="mono"` 等宽；超宽自动缩小（记 info）。注意：等宽字体不含中文，代码块中的中文必须用 `font="sans"` 单独显示（见常见坑 #12） |
| `s.text(…)` 的 `split` 取 `"char"/"word"/"line"`：逐字/逐词/逐行入场（word：拉丁按词、中文按字、标点并入前一词；空格占据节拍） |
| `s.list(条目数组, at=, icon=, stagger=, size=, gap=)` | 逐条滑入；icon：内置 check / circle-check / star / rocket / arrow / dot / warn / heart / plus / cross / spark，或 `tabler:名字`（Tabler 图标 5070 个，见下） |
| **笔触图元（strokes）** | huashu 笔触移植：`strokes.stroke(c,x,y,ang,ln,wd,col)` 单笔、`strokes.field(...)` 方向场铺笔（网格+角度函数+沸腾色+遮罩）、`strokes.boil(...)` 8fps 沸腾色、`strokes.stroke_path(...)` 路径笔触、`strokes.steam(...)` 热气、`strokes.mix/hx` 调色。相机变换由调用方处理；点序已内置防蝴蝶结 |
| **风格渲染器（styles 第一期 8 种）** | huashu「平涂底稿→取色重画」移植：`arr, sc = styles.base(c, 底稿fn, scale=0.5)` 平涂离屏底稿；然后 `styles.dabs/seurat/mosaic/facets/halftone/pixel8/ink/watercolor(c, arr, sc, **参数)` 整幅重画。例：`dabs(cell=13, boil_fps=6)`（印象派，沸腾换种子）、`ink(cell=9)`（底稿画成明暗素描，>=thresh 留白）、`watercolor(cell=50)`（跨 pass alpha_composite 水彩叠色）。全部确定性；单帧 45–600ms，画帧预算内。注意 alpha 叠层要用 `Image.alpha_composite`（ImageDraw 对 RGBA 目标是替换不是混合） |
| **图标系统（Tabler）** | `wv.icons.char("brand-github")` 按名取字符；名字表见仓库 `docs/icons.html`（可搜索）。`icon="tabler:名字"` 或已知 tabler 名直接可用；未知名 lint warn。`s.text(..., font="tabler")` 画大图标（纯图标元素，中文另起元素）。绘制内 `c.text(字符, x, y, size, col, alpha=, font="tabler")` |
| `s.counter(从, 到, at=, dur=1.0, format="%d", size=, pos=)` | 滚动 + 自动滴答与叮；`.done` 是结束秒 |
| `s.image(路径, at=, width=, height=, radius=, title=, caption=, shadow=, bg=, border=, zoom=)` | 只给宽或高则等比。**卡片词**：`title` 加窗口标题栏（卡内顶端，三点+标题+分隔线，自动配卡面）、`caption` 卡外下方说明（caption 样式）、`bg`/`border` 卡面与描边（`True` = 主题色）、`shadow` 柔和投影（默认：卡片与小图开、四角透明图与全屏图自动关）。`zoom` 卡内推近：数值或关键帧 `[(本地秒, 倍数, cx, cy[, 缓动]), ...]`（cx/cy 是 0~1 画面坐标）；占画面 ≥40% 且停留 ≥3s 时**默认自动 Ken Burns**（1.0→1.07 慢推，写了 zoom 则关闭） |
| `s.draw(fn, at=, width=, height=, bg=, border=, radius=, x=, y=)` | 给了 width/height 是方框元素（参与排版、自动裁剪）；不给是整屏画布 |
| `s.burst("sparkle"/"confetti", on=元素, at=, radius=)` | 定点爆发 |
| `s.audio(来源, at=, gain=, text=, words=, on=)` | **配音/旁白/录音**（见「配音」）：来源 = 音频文件路径或 `{path;text;words}`（`wv.voice.tts()` 的返回值直接传）；返回 `.at`（开口）/`.done`（说完）/`.duration`/`.text`/`.words`/`.word("词")`；自动去首尾静音、响度对齐 -16 LUFS；说话时配乐自动 -8dB 闪避 |

通用选项：`at` 命中时刻；`out` 消失时刻；`opacity`；`sfx=False` 关自动音效；
`sfx=[(0.4,"pop"),(1.2,"success",-8)]` 自定义音效列表（相对 at 的秒数）。

### 入场预设（at = 命中时刻）

| enter | 时长 | at 含义 | 动作 | 自动音效 |
|---|---|---|---|---|
| fade | 0.5 | 开始出现 | 淡入 | 无 |
| rise | 0.6 | 开始出现 | 淡入 + 上浮 | swish（轻） |
| slide | 0.5 | 开始出现 | 从左滑入（清单默认） | swish（轻） |
| pop | 0.5 | 开始出现 | 弹出过冲（hero 默认） | pop |
| punch | 0.35 | 完全可见 | 放大快速收回（快剪） | impact（轻） |
| slam | 0.3 起跳 + 0.3 余震 | 落地 | 从大加速砸下 + 落地挤压 + 震屏 | impact |
| type | 每字 0.045s | 第一个字 | 打字 + 光标 | typing |
| none | — | — | 无 | 无 |

同名音效 60ms 内去重；subtitle/body/caption 的音效额外 -6dB。

### 转场

`cut`（默认，0s）/ `fade`（0.5s 交叉淡化）/ `flash`（0.4s 白闪）/ `wipe`（0.5s 从左擦除）/
`push`（0.5s 推出）/ `zoom`（0.5s 缩放）。
转场占用**新场景的开头 D 秒**；转场窗口与 slam/punch 的急变在闪烁检测中自动排除。

### 排版

- 不给 `y` 的元素参与自动排版：`pos` 含 top/bottom 贴安全区，其余在中部；**时间重叠且水平相交的元素按声明顺序上下堆叠**；时间不重叠的依次替换同一位置。
- 给了 `x`/`y` 的元素不参与排版（自己负责位置）。
- 安全区边距 = 0.085 × 短边。

### 主题与颜色

- `theme="midnight"/"punch"/"light"`，或传字典覆盖（base/colors/styles/bg）。
- 颜色可写调色板名：`fg / soft / dim / accent / emph / panel / line / bg / white`，或 `"#RRGGBB"`、`(r,g,b)`。
- `bg`：默认深色渐晕；`"accent"` 强调色底（文字自动反色）；`"#RRGGBB"`；图片路径（cover 铺满）+ `{"image":..., "grain":3}`。

## 声音

### 音效（`film.sfx(名, at, gain=, dur=, pitch=)`，at 是全局秒）

impact / punch / pop / swish / swipe / whoosh / click / tick / ding / chime / success /
error / riser / glitch / sparkle / notification / typing / bassdrop / shutter

- `gain` 单位 dB（-6 = 轻一半）；`dur` 覆盖时长；`pitch` 半音数。
- 对齐手法：命中前放 `riser`（dur = 到命中的间隔），命中点放 `impact`；`at` 就是那个命中的数。

### 配乐（只渲染，不含模板）

配乐**没有风格模板**——引擎只做渲染，编曲由你（AI）自己写。用 `wv.wa` 构造一份乐谱，赋给 `film.music`：

```python
score = wv.wa.Song(bpm=120, beats_per_bar=4, tail=0.5)
pad   = score.track("pad",   name="pad",   gain_db=-16.0, seed=1)
bass  = score.track("bass",  name="bass",  gain_db=-9.0)
pluck = score.track("pluck", name="arp",   gain_db=-11.0, pan=0.12)

MAJ = wv.wa.resolve_scale("major")            # 音阶：半音偏移序列
def chord(deg):                               # 级数 → 音名列表
    k = len(MAJ)
    return [60 + MAJ[i % k] + 12 * (i // k) for i in (deg, deg + 2, deg + 4)]

PROG = (0, 4, 5, 3)                           # I–V–vi–IV
for bi in range(bars):
    b0, ch = bi * 4.0, [wv.wa.theory.midi_to_name(m) for m in chord(PROG[bi % 4])]
    for n in ch:
        pad.note(b0, n, 4.05, 0.5)            # 长音垫底
    pluck.grid(b0, 0.5, [ch[0], ch[1], ch[2], ch[1]], dur=0.55, vel=0.5)   # 琶音
    bass.note(b0, trans(ch[0], -24), 1.8, 0.75)
    bass.note(b0 + 2.0, trans(ch[0], -24), 1.8, 0.6)

score.length(beats=duration / (60.0 / 120))   # 铺满全片
score.fade(out_seconds=2.5)                   # 片尾淡出
film.music = score
```

**乐谱 API（`wv.wa`）**

| 用途 | 写法 |
|---|---|
| 建曲 | `Song(bpm=, beats_per_bar=4, tail=0.5)`；`spb` = 每秒拍数 |
| 加声部 | `song.track(乐器名, gain_db=, pan=, seed=)` — 乐器名见下 |
| 单音 / 多音 | `t.note(拍, "C4", 时长拍, 力度0~1)` / `t.notes([(拍,"C4",拍,力度), ...])` |
| 网格 | `t.grid(起始拍, 步长拍, ["C4","E4",None,...], dur=, vel=)` — `None` 休止 |
| 打击 | `t.hit(拍, 力度)` / `t.hits([(拍,力度), ...])` |
| 长度 / 收尾 | `song.length(beats=/seconds=/bars=)`；`song.fade(in_seconds=, out_seconds=)` |
| 闪避 | `song.sidechain(source_track 或 时间表, ...)` — 让某声部给另一声部让路 |
| 渲染（自动） | 引擎内部调 `song.render(wav=..., lufs=-14)`；你不用手动渲染 |

乐器（`track()` 第一个参数）：`bass` / `pluck` / `bell` / `rhodes`（音高类）；`kick` / `hat` / `clap` / `snare` / `crash`（打击类）；`pad`（和声垫）；`vinyl`（噪纹）；`riser`（上行）；另有 19 种 SFX 名。

音高与和声工具（`wv.wa` 顶层 / `wv.wa.theory`）：`midi("A3")→57`、`freq(...)`、`chord(...)`、`scale(...)`、`resolve_scale("major"/"minor"/"dorian"/...)`、`SCALES`、`parse_note`、`midi_to_freq`、`midi_to_name`。

**要点**

- 曲式、和弦、旋律、配器、音量**全部显式写出**——没有默认风格、没有随机预设；同样的乐谱逐样本可复现。
- 时长要 ≥ 影片时长：用 `song.length(beats=duration / spb)` 铺满，或让乐谱自然长于影片（引擎按影片长度裁剪/补零到 `duration + 1s`）。
- 引擎渲染结果经 `audio.py` 的 `render_score()` 解码为 48kHz 单声道，峰值归一到 0.85，再进混音链；配音期间配乐自动 -8dB 闪避（与音效一致）。
- 也可不用引擎：`film.music = {"score": song, "gain": -3}`（乐谱 + 增益dB），或 `film.music = "res/bgm.mp3"`（现成音频循环铺满全片）。
- 参考实现：`examples/hello-world/film.py` 的 `make_score()`（C 大调 I–V–vi–IV、pad/arp/bass 三声部、片尾落主和弦）。

#### 换成 write-audio-pro（真实采样音源）

默认模块 `runtime/write_video/write_audio/` 是**纯合成**（零依赖）。要钢琴/弦乐/管弦这类**真实采样**音色，
整体换成 [write-audio-pro](https://github.com/haocker/write-audio-pro) 即可，**两步、不改代码**：

```bash
pip install numpy pretty_midi mido
sudo apt install fluidsynth musescore-general-soundfont     # macOS: brew install fluid-synth

cd runtime/write_video
mv write_audio write_audio.simple                            # 备份原实现
cp -r /path/to/write-audio-pro-skill/runtime/write_audio_pro/. write_audio/
```

目录名保持 `write_audio`（包内换成 pro 的实现），`wv.wa` 自动指向 pro；想切回：
`rm -rf write_audio && mv write_audio.simple write_audio`。

**乐谱要改的地方**：

| 项 | 合成版（默认） | pro |
|---|---|---|
| 乐器名 | `pad` / `pluck` / `bass` / `bell` / `rhodes` / 打击类 | GM 真实乐器 `piano` / `strings` / `cello` …（见 pro 的 `GM` / `ENSEMBLES`） |
| `note` 力度 | 0–1 | **0–127** |
| 专有方法 | `grid` / `hit` / `hits` / `sidechain` | 无，用 `notes` + 声部编排代替 |
| 额外能力 | — | `reverb` 混响、`pad_chord` 等 |

```python
score = wv.wa.Song(bpm=66)
score.track("piano",   gain_db=0) .notes([(0, "A4", 2, 80), (2, "C5", 2, 80)])
score.track("strings", gain_db=-6).notes([(0, "A3", 4, 70), (4, "F3", 4, 70)])
score.length(bars=8)
film.music = score                                           # film.music 接口不变
```

混音链、响度归一、配音闪避都不用动——`render_score()` 按 `Song.render(wav=...)` 读回音频，两个模块都兼容。
（pro 渲染依赖 FluidSynth + SoundFont，首次渲染会先跑 MIDI，比纯合成慢。）

### 配音（edge-tts → `s.audio`）

配音只认音频文件：`wv.voice.tts()` 生成的、真人录的、别人给的 mp3 都一样，走同一条 `s.audio` 通道进片。

```python
import write_video as wv

v1 = wv.voice.tts("只用一句话，能做视频吗？", "/res/voice/q1.mp3")   # 晓晓（默认女声）
q = s.audio(v1, at=0.8)                        # v1 直接传：path/text/words 全带上
s.text(v1["text"], at=q.at, style="subtitle")  # 台词长在画面里（不做字幕条）
s.text("品牌名", at=q.done + 0.5, style="hero", enter="slam")

v2 = wv.voice.tts("能。一句代码，一支短片。", "/res/voice/a1.mp3", voice="云希", rate=5)
a = s.audio(v2, at=q.done + 0.4)
s.text("那句代码", at=a.word("代码"))            # 精确到词（词时间来自合成）
```

- 依赖与联网：`pip install edge-tts`；合成走在线服务，**需要联网**。合成结果缓存在 `<路径>.json`（同文/同音色/同参数不重复联网）。
- 音色：别名 `晓晓`（默认）/`晓伊`/`云希`/`云健`/`云扬`/`晓北`（东北）/`晓妮`（陕西）/`粤语女`/`粤语男`/`台湾女`/`台湾男`；也可直接写完整音色名（`wv.voice.list_voices("zh")` 看全部）。`rate`/`volume` 写 `-10` 或 `"-10%"`。
- 词时间：返回的 `words = [[词, 开头秒, 时长], ...]`（相对文件开头）；`q.word("词"[, 第几次])` 得到该词的成片秒，直接写进画面元素的 `at`。词表缺失时按字数估算（lint 记 info）；找不到的词记 error 级 lint。
- 时间手法：下一句写 `at=q.done + 0.3`；画面文字写 `at=q.at`；要让元素跟着声音出现就写 `on=q`。
- 响度：每段自动对齐 -16 LUFS（不同音色/来源能差 5dB 以上），`gain` 再微调。说话期间配乐自动压低 8dB（开口前 0.15s 压、说完保持 0.25s、0.6s 回升；两段间隔 <1s 中间不回升），音效不受影响。
- lint：文件找不到/读不出/整段静音 → error（拒绝渲染）；两段重叠、超出片尾 → warn；越过场景结尾 → info（旁白跨镜头是正常用法）。
- 不用 edge-tts 也行：任何 TTS 或真人录音的 mp3 走同一通道；`words` 可手写 `[(词, 开头秒, 时长), ...]`。

## 自绘菜单（canvas 速查）

`fn(c, t)`：t 是元素本地秒（= 全局秒 − at）。c 上可用的绘制方法：

`rect(x,y,w,h, fill=, outline=, width=, radius=, alpha=)`、`line(x1,y1,x2,y2,...)`、`lines(点数组,...)`、
`polygon(点数组,...)`、`circle(x,y,r,...)`、`ellipse(x,y,rx,ry,...)`、`arc(x,y,r,start,end,...)`（0°=三点钟，顺时针）、
`text(s,x,y,size=,color=,bold=,align=,valign=,alpha=,font=,line_gap=)`、`text_width(s,size,...)`、
`image(path,x,y,w=,h=,alpha=,radius=)`、`glow(x,y,r,color=,alpha=)`。

**手绘三参数**（`lines` / `polygon` 通用，2D 动漫/手绘感的核心）：

- `curve=True` — Catmull-Rom 过点样条（skia cubicTo），折线变圆润曲线，放大无棱角。
- `jitter=幅度(设计像素)` — 手绘抖动：点沿法向低频颤动 + 描边变宽压感（round cap 逐段调制），`seed` 固定形状。fill/outline 一致抖。
- `smooth=` — 缺省跟随 `curve or jitter>0`；显式 `smooth=False` 得"抖而不圆"的机械手绘边（列车/楼群/机械体）。

例：人物发丝 `c.lines(pts, width=2.0, curve=True, jitter=0.9, seed=43)`；城市天际线 `c.polygon(pts, fill=col, curve=False, jitter=1.4, smooth=False)`。

装饰级效果（常用于全片层 `film.draw` 为每帧加质感）：

- `gradient(x, y, w, h, colors, direction="radial", alpha=1.0)` — 渐变填充。
  `colors=[(位置0~1, 颜色名), ...]`；`direction` 取 `"radial"` / `"vertical"` / `"horizontal"`。
  不传 x/y/w/h 则铺满全画布。
- `vignette(radius=0.65, power=1.8, color=(0,0,0), alpha=0.55)` — 边缘暗角。
  `radius` 暗角起始半径比例，`power` 衰减指数。
- `grid(spacing=80, color="soft", alpha=0.05, width=1.0)` — 科技网格背景线。
- `scanlines(spacing=3, alpha=0.08)` — 水平扫描线（复古 CRT 效果）。

工具：`c.width/height`、`c.progress(a,b,"easeOutCubic")`、`c.rand(i)`（固定种子）、`c.spring(t)`、`c.decay(t)`、

工具：`c.width/height`、`c.progress(a,b,"easeOutCubic")`、`c.rand(i)`（固定种子）、`c.spring(t)`、`c.decay(t)`、
`c.wiggle(t,freq,amp,seed)`、`c.lerp`、`c.box(元素)`、`c.color(色,alpha)`、`c.ctx.time`（全局秒）。

缓动名：linear / easeInQuad / easeOutQuad / easeInOutQuad / easeInCubic / easeOutCubic / easeInOutCubic /
easeInSine / easeOutSine / easeInOutSine / easeInExpo / easeOutExpo / easeInBack / easeOutBack / easeInOutBack。

八种基本手法（每个只演示一种，按内容组合，不要整块照抄）：

```python
# ① 光晕 + 辉光笔：先垫柔光，再用宽的半透明笔垫底
s.draw(lambda c, t: (c.glow(960, 540, 260, "accent", 0.25),
                     c.lines([(560, 640), (760, 440), (960, 560), (1160, 380), (1360, 480)], "accent", 14, alpha=0.14),
                     c.lines([(560, 640), (760, 440), (960, 560), (1160, 380), (1360, 480)], "accent", 3)))
```

```python
# ② 画出来：线条按进度生长，笔尖带一颗亮点
def shot(c, t):
    p = c.progress(0.2, 1.4, "easeInOutCubic")
    if p <= 0:
        return
    c.arc(960, 540, 200, -90, -90 + 360 * p, "accent", 4)
    a = math.radians(-90 + 360 * p)
    c.circle(960 + 200 * math.cos(a), 540 + 200 * math.sin(a), 6, fill="fg")
```

```python
# ③ 火花：解析式（位置是“事件后第几秒”的函数），种子固定
HIT = 1.0
def shot(c, t):
    age = t - HIT
    if age < 0 or age > 0.8:
        return
    fade = 1 - age / 0.8
    c.glow(960, 540, 160 * fade, "accent", 0.5 * fade)
    for i in range(24):
        ang = c.rand(i) * 6.283
        d = (40 + c.rand(i + 100) * 220) * (1 - math.exp(-5 * age))
        x, y = 960 + math.cos(ang) * d, 540 + math.sin(ang) * d
        c.line(x, y, x - math.cos(ang) * 20 * fade, y - math.sin(ang) * 20 * fade,
               "accent", 3, alpha=fade)
```

```python
# ④ 运动：弹簧过冲（出现）、衰减振荡（落地挤压）、平滑抖动（受击）
def shot(c, t):
    sc = c.spring(t - 0.2)                 # 从 0 弹到 1 的过冲
    if sc <= 0.001:
        return
    sq = 1 + 0.15 * c.decay(t - 1.2, 3, 9) # 落地挤压
    dx = c.wiggle(t, 24, 10)               # 受击平滑抖动
    R = 120 * sc
    c.rect(960 + dx - R, 540 - R * sq, R * 2, R * 2 * sq, fill="accent", radius=36)
```

```python
# ⑤ 逐字显露：用文字切片（能画多少就画多少），淡字垫底保证骨架可读
def shot(c, t):
    label = "画面"
    c.text(label, 960, 540, 220, "accent", alpha=0.14)   # 淡字垫底
    n = int(len(label) * c.progress(0.2, 1.2, "easeInOutCubic"))
    c.text(label[:n], 960, 540, 220, "accent")
```

```python
# ⑥ 取景：同一个画面函数，整屏画一份，再缩小、平移、时间错开放到别处
def orbit(c, t, ox, oy, k):
    c.glow(ox, oy, 200 * k, "accent", 0.3)
    c.circle(ox + 160 * math.sin(t * 2) * k, oy, 40 * k, fill="accent")

def shot(c, t):
    orbit(c, t, 500, 300, 1.0)
    orbit(c, t + 0.5, 1500, 800, 0.4)
```

```python
# ⑦ 事件表：画面按表里的时刻画，音效按同一张表配；改节奏只改表
beats = {"hits": [0.6, 1.1, 1.6], "done": 2.4}

def shot(c, t):
    for i, h in enumerate(beats["hits"]):
        k = c.progress(h, h + 0.4, "easeOutBack")
        if k > 0:
            c.circle(760 + i * 100, 540, 24 * k, fill="accent")
    if t >= beats["done"]:
        c.text("完成", 960, 660, 48, "accent")

s2.draw(shot, at=3.0)
for h in beats["hits"]:                       # 音效读同一张表（换算成全局秒）
    s2.sfx("pop", 3.0 + h, gain=-8)
s2.sfx("success", 3.0 + beats["done"])
```

```python
# ⑧ 对准声明元素：c.box 拿到它的排版矩形（不含它自己的入场位移）
code = s2.text('var radius = 12;', at=0.3, size=46, font="mono")

def shot(c, t):
    b = c.box(code)
    a = c.progress(0.8, 1.2)
    if a <= 0:
        return
    c.rect(b[0] - 12, b[1] - 8, b[2] + 24, b[3] + 16, outline="accent", width=3, radius=12, alpha=a)
    c.text("改这里", b[0] + b[2] / 2, b[1] - 40, 32, "accent", alpha=a)
```

**从轮子学手艺**：运行时的卡片/预设/自绘内核就在 `runtime/write_video/` 里（`canvas.py`/`film.py`），遇到难题先读它。

## 检查循环

1. **静帧**：`film.frame(2.2, "check/f2.2.png")` 看关键帧（大字、招牌、转场后）；几何/颜色问题用像素量，不靠猜。
2. **联系表**：`film.sheet("check/sheet.png")` 一眼看全片节奏。
3. **草稿**：`film.render("artifacts/demo.mp4", draft=True, flicker=False)` 半分辨率快速看动态（约 1/3 时间）。
4. **整片**：`film.render("artifacts/demo.mp4")` → 读报告：lint / flicker / audio / 耗时。
5. **回读**：`from write_video import checks, render; checks.scan_video("artifacts/demo.mp4", render.find_ffmpeg())`——成片再扫一次闪。

## 交付前自检

> 色板一致性、一屏一个焦点、数字口径、审片纪律，见 `knowledge/craft.md`（蒸馏自 huashu-art-motion）。

- lint 无 error；warn 要么修要么记录保留理由；info 看一眼（阅读时间不足、自动缩小等）。
- flicker 没有未解释的事件；有事件先看 `*.flicker.png` 条带定位（突然出现/消失？入场透明度错误？）。
- 逐行对照分镜：场景齐全、文案逐字、命中时刻对、招牌到位。
- 音频约 -16 LUFS、真峰值 ≤ -1.5 dBTP（报告里有）；静音属正常。
- 报告里的耗时按本机如实说，不当作所有机器的承诺。

## 改版

- 上一版产物移到 `artifacts/vN/`（MP4 + 脚本副本 + HANDOFF），再小改重渲。
- 「闪一下/抖一下」当真问题：先看条带定位，别先改动效。「太快」→ 延长停留或减字；「看不清」→ 加字号、延长、查对比度；「太吵」→ 调 gain 或换配乐。

## 常见坑（真实踩过）

1. 自绘里别用累积状态或 `random.random()`——必须 `c.rand(i)`，只依赖 t；否则逐帧渲染不一致 → 闪烁告警。
2. 场景首尾相接；转场占新场景开头；不要重叠场景。
3. `slam` 不要放在场景第 0 秒（要 0.3 秒起跳）。
4. 自绘别手画大渐变/多层大圆——用 `c.glow`（自带缓存）；大范围图元越多越慢。
5. 突然出现/消失的元素会触发闪烁检测——用 `enter` 或 alpha 渐入渐出。
6. 中文缺字/方块：用 `WV_FONT_SANS` 指定字体文件（见常见坑 #12 关于 `font="mono"` 的特例）。
7. `typing`、清单、slam 这类音效已自动生成，不用手写；自定义用 `sfx=[...]`。
8. 想彻底无缝的连续镜头：把绘制挂在**全片层** `film.draw(fn, at=0)`（场景内的整屏自绘会在场景结束时被淡出）。
9. 渲染前先 `film.lint()`；有 error（找不到图片/未知音效）会拒绝渲染。
10. 单帧 PNG 已做加速；整片速度看报告的 `timings.frames`。
11. 配音 mp3 手工替换后要删掉同名 `.json` 缓存（否则词时间还是旧的）；`wv.voice.tts()` 换参数时会自动重合成。
12. **`font="mono"` 不含中文**：系统自带的等宽字体（DejaVu Sans Mono / Consolas / Menlo）均为纯拉丁字体，代码块里的中文注释、字符串会显示为豆腐块。做法：把中文从代码行拆出来，用 `font="sans"` 单独显示；或设环境变量 `WV_FONT_MONO` 指向含中文的等宽字体（如 Noto Sans Mono CJK）。
13. **`cut` 场景的自绘要显式 `enter="none"`**：draw 元素默认继承样式的 `enter="fade"`（0.5s 淡入），切镜首帧只有主题底色 → 观感"切过去黑一下才出现内容"。正反打等硬切场景：`s.draw(fn, at=…, enter="none")`。fade/flash 转场的场景不用改（转场本身盖住淡入）。
14. **闪烁误报两类**：① `cut` 切镜帧（runtime 已自动排除场景边界 ±1 帧）；② 高速平移物体（列车/ fast pan，平坦色块使运动补偿失败）——用 `film.flicker_exclude(t0, t1[, x, y, w, h])` 声明排除窗口，别为过关把运镜放慢。

## 性能（本机参考）

- 1080p、ss=2、文字类场景约 40~60ms/帧；带招牌自绘约 60~100ms/帧；draft（半分辨率）约 1/3。
- 600 帧（20 秒）整片：约 1 分钟（含音频与编码；示例片实测 58 秒）。
- 想更快：`ss=1`（画质略降）、减少同屏元素、招牌自绘里少用大范围 alpha 图元。
