# handdrawn · 逐帧手绘 · 铅笔起稿、水彩晕染的绘本小屋，一秒重画 12 张，镜头一动才发现整幅画是立体的

- 来源: sy-styles-20 styles/01-handdrawn（MIT, 肖雄）
- 层次: sy 实用风格
- 技术: WebGL（光线步进 G-buffer + 风格化 pass）+ Canvas 2D 手绘叠加
- wv 可移植性: 部分可移植——手绘笔触、逐字书写、烟雾、纸飞机直接可移植；G-buffer→水彩/线稿的风格化管线需新渲染器

## 核心手法

- 管线：pass1 光线步进出 G-buffer（3 张 MRT：法线+线性深度 RGBA16F / 材质 id NEAREST / 光照+AO+阴影），pass2 风格化；另有 2D 叠加层按通道编码：R=蓝铅笔稿、G=石墨笔触、B=烟。
- 纸：纸高 paperH = fbm2(dc*.21)*.65 + vnoise2(dc*.95)*.35，法线扰动 ±.17，tooth=smoothstep(.3,.7,ph) 参与所有笔触调制；画幅是干笔刷椭圆晕边（中心 (600,330)、半径 640×380）+ fbm 边缘抖动，设计空间 1216×684。
- 水彩：每材质 id 有 washStart + fbm2(dc*.011+id*2.3) 抖动 ±.36；湿润期 wet=exp(-age/.55)，干边 rim（8 方向 id 突变、半径 3.4px）+ 湿前沿 front（0-0.45s 一条深边扫过），颗粒 gran=vnoise2(dc*.9)；阴影是 4.0s 后上的第二层 glaze（按 dc.x/1216*.35 横扫）。
- 石墨线稿：4 方向采样深度/法线/id 突变两圈（rA=1.2px、rB=0.72px，随压感 pres=.55+.8noise 和距离缩放），第二笔 sketchy 偏移 boil()；深阴影里 45° 排线（方向 hd=(.62,.78)，u=dot(dc,hd)/4.4+噪声断线）。
- 手绘笔触 polyDraw：按弧长重采样 step=5px，压感 0.55+0.45*n1，双频抖动（38K 长波 + 9K 短波带 frameKey 相位），两端收细，支持 overshoot（蓝稿端点超出 0.1-0.45）；每 12fps 帧换一次 boil 相位（frameKey=t*12，t=f12/12）。
- 物件：小屋 sdBox（屋脊下垂 q.y+=.05(1-q.x²/1.95)…，整体倾斜 q.x-=.018q.y），大树=胶囊干+10 个 smin(k=.32) 球团+fbm3 位移 .34，松树 4 层参差锥台，栅栏桩距 0.24，小路 pathX=.35+1.05sin((z-.9)*.33)+.08(z-.9)。
- 坑：SwiftShader 下着色器分支全跑，G-buffer/风格化都分 10 条 scissor 带 + gl.finish() 逐带渲；2D 画布要 willReadFrequently。
- wv 对应: 手绘管线（canvas strokes: curve/jitter/smooth）+ 需新渲染器（G-buffer→水彩/干边/排线风格化 pass，含 boil、纸纹、颗粒）

## 母题动画与钩子

- 0-1.6s 蓝稿按 STROKES 表逐笔画（每笔 0.06-0.22s），1.3s 起水彩逐材质 flood，3.6-4.1s 石墨细节上线，4.0s 阴影 glaze；蓝稿 3.4-4.6s 淡到 0.42 保留。
- 钩子在 4.75s：镜头从正面切到环绕，观众才发现画是 3D；6.2-8.6s 落日（太阳 [-0.55,0.62,0.58]→[-0.85,0.24,-0.5]），背光树叶 rimL 发光、窗玻璃转金。
- 纸飞机 Catmull-Rom 10 键 4.9-10.4s 绕树一圈，banking=clamp(侧向加速度*9,±0.9)+0.05sin(t*7)；烟囱 24 团烟（4.5s 起、life 3.2s、r=0.08+0.15a）；字幕 7.75s 逐字写出（每字 0.085s）+ 手绘下划线，签名 4.9s 逐字。
- cues: pencil 0.2 / scribble 1.3 / swell 2.6 / whoosh 4.75 / whoosh_up 7.0 / pencil 7.75。

## 签名转场/镜头

- 正面定机 → 双轨道键环绕（ORB0→ORB1 插值，pivot [0.5,-0.5]，FL=1.72，y 抬 0.12sin(u·PI)），配 12fps 定格 + 运动模糊。
