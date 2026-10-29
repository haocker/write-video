# flat-zoom · 扁平矢量 · 一镜到底无限推进：手机→屏幕里的城→亮灯的窗→房间→剪辑软件，无缝循环

> wv 样片：已移植（样片 examples/style-ports/flat-zoom/film.py）

- 层次: 实用风格
- 技术: Canvas 2D（矢量插画 + 递归嵌套画布）
- wv 可移植性: 直接可移植（纯 2D 图元 + clip/scale 递归）

## 核心手法

- 无限缩放的骨架：4 层插画各有一个「传送门」矩形——A 手持手机 portal=[850,335,800,450] → B 城市黄昏里一扇亮窗 [1052,612,115,64.7] → C 房间里的笔记本屏 [806.4,420,307.2,172.8] → D 剪辑软件预览窗 [672,118,576,324] → 又是 A。每层 s=portal宽/1920、log=ln(1/s)，TOTAL=Σlog。
- 全局对数推进：t0=0.35 起步，a=0.65 ease-in、d=0.75 ease-out、t1=7.55，v=TOTAL/(a/2+c+d/2) 保证全程匀速俯冲不顿挫；g(t) 分段二次式，累计过每层 log 换层，Z=exp(f)。
- 变换：ctx.setTransform(K0*Z,0,0,K0*Z,K0*Fx*(1-Z),K0*Fy*(1-Z))，其中 Fx=P[0]/(1-L.s)——传送门在缩放下钉在原地。
- 递归绘制 drawLevel：clip 传送门 → scale(L.s) → 画下一层（深度 3 或屏宽 <3px 停）；穿屏前 0.55-0.92 进度内屏幕 UI 用 inOutSine 熔掉。
- 视差：当前满屏层内部用 par(p) 按 Z^-p 缩放子层（天空 0.42 / 远景 0.28 / 中景 0.12），推进时有纵深。
- 填充细节：反应气泡（bezier 心形、+1 气泡）、云 t*18 漂移、鸟 sin(t*10) 扇翅、桥上火车 t*260、时钟 ha=t*0.6/ma=t*6、马克杯蒸汽、桌沿睡觉的猫呼吸 br=1+0.03sin(t*2.4)。
- 调色板：coral #ff6b57 / navy #1d2a5c / teal #2ec4b6 / yellow #ffd166 / cream #fff4e0。
- wv 对应: 图元直绘（rect/ellipse/polygon/gradient/text）+ 递归 clip/scale；直接可移植

## 母题动画与钩子

- 0.35-7.55s 一镜到底匀速穿越 4 层，每个传送门 pop 一次（cues 1.5/3.1/4.9/6.4）；钩子在 7.55s：预览窗里出现的手就是开场那只手，闭环成立，impact_soft+sparkle 收尾。
- 标题 7.6-8.15s outBack(1.6) 弹入「一镜到底」双层描边。
- cues: whoosh_up 0.5 / pop ×4 / impact_soft 7.55 / sparkle 7.7。

## 签名转场/镜头

- 对数缩放穿屏（portal clip + scale），匀速俯冲公式保证循环无缝。
