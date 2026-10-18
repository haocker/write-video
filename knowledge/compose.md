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
| **笔触图元（strokes）** | huashu 笔触移植：`strokes.stroke(c,x,y,ang,ln,wd,col)` 单笔、`strokes.field(...)` 方向场铺笔（网格+角度函数+沸腾色+遮罩）、`strokes.boil(...)` 8fps 沸腾色、`strokes.stroke_path(...)` 路径笔触、`strokes.ribbon(c, pts, width_fn, col, taper=(头,尾))` 可变宽度路径（外粗内细/披帛/书法线，法线偏移拼多边形一次填充）、`strokes.brush(c, pts, width=, tone=, dry=, reveal=)` 毛笔笔触（笔压包络+湿笔芯+连续笔毛飞白，tone 五色焦浓重淡清，reveal 段内揭示进度）、`strokes.steam(...)` 热气、`strokes.mix/hx` 调色。相机变换由调用方处理；点序已内置防蝴蝶结 |
| **风格渲染器（styles 底稿重画）** | huashu「平涂底稿→取色重画」移植：`arr, sc = styles.base(c, 底稿fn, scale=0.5)` 平涂离屏底稿；然后 `styles.dabs/seurat/mosaic/facets/halftone/pixel8/ink/watercolor(c, arr, sc, **参数)` 整幅重画。例：`dabs(cell=13, boil_fps=6)`（印象派，沸腾换种子）、`ink(cell=9)`（底稿画成明暗素描，>=thresh 留白）、`watercolor(cell=50)`（跨 pass alpha_composite 水彩叠色）、`pixel8(cw=160, dither=0.12, dither_mode="ordered", cycle=2)`（Bayer 有序抖动 + 调色板循环流色）。另有 `styles.flowlines(c, arr, sc, cell=24, steps=26, step=7, width=9, a=0.78, field=f(x,y,t)->弧度, classify=f(x,y)->区域key, params={区域: dict(steps/step/width/a/field/palette)}, outline=0, mix=0, palette=)` 流场长笔（蒙克=outline 0 薄涂/梵高=outline 0.85 厚涂+区域色板 mix 0.42；越出区域即停边界干净；必须按区域分遍参数，全图同参数糊成地毯）、`styles.leather(c, shape_fn, 皮色, carve_fn, edge=6, shadow=(0.28,6,(7,5)))` 皮影皮件（shape(d,k) 画白剪影→carve(d,k) 刻纹（离皮边 2×edge 自动护住）→深褐描边→偏移软影+multiply 印染透光；白色部位=另起一件 carve 全刻只留皮边）、`styles.roman(c, arr, sc, cell=12, edge_thresh=34, small=0.5)` 庞贝马赛克 Hausner 简化版（灰浆打底→半错位旋转方块石（四条半边独立抖动+不规则缝）→沿轮廓小石行（底稿 RGB 差边缘上铺小石）→斜面明暗上左亮下右暗；底稿要平涂+粗描边；马赛克字/脸=等宽粗笔画每笔约 2 块石头宽）。全部确定性；单帧 45–600ms，画帧预算内。注意 alpha 叠层要用 `Image.alpha_composite`（ImageDraw 对 RGBA 目标是替换不是混合） |
| **材质纹理 overlay** | `sty.texture(c, kind="paper"/"rock"/"crack"/"drag"/"brush", strength=0.5, seed=0, boil_fps=0, n=None)`——宣纸/画布纹、岩壁浮雕（噪声法向明暗）、龟裂纹（噪声等值线）、drag 竖向油画拖笔（竖向拉长 fbm+soft-light，霍珀：墙必须平刷痕只能若有若无）、brush 长条水粉刷痕（60-300px/宽 6-22/黑白各半/overlay，马蒂斯，n=笔痕密度默认约 2600），multiply/明暗合成保饱和（lighter/低 alpha 洗白底色，01_cave 火光坑）；`boil_fps` 纹理按 N fps 沸腾（换种子），0=静态缓存。渲染器之后调用，叠在整幅上 |
| **软钟 + 长影（达利）** | `sty.softclock(c, cx, cy, r=88, sag=0.8, fold=-34, flare=-0.12, t=None, hand_speed=5)`——软钟：圆盘局部坐标沿映射采样（v<=fold 躺台面 y 压缩 0.30，v>fold 垂下外摊+中央下垂高斯+sin 波纹），外框/表盘/12 刻度/指针/折线高光同一映射；sag 1.2s 内 0.1→1.4 才看得出淌，flare 负值=软布外摊、正值=冰淇淋筒。`sty.longshadow(c, sils, yg, kx=0.85, ky=0.55, alpha=0.55, blur=1.5, horizon=None)`——剪影 AFFINE 投到着地线 yg（x'=x+kx(yg-y)，y'=yg-ky(yg-y) 往右后方躺），sils 是 f(d,k) 画白剪影（同一张离屏，重叠处不加深），horizon 只留地面部分；影子必须画在墙/桌**下面**（底版拆层），kx=0.85+0.6·easeInOut(lt/1.2) 影子明显变长 |
| **深度模糊 DoF** | `film.post = lambda img, t: sty.post_dof(img, depth, focus=0.3, max_coc=14, bands=6)`——按深度图分层 blur，越离焦越糊（微距景深/3d 感）。`depth` 是 (h,w) 数组（0=焦点处，1=最远）或预设 `"bottom"`（下近上远）/"top"/"center"（中心实四周虚）；自定义深度在 scene_fn 里按物体位置画深度图传进来 |
| **图标系统（Tabler）** | `wv.icons.char("brand-github")` 按名取字符；名字表见仓库 `docs/icons.html`（可搜索）。`icon="tabler:名字"` 或已知 tabler 名直接可用；未知名 lint warn。`s.text(..., font="tabler")` 画大图标（纯图标元素，中文另起元素）。绘制内 `c.text(字符, x, y, size, col, alpha=, font="tabler")` |

**坑：三款正文字体（伟君黑/标题黑/喜脉体）缺符号字形**——`→`（U+2192）、`✓`（U+2713）等符号在正文里会**静默渲染成空白**（PIL 对缺字形无提示）；`·`（U+00B7）有。符号/箭头一律用 `wv.icons.char("arrow-right")`（Tabler 3472 个）或 `font="tabler"`，或在正文里换用 `·`/`/` 分隔。运行时已内置覆盖检查：Canvas.text 首次遇到缺字形字符会打印 lint 告警（`fonts.warn_missing_glyphs`，fontTools cmap 精确比对）。
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

### 骨骼动画（`wv.rig`）

骨骼层级 + FK + 关键帧轨道，皮肤为 2.5D 图元挂骨骼（球体/胶囊/多边形）。参考实现见 `rig-demo/film.py`（Q 版角色走路/挥手/待机）。

```python
from write_video.rig import Bone, Rig, Track, capsule, xform

rig = Rig((root_x, root_y), [              # root=髋部世界锚点
    Bone("root", None, 0, 0),              # rest=相对父骨静止角；y 向下：-90=上 90=下
    Bone("spine", "root", 113, -90),
    Bone("head", "neck", 80, 0),
    Bone("arm_l", "spine", 44, 190, off_w=(-63, -19)),   # off_w=相对父骨末端的世界固定偏移
    ...])
IDLE = Track({"spine": [(0, 0), (1.2, 2.5), (2.4, 0)]}, dur=2.4, loop=True)
pose = {**IDLE.at(t)}                      # 多轨叠加：后者按骨覆盖
xf = rig.solve(pose, root=(x, y))          # → {bone: (origin, end, world_deg, z)}
capsule(cv, xf["arm_l"][0], xf["arm_l"][1], r, skin, skin_sh, skin_hi)   # 2.5D 胶囊
cv.polygon(xform(pts, head_center, tilt), ...)   # 局部点集 → 旋转+平移
```

**坑：皮肤旋转只用姿态偏移（tilt），骨骼世界角是骨骼指向**——head 骨世界角恒 ≈ −90（指向上），脸/头发按世界角旋转会整体转 90°；tilt = world_deg − rest 链（或 world_deg + 90 对竖直脊柱）。鞋子同理（shin 世界角 −90）。

**装配层（PNG 部件挂骨）**：`SpriteSkin` 把透明 PNG 部件装到骨骼上（cutout/纸片人皮肤），每帧按骨骼变换贴图（PIL rotate+expand，pivot 对准骨骼 origin）。JSON 装配文件一体存取：`rig, skin, tracks = wv.rig.load_rig("boy.rig.json")`（结构：root/bones/skin.parts/tracks，`save_rig` 对称写回）。

```json
"skin": {"parts": [
  {"bone": "arm_l", "png": "part_arm_l.png", "z": 2, "pivot": [11, 0], "rot_off": -90}]}
```

**装配坑三条**：① 部件以"所属骨骼 origin"为锚渲染——部件图里 pivot 那个像素对准骨骼 origin，输出统一缩放到骨骼尺度；② 悬挂部件（臂/腿）内容朝下画时 `rot_off=-90`（图像旋转后内容指向 = 90+deg，要对准骨骼方向需 deg=world−90）；朝上内容（头挂竖直脊柱）`rot_off=+90`；③ SpriteSkin 全程按画布设备像素（cv.ss）换算——设计像素 origin/offset 乘 ss、部件 px 乘 scale×ss，混用会整体缩一半且错位。部件自带的脖子画进 head 部件（随头倾斜），画进 torso 会在头倾斜时露边。

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

**坑：`film.music` 必须拿到 `wa.Song` 对象本身。** `sc.render(lufs=…)` 的返回值是渲染报告 dict，把它赋给 `film.music` 会被混音器静默跳过（成片只剩音效、没有配乐）。响度交给混音器处理：`film.music = {"score": song, "gain": -2.0}`（render_score 按 -14 LUFS 渲 + gain dB）。

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

### 旋律写法（作曲指南，优先级高于风格描述）

创作旋律、动机、线条时统一遵循。写谱前先定旋律骨架（动机 + 节奏型 + 和声进行），像分镜一样先想后写。

#### 一、调式与和声约束

1. 不默认直接使用自然大调与主大三和弦作为唯一基础，优先根据曲风选择适配调式：五声调式、自然小调、和声小调、布鲁斯调式等都可选用。
2. 不长期停留在一级主和弦内循环，避免旋律完全依附主和弦骨架音展开。
3. 和弦进行避免简单 I-IV-V 无限循环，合理安排和弦色彩、悬置与解决；悬疑、氛围感曲目可以刻意延迟解决、保留不协和张力。
4. 旋律音逻辑：强拍可以使用和弦内音，弱拍、过渡位置合理安排经过音、辅助音、邻音，不允许整段旋律全部由和弦骨架音构成。

#### 二、动机约束（核心，规避流水线同质化）

1. 动机长度控制在 2-4 音为主，不使用单一动机原样不间断复制循环；动机发展优先采用移位、反向、节奏拉伸、增减装饰音等变体手法。
2. 禁止连续重复主和弦上下行套路动机，如 1353、1351、3513 这类短句持续使用。
3. 避免长段平直同向音阶线条，连续同向级进不超过 4 个音，尽量及时转向。

#### 三、旋律线条与音域约束

1. 旋律线条混合搭配拱型、山谷型、小幅锯齿波动、长线条缓慢级进等形态，不全程只用单一走向。
2. 旋律大跳之后尽量反向级进收敛，防止线条散乱、难以演唱；根据人声定位控制整体音域宽度。
3. 乐句终止不要习惯性全部落在主音，可合理停在调式其他稳定或悬置音，形成呼吸感与乐句之间的牵引力。

#### 四、节奏约束

1. 不要通篇使用均匀均分节奏，搭配附点、切分、长短音对比、休止留白丰富节奏层次。
2. 歌词类旋律贴合语言自然语调与断句逻辑，重音匹配语言重点，不生硬套固定强弱模板。
3. 根据情绪选择节拍，不安、诡异题材可以使用不对称节拍；叙事类曲目预留乐句呼吸停顿。

#### 五、装饰音与技法约束

1. 装饰音（倚音、滑音、波音等）按需使用，不堆砌；五声乡土旋律多用滑音、倚音，少强行加入半音。
2. 悬疑、诡异氛围可以适度使用小二度邻音摩擦、缓慢半音滑行；抒情叙事曲目控制不协和音密度。

#### 六、自检（完成旋律后自查）

1. 是否大量只使用和弦骨架音，缺少经过音、邻音？
2. 是否存在套路动机不间断循环？
3. 是否连续长段同向音阶上行或下行？
4. 是否每一个乐句结尾都落在主音？
5. 大跳之后有没有对应的收敛处理？
6. 选用的调式色彩是否和目标曲风匹配？

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
15. **像素量化会把大面积低 alpha 叠色压成硬边亮块**：暗场里 `rect/polygon` 的 `alpha≈0.05` 大色块（如镜球光锥）经 pixel8 就近取色后变成一整块高亮矩形，比不画更糟。做法：用小面积光点/明确图元（环绕光斑、落点椭圆）表现发光，不用大面积极淡叠色。整片就是拍子同步闪烁时（夜店/电子），用 `film.flicker_exclude(0, 片长)` 整片声明。
16. **pixel8 的 cw 必须同时整除画布宽高，否则整片发糊**：cw=140 时 cell=13.71px 非整数 → 2x 超采样画布上格子落在半像素（27/28px 交错）→ `reduce(2)` 平均下采样时 2x2 块跨格边界 → 每个像素边出现混合过渡带（灰色晕边）。做法：cell 取设计像素整数且两轴整除——1920x1080 用 cw=160（cell 12px：1920/12、1080/12 都整除，2x 下 24px 偶数格，reduce 平均完全在格内=精确）。另：`film.render(path, quality=16)` 可提高编码质量（数值越小质量越高，默认 19）。
17. **pixel8 下的灰边与文字糊碎（两类混色）**：① 底稿降采样必须用 `Image.BOX`（每格严格取自己区域的均值，零跨界）——BILINEAR 滤波窗口跨 2 个格，即使元素完全落格，边界格也混进邻格颜色（红+蓝、金+天蓝混出灰，调色板里的中灰成了混合色最近邻 → 精灵四周灰边）；② PIL 字体过量化器必然糊碎（抗锯齿渐变+曲线字形被格心采样撕开）——文字用 `bc.pixel_text(s, x, y, px=12, color, align)`（5x7 点阵字，每字素=整格矩形，BOX 平均恒纯色，天生锐利；px 取量化格倍数）。配套：所有精灵/元素坐标吸附量化格（移动按格跳，正是 8-bit 正统），小字素细节（6px）落半格会混色，但暖色系内混色安全。

## 一点透视布局（舞台/室内镜头）

俯视平铺的镜头（夜店、教室、房间）最容易"贴纸感"，因为所有物体底边等高、无纵深。配方：

- 定消失点 `VP=(cx, 视平线y)` 与墙脚线：地板从墙脚画到画面底，纵线全部连向 VP，横线用 `y = 墙脚 + 深 * (i/N)**2`（i 大靠观众，间距递增）。
- 每条底边统一落地：同一深度的物体底边 y 相同；更近的物体底边更低。舞台做成 riser：顶面梯形（后窄前宽）+ 竖直前脸。
- 台面/桌面上的圆形（唱盘、盘子）压扁成椭圆 `ellipse(x, y, rx, ry≈0.3rx)`；立式物体（音箱）保持正面矩形。
- 人群按排缩放：远排 `r` 小、`body_h` 小、底边高；近排 `r` 大、贴底裁切。t 用 `film.flicker_exclude(0, 片长)` 声明的整片闪烁除外。
- **绘制顺序决定遮挡**：先画会给主体遮挡的东西——激光/光锥先画，舞台与人物后画自然挡住下段，光束就不会糊住主角脸。

## 定格动画与运动模糊（frame_key / mb）

- **定格动画帧去重**：全部内容按 N fps 步进时（像素风/黏土/8-bit），给 Film 声明 `frame_key=lambda t: int(t * N)`——key 相同的帧直接复用上一帧编码字节，只渲染独立帧。12fps 步进 30fps 成片提速约 2.5x。**前提是所有内容都步进**（有连续运动的内容会被冻住）。
- **子帧运动模糊**：`film.render(path, mb=6)`——每帧渲染 6 个子帧按快门角展开平均（`shutter=0.5` 默认 180° 快门），快速运镜的拖影/跨步进边界的双影都是真实快门行为。代价：渲染时间 ×mb。定格动画配合 frame_key 用 `mb=2, shutter=0`（或不开）。
- 两者都来自 sy-styles-20 的移植（render.js 的 frameKey 去重 + --mb 子帧叠加）。

## 后处理（film.post：DoF + 电影感 + VHS + bloom + 行列位移 + 金色度）

```python
film.post = lambda img, t: sty.post_cinema(
    sty.post_vhs(sty.post_bloom(img, strength=0.55, threshold=0.75), t,
                 shift=2.5, scan=0.18, noise=0.05, chroma=2.5),
    t, vignette=0.35, grain=0.04, ca=0.6, contrast=1.05, sat=1.05)
```

- `sty.post_dof(img, depth, focus=, max_coc=, bands=6)`：按深度图分层 blur，越离焦越糊。链式组合：DoF/bloom → VHS → warp/gold → cinema（颗粒/暗角在最上）。
- `sty.post_bloom(img, strength=0.6, threshold=0.75)`：亮部提取 → 两级高斯 → screen 回叠（shinkai/synthwave 的 glow），明暗交界与霓虹出辉光。
- `sty.post_vhs(img, t, shift=3, scan=0.22, noise=0.07, chroma=3.5)`：VHS 录像带后期（huashu 26 + sy 12 融合）——RGB 通道分离（错位随时间摆动+偶发跳变）、跟踪噪声带下滚撕扯、扫描线、噪点，按帧号种子确定性。
- `sty.post_warp(img, t, row_amp=(9,4), row_f=(0.012,0.031), col_amp=6, col_f=0.009, speed=1)`：整幅行列正弦位移（munch「整个世界在流动」）——人、猫、桌一起晃，比单独画摇摆线便宜。行位移基准配方 `9·sin(y·.012+4.2t)+4·sin(y·.031-6t)`；边缘钳位拉伸不露黑边。
- `sty.post_gold(img, t, recolor=1.0, sweep=0.62, sweep_t0=0, sweep_dur=1.15, glint=10, mask=None, bright=0)`：金色度遮罩（gothic/klimt）——逐像素识别金色（(r-b-70)/50·(g-b-30)/40·(r-140)/40 连乘，羊皮纸自动排除，凡金色的地方自动被扫到）；recolor 金箔重着色（fbm+横向打磨纹，lo/mid/hi 三色插值）、sweep 斜向**匀速**扫光（inOut 缓动会提前扫出金区）、glint 遮罩内四角星闪烁。mask 可显式传 (h,w) 遮罩或 `bright=阈值` 用亮部。
- `sty.post_cinema(img, t, ...)`：色散（ca，0 关）/曝光（expo）/对比/饱和/lift-gain 调色/暗角（vignette）/确定性颗粒（grain 按帧号种子，同一 t 永远同图）。numpy 实现，约 20ms/帧。
- 材质纹理用 `sty.texture(c, kind, strength, ...)`（在 scene_fn 里、渲染器之后调用），详见上方速查表。
- film.post 在**输出分辨率**上跑（render_frame 缩放之后），单帧检查、联系表、闪烁检测看到的都是后处理后的画面（所见即所得）。
- **VHS/错位类后期只能打在平滑大色块上**（霓虹/渐变）：高频笔触纹理（dabs cell 小）+ 通道错位=全帧 RGB 碎化， huashu 的 VHS 也只用于平滑霓虹场景。写实时开 vignette+grain+轻 ca+DoF；扁平插画/像素风少开（污染平涂）。

## 性能（本机参考）

- 1080p、ss=2、文字类场景约 40~60ms/帧；带招牌自绘约 60~100ms/帧；draft（半分辨率）约 1/3。
- 600 帧（20 秒）整片：约 1 分钟（含音频与编码；示例片实测 58 秒）。
- 想更快：`ss=1`（画质略降）、减少同屏元素、招牌自绘里少用大范围 alpha 图元。
