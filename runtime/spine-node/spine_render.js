// Spine 官方运行时 node-canvas 直渲（无浏览器）。
// 用法：node spine_render.js <动画名> <时间数组JSON> <输出前缀>
//      环境变量 W/H/SS 画布与超采样；FLIP_X=1 水平翻转
// 依赖：npm install（spine-canvas 4.2 + canvas 3）
// 素材：ASSET_DIR 环境变量，默认 /workspace/spine-assets/4.2（spineboy-pma.*）
const fs = require('fs');
const path = require('path');
const { createCanvas, loadImage } = require('canvas');
const spine = require('@esotericsoftware/spine-canvas');

const ASSET_DIR = process.env.ASSET_DIR || '/workspace/spine-assets/4.2';

// 接缝修复：clip 抗锯齿留缝 -> 不透明三角外扩 2px；半透明三角外扩 0.5px（避免叠加变暗）
const alphaCache = new Map();
function getAlpha(img) {
    let d = alphaCache.get(img);
    if (!d) {
        const c = createCanvas(img.width, img.height);
        const g = c.getContext('2d');
        g.drawImage(img, 0, 0);
        d = g.getImageData(0, 0, img.width, img.height).data;
        alphaCache.set(img, d);
    }
    return d;
}
function alphaAt(img, u, v) {
    const x = Math.min(img.width - 1, Math.max(0, Math.round(u * (img.width - 1))));
    const y = Math.min(img.height - 1, Math.max(0, Math.round(v * (img.height - 1))));
    return getAlpha(img)[(y * img.width + x) * 4 + 3];
}

class SeamlessRenderer extends spine.SkeletonRenderer {
    drawTriangle(img, x0, y0, u0, v0, x1, y1, u1, v1, x2, y2, u2, v2) {
        const opaque = [alphaAt(img, u0, v0), alphaAt(img, u1, v1), alphaAt(img, u2, v2),
                        alphaAt(img, (u0 + u1 + u2) / 3, (v0 + v1 + v2) / 3)]
            .every(a => a >= 250);
        const amt = opaque ? 2.0 : 0.5;
        const cx = (x0 + x1 + x2) / 3;
        const cy = (y0 + y1 + y2) / 3;
        const ex = (px, py) => {
            const dx = px - cx, dy = py - cy;
            const len = Math.hypot(dx, dy) || 1;
            const k = (len + amt) / len;
            return [cx + dx * k, cy + dy * k];
        };
        const [ax, ay] = ex(x0, y0);
        const [bx, by] = ex(x1, y1);
        const [dx2, dy2] = ex(x2, y2);
        super.drawTriangle(img, ax, ay, u0, v0, bx, by, u1, v1, dx2, dy2, u2, v2);
    }
}

async function createPlayer(opts) {
    const atlasText = fs.readFileSync(path.join(ASSET_DIR, 'spineboy-pma.atlas'), 'utf-8');
    const skeletonText = fs.readFileSync(path.join(ASSET_DIR, 'spineboy-pro.json'), 'utf-8');
    const img = await loadImage(path.join(ASSET_DIR, 'spineboy-pma.png'));

    const atlas = new spine.TextureAtlas(atlasText);
    for (const page of atlas.pages) page.setTexture(new spine.CanvasTexture(img));

    const json = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas));
    const skeletonData = json.readSkeletonData(skeletonText);
    const skeleton = new spine.Skeleton(skeletonData);
    const state = new spine.AnimationState(new spine.AnimationStateData(skeletonData));

    const W = opts.width || 512, H = opts.height || 760, SS = opts.ss || 2;
    const canvas = createCanvas(W * SS, H * SS);
    const ctx = canvas.getContext('2d');
    const renderer = new SeamlessRenderer(ctx);
    renderer.triangleRendering = true;

    return {
        skeleton, state, skeletonData, canvas, ctx, renderer,
        setAnimation(name, loop = true) {
            const entry = state.setAnimation(0, name, loop);
            return entry;
        },
        seek(t) {
            const entry = state.tracks[0];
            entry.trackTime = t;
            state.update(0);
            state.apply(skeleton);
            skeleton.updateWorldTransform(spine.Physics.update);
        },
        draw(footYRatio = 0.9, heightRatio = 0.82, flipX = false) {
            const scale = (H * SS * heightRatio) / skeletonData.height;
            ctx.save();
            ctx.translate(W * SS / 2, H * SS * footYRatio);
            ctx.scale(flipX ? -scale : scale, -scale);
            renderer.draw(skeleton);
            ctx.restore();
        },
        clear() {
            ctx.clearRect(0, 0, W * SS, H * SS);
        },
        toBuffer() {
            return canvas.toBuffer('image/png');
        },
    };
}

async function main() {
    const animName = process.argv[2] || 'walk';
    const times = JSON.parse(process.argv[3] || '[0.3]');
    const outPrefix = process.argv[4] || '/workspace/sa-node';
    const p = await createPlayer({});
    p.setAnimation(animName, true);
    for (const t of times) {
        p.clear();
        p.seek(t);
        p.draw();
        fs.writeFileSync(`${outPrefix}-${animName}-${t}.png`, p.toBuffer());
        console.log('OK', `${outPrefix}-${animName}-${t}.png`);
    }
}

module.exports = { createPlayer, SeamlessRenderer };

if (require.main === module) {
    main().catch(e => { console.error(e); process.exit(1); });
}
