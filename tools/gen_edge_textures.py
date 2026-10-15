"""生成街道两头（教堂 / 墓地 / 西头画布）的贴图。确定性（固定随机种子）。

用法：
  .venv/bin/python tools/gen_edge_textures.py            纸条、墓碑刻字图集、玛莎墓碑、空白墓碑、干草、画布背面 / 织纹法线
  .venv/bin/python tools/gen_edge_textures.py --canvas   只做画布：把 Blender 渲染的 canvas_raw.png 加工成"手绘布景" canvas_paint.jpg
                                                         （tools/blender/build_edges.py --paint 会自动调用）
输入：art/source/fonts/IMFeENsc28P.ttf（墓碑刻字）、Zeyada.ttf（手写纸条），均为 SIL OFL，只栅格化不分发。
输出：art/source/_derived/edges/*（graves.json 记录每块墓碑在图集里的格子，build_edges.py 读它）
"""
import json, math, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "art" / "source"
OUT = SRC / "_derived" / "edges"
SERIF = SRC / "fonts" / "IMFeENsc28P.ttf"
HAND = SRC / "fonts" / "Zeyada.ttf"

# ---------------------------------------------------------------- 墓碑数据（虚构人名，1860s–1881）
# kind: round / flat / gothic / cross；w, h = 露出地面的宽高（米）
GRAVES = [
    ("Grave_01", "round",  0.55, 0.80, 0.30, [("JOSIAH T. WARE", 1.0), ("1821 – 1868", 0.8), ("AT REST", 0.7)]),
    ("Grave_02", "round",  0.50, 0.72, 0.25, [("ELIZA", 1.0), ("WIFE OF JOSIAH", 0.65), ("1826 – 1871", 0.75)]),
    ("Grave_03", "flat",   0.36, 0.42, 0.10, [("BABY", 0.9), ("HOLLIS", 0.9), ("1874", 0.8)]),
    ("Grave_04", "gothic", 0.58, 0.95, 0.20, [("SILAS", 1.0), ("McCREADY", 1.0), ("KILLED AT THE", 0.6), ("NARROWS MINE", 0.6), ("1877", 0.8)]),
    ("Grave_05", "cross",  0.62, 1.05, 0.15, [("AMOS PRUETT", 1.0), ("1880", 1.0)]),
    ("Grave_06", "cross",  0.58, 0.98, 0.15, [("UNKNOWN", 1.0), ("WEST ROAD 1879", 0.75)]),
    ("Grave_07", "flat",   0.52, 0.66, 0.30, [("CORNELIUS", 0.9), ("DUFF", 1.0), ("1833 – 1866", 0.75)]),
    ("Grave_08", "round",  0.48, 0.70, 0.30, [("LETTIE MAE", 0.95), ("GRAY", 0.95), ("1862 – 1875", 0.75), ("ASLEEP", 0.6)]),
    ("Grave_09", "cross",  0.60, 1.00, 0.15, [("W.H. BRANNOCK", 1.0), ("1840–81", 1.0)]),
    ("Grave_10", "gothic", 0.50, 0.85, 0.20, [("HANNAH", 1.0), ("ODELL", 1.0), ("1858 – 1879", 0.75), ("BELOVED", 0.6)]),
    ("Grave_11", "cross",  0.56, 0.95, 0.15, [("EZRA COLE", 1.0), ("1872", 1.0)]),
    ("Grave_12", "cross",  0.48, 0.82, 0.15, [("J. B.", 1.0), ("1864", 1.0)]),
]
MARTHA = ("Grave_Martha", "round", 0.68, 0.95, 0.20)
BLANK = ("Grave_Blank", "round", 0.62, 0.88, 0.20)
ATLAS, COLS, ROWS = 2048, 4, 3


# ---------------------------------------------------------------- 噪声
def vnoise(rng, w, h, scale, periodic=False):
    """值噪声（双三次放大），0..1。periodic=True 时可无缝平铺（要求 w、h 能被 scale 整除）。"""
    gw, gh = max(2, w // scale), max(2, h // scale)
    g = rng.random((gh, gw)).astype(np.float32)
    if periodic:
        big = np.tile(g, (3, 3))
        im = Image.fromarray((big * 255).astype(np.uint8)).resize((gw * 3 * scale, gh * 3 * scale), Image.BICUBIC)
        a = np.asarray(im, np.float32) / 255.0
        return a[gh * scale:gh * scale + h, gw * scale:gw * scale + w]
    g = np.pad(g, 2, mode="reflect")
    im = Image.fromarray((g * 255).astype(np.uint8)).resize(((gw + 4) * scale, (gh + 4) * scale), Image.BICUBIC)
    a = np.asarray(im, np.float32) / 255.0
    return a[2 * scale:2 * scale + h, 2 * scale:2 * scale + w]


def fbm(rng, w, h, base, octaves=4, periodic=False):
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0; s = base
    for _ in range(octaves):
        out += amp * vnoise(rng, w, h, max(1, s), periodic); tot += amp
        amp *= 0.5; s = max(1, s // 2)
    return out / tot


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def normal_from_height(hgt, strength):
    """高度图 → OpenGL 法线贴图（绿 = 向上）。"""
    dx = np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)
    dy = np.roll(hgt, 1, 0) - np.roll(hgt, -1, 0)     # 图像行向下，GL 的 +V 向上
    n = np.stack([-dx * strength, -dy * strength, np.ones_like(hgt)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def text_mask(W, H, items, font_path):
    """items = [(text, cx, cy, size_px, max_w)] → 0..1 遮罩（居中）。"""
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    for text, cx, cy, size, max_w in items:
        size = int(size)
        while size > 8:
            f = ImageFont.truetype(str(font_path), size)
            b = d.textbbox((0, 0), text, font=f)
            if b[2] - b[0] <= max_w: break
            size -= 2
        d.text((cx - (b[2] - b[0]) / 2 - b[0], cy - (b[3] - b[1]) / 2 - b[1]), text, font=f, fill=255)
    return np.asarray(m, np.float32) / 255.0


# ---------------------------------------------------------------- 石头 / 木头表面
def stone_surface(rng, W, H, age):
    """风化的砂岩 / 石灰岩：底色 + 斑点 + 地衣 + 顶部往下的雨痕。返回 (rgb, height)。"""
    f1 = fbm(rng, W, H, 64); f2 = fbm(rng, W, H, 8, 3)
    base = np.array([0.66, 0.63, 0.57], np.float32) if age > 0.2 else np.array([0.80, 0.78, 0.74], np.float32)
    col = base * (0.9 + 0.14 * f1[..., None]) * (0.94 + 0.1 * f2[..., None])
    speck = rng.random((H, W)).astype(np.float32)
    col *= (1 - 0.18 * (speck > 0.985))[..., None]
    # 雨痕：竖直拉长的噪声，越靠上越重
    streak = vnoise(rng, W, H, 6)
    streak = np.asarray(to_img(streak).resize((W // 6 + 1, 4)).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    yy = np.linspace(1, 0, H, dtype=np.float32)[:, None]
    col *= (1 - age * 0.25 * np.clip(streak - 0.4, 0, 1) * (0.4 + yy))[..., None]
    # 地衣：两色斑块
    lich = fbm(rng, W, H, 32, 4)
    a1 = np.clip((lich - (0.74 - 0.08 * age)) * 5, 0, 1) * age * 0.7
    col = col * (1 - a1[..., None] * 0.7) + np.array([0.70, 0.70, 0.52]) * a1[..., None] * 0.7
    lich2 = fbm(rng, W, H, 16, 3)
    a2 = np.clip((lich2 - (0.78 - 0.06 * age)) * 6, 0, 1) * age * 0.6
    col = col * (1 - a2[..., None] * 0.6) + np.array([0.24, 0.24, 0.20]) * a2[..., None] * 0.6
    # 下部泥土返潮
    col *= (1 - 0.25 * age * np.clip((0.12 - (1 - yy)) / 0.12, 0, 1))[..., None]
    hgt = f2 * 0.6 + f1 * 0.4 + a1 * 0.3
    return col.astype(np.float32), hgt.astype(np.float32)


def wood_surface(rng, W, H, age=1.0):
    """风吹日晒发灰的松木板（竖纹）。"""
    xx = np.arange(W, dtype=np.float32)[None, :] / W
    n = fbm(rng, W, H, 32)
    n = np.asarray(to_img(n).resize((W, max(2, H // 16))).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    rings = np.sin((xx * 26 + n * 1.5) * math.pi) * 0.5 + 0.5
    fine = vnoise(rng, W, H, 2)
    fine = np.asarray(to_img(fine).resize((W, max(2, H // 40))).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    grey = np.array([0.55, 0.52, 0.47], np.float32); brown = np.array([0.48, 0.38, 0.28], np.float32)
    col = grey * age + brown * (1 - age)
    col = col * (0.8 + 0.1 * rings[..., None] + 0.12 * fine[..., None]) * (0.9 + 0.15 * vnoise(rng, W, H, 48)[..., None])
    cracks = (fine < 0.12).astype(np.float32)
    col *= (1 - 0.4 * cracks)[..., None]
    hgt = rings * 0.3 + fine * 0.5 - cracks
    return col.astype(np.float32), hgt.astype(np.float32)


def engrave(col, hgt, mask, depth=1.0, dark=0.45):
    """刻字：凹槽变暗 + 按左上光烘一点明暗，保证任何光照下都读得清。"""
    m = np.asarray(to_img(mask).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0
    hgt = hgt - m * depth
    gx = np.roll(m, -2, 1) - np.roll(m, 2, 1); gy = np.roll(m, -2, 0) - np.roll(m, 2, 0)
    shade = (gx + gy) * 0.35               # 凹槽的左上内壁在阴影里，右下内壁亮
    col = col * (1 - m[..., None] * (1 - dark)) + shade[..., None] * 0.6
    return np.clip(col, 0, 1), hgt


def outline_mask(kind, W, H):
    """墓碑轮廓遮罩（与 build_edges.py 的轮廓一致），轮廓外画成泥色避免采样溢出。"""
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    if kind == "round":
        r = W / 2; d.rectangle([0, r, W, H], fill=255); d.ellipse([0, 0, W, 2 * r], fill=255)
    elif kind == "gothic":
        d.rectangle([0, W * 0.6, W, H], fill=255); d.polygon([(0, W * 0.6), (W / 2, 0), (W, W * 0.6)], fill=255)
    else:
        d.rectangle([0, 0, W, H], fill=255)
    return np.asarray(m, np.float32) / 255.0


def stone_cell(kind, w, h, lines, seed, age=0.8, font=SERIF, px_per_m=800):
    W, H = int(w * px_per_m), int(h * px_per_m)
    rng = np.random.default_rng(seed)
    if kind == "cross":
        col, hgt = wood_surface(rng, W, H)
        bar_c = H * 0.26; bar_h = 0.15 * px_per_m
        items = [(lines[0][0], W / 2, bar_c, bar_h * 0.62, W * 0.92)]
        stem = 0.13 * px_per_m
        if len(lines) > 1:
            items.append((lines[1][0], W / 2, bar_c + bar_h * 1.1, stem * 0.55, stem * 0.95 if len(lines[1][0]) < 6 else W * 0.9))
        # 刀刻 + 烧焦：粗糙、偏黑
        mask = text_mask(W, H, items, font)
        col, hgt = engrave(col, hgt, mask, depth=0.8, dark=0.25)
        return col, hgt
    col, hgt = stone_surface(rng, W, H, age)
    top = W * 0.5 if kind == "round" else (W * 0.55 if kind == "gothic" else H * 0.1)
    avail = H * 0.68 - top            # 底下约 20% 埋在土里 / 被基座挡住
    tot = sum(s for _, s in lines)
    unit = min(avail / (tot * 1.45), W * 0.16)
    y = top + unit * 0.4
    items = []
    for text, s in lines:
        sz = unit * s * 1.15
        items.append((text, W / 2, y + sz * 0.5, sz, W * 0.82))
        y += sz * 1.45
    col, hgt = engrave(col, hgt, text_mask(W, H, items, font))
    return col, hgt


def mud_outside(col, kind, W, H):
    m = outline_mask(kind, W, H)[..., None]
    return col * m + np.array([0.35, 0.3, 0.25]) * (1 - m)


def gen_stones():
    cw, ch = ATLAS // COLS, ATLAS // ROWS
    atlas_c = np.zeros((ATLAS, ATLAS, 3), np.float32); atlas_h = np.zeros((ATLAS, ATLAS), np.float32)
    meta = {}
    for i, (gid, kind, w, h, t, lines) in enumerate(GRAVES):
        col, hgt = stone_cell(kind, w, h, lines, seed=100 + i, age=0.6 + 0.4 * ((i * 37) % 10) / 10)
        if kind != "cross":
            col = mud_outside(col, kind, col.shape[1], col.shape[0])
        cx, cy = (i % COLS) * cw, (i // COLS) * ch
        atlas_c[cy:cy + ch, cx:cx + cw] = np.asarray(to_img(col).resize((cw, ch), Image.LANCZOS), np.float32) / 255.0
        hh = Image.fromarray(((hgt - hgt.min()) / (np.ptp(hgt) + 1e-6) * 255).astype(np.uint8)).resize((cw, ch), Image.LANCZOS)
        atlas_h[cy:cy + ch, cx:cx + cw] = np.asarray(hh, np.float32) / 255.0
        # UV 矩形（Blender UV：原点在左下）
        meta[gid] = {"kind": kind, "w": w, "h": h, "t": t, "lines": [l for l, _ in lines],
                     "uv": [cx / ATLAS, 1 - (cy + ch) / ATLAS, (cx + cw) / ATLAS, 1 - cy / ATLAS]}
    to_img(atlas_c).save(OUT / "edge_graves_atlas.jpg", quality=92)
    to_img(normal_from_height(atlas_h, 3.0)).save(OUT / "edge_graves_atlas_n.png")
    for gid, kind, w, h, t, lines, age, name in (
            (*MARTHA, [("MARTHA", 1.25), ("DIED", 0.6), ("JUNE 14, 1882", 0.8), ("— STRUCK OUT —", 0.42)], 0.25, "martha"),
            (*BLANK, [], 0.0, "blank")):
        W = 1024 if name == "martha" else 512
        if lines:
            col, hgt = stone_cell(kind, w, h, lines, seed=7 if name == "martha" else 8, age=age, px_per_m=W / w)
        else:
            rng = np.random.default_rng(9)
            col, hgt = stone_surface(rng, int(w * W / w), int(h * W / w), age)
        col = mud_outside(col, kind, col.shape[1], col.shape[0])
        to_img(col).resize((W, W), Image.LANCZOS).save(OUT / f"edge_grave_{name}.jpg", quality=92)
        hn = (hgt - hgt.min()) / (np.ptp(hgt) + 1e-6)
        to_img(normal_from_height(np.asarray(to_img(hn).resize((W, W), Image.LANCZOS), np.float32) / 255.0, 4.0 if lines else 1.2)).save(OUT / f"edge_grave_{name}_n.png")
        meta[gid] = {"kind": kind, "w": w, "h": h, "t": t, "lines": [l for l, _ in lines], "uv": [0, 0, 1, 1]}
    # 墓碑侧面 / 顶面用的无缝石头
    rng = np.random.default_rng(11)
    col, hgt = stone_surface(rng, 512, 512, 0.5)
    col = np.asarray(to_img(col).filter(ImageFilter.GaussianBlur(0.5)), np.float32) / 255.0
    to_img(col).save(OUT / "edge_stone_side.jpg", quality=90)
    (OUT / "edge_graves.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- 纸条
def paper(rng, W, H):
    base = np.array([0.86, 0.80, 0.64], np.float32)
    a = base * (0.9 + 0.12 * fbm(rng, W, H, 64)[..., None]) * (0.96 + 0.06 * vnoise(rng, W, H, 2)[..., None])
    ex = np.minimum(np.arange(W)[None, :], W - 1 - np.arange(W)[None, :]) / (W * 0.12)
    ey = np.minimum(np.arange(H)[:, None], H - 1 - np.arange(H)[:, None]) / (H * 0.12)
    edge = np.clip(1 - np.minimum(ex, ey), 0, 1) ** 1.5
    a = a * (1 - 0.35 * edge[..., None]) + np.array([0.45, 0.32, 0.16]) * 0.35 * edge[..., None]
    return a


def gen_note():
    W, H = 512, 384
    rng = np.random.default_rng(4243)
    a = paper(rng, W, H)
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    for i, t in enumerate(("TO BE", "WRITTEN")):
        f = ImageFont.truetype(str(HAND), 128)
        b = d.textbbox((0, 0), t, font=f)
        d.text(((W - (b[2] - b[0])) // 2 - b[0] + (i * 18 - 10), 60 + i * 140 - b[1]), t, font=f, fill=255)
    ink = np.asarray(m.filter(ImageFilter.GaussianBlur(0.8)), np.float32)[..., None] / 255.0
    ink *= (0.8 + 0.2 * vnoise(rng, W, H, 6))[..., None]
    a = a * (1 - ink) + np.array([0.10, 0.07, 0.05]) * ink
    # 钉子 + 锈迹
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(xx - W / 2, yy - 26)
    a = a * (1 - np.clip((14 - r) / 3, 0, 1)[..., None]) + np.array([0.12, 0.1, 0.09]) * np.clip((14 - r) / 3, 0, 1)[..., None]
    rust = np.clip(1 - np.abs(xx - W / 2 - 2) / 6, 0, 1) * np.clip((yy - 30) / 10, 0, 1) * np.clip(1 - (yy - 30) / 70, 0, 1)
    a = a * (1 - 0.35 * rust[..., None]) + np.array([0.45, 0.22, 0.08]) * 0.35 * rust[..., None]
    to_img(a).save(OUT / "edge_note_tbd.jpg", quality=92)


# ---------------------------------------------------------------- 干草卡片
def gen_grass():
    S = 1024
    rng = np.random.default_rng(55)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cols = [(196, 168, 110), (170, 140, 88), (150, 128, 90), (205, 186, 140), (128, 112, 80), (120, 116, 84)]
    for _ in range(170):
        x0 = rng.normal(S / 2, S * 0.16); hgt = S * rng.uniform(0.35, 0.95)
        lean = rng.normal(0, 0.35) * hgt; c = cols[rng.integers(len(cols))]
        wid = rng.uniform(5, 11); pts = []
        for k in range(12):
            t = k / 11
            pts.append((x0 + lean * t * t, S - 1 - hgt * t, wid * (1 - t) + 1))
        for (xa, ya, wa), (xb, yb, wb) in zip(pts, pts[1:]):
            d.line([(xa, ya), (xb, yb)], fill=(*c, 255), width=max(1, int(wa)))
        if rng.random() < 0.25:     # 草穗
            xt, yt, _ = pts[-1]
            for k in range(6):
                jx = rng.normal(0, 3); d.ellipse([xt - 4 + jx, yt + k * 7, xt + 4 + jx, yt + k * 7 + 10], fill=(*cols[3], 255))
    im = im.resize((512, 512), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255.0
    yy = np.linspace(0, 1, 512)[:, None]
    a[..., :3] *= (0.6 + 0.4 * (1 - yy))[..., None]   # 根部暗
    # 透明处填邻近颜色，避免 mip 发黑边
    rgb = a[..., :3].copy(); al = a[..., 3:]
    blur = np.asarray(Image.fromarray((rgb * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32) / 255.0
    wb = np.asarray(Image.fromarray((al[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255.0
    fill = blur / np.maximum(wb, 1e-3)
    rgb = rgb * al + np.clip(fill, 0, 1) * (1 - al)
    out = np.concatenate([rgb, al], -1)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(OUT / "edge_grass_dry.png")


# ---------------------------------------------------------------- 画布背面 + 织纹
def gen_canvas_back():
    S = 512; P = 8            # 每根线 8 px
    rng = np.random.default_rng(77)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    warp = np.sin(np.pi * xx / P) ** 2 * (0.5 + 0.5 * np.sign(np.sin(np.pi * (yy / P + np.floor(xx / P)))))
    weft = np.sin(np.pi * yy / P) ** 2 * (0.5 - 0.5 * np.sign(np.sin(np.pi * (yy / P + np.floor(xx / P)))))
    hgt = warp + weft + 0.4 * vnoise(rng, S, S, 2, periodic=True) + 0.5 * vnoise(rng, S, S, 64, periodic=True)
    to_img(normal_from_height(hgt.astype(np.float32), 1.2)).save(OUT / "edge_canvas_weave_n.png")
    col = np.array([0.74, 0.68, 0.56], np.float32) * (0.85 + 0.1 * hgt[..., None] / hgt.max())
    col *= (0.9 + 0.15 * fbm(rng, S, S, 64, periodic=True))[..., None]
    to_img(col).save(OUT / "edge_canvas_back.jpg", quality=90)


# ---------------------------------------------------------------- 画：Blender 渲染 → 手绘布景
CANVAS_Y0, CANVAS_Y1, CANVAS_Z0, CANVAS_Z1 = -34.0, 20.0, -0.1, 14.0
HOLE = (-8.6, -6.0, -0.1, 3.4)     # y0, y1, z0, z1：路口那块可以撕开的布
SEAM_W = 2.7                       # 一幅布宽（米）


def kuwahara(a, r):
    """快速 Kuwahara（积分图）：油画一样的平块笔触，保留边缘。a: HxWx3 float。"""
    H, W, _ = a.shape
    lum = a @ np.array([0.3, 0.59, 0.11], np.float32)
    pad = lambda x: np.pad(x, ((r + 1, r + 1), (r + 1, r + 1)) + ((0, 0),) * (x.ndim - 2), mode="edge")
    def box_sum(x):
        p = pad(x); c = p.cumsum(0).cumsum(1)
        c = np.pad(c, ((1, 0), (1, 0)) + ((0, 0),) * (x.ndim - 2))
        return c
    cs_l, cs_l2, cs_c = box_sum(lum), box_sum(lum * lum), box_sum(a)
    n = (r + 1) ** 2
    best_var = np.full((H, W), np.inf, np.float32); out = np.zeros_like(a)
    for dy0, dx0 in ((-r, -r), (-r, 0), (0, -r), (0, 0)):
        y0 = np.arange(H) + r + 1 + dy0; x0 = np.arange(W) + r + 1 + dx0
        Y0, X0 = y0[:, None], x0[None, :]; Y1, X1 = Y0 + r + 1, X0 + r + 1
        def rect(c):
            return c[Y1, X1] - c[Y0, X1] - c[Y1, X0] + c[Y0, X0]
        m = rect(cs_l) / n; v = rect(cs_l2) / n - m * m
        sel = v < best_var
        best_var = np.where(sel, v, best_var)
        out = np.where(sel[..., None], rect(cs_c) / n, out)
    return out


def gen_canvas():
    raw = Image.open(OUT / "edge_canvas_raw.png").convert("RGB")
    W, H = 4096, 2048
    a = np.asarray(raw.resize((W, H), Image.BICUBIC), np.float32) / 255.0
    rng = np.random.default_rng(2026)
    m_per_px_x = (CANVAS_Y1 - CANVAS_Y0) / W
    m_per_px_y = (CANVAS_Z1 - CANVAS_Z0) / H
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wy = CANVAS_Y0 + (xx + 0.5) * m_per_px_x          # 布面上的世界 y
    wz = CANVAS_Z1 - (yy + 0.5) * m_per_px_y          # 世界 z
    # 0) 画布最底下 ~0.15 m 埋在地里，渲染里那几行是路面以下（黑）：用上方的颜色填平
    fill_row = int((CANVAS_Z1 - 0.15) / (CANVAS_Z1 - CANVAS_Z0) * H)
    a[fill_row:] = a[fill_row - 1:fill_row]
    # 1) 油画笔触：大笔刷平块 + 方向性笔痕
    a = kuwahara(a, 5)
    a = kuwahara(a, 3)
    sky = np.clip((wz - 2.6) / 2.0, 0, 1)
    sh = vnoise(rng, W, H, 3)
    horiz = np.asarray(to_img(sh).resize((W // 24, H)).resize((W, H), Image.BICUBIC), np.float32) / 255.0   # 横扫（天空）
    diag = np.asarray(to_img(vnoise(rng, W, H, 3)).resize((W // 6, H // 3)).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    stroke = horiz * sky + diag * (1 - sky)
    a = a * (1 + 0.10 * (stroke[..., None] - 0.5))
    # 2) 轻微色阶化 + 褪色、黑位抬高、偏暖的旧清漆
    a = np.round(a * 28) / 28
    lum = (a @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
    a = lum + (a - lum) * 0.78
    a = 0.07 + a * 0.9
    a *= np.array([1.03, 1.0, 0.93], np.float32)
    # 3) 布幅接缝（竖直）：一道暗缝 + 两侧微微隆起的折边 + 针脚
    seam_xs = [CANVAS_Y0 + SEAM_W * k for k in range(1, int((CANVAS_Y1 - CANVAS_Y0) / SEAM_W) + 1)]
    for sx in seam_xs:
        dpx = (wy - sx) / m_per_px_x
        line = np.exp(-(dpx / 1.1) ** 2)
        ridge = np.exp(-((np.abs(dpx) - 4) / 3) ** 2)
        a *= (1 - 0.13 * line + 0.04 * ridge)[..., None]
        stitch = line * (np.sin(yy * 1.2) > 0.4)
        a = a * (1 - 0.06 * stitch[..., None])
    # 4) 水渍：几圈潮印 + 从顶上流下来的污痕
    for _ in range(8):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H) if rng.random() < 0.5 else rng.uniform(H * 0.7, H)
        rr = rng.uniform(40, 220)
        d = np.hypot((xx - cx) / 1.0, (yy - cy) / 0.6)
        wob = 1 + 0.15 * (vnoise(rng, W, H, 64) - 0.5)
        ring = np.exp(-((d / rr - wob) / 0.07) ** 2) * 0.09 + np.clip(1 - d / (rr * wob), 0, 1) ** 0.5 * 0.07
        a = a * (1 - ring[..., None]) + np.array([0.42, 0.32, 0.18]) * ring[..., None]
    drip = vnoise(rng, W, H, 4)
    drip = np.asarray(to_img(drip).resize((W // 4, 6)).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    drip = np.clip(drip - 0.62, 0, 1) * 2.5 * np.clip(1 - yy / (H * 0.5), 0, 1)
    a = a * (1 - 0.25 * drip[..., None]) + np.array([0.35, 0.3, 0.22]) * 0.25 * drip[..., None]
    # 5) 底边：泥污 + 磨毛的线头
    bottom = np.clip((0.55 - wz) / 0.6, 0, 1) * (0.7 + 0.3 * vnoise(rng, W, H, 16))
    a = a * (1 - 0.55 * bottom[..., None]) + np.array([0.33, 0.27, 0.2]) * 0.55 * bottom[..., None]
    fray = (rng.random(W) < 0.35) * rng.uniform(0.0, 0.18, W)
    threads = (wz < CANVAS_Z0 + 0.06 + fray[None, :]) & (wz < 0.15)
    a[threads] = a[threads] * 0.6 + np.array([0.55, 0.48, 0.38]) * 0.4
    # 6) 四边留白：没上颜料的生布，笔触边缘参差
    raw_col = np.array([0.72, 0.66, 0.54], np.float32) * (0.92 + 0.1 * vnoise(rng, W, H, 8)[..., None])
    edge_n = 0.12 * vnoise(rng, W, H, 12)
    margin = np.minimum(np.minimum(wy - CANVAS_Y0, CANVAS_Y1 - wy), CANVAS_Z1 - wz)
    unp = np.clip((0.35 + edge_n - margin) / 0.06, 0, 1)
    a = a * (1 - unp[..., None]) + raw_col * unp[..., None]
    # 7) 织纹（像素级）：近看是布
    weave = (np.sin(xx * np.pi * 0.5) * np.sin(yy * np.pi * 0.5)) * 0.025
    a = a * (1 + weave[..., None])
    # 8) 撕口：活页（南边 y0）是折痕；上沿、北沿是撕开的毛边
    y0, y1, z0, z1 = HOLE
    tear_n = (vnoise(rng, W, H, 3) - 0.5) * 0.5 + (vnoise(rng, W, H, 24) - 0.5) * 4
    d_top = (wz - z1) / m_per_px_y + tear_n * 3
    d_side = (wy - y1) / m_per_px_x + tear_n * 3
    in_y = (wy > y0 - 0.02) & (wy < y1 + 0.02)
    in_z = wz < z1 + 0.02
    tear = np.zeros((H, W), np.float32)
    tear += np.exp(-(d_top / 1.6) ** 2) * in_y
    tear += np.exp(-(d_side / 1.6) ** 2) * in_z
    fibers = np.clip((np.exp(-((np.abs(d_top) - 3.5) / 1.2) ** 2) * in_y + np.exp(-((np.abs(d_side) - 3.5) / 1.2) ** 2) * in_z), 0, 1)
    fibers *= rng.random((H, W)) > 0.5
    a = a * (1 - 0.45 * np.clip(tear, 0, 1)[..., None])
    a = a * (1 - 0.6 * fibers[..., None]) + np.array([0.82, 0.77, 0.66]) * 0.6 * fibers[..., None]
    crease = np.exp(-(((wy - y0) / m_per_px_x) / 2.5) ** 2) * in_z
    a = a * (1 - 0.18 * crease[..., None])
    # 布被反复抓过的地方更脏
    grab = np.exp(-(((wy - (y0 + y1) / 2) / 1.6) ** 2 + ((wz - 1.3) / 1.0) ** 2))
    a = a * (1 - 0.1 * grab[..., None])
    # Unity 的贴图上限是 2048（TextureImportRules），所以在 y = -7（正好是一道布幅接缝）劈成南北两张 2048²
    img = to_img(a)
    img.crop((0, 0, W // 2, H)).save(OUT / "edge_canvas_paint_s.jpg", quality=90)
    img.crop((W // 2, 0, W, H)).save(OUT / "edge_canvas_paint_n.jpg", quality=90)
    print("wrote", OUT / "edge_canvas_paint_[sn].jpg")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--canvas" in sys.argv:
        gen_canvas(); return
    gen_note(); gen_stones(); gen_grass(); gen_canvas_back()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
