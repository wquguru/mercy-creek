"""生成街道招牌贴图（手绘油漆字 + 风化）及小镇纸条 / 告示 / 钟面，确定性输出到 art/source/_derived/street/。

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
    # 北侧一排（tools/blender/build_town.py）
    "saloon":        ((0.30, 0.09, 0.06), (0.94, 0.84, 0.58), (0.08, 0.05, 0.03), 2048, 288, "MERCY CREEK SALOON", "WINES · LIQUORS · CIGARS"),
    "telegraph":     ((0.86, 0.82, 0.70), (0.12, 0.16, 0.30), (0.55, 0.12, 0.08), 1024, 224, "TELEGRAPH", "MESSAGES SENT & RECEIVED"),
    "undertaker":    ((0.07, 0.07, 0.07), (0.84, 0.80, 0.70), (0.30, 0.28, 0.26), 1024, 224, "UNDERTAKER", "COFFINS · FUNERALS"),
    "sheriff":       ((0.80, 0.74, 0.58), (0.16, 0.12, 0.08), (0.55, 0.40, 0.10), 1024, 224, "SHERIFF", "JAIL · OFFICE"),
    "baths":         ((0.20, 0.30, 0.34), (0.95, 0.90, 0.76), (0.08, 0.06, 0.05), 1024, 224, "BATHS · SHAVE", "HOT WATER 25¢"),
}
HAND = ROOT / "art" / "source" / "fonts" / "Zeyada.ttf"     # SIL OFL 手写体（门上纸条）


def paper(rng, W, H, base=(0.86, 0.81, 0.68)):
    """旧纸：底色 + 低频污渍 + 纤维噪声 + 边缘发黄。返回 float RGB。"""
    a = np.ones((H, W, 3), np.float32) * np.array(base, np.float32)
    a *= (0.9 + 0.1 * noise(rng, W, H, 48))[..., None]
    a *= (0.96 + 0.04 * noise(rng, W, H, 2))[..., None]
    ex = np.minimum(np.arange(W)[None, :], W - 1 - np.arange(W)[None, :]) / (W * 0.12)
    ey = np.minimum(np.arange(H)[:, None], H - 1 - np.arange(H)[:, None]) / (H * 0.12)
    e = np.clip(1 - np.minimum(ex, ey), 0, 1)[..., None] * 0.35
    return a * (1 - e) + np.array([0.55, 0.42, 0.25]) * e


def ink(a, layer, color=(0.08, 0.07, 0.06), amount=0.92):
    """把 L 图层（白字）当墨迹压到纸上。"""
    m = np.asarray(layer, np.float32)[..., None] / 255.0 * amount
    return a * (1 - m) + np.array(color, np.float32) * m


def save(a, name):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)).save(OUT / name, quality=90)
    print("wrote", OUT / name)


def make_note():
    """门上钉的手写纸条 "TO BE WRITTEN"（待写的建筑）。"""
    W, H = 384, 288
    rng = np.random.default_rng(4242)
    a = paper(rng, W, H)
    font = HAND if HAND.exists() else FONT
    lay = Image.new("L", (W, H), 0); d = ImageDraw.Draw(lay)
    for i, (t, sz) in enumerate((("TO BE", 92), ("WRITTEN", 92))):
        f = ImageFont.truetype(str(font), sz)
        b = d.textbbox((0, 0), t, font=f)
        d.text(((W - (b[2] - b[0])) // 2 - b[0] + (i * 14 - 8), 34 + i * 108 - b[1]), t, font=f, fill=255)
    lay = lay.rotate(-3, resample=Image.BICUBIC)
    a = ink(a, lay, (0.10, 0.08, 0.07), 0.9)
    yy, xx = np.mgrid[0:H, 0:W]                       # 钉子孔周围的锈迹
    r = np.hypot(xx - W / 2, yy - 16)
    a = a * (1 - (np.exp(-(r / 9) ** 2) * 0.6)[..., None]) + np.array([0.3, 0.17, 0.08]) * (np.exp(-(r / 9) ** 2) * 0.6)[..., None]
    save(a, "note_tbd.jpg")


NOTICES = {
    "notice_rates": ["TELEGRAMS", "—", "TEN WORDS ... 25¢", "EACH ADD'L WORD ... 2¢", "NIGHT LETTERS HALF RATE", "", "PAY AT THE WICKET"],
    "notice_hours": ["NOTICE", "", "THIS OFFICE OPEN", "7 A.M. TO 6 P.M.", "SUNDAYS CLOSED", "", "BY ORDER OF THE AGENT"],
    "notice_line":  ["NOTICE", "", "THE LINE WEST OF", "MERCY CREEK", "IS NOT IN SERVICE", "", "NO MESSAGES ACCEPTED"],
}


def make_notices():
    """电报局墙上钉的告示（印刷字）。"""
    W, H = 256, 352
    for k, (name, lines) in enumerate(NOTICES.items()):
        rng = np.random.default_rng(900 + k)
        a = paper(rng, W, H, base=(0.88, 0.84, 0.72) if k != 1 else (0.84, 0.78, 0.62))
        lay = Image.new("L", (W, H), 0); d = ImageDraw.Draw(lay)
        y = 30
        for i, t in enumerate(lines):
            if not t:
                y += 18; continue
            f, b = fit_font(d, t, W - 50, 44 if i == 0 else 24)
            d.text(((W - (b[2] - b[0])) // 2 - b[0], y - b[1]), t, font=f, fill=255)
            y += (b[3] - b[1]) + (20 if i == 0 else 14)
        d.rectangle([12, 12, W - 13, H - 13], outline=255, width=2)
        save(ink(a, lay, (0.07, 0.06, 0.05), 0.88), f"{name}.jpg")


def make_clock():
    """挂钟表盘（罗马数字，指针另建模型）。"""
    import math
    S = 512
    rng = np.random.default_rng(31)
    a = paper(rng, S, S, base=(0.90, 0.86, 0.74))
    lay = Image.new("L", (S, S), 0); d = ImageDraw.Draw(lay)
    c = S / 2
    d.ellipse([c - 236, c - 236, c + 236, c + 236], outline=255, width=6)
    d.ellipse([c - 200, c - 200, c + 200, c + 200], outline=255, width=2)
    for i in range(60):
        ang = math.radians(i * 6); r0 = 200 if i % 5 else 186
        d.line([(c + r0 * math.sin(ang), c - r0 * math.cos(ang)), (c + 212 * math.sin(ang), c - 212 * math.cos(ang))], fill=255, width=4 if i % 5 == 0 else 2)
    nums = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    f = ImageFont.truetype(str(FONT), 46)
    for i, t in enumerate(nums):
        ang = math.radians(i * 30)
        x, y = c + 148 * math.sin(ang), c - 148 * math.cos(ang)
        b = d.textbbox((0, 0), t, font=f)
        d.text((x - (b[2] + b[0]) / 2, y - (b[3] + b[1]) / 2), t, font=f, fill=255)
    a = ink(a, lay, (0.06, 0.05, 0.05), 0.9)
    yy, xx = np.mgrid[0:S, 0:S]                        # 表盘外的木边用深色填满
    a[np.hypot(xx - c, yy - c) > 246] = (0.18, 0.11, 0.06)
    save(a, "clock_face.jpg")


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
    make_note(); make_notices(); make_clock()
