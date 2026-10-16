# morph · 形变动画 · 上万光点在三维空间漂浮，一次次变形：想法→灯泡→作品→播放键→爆款，每次卷起气流

- 来源: sy-styles-20 styles/06-morph（MIT, 肖雄）
- 层次: sy 实用风格
- 技术: Canvas 2D（CPU 粒子 + sprite 加色合成）
- wv 可移植性: 直接可移植（粒子采样、curl 场、glow 合成全是 2D 代码；量大时可换 GPU 点渲染）

## 核心手法

- 形状采样 samplePoints：形状画在 1000×520 离屏画布，每 2px 采 alpha>128 的点；38% 取边缘点（±3px 邻域检测），其余内部随机；z 深度 ±depth/2（0.16-0.22）。形状=900 300px 粗体字（想法/作品/爆款）+ 灯泡（arc+梯形+3 道螺纹，destination-out 抠灯丝）+ 播放键（roundRect 460×380 圆角 90 抠三角）。
- 初始星云：双臂旋星系，r=pow(rnd,0.6)*4.2，臂差 PI，绕臂角 r*1.25，z 压扁 0.55。
- 时序：T_FORM=[0.55,2.0,3.45,4.9,6.35]，DUR=1.0；错峰左→右：t0=T_FORM[k]+(目标x+5)*0.045，每粒按 inOutCubic 独立插值。
- 气流：过渡期 swirl=sin(PI*u)*1.35 乘 curl 场（nz=sin·cos 伪噪声的有限差分，e=0.08），平时 idle 微颤 0.012sin(t*1.3+phase)。
- 落定：弹性过冲 exp(-st*7)*sin(st*22)*0.04 缩放；终章爆款 burst=exp(-((t-6.95)/0.25)²) 径向炸开 0.25*SIZE。
- 绘制：径向渐变 sprite 按 5 色 PAL 量化（v-v%8）着色，'lighter' 叠加；颜色按 x 位置在 PAL/PAL2 间渐变（hx=(x+5)/10）。
- 合成：粒子先画在独立画布，主画布 3 遍叠回（blur 14/alpha .85 + blur 4/alpha .6 + 原图），径向渐变底 #141a3a→#05060f。
- 相机：yaw=0.35sin(t*0.55)-0.1、pitch=0.08sin(t*0.4) 慢摆，camZ=7.2、F=1150；深度模糊 |d-camZ|/2.6 调大 sprite 半径、降 alpha。
- wv 对应: 图元直绘（canvas 粒子 sprite + 'lighter' glow 合成）；粒子量大时可换 GPU 点渲染器，手法完全一致

## 母题动画与钩子

- 每 1.45s 一次形变（5 个形状），每次卷起 curl 气流并左→右扫过；钩子在 6.95s：爆款成形瞬间径向 burst + impact_soft/sparkle。
- cues: swell 0.3 / morph ×5（每个成形+0.05）/ impact_soft 6.95 / sparkle 7.0。

## 签名转场/镜头

- 慢速摆动环绕（yaw ±0.35rad、pitch ±0.08），让粒子团读作空间里的雕塑。
