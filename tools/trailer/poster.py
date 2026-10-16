"""竖版海报（X / 社交平台 4:5，1080×1350）：python tools/trailer/poster.py <竖版镜头目录> <输出.jpg> [镜头名 帧号]

镜头要用竖版窗口重拍（shoot 时 -screen-width 1080 -screen-height 1350），不从横版裁：
横版裁成 4:5 只剩 864 像素宽，放大发糊。调色和字体与预告片一致（edit.py）。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from edit import FELL, INK, ZH, font, grade, spaced  # noqa: E402

W, H = 1080, 1350


def line(img, text, fnt, track, cy, color=INK, glow=0.0, shadow=0.0):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    glyphs, tw = spaced(d, text, fnt, track)
    asc, desc = fnt.getmetrics()
    x0, y0 = W / 2 - tw / 2, cy - (asc + desc) / 2
    for amt, col, blur, dy in ((shadow, (0, 0, 0), 0.2, 4), (glow, color, 0.35, 0)):
        if amt > 0:
            s = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(s)
            for ch, x in glyphs:
                sd.text((x0 + x, y0 + dy), ch, font=fnt, fill=(*col, int(255 * amt)))
            layer = Image.alpha_composite(layer, s.filter(ImageFilter.GaussianBlur(fnt.size * blur)))
            d = ImageDraw.Draw(layer)
    for ch, x in glyphs:
        d.text((x0 + x, y0), ch, font=fnt, fill=(*color, 255))
    return Image.alpha_composite(img, layer)


def main():
    shots, out = Path(sys.argv[1]), Path(sys.argv[2])
    name, idx = (sys.argv[3], int(sys.argv[4])) if len(sys.argv) > 4 else ("void", 60)
    src = Image.open(shots / name / f"{idx:04d}.jpg").convert("RGB").resize((W, H), Image.LANCZOS)
    x = grade(np.asarray(src, np.float32) / 255, None)

    # 上下压暗留字：上方放开场日期，下方放片名区；中间画布门保持原亮度
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    yy, xx = yy / H, xx / W
    top = np.clip(1 - yy / 0.22, 0, 1) ** 1.6 * 0.75
    bot = np.clip((yy - 0.52) / 0.40, 0, 1) ** 1.3 * 0.88
    vig = 1 - 0.32 * np.clip(((xx - 0.5) / 0.5) ** 2 + ((yy - 0.45) / 0.55) ** 2, 0, 2) ** 1.3
    x = x * ((1 - top) * (1 - bot) * vig)[..., None]
    g = np.kron(np.random.default_rng(7).normal(0, 1, (H // 2, W // 2)), np.ones((2, 2)))[..., None]
    x = np.clip(x + g * 0.022 * (0.4 + 0.6 * (1 - x)), 0, 1)

    img = Image.fromarray((x * 255 + 0.5).astype(np.uint8)).convert("RGBA")
    img = line(img, "1882 年 6 月 14 日，下午三点。", font(ZH, 30), 0.16, 62, (214, 202, 180), shadow=0.6)
    img = line(img, "MERCY CREEK", font(FELL, 94), 0.18, 1022, (242, 230, 206), glow=0.45, shadow=0.5)
    img = line(img, "第几稿，你才会醒来？", font(ZH, 42), 0.22, 1118, INK, shadow=0.7)
    d = ImageDraw.Draw(img)
    d.line([(W / 2 - 60, 1180), (W / 2 + 60, 1180)], fill=(200, 186, 160, 160), width=1)
    img = line(img, "macOS  ·  网页版  ·  即将推出", font(ZH, 28), 0.14, 1224, (200, 186, 160))
    img = line(img, "游戏实机画面", font(ZH, 19), 0.2, 1306, (130, 122, 110))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=95, subsampling=0)
    print(out)


if __name__ == "__main__":
    main()
