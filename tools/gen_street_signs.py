"""生成对街招牌贴图（手绘油漆字 + 风化），确定性输出到 art/source/_derived/street/。

用法：<带 Pillow 的 python> tools/gen_street_signs.py
字体：art/source/fonts/Rye-Regular.ttf（SIL OFL，tools/fetch_assets.py 下载）。只栅格化成贴图，字体文件不进工程。
"""
import pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "art" / "source" / "fonts" / "Rye-Regular.ttf"
OUT = ROOT / "art" / "source" / "_derived" / "street"

# 名字 → (底色, 字色, 描边色, 宽, 高, 小字)
SIGNS = {
    "general_store": ((0.20, 0.27, 0.22), (0.93, 0.86, 0.66), (0.55, 0.12, 0.08), 1024, 256, "GENERAL STORE", "DRY GOODS · HARDWARE · PROVISIONS"),
    "assay_office":  ((0.88, 0.82, 0.68), (0.14, 0.12, 0.10), (0.62, 0.45, 0.12), 1024, 256, "ASSAY OFFICE", "GOLD & SILVER BOUGHT"),
    "hotel":         ((0.42, 0.10, 0.08), (0.95, 0.88, 0.66), (0.10, 0.06, 0.04), 1024, 256, "HOTEL", "MERCY CREEK · ROOMS & BOARD"),
    "feed_livery":   ((0.85, 0.80, 0.68), (0.30, 0.10, 0.07), (0.20, 0.16, 0.12), 1024, 256, "FEED & LIVERY", "HORSES BOARDED · HAY · GRAIN"),
    "barber":        ((0.92, 0.88, 0.78), (0.20, 0.18, 0.40), (0.55, 0.12, 0.08), 512, 128, "BARBER", "BATHS 25¢"),
    "bank_window":   ((0.03, 0.03, 0.035), (0.80, 0.64, 0.30), (0.03, 0.03, 0.035), 512, 128, "BANK", ""),
}


def fit_font(draw, text, max_w, max_h):
    size = max_h
    while size > 8:
        f = ImageFont.truetype(str(FONT), size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h:
            return f, b
        size -= 2
    return f, b


def noise(rng, w, h, scale):
    """低频值噪声（双线性放大），0..1。"""
    g = rng.random((h // scale + 2, w // scale + 2))
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((w + scale * 2, h + scale * 2), Image.BICUBIC)
    return np.asarray(im, np.float32)[:h, :w] / 255.0


def make(name, bg, fg, edge, W, H, text, small):
    rng = np.random.default_rng(sum(map(ord, name)) * 7919)
    to8 = lambda c: tuple(int(v * 255) for v in c)
    im = Image.new("RGB", (W, H), to8(bg))
    d = ImageDraw.Draw(im)
    m = H // 14
    d.rectangle([m, m, W - m - 1, H - m - 1], outline=to8(edge), width=max(3, H // 40))
    d.rectangle([m * 2, m * 2, W - m * 2 - 1, H - m * 2 - 1], outline=to8(fg), width=max(1, H // 120))
    main_h = int(H * (0.50 if small else 0.62))
    f, b = fit_font(d, text, W - m * 8, main_h)
    tw, th = b[2] - b[0], b[3] - b[1]
    y0 = int(H * (0.16 if small else 0.2)) - b[1]
    x0 = (W - tw) // 2 - b[0]
    sh = max(2, H // 60)
    d.text((x0 + sh, y0 + sh), text, font=f, fill=to8(edge))   # 投影描边，像手绘招牌
    d.text((x0, y0), text, font=f, fill=to8(fg))
    if small:
        fs, bs = fit_font(d, small, W - m * 10, int(H * 0.13))
        d.text(((W - (bs[2] - bs[0])) // 2 - bs[0], int(H * 0.74) - bs[1]), small, font=fs, fill=to8(fg))
    a = np.asarray(im, np.float32) / 255.0
    # 木纹：横向细条纹
    yy = np.arange(H)[:, None] / H
    grain = 0.025 * np.sin(yy * 140 + noise(rng, W, H, 64) * 4) + 0.05 * (noise(rng, W, H, 4) - 0.5)
    # 掉漆：低频遮罩阈值处露出底木
    peel = noise(rng, W, H, 64) * 0.45 + noise(rng, W, H, 10) * 0.35 + noise(rng, W, H, 3) * 0.2
    wood = np.array([0.42, 0.32, 0.22], np.float32)
    mask = np.clip((peel - 0.70) * 10, 0, 1)[..., None] * 0.85
    a = a * (1 - mask) + wood * mask
    a = a * (1 + grain[..., None])
    # 日晒褪色 + 边缘污渍
    fade = 0.85 + 0.15 * noise(rng, W, H, 96)[..., None]
    a = a * fade + 0.06 * (1 - fade)
    ex = np.minimum(np.arange(W)[None, :], W - 1 - np.arange(W)[None, :]) / (W * 0.08)
    ey = np.minimum(np.arange(H)[:, None], H - 1 - np.arange(H)[:, None]) / (H * 0.25)
    dirt = np.clip(1 - np.minimum(ex, ey), 0, 1)[..., None] * 0.25
    a = a * (1 - dirt) + np.array([0.25, 0.2, 0.15]) * dirt
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    OUT.mkdir(parents=True, exist_ok=True)
    out.save(OUT / f"sign_{name}.jpg", quality=90)
    print("wrote", OUT / f"sign_{name}.jpg")


if __name__ == "__main__":
    for k, v in SIGNS.items():
        make(k, *v)
