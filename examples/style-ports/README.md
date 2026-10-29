# wv 风格移植台账

12/16 张全部完成（3 张 3D 依赖卡永久不移植，handdrawn 此前已移植）。
每张卡一部样片 film.py，全部 lint 0 error、显式乐谱、确定性渲染。

| 卡 | 样片 | 成片 | 移植要点（简） |
|---|---|---|---|
| isometric | `examples/style-ports/isometric/film.py`（国风变体 `forbidden_city.film.py`） | `isometric-city.mp4` | 正交投影 P(x,y,z) + box 法线剔除 + 凸包阴影 + 夜灯 glow；环绕运镜 + 物件按 ry 画家算法排序 |
| flat-zoom | `flat-zoom/film.py`（v2 重做《画中屋》，v1 存 `film_v1_old.py`） | `flat-zoom.mp4` | **概念：小屋亮窗→屋内挂画→画中屋循环**（传送门为真实物件，尺寸关系成立，循环由构图保证）。技术：不动点锚传送门中心→屏幕中心 F=(Pc-s·C)/(1-s)；每层单变换直绘（矢量任意倍率清晰）；门内层临时画布须按设备分辨率 `sc=zr·(pw/W)·SS`——漏乘 SS 内容只有一半大（踩过）；AFFINE 逆变换 1:1 浮点贴回 (1,0,-corner,0,1,-corner)；嵌套深度 1 时给门内画简化内容（避免空画框断层） |
| lineart | `lineart/film.py` | `lineart.mp4` | 504 根流线 curl+风预烘焙 → 错峰 lerp 到山脊折线（ROWZ=3+52·(i/N)^1.35）→ 实心化按深度错峰；lighter 用双层描边近似；走山光 3 遍描边+glow |
| morph | `morph/film.py` | `morph.mp4` | PIL 离屏形状 2px 采样+MinFilter 边缘检测；swirl=sin(πu)·1.35×curl；落定过冲 exp(-7t)sin(22t)·0.04；glow sprite 降采样两遍叠回 |
| sticker | `sticker/film.py` | `sticker-poster.mp4` | 牛皮纸变体：模切白边=白底圆角垫+art；贴下 scale 1.35→1 inQuad + 影子收紧 (6+lift·34, 10+lift·48) + squash 0.06exp(-14t)cos(34t)；反光带 0.9s 扫过后留静态光泽；12fps 定格量化 + 相机 log 空间拉远 z→0.662 |
| hud | `hud/film.py` | `hud-pointcloud.mp4` | 7.5 万点云 numpy bincount 散射加色（RGB float 缓冲）；pitch 正值=俯视 `y2=y·cp+z2·sp, z3=-y·sp+z2·cp`；扫描波 rev/wave 双函数；glitch=np.roll 切片+RGB split（整屏 draw 可读 c.img，先 flush） |
| editorial | `editorial/film.py` | `editorial-paper.mp4` | 版面 1600×2600 一次烘焙；仿射系数必须乘超采样 PSS；相机 log 空间插值 + 拉远 skew；荧光笔重画被高亮文字保可读；RGBA 底上 alpha 写入是覆盖非混合（坑） |
| collage | `collage/film.py` | `collage-kraft.mp4` | 撕边=2.2px 步长双频噪声+白纤维芯；mono/riso 网点（双色 numpy multiply）；12fps 定格+曝光微闪 ±0.0175；sprite 预热防帧内建 Canvas 清 skia scratch（大坑，曾致 42 单帧闪烁） |
| glass | `glass/film.py` | `glass-aurora.mp4` | 毛玻璃=壁纸离屏 GaussianBlur 后按卡区域裁贴+白 8.6% 叠层；玻璃珠=清晰壁纸放大 2.2×圆形裁贴；多 Canvas 实例各自 flush 防串层 |
| variety | `variety/film.py` | `variety-fried-egg.mp4` | 花字单字 sprite：stroke_width 三层描边+挤出 10 层+竖向渐变+高光带，scale 桶缓存；CJK 需逐字累积 advance（等宽度假象坑）；punch z=1+amt·exp(-Δt·7)+闪白 |
| pagecam | `pagecam/film.py` | `pagecam.mp4` | CSS 3D→手写透视 F=2200 + PIL PERSPECTIVE 四点单应（numpy 解 8×8）；DOF 量化 blur 档缓存 + rack focus；面板/clip 弹簧 1-e^(-ct/2)cos(2πft) |
| blueprint | `blueprint/film.py` | `blueprint.mp4` | 扫描线变身=实物/线稿两 sprite 行掩膜 Image.composite；标注层 alpha×行掩膜再贴（直接 paste 会把透明像素糊黑）；绘图仪辉光 tip=exp(-((xr-uR+0.12)/0.1)²) |

**不移植（3D 依赖，永久）**：3d-render、liquid、clay——卡内已标注编排层可借鉴（节拍/曲线/cue），画面用 2D 近似或跳过。

**共性经验**（全部样片验证过）：
- 整屏自绘 `s1.draw(fn, at=0, enter="none")` 防 0.5s 淡入洗白
- 随机一律 hash1/RandomState(seed)，render(t) 确定性
- 多 Canvas 实例必须各自 flush；帧内建 Canvas 会清共享 skia scratch（先预热 sprite）
- 有意急变（穿屏/glitch/定格跳动）用 `flicker_exclude(t0, t1)` 声明
- 快速运镜贴高对比文字边缘会触发闪烁误报，连帧对差核实后保留并注明
