# 解说动画语法 · wv 版（syntax.py）

- 位置: `runtime/write_video/motion.py`（MO 缓动/时间库）+ `runtime/write_video/syntax.py`（Cam 相机 + 转场 + 8 scaffold）
- 移植口径: 镜头语法/节奏/版式/对位按示范片实测参数移植；具体素材（截图/角色帧库）为用户内容，scaffold 用程序化占位

## 三层结构

1. **MO 缓动/时间库**（motion.py，纯函数）：`seg/at/step/beat/on_beat` 时间片、`smooth(6t⁵−15t⁴+10t³)/sine_in_out/cubic/quint/expo/back_out/elastic` 缓动、`bezier()`（牛顿迭代）、`spring()`（SwiftUI 三分支）、`spring_hz/settle`（频率/衰减）、`lagged/wiggle/there_and_back`、`invert()`（缓动反查，t3 标注用）、`slam_k/slam`（砸入 1.55→0.94→1.0）、`PULSE` 时长表（punch 0.28 / pan 0.30 / slam 0.17 / push 0.9 / glide 0.7 / pull 1.1）。
2. **Cam 世界相机**（syntax.py）：`Cam(c, x, y, z, r)` 画布包装——图元级矢量重画（所有点先变换再交给画布，缩放转场不放大位图）；`cam_track(base, events, t)` 镜头动作表（push/pull/glide/to/punch/pan/slam/shake/cut，相机只由 t 算）；`cam_zlerp` 对数缩放（线性插值禁用）、`cam_cover`（≈1101/r）、`cam_anchor/push_to`；`layer(d)` 视差；`cam_drift` 手持微漂。
3. **转场**（帧级离屏合成）：`transition(c, kind, fa, fb, lt_a, lt_b, u, arg)` + `seq_scene(seqs)` 段落合成器——A/B 都按各自时间全量矢量重画（live）；kind: cut/cross/push/bands/smash/zoom/lens。

## 8 种语法 scaffold（每段一块全屏画面，签名 `fn(cv, lt, spec)`）

| scaffold | 语法 | spec 要点 | 一句话核心 |
|---|---|---|---|
| `y1_scale` | Kurzgesagt 扁平科普 | title/node/sats/cam_events | 中心物（名字哈希→形状/色，双色分面）+卫星节点+连线脉冲，相机在尺度间穿行 |
| `y2_desk` | Vox 拼贴 | items/threads/hl/circle | 真实材料桌面（纸纹+冲印件+红线索绳+荧光笔+红圈），相机滑、元素 12fps 顿 |
| `y3_board` | 白板手绘 RSA | blocks（text/lines）/accent | 说一句写一句，相机跟论证走，最后拉远看全图；马克笔只在画时入画 |
| `y4_story` | 故事型简笔角色 | shots（mid/insert/react/wide/close） | 口播是主角：姿势 0.1s 快切后定住（squash 回弹），反应特写闭嘴+汗滴 |
| `y5_type` | 动态文字 | bg/ink/main/sub/tag/ghost | 主词踩重音砸入（springHz 2.2/10），辅句槽升起，画面永远一个焦点 |
| `t1_math` | 3Blue1Brown | concepts（grid/write/morph/neurons/indicate） | 纯黑底+高饱和细线，Transform 把上一个概念直接变成下一个（morph 点列对齐）；分场淡出：下一个概念开始时旧概念整体 0.45s 退场，同屏只有一层 |
| `t2_keynote` | 发布会界面 | block（title/number/shot） | 一屏一件事，光斑底，名词数字口播说到时落定（expo_out 计数） |
| `t3_chart` | 财经图表 | chart（bar/line）/event/number | 先坐标系再数据最后只标一件事；折线按 x smooth 推进，标注在线头经过事件点时弹出 |

## 用法

```python
from write_video import syntax as sx

SEQS = [
    {"t0": 0.0, "dur": 2.5, "fn": lambda cv, lt: sx.t2_keynote(cv, lt, title_spec), "trans": "cut"},
    {"t0": 2.5, "dur": 5.0, "fn": lambda cv, lt: sx.y1_scale(cv, lt, y1_spec), "trans": "push",
     "trans_dur": 0.45},
    {"t0": 7.5, "dur": 5.0, "fn": lambda cv, lt: sx.y2_desk(cv, lt, y2_spec), "trans": "bands"},
    # ...
]
film.scene(0, total).draw(sx.seq_scene(SEQS), at=0, enter="none")
```

示范片：`/workspace/syntax-demo/film.py`（8 段 41s，走完全部语法+转场）。

## 节奏与对位（移植的 12 条跨语法规律核心）

- 镜头只由时间决定，场景按相机矢量重画（Cam 图元级重画保证放大 60 倍不糊）
- 缩放用 `cam_zlerp` 对数插值；穿进半径 r 的开口倍数 ≥ `cam_cover(r) ≈ 1101/r`
- 揭开帧对齐拍点：段起点 = 小节线 − 揭开点 × 转场时长（`mo.on_beat`；zoom .55 / 色带 .6 / push .58）
- 两层帧率：相机平滑、元素步进（拼贴 12fps、角色 24fps，`mo.step(t, fps)`）
- 入场慢退场快落定后停（入场 0.3-0.4s、退场 0.18s、停 ≥0.5s）
- 一屏一个焦点；颜色=概念（语义色 ≤4 种）
- 动在事件上，镜头有来有回（push 后用 pull/glide/切换开，别连着三镜往里推）

## 坑（移植时踩过的）

- **PIL 半透明文字**：文字 glyph 直接写 source alpha、与底混合失败，拍平后变实心——Canvas.text 已修（alpha<1 时渲临时层再按 alpha 合成）
- **帧图模式**：Film 渲染路径的 img 是 RGB，`alpha_composite` 只在 RGBA 下可用——离屏合成按 `img.mode == "RGBA"` 判定
- **smash/zoom 的 settle 用位图近似**（0.2-0.6s 窗口内可接受）；长推镜头一律走 Cam 矢量重画
- **t2 大数字必须 max_width**（超出 bx.w·0.86 等比缩字号），数字等宽排布防抖
- **y1 ghost/标签类低 α 文字**同理走临时层合成
- **t1 连线圆周到圆周**（两端沿连线方向回退神经元半径），连圆心会穿模
- **y2 暗角是径向**（中心干净四角压暗），平涂 alpha 会把画面整体压灰
- **y3 马克笔 tip 是世界坐标**，画屏幕空间马克笔前先 `k.pt()` 变换
- **相框版式判定**：素材宽不到画宽 60% 连续超 2 镜 = 不合格；截图等比放、满幅优先
- 撕纸转场/每图弹入/纸纹逐帧抖——模板网站做法，5 支样片 0 次出现，禁用
