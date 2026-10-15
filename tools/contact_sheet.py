"""把 Reviews/unity 下的截图拼成一张对照图：行 = 机位，列 = 时间点。"""
import sys, glob, os, re
from PIL import Image, ImageDraw
d = sys.argv[1]; out = sys.argv[2]
files = sorted(glob.glob(os.path.join(d, "game_*_t*.png")))
views = sorted({re.match(r"game_(.+)_t\d+", os.path.basename(f)[:-4]).group(1) for f in files})
times = sorted({re.search(r"_t(\d+)", f).group(1) for f in files})
W, H = 800, 450
sheet = Image.new("RGB", (W * len(times), (H + 24) * len(views)), "black")
dr = ImageDraw.Draw(sheet)
for r, v in enumerate(views):
    for c, t in enumerate(times):
        f = os.path.join(d, f"game_{v}_t{t}.png")
        if os.path.exists(f):
            sheet.paste(Image.open(f).convert("RGB").resize((W, H)), (c * W, r * (H + 24) + 24))
        dr.text((c * W + 8, r * (H + 24) + 6), f"{v}  t={int(t)}s", fill="white")
sheet.save(out)
print(out)
