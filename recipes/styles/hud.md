# hud · 赛博朋克 HUD · 无人机飞进激光雷达点云城市，扫描波点亮街区，全套飞行 HUD 最后锁定一辆飞车

- 来源: sy-styles-20 styles/08-hud（MIT, 肖雄）
- 层次: sy 实用风格
- 技术: Canvas 2D（点云加色投影 + HUD 图元）
- wv 可移植性: 直接可移植（点云是预生成数组 + fillRect，HUD 全是 line/text/rect）

## 核心手法

- 点云城市：楼=22 排×两侧×4 列的盒子，每层楼板 y+=3.2 沿四面临线采点（step 2.2）、竖向棱 0.8 加密、屋顶描边；部分临街面挂霓虹牌（0.5 步密发光面片）；地面网格+大道车道线。总点数约 5 万，预生成进 PX/PY/PZ/PK 数组。
- 投影：yaw/pitch/roll 三轴旋转 + F=1050 透视，逐点 fillRect（'lighter'），点尺寸按深度分级（<40 → 2×、<90 → 1.4×）。
- 扫描波：scanR=(t-0.9)*260，rev=clamp((scanR-dist)/30) 波过才显形，波前 wave=exp(-((dist-scanR)/10)²) 提亮到白 rgba(230,255,255)；楼体按深度在 cyan→紫间取色（阈值 0.45），霓虹牌 pink/amber/cyan 闪烁 sin(t*8)，地面蓝雾 exp(-z/170)。
- HUD 组件逐个 boot（outCubic 0.35s，0.1/0.35/0.6/0.8/1.0/1.2s 依次）：四角框、罗盘条（±30°、10px/度、15° 一档标数）、ALT/SPD 带刻度、俯仰梯度虚线（随 roll 旋转）、雷达（conic gradient 扫掠 t*2.6，光点在扫过后 2.5rad 内可见）、数据面板逐行打字（0.12s 错峰）。
- 目标锁定：2.8s 起捕获框 220→80 收缩+抖动（sin(t*7.3)*18），6.25s 锁定 outBack 收到 46、转 45°、变粉、画圈，LOCKED 按 sin(t*14) 闪烁，虚线从准星连到目标。
- 飞车目标：14 段红色拖尾 + 航行灯，闪烁 sin(t*12)。
- 后期：glitch 时刻表 [7.65/0.28, 3.35/0.08, 6.22/0.1]——9 条水平切片横移 ±120px + RGB split 8px；每 3px 一条扫描线 alpha 0.18；暗角。
- wv 对应: 图元直绘（rect/line/text/pixel_text）+ 预生成点云；直接可移植

## 母题动画与钩子

- 0.9s 扫描波从无人机荡开点亮全城（3s 内 rev 走完），HUD 分层 boot 到 1.55s 齐活；钩子在 6.25s 目标锁定（lock 音效 + 粉框咬合），7.65s 大 glitch，8.0s RGB 分离标题砸入。
- cues: boot 0.1 / whoosh 1.2 / beep 3.4·4.4·5.4 / lock 6.3 / glitch 7.7 / impact_soft 8.2。

## 签名转场/镜头

- 低空穿城飞行（z=-40+t*46+inOutSine*70 加速，y 38→22 俯冲，7.6s 后 roll 压 0.18 坡度）。
