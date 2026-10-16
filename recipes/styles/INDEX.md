# 风格配方卡总索引（51 张 · huashu 35 + sy-styles-20 20，重复 4 对已融合）

> **先读这一句**：huashu 的 35 张样片是同一个构图（风格在变、场景不变），做新题材要为题材重新构图——卡里的渲染器、笔法、色彩逻辑、母题动法可以拿走，坐标、角色、家具不要搬过去。sy-styles-20 的卡同理：手法与编排可拿走，3D 依赖的部分标注了可移植性。

**已移植到 wv runtime 的渲染器**：dabs（印象派/色点）/ seurat（点彩）/ mosaic（镶嵌）/ facets（立体主义切面）/ halftone（波普网点）/ pixel8（像素，含 dither_mode="ordered" Bayer、cycle 调色板循环）/ ink（水墨）/ watercolor（水彩）/ texture（材质纹理 paper/rock/crack）/ post_dof（深度模糊）/ post_cinema（电影感后期）/ post_vhs（VHS 录像带后期：RGB 分离+跟踪带+扫描线）/ post_bloom（泛光）/ strokes.ribbon（可变宽度路径）/ strokes.brush（毛笔笔压飞白）/ 手绘管线 strokes（curve/jitter/smooth）/ pixel_text（5x7 点阵字）。

## 材料层（可盖任何题材）

| 卡 | 风格 | wv 对应 | 质量 | 短板 |
|---|---|---|---|---|
| postimp | 梵高（标杆） | dabs 参数化配置＋纹理/图元；星空漩涡方向场需 field 扩展 | ★★★ | 每帧 120ms 最重 |
| impressionism | 印象派 | dabs＋区域色板配置＋手绘管线 | ★★ | 脸和手被笔触打碎 |
| seurat | 修拉点彩 | seurat 已移植（参数直接对应） | ★★ | 偏静；网格规整 |
| ghibli | 吉卜力水彩 | watercolor＋texture(paper)＋月牙影图元；wash 水痕边参数需补 | ★★ | 人物不如背景 |
| ink | 水墨写意（融合 sy 18-ink） | ink＋watercolor＋texture(paper)；毛笔 brush 需 strokes 补笔压包络 | ★★ | 人物不够写意 |
| pop | 利希滕斯坦波普 | halftone＋ink 粗黑描边；本戴点建议 createPattern 平铺快两个数量级 | ★★★ | — |
| pixel | 8-bit 像素（融合 sy 13-pixel） | pixel8（cw 整除/dither_mode/cycle/pixel_text 全齐）；dep 分层灯光用底稿分层绕 | ★★★ | 猫头压窗台 |
| synthwave | 蒸汽波/赛博霓虹（融合 sy 12-synthwave） | post_cinema 近似 VHS；完整 VHS 后期（RGB 分离+跟踪带+扫描线）需新渲染器；霓虹/网格/铬金字图元直绘 | ★★★ | 部件交界也发光 |
| shinkai | 新海诚光影 | 图元直绘（cel 分层/云光晕光柱）；泛光 bloom 需新渲染器（降采样 blur+screen 回叠） | ★★ | 室内背景密度不够 |
| rembrandt | 伦勃朗明暗 | dabs＋texture＋光照图 multiply 图元＋post_cinema | ★ | 人物扁平（审片 5/10），最该重做 |
| cubism | 分析立体主义 | facets＋texture；仿木纹/模版字图元直绘 | ★★ | 偏亮，深褐大面不够 |
| matisse | 马蒂斯剪纸 | polygon 剪纸＋手绘 jitter；水粉刷痕可用 texture(paper) 近似 | ★★★ | 水粉刷痕偏重 |
| flat2026 | 当代扁平插画 | 图元直绘＋dabs 颗粒点彩 | ★★★ | — |
| haring | 凯斯·哈林 | 图元直绘＋手绘 curve 胶囊肢体 | ★★★ | 少女不够哈林 |
| rubberhose | 1930 橡皮管卡通 | 手绘管线＋图元直绘＋texture（胶片噪声/划痕） | ★★★ | 运动大半是胶片噪声 |
| nouveau | 慕夏新艺术 | 手绘 curve 打底；可变宽度 ribbon（法线偏移拼多边形）需新渲染器 | ★★★ | 猫姿势僵 |
| constructivism | 构成主义（窄） | halftone 可变点径＋texture 旧纸＋图元直绘 | ★★★ | 缺喇叭形文字锥 |
| bauhaus | 包豪斯（融合 sy 11-bauhaus，窄） | huashu 版图元直绘；sy 3D 错觉对齐不可移植 | ★★★ | 猫头偏离骨架位 |
| roman | 庞贝马赛克（窄） | mosaic 已移植；距离场沿轮廓排石+Voronoi 灰浆需新渲染器 | ★★★ | 小尺度脸部细节少 |
| raytrace | 早期光追 CGI（窄） | 图元直绘为主；逐像素棋盘地/铬球映射需新渲染器 | ★★ | 猫腿直柱、脸像面具 |

## 时代标本（速通/穿越/致敬）

| 卡 | 风格 | wv 对应 | 质量 | 短板 |
|---|---|---|---|---|
| cave | 洞穴岩画 | ink 炭线＋texture 岩壁；高度场法线着色需新渲染器 | ★★★ | 人形太卡通 |
| egypt | 埃及墓室壁画 | 图元直绘＋texture 斑驳；P.texture 首帧 170ms 要 init 预热 | ★★★ | 端杯肘偏僵 |
| greek | 阿提卡黑绘 | 手绘管线＋polygon 剪影＋texture 陶土底；锥形斑需新渲染器 | ★★★ | 裙摆偏厚 |
| gothic | 哥特泥金手抄本 | texture（金箔拉丝/羊皮纸）＋图元；金色度遮罩需新渲染器 | ★★★ | 金发像兜帽 |
| renaissance | 文艺复兴晕涂 | post_dof＋texture（龟裂/画布纹）＋dabs；sfumato 角色合成需离屏新实现 | ★★ | 猫偏卡通；整体偏静 |
| klimt | 克里姆特金色时期 | texture（fbm 金箔/金粉）＋图元纹样直绘 | ★★★ | 桌上的手没接袖子 |
| munch | 蒙克表现主义 | 需新渲染器：flowLines 流场积分＋整幅行列 warp | ★★ | 墙面曾被读成梵高 |
| dunhuang | 敦煌壁画 | texture（剥落/做旧）＋ink 铁线描；披帛 ribbon 需可变宽度渲染器 | ★★ | 飞天造型粗 |
| kusama | 草间弥生波点 | 图元直绘（行波改 r；镜屋灯 3D 透视投影+加法合成） | ★★★ | 人物与墙同色靠轮廓撑 |
| dali | 达利超现实 | 需新渲染器（softMap 软钟/剪切仿射长影）；景深可借 post_dof | ★★ | 人物偏矢量插画 |
| hopper | 霍珀美国现实主义 | 图元直绘（光斑 clip+双版本缓存）；竖向 fbm 拖笔需新渲染器 | ★★★ | 猫全程在阴影里 |
| kirby | 漫威 Kirby 银河时代 | halftone/mosaic 套色＋图元（krackle/拟声字多层挤出）；clip evenodd 需新渲染器 | ★★ | 更像利希滕斯坦 |
| monet | 莫奈睡莲 | dabs（参数直接对应）＋图元水面光斑；桥衬底靠图层顺序 | ★★ | 空间别扭（墙是池水） |
| shadowpuppet | 中国皮影 | 需新渲染器（皮件刻纹+印染透光管线）＋图元幕布 | ★★★ | 重叠相乘发黑；121ms 偏慢 |
| picasso_blue | 毕加索蓝色时期 | dabs＋texture＋图元；手绘需补 cap 参数根治圆头密排 | ★★ | 造型不够忧郁 |

## sy 实用风格（sy-styles-20，工程配方）

| 卡 | 风格 | 技术 | 可移植性 | wv 对应 |
|---|---|---|---|---|
| handdrawn | 逐帧手绘 | Canvas 2D | 部分可移植 | 手绘管线＋需 G-buffer→水彩/排线风格化 pass |
| isometric | 等轴 2.5D 小城 | Canvas 2D | 直接可移植 | 图元直绘（正交投影/凸包阴影/glow） |
| flat-zoom | 无限推进 | Canvas 2D | 直接可移植 | 图元直绘＋递归 clip/scale 对数缩放 |
| lineart | 金线山脊 | Canvas 2D | 直接可移植 | 手绘管线 polyline+lighter |
| 3d-render | 3D 渲染 | 光线步进 | 不可移植 | 编排层可借鉴（drop 弹跳/欧拉盘进动/cue 节拍） |
| morph | 粒子形变 | Canvas 2D | 直接可移植 | 粒子 sprite+lighter glow（量大换 GPU） |
| sticker | 贴纸风科普 | Canvas 2D | 直接可移植 | 图元直绘+离屏 sprite 合成 |
| hud | LiDAR 点云 HUD | Canvas 2D | 直接可移植 | 图元直绘＋预生成点云 |
| collage | 拼贴剪贴 | WebGL | 部分可移植 | texture 纸片/post_cinema；三缓冲高度场打光需新 pass |
| glass | 玻璃拟态 | WebGL | 部分可移植 | 图元（壁纸/时钟/UI）；2D SDF 折射需 WebGL pass |
| liquid | 液态金属 | 光线步进 | 不可移植 | 速度斜坡时钟/spring/jelly 曲线可移植 2D |
| variety | 综艺花字 | Canvas 2D | 部分可移植 | 花字/贴纸/闪光/推镜纯 2D 直接移植 |
| pagecam | 页面 2.5D 推镜 | Canvas 2D | 部分可移植 | 图元画面板＋仿射/透视变换＋post_dof |
| editorial | 数据新闻编辑风 | Canvas 2D | 直接可移植 | 图元直绘＋texture 纸纹；CJK 逐字断行需自实现 |
| clay | 黏土定格 | 光线步进 | 不可移植 | 12fps frameKey/boil/挤压拉伸曲线可移植 2D |
| blueprint | 蓝图工程图 | 光线步进 | 部分可移植 | 2D 标注层（尺寸线/引线/标题栏）直接移植 |

## 转场

全部签名转场汇总见 `_转场合集.md`（16 个转场带参数 + 三条通用经验）。

## 质量分布与下一步

- ★★★ 20 种、★★ 14 种、★ 1 种（huashu 侧）。
- **最普遍的短板是角色**：背景过了风格渲染器就像那个风格，角色只用矢量骨架平涂就像贴上去的。下一轮提质先从「角色也过同一个渲染器／按该风格重塑造型」做起。
- wv 侧需要新渲染器的汇总（已完成：texture、post_dof、post_cinema、post_vhs、post_bloom、ribbon、brush、Bayer 抖动、cycle）：flowLines 流场积分+整幅行列 warp（munch/postimp 漩涡）、softMap 软钟+剪切仿射长影（dali）、皮件刻纹+印染透光（shadowpuppet）、距离场排石+Voronoi 灰浆（roman andamento）、逐像素金色度遮罩（gothic/klimt 扫光）、G-buffer→水彩/排线风格化 pass（handdrawn）、2D SDF 折射（glass）、立体主义 clip evenodd 羽化排线（kirby）、披帛 ribbon 已完成、竖向 fbm 拖笔（hopper）、长条笔痕 overlay（matisse 水粉刷痕）。
