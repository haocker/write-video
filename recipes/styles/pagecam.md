# pagecam · 真实页面 2.5D 推镜 · 把真实剪辑软件拆成悬浮图层

> wv 样片：已移植·降级（CSS 3D 换手写透视+PIL 单应+DOF 量化，样片 examples/style-ports/pagecam/film.py）

- 层次: 实用风格
- 技术: DOM/CSS 3D（无 WebGL、无 Canvas 渲染器；纯 DOM + perspective/transform/filter）
- wv 可移植性: 部分可移植——面板/时间线/光标可画成 canvas 图层；CSS 3D 透视与逐层景深需手写投影矩阵 + post_dof 近似

## 核心手法
- "真实页面"＝DOM 搭的剪辑软件：5 块面板（顶栏/媒体库/预览监视器/属性检查器/时间线），perspective:2200px，面板是圆角深色卡＋顶部红黄绿圆点＋内描边高光＋box-shadow 0 40px 90px。
- **2.5D 拆层**：面板先 spring(k:120,c:16) 逐个飞入（错 0.08s，从 z-600），再按 Z={top:30, lib:-70, mon:0, ins:-40, tl:90} 分离到不同深度 sep·2.2。
- 相机 rotateX(8°·sep) rotateY(-19°·sep) 揭示层间纵深；结束时收回平面推进监视器。
- **景深切换**：逐面板 blur=|Z[id]-focus|·0.045px，焦点 3-6s 停在时间线，5.8s 起 0.8s 内 rack focus 到监视器——这是"像真实镜头"的关键。
- 光标演示：SVG 箭头沿 lerp 路径 p0(900,760)→AI 按钮(1440,26)→时间线(760,740)，3.75s 点击（按下 scale .85＋紫色 ring 120px 扩散淡出），按钮 scale .94 反馈。
- 素材飞上时间线：8 条 clip spring(k:180,c:14) 错 0.12s 从 (+220,-260) 落下（缩放 .6→1），clip 是缩略图重复的胶片条；字幕条 spring(k:220,c:13) 逐个落下；音乐波形 clipPath inset 从左到右揭示；红色播放头 #ff4d6d 前进。
- 监视器真的在播：75 张预载帧从 5.4s 起按 15fps 播放，时间码 00:00:SS:FF 格式；未播放时压暗叠白色播放三角。
- 坑：动画全部用 spring/cue 的确定性时间函数（render(t) 契约），CSS 里只留静态样式，避免真实时间依赖。

wv 对应: 图元直绘（rect/text/gradient 画面板）＋ 仿射/透视变换模拟 2.5D 推镜（手写 3D 矩阵或降级为 skew+scale）＋ post_dof（分层 blur）；CSS transition/filter 语义需转成逐帧确定性绘制

## 母题动画与钩子
- 节拍：0.2s whoosh 面板飞入 → 1.2-2.6s 拆层＋相机倾斜 → **3.75s 光标点下「AI 一键成片」（钩子）**→ 3.95-5.2s 素材逐条飞上时间线 → 5.4s 监视器开播 → 6.5s 相机推进监视器（scale→1.55）→ 8.4s 标题。
- 音效：whoosh/swell/click/sparkle/pop×3/zoom/chime。

## 签名转场/镜头
拆层推镜一镜到底；结尾"镜头推进监视器屏幕"是转场钩子，可与 03-flat-vector 的无限推进衔接。
