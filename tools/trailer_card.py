"""宣传片片尾字卡（ffmpeg 没编 drawtext，用 Pillow 出帧）：python tools/trailer_card.py <输出目录> [秒数]"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 3.5
font = Path(__file__).resolve().parents[1] / "art/source/fonts/NotoSerifSC-Regular.otf"
big, small = ImageFont.truetype(str(font), 110), ImageFont.truetype(str(font), 46)
bg, ink, gold = (13, 10, 8), (240, 226, 200), (232, 196, 138)
for f in range(int(secs * 30)):
    t = f / 30
    im = Image.new("RGB", (1920, 1080), bg); d = ImageDraw.Draw(im)
    def text(s, fnt, col, y, a):
        a = max(0.0, min(1.0, a))
        c = tuple(int(bg[i] + (col[i] - bg[i]) * a) for i in range(3))
        w = d.textlength(s, font=fnt); d.text(((1920 - w) / 2, y), s, font=fnt, fill=c)
    text("MERCY CREEK", big, ink, 1080 / 2 - 140, t / 0.8)
    text("每天下午三点，一切重来。", small, gold, 1080 / 2 + 30, (t - 0.6) / 0.8)
    im.save(out / f"card_{f:04d}.png")
