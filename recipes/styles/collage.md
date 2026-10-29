# collage · 拼贴剪贴 · 牛皮纸上一张张撕下、剪好、贴上：杂志字、网点印刷、拍立得、压纹标签和红印章

> wv 样片：已移植·降级（高度场打光换 texture+投影，样片 examples/style-ports/collage/film.py）

- 层次: 实用风格
- 技术: Canvas 2D（三缓冲物料）+ WebGL 打光 + 12fps 定格
- wv 可移植性: 部分可移植——撕纸/贴纸/印章/网点直接可移植；三缓冲高度场打光（面积光软影/AO/接触硬化）需新渲染 pass

## 核心手法

- 三缓冲物料：每件道具出 3 张 sprite——ALB 反照率、PRP 物性（R=高度 0-16px、G=gloss、B=tooth，编码 ZS=255/16）、LFT 抬升遮罩（LMAX=130px）；合成进整屏缓冲后由 WebGL 打光。
- 打光：法线=高度梯度+纸纹 bump（3 阶 gnoise，扰动 1.1）；面积光软影=20 步地平线遮挡搜索（1 束中心 ×2 + ±0.14rad 两束，lr=0.15 接触硬化）；AO=8 方向×2 半径（2.5/9px）；窗光反射 schlick F=.04+.96(1-ndv)^5，rough=mix(.55,.05,gloss)；gloss>0.97 走金属分支；黄金时刻 gobo=窗前植物叶影（fbmL 拉长）+窗棂影。
- 纸边 outline()：撕边 't'（每 2.2px 一点，amp=6-9 双频噪声+sin taper，band 宽给出白色纤维芯）、剪边 'c'（1-2 个折点）；55% 概率在撕边种纤维短线。
- 网点印刷 halftone：图缩到 150px 宽采样；riso 双色（粉 rgba(255,72,130,.9)/蓝 rgba(36,78,206,.88)，网角 0.26/1.31，错位 ±1.1px，multiply）、mono 新闻纸（step 4.4）；点径=step*0.6*sqrt(k)*(0.92+0.16hash)。
- 道具清单：撕边报纸（4 栏假字+mono 网点图）、剪刀黄圆（r=300、96 点、每 9 点一个折角）、光面杂志页（内页 gloss 0.62、卷角 relief）、riso 印刷、拍立得（泡沫垫 z=5.5）、勒索信标题（8 字各一块芯片，SPEC 表指定 bg/fg/字体/z/gloss/边型）、Dymo 压纹标签（relief 字模糊抬高）、美纹胶带 ×4（conf:true、波形撕头）、打印纸条+订书钉（gloss 1.0 金属）。
- 印章：油墨纹理 inkTexture（n2 噪声调 alpha + 4% 脱色斑，wear 0.3-0.45），multiply 盖进反照率，湿墨 1.6s 内 green 通道 'lighter' 闪光。
- 12fps：frameKey=t*12，t=f12/12，镜头缓推 camZ 1→1.085 + 每帧 hash 抖动 0.9px（定格感）；曝光闪烁 flick=1±0.0175。
- wv 对应: 已移植渲染器（post_cinema 同款 ACES/色散/颗粒后期）+ 需新渲染器（ALB/PRP/LFT 三缓冲高度场打光 pass）；纸片 sprite 手法可直接用 texture 渲染器

## 母题动画与钩子

- 道具按 t0 表飞入（from 偏移 260-420px、frot 旋转、lift 110→0，dur 0.42s outCubic+inOutSine），2.15s 起标题 8 块芯片以 0.21s 间隔啪啪落下；钩子在 6.67s 红印章「印」盖下（stamp 音效 gain 0.75、湿墨闪光），7.0s 蓝色日期章跟上。
- 黄金时刻：7.1-9.5s 窗光方位角 az -2.30→-2.84、仰角 el 0.64→0.38，光色 Lc 变暖，gobo 叶影扫过桌面。
- cues: paper/slap 密集组（0.2-3.9s）/ tape ×4 / click 5.42 / marker ×3 / stamp 6.65·7.0 / swell 7.3。

## 签名转场/镜头

- 微距定机缓推（12fps + 每帧抖动），窗光随时间滑走当转场。
