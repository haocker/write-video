# variety · 综艺花字 · 多层描边花字把一颗煎蛋拍成综艺名场面

- 来源: sy-styles-20 styles/15-variety（MIT, 肖雄）
- 层次: sy 实用风格
- 技术: 光线步进 3D（煎蛋 footage）+ Canvas 2D 花字全套
- wv 可移植性: 部分可移植——花字/贴纸/字幕/闪光/推镜是纯 2D，可直接移植；煎蛋 footage 是 raymarch SDF，需新渲染器或换 2D 素材

## 核心手法
- footage：铸铁锅 raymarched（锅沿/导流/手柄 SDF），蛋白摊开 R1=.47 带过冲涟漪 (1-exp(-u·5.5)·cos(u·9)·.92)，厚度 .04·(0.47/spread)^1.6 体积守恒；焦脆蕾丝＝vnoise 洞＋花边，气泡格 q·22 生命周期循环；蛋黄 jiggle 1-.32exp(-5u)cos(22u)，POKE=7.25 被筷子戳后流心（lobe SDF＋噪声摆动）；黑胡椒 step(.986, hash(floor(p.xz·160)))。
- **花字 vText**（核心资产）：三层描边——深色 s1 宽 .34fs、白 s2 宽 .2fs、彩色点缀 s3 宽 .075fs；下方挤出 depth 10-14 层（每层偏移 i·.55, i·.9）；竖向线性渐变填充（亮→暗→更暗）；source-atop 在上半叠高光带。
- 每个字独立 popIn（outBack 2.2）＋独立抖动（sin(t·31+i·2)·5px）；拟声字逐字入场错 0.09s。
- 贴纸：emoji 加模切白边——source-in 做白色 mask，向 16 个方向偏移 shadowBlur 0.8pad 重画，再叠原图，按 (emoji,size) 缓存。
- 字幕 5 段按时间表逐字淡入；缩略图缓存避免每帧重建。
- 爆炸线 burst（n 个楔形扇块双色交替）、八角星 spark、底部字幕 700 46px 黑描边 9px＋白填充；左上角红底白边 tag 药丸＋🍳 贴纸。
- 卡点：zoom punch z=1+punch(HIT+.02,.12)+punch(POKE,.16)，punch=amt·exp(-Δt·7)；命中瞬间相机抖 sin(61t)·.012·sh＋曝光 punch（+.6/+.9）；整帧闪白 rgba(255,255,255,fl·.55)。
- 热气 6 个 blur(16px) 椭圆 screen 叠加；胡椒雨 70 条小矩形（每条错 0.04s 落下）；色分级 lift/gain 暖偏＋grain .04。

wv 对应: 图元直绘（text/gradient/sticker 缓存法）＋ post_cinema（闪白/推镜/抖动）；煎蛋 footage 需新渲染器（raymarch SDF）或换成已有 2D 素材

## 母题动画与钩子
- 节拍：0.62s 啪嗒落锅（burst＋168px 花字）→ 1.4s 完美落锅＋👌 → 2.6s 滋滋滋～（逐字抖动）→ 5.0s 撒黑胡椒✨ → 6.55s 悬念「最关键的一步……」→ **7.25s 筷子戳蛋黄流心（钩子）**：burst 半径 760px＋「流心了！！！」196px 花字＋😍🥚 贴纸 → 8.6s 完美溏心蛋＋五星＋「满分」红章（scale 1+.6exp(-9u) 过冲）。
- 字幕 5 段按时间表切换，handle 右上角。

## 签名转场/镜头
无镜头切换；"punch 推镜＋闪白＋花字砸入"三件套就是转场语法，每次命中重复一次。
