# isometric · 等轴 2.5D · 悬浮小城十秒长出来：道路自己画、楼房弹起、车跑云走，太阳落山灯一盏盏亮

> wv 样片：已移植（样片 examples/style-ports/isometric/film.py（国风变体 forbidden_city.film.py））

- 层次: 实用风格
- 技术: Canvas 2D（正交投影 box 渲染器）
- wv 可移植性: 直接可移植（全部是 2D 多边形/渐变图元，投影在 JS 里算）

## 核心手法

- 正交投影 P(x,y,z)：绕 AZ 旋转 x/y，屏幕 y = ry*SC*sin(EL) - z*SC*cos(EL)；AZ=PI/4、EL=0.52、SC=50。所有物体都是轴对齐盒子 box(x0,y0,z0,x1,y1,z1)：4 个侧面（法线朝向检测 nry>0.001 才画）+ 顶面 + 白色顶棱描边。
- 光：单方向太阳 shadeFace=0.62+0.42*max(0,dot(n,SUN))，再乘面向系数 (0.86+0.14*nry)；全局色调 tint 按 DUSK/NIGHT 在 DAYT #ffffff → DUSKT #ffb38a → NIGHTT #6068c0 间混，夜里整体乘 (1-NIGHT*0.42)。
- 影：每个物件脚印 4 点沿 -SUN 方向投出（sx=-SUN[0]/SUN[2]），8 点凸包填 #1d2a52 alpha 0.16，clip 在地板块内，NIGHT>0.6 消失。
- 楼：14×14 格，路在 x∈{4,9}、y∈{6}；层数=1+floor(hash*3.5 + max(0,6-离心距)*1.1*hash)，中心高外圈低，9 色盘 PALB，塔楼固定 13 层。窗户按面宽 1.6 列/层高 0.32 网格排布，夜里 hs<0.82 的亮（#bfe9ff/#ffd88a/#ffe9c2，闪烁 sin(T*3+hs*40)），白天 #a9cdea 加白色反光斜条。
- 夜灯 glow：点光源收进 lights[]，画到半分辨率 glow 画布（radial gradient，'lighter'），再 blur(3px) 叠回主画布。
- 母题物件：摩天轮 R=1.5、轮心高 1.8、12 轿厢 ang=t*0.5、轮圈 #ff7aa2；12 辆车沿路循环（v=1.1-1.8，前灯/尾灯/光锥都进 lights[]）；路灯沿路每 2 格一根；公园 26 棵树。
- wv 对应: 图元直绘（rect/polygon/gradient/text）——正交投影、凸包阴影、glow 合成都是普通 2D 代码，直接可移植

## 母题动画与钩子

- 建城：0.9s 起楼房从中心向外一圈圈弹起（t0=0.9+离心距*0.14+hash*0.25，spring(k:210,c:15) 带 1.12 过冲），路先画（outCubic inv(0.35,1.25) 沿长度揭示+虚线），2.6s 车流汇入。
- 钩子在 4.4-7.6s：DUSK=inOutSine((t-4.4)/1.6)、NIGHT=inOutSine((t-5.9)/1.6)，太阳从 [-0.6,-0.35,0.72] 沉到 [-0.95,0.1,0.28]，窗户和路灯按各自 hash 阈值一盏盏亮起，90 颗星浮现。
- cues: whoosh 0.35 / blocks 1.0·1.6·2.2（三波楼）/ swell 5.2 / chime 6.4。

## 签名转场/镜头

- 开场从画布下方 spring(k:90,c:13) 落入，3.2s 起缓慢环绕 AZ+0.55rad 并推近 SC 76→84。
