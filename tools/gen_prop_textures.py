"""生成道具用的文字贴图（日历、信、打字纸、笔记本内页、打字机键帽图集）。确定性（固定随机种子）。

用法：<装了 Pillow 的 python> tools/gen_prop_textures.py
输入：art/source/ambientcg/Paper005（CC0 纸张底纹）、art/source/fonts/Rye-Regular.ttf（SIL OFL，只栅格化不分发）
输出：art/source/_derived/props/*.png
"""
import calendar, pathlib, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "art" / "source"
OUT = SRC / "_derived" / "props"
FONT = str(SRC / "fonts" / "Rye-Regular.ttf")
INK = (52, 34, 22)          # 褐色铁胆墨水
RED = (150, 30, 24)


def font(sz):
    return ImageFont.truetype(FONT, sz)


def paper(w, h, tint=(1.0, 0.97, 0.88), seed=0):
    base = Image.open(next((SRC / "ambientcg" / "Paper005").glob("*_Color.jpg"))).convert("RGB")
    base = base.resize((max(w, h), max(w, h))).crop((0, 0, w, h))
    # 提亮并偏旧黄：Paper005 偏深，信纸要浅
    r, g, b = base.split()
    lut = lambda t: (lambda v: min(255, int((v * 0.55 + 120) * t)))
    base = Image.merge("RGB", (r.point(lut(tint[0])), g.point(lut(tint[1])), b.point(lut(tint[2]))))
    # 边缘泛黄 / 暗角
    rnd = random.Random(seed)
    vig = Image.new("L", (w, h), 0); d = ImageDraw.Draw(vig)
    for i in range(40):
        d.rectangle([i * 2, i * 2, w - 1 - i * 2, h - 1 - i * 2], outline=int(255 * (1 - i / 40) * 0.5))
    vig = vig.filter(ImageFilter.GaussianBlur(18))
    stain = Image.new("RGB", (w, h), (150, 110, 60))
    base = Image.composite(stain, base, vig.point(lambda v: v // 3))
    # 几块淡水渍
    d2 = ImageDraw.Draw(base, "RGBA")
    for _ in range(3):
        x, y, rr = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(30, 90)
        d2.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(140, 100, 50, 10), outline=(140, 100, 50, 22), width=2)
    return base


def hand_text(img, xy, text, size, color=INK, seed=1, spacing=0.92, wobble=2.0, rot=4.0):
    """逐字抖动 + 微旋转，模拟手写；返回结束 x。"""
    rnd = random.Random(seed); f = font(size)
    x, y = xy
    for ch in text:
        if ch == " ":
            x += size * 0.32; continue
        bb = f.getbbox(ch); cw, chh = bb[2] - bb[0] + 8, size + 16
        g = Image.new("L", (cw + 16, chh + 16), 0)
        ImageDraw.Draw(g).text((8 - bb[0], 8), ch, font=f, fill=255)
        g = g.rotate(rnd.uniform(-rot, rot), resample=Image.BICUBIC, expand=False)
        col = Image.new("RGB", g.size, tuple(max(0, c + rnd.randint(-12, 12)) for c in color))
        img.paste(col, (int(x), int(y + rnd.uniform(-wobble, wobble))), g.point(lambda v: int(v * rnd.uniform(0.8, 0.95))))
        x += (bb[2] - bb[0]) * spacing + size * 0.04
    return x


def typed_text(img, xy, text, size, seed=2):
    """打字机：等宽步进、墨色深浅不一、个别字偏上下。"""
    rnd = random.Random(seed); f = font(size); d = ImageDraw.Draw(img)
    x, y = xy; step = size * 0.62
    for ch in text:
        if ch != " ":
            bb = f.getbbox(ch)
            ink = rnd.randint(20, 70)
            d.text((x + (step - (bb[2] - bb[0])) / 2 - bb[0], y + rnd.uniform(-1.5, 1.5)), ch, font=f, fill=(ink, ink - 5, ink - 8))
        x += step


def calendar_page():
    W, H = 768, 1024
    im = paper(W, H, seed=3); d = ImageDraw.Draw(im)
    def ctext(y, s, sz, col=INK):
        f = font(sz); bb = d.textbbox((0, 0), s, font=f); d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], y), s, font=f, fill=col)
    ctext(40, "COMPLIMENTS OF", 26)
    ctext(78, "J. HALE & SONS", 52, RED)
    ctext(146, "General Merchandise  ·  Mercy Creek", 24)
    d.line([(60, 190), (W - 60, 190)], fill=INK, width=3); d.line([(60, 197), (W - 60, 197)], fill=INK, width=1)
    ctext(220, "JUNE", 130)
    ctext(368, "1882", 64, RED)
    # 日期格
    gx0, gy0, cw, ch = 54, 470, (W - 108) / 7, 92
    days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i, s in enumerate(days):
        f = font(24); bb = d.textbbox((0, 0), s, font=f)
        d.text((gx0 + i * cw + (cw - bb[2]) / 2, gy0), s, font=f, fill=RED if i == 0 else INK)
    cal = calendar.Calendar(firstweekday=6).monthdayscalendar(1882, 6)
    y0 = gy0 + 40
    for r in range(len(cal) + 1):
        d.line([(gx0, y0 + r * ch), (gx0 + 7 * cw, y0 + r * ch)], fill=(90, 70, 50), width=2)
    for c in range(8):
        d.line([(gx0 + c * cw, y0), (gx0 + c * cw, y0 + len(cal) * ch)], fill=(90, 70, 50), width=2)
    for r, week in enumerate(cal):
        for c, day in enumerate(week):
            if not day: continue
            f = font(44); s = str(day); bb = d.textbbox((0, 0), s, font=f)
            cx, cy = gx0 + c * cw + cw / 2, y0 + r * ch + ch / 2
            d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - 26), s, font=f, fill=RED if c == 0 else INK)
            if day == 14:   # 被反复圈过的那天：好几圈红墨水
                rnd = random.Random(14)
                for k in range(4):
                    rx, ry = 44 + rnd.uniform(-4, 6), 38 + rnd.uniform(-4, 6)
                    ox, oy = rnd.uniform(-4, 4), rnd.uniform(-4, 4)
                    d.ellipse([cx - rx + ox, cy - ry + oy, cx + rx + ox, cy + ry + oy], outline=(165, 25, 20), width=3)
    return im


def letter_page():
    W, H = 800, 1024
    im = paper(W, H, tint=(1.0, 0.98, 0.92), seed=5)
    # 三折痕
    d = ImageDraw.Draw(im, "RGBA")
    for y in (H // 3, 2 * H // 3):
        d.line([(0, y), (W, y)], fill=(120, 90, 60, 70), width=3)
        d.line([(0, y + 3), (W, y + 3)], fill=(255, 250, 235, 60), width=2)
    hand_text(im, (70, 70), "Mercy Creek, June 14", 34, seed=11)
    hand_text(im, (70, 160), "Nell —", 52, seed=12)
    lines = ["Don't trust", "the clock.", "", "Go to room 4."]
    y = 250
    for i, s in enumerate(lines):
        if s: hand_text(im, (110, y), s, 62, seed=20 + i)
        y += 96
    hand_text(im, (W - 300, 760), "— yours, N.", 44, seed=30)
    return im


def typed_page():
    W, H = 784, 1024     # 信纸比例 8.5 x 11
    im = paper(W, H, tint=(1.02, 1.0, 0.95), seed=7)
    lines = ["DRAFT  VII", "", "Afternoon. The piano begins", "again. Gus says it will be a", "fine day, Nell. He says it", "twice.", "",
             "Nell pushed open the door", "of Room 4 ..."]
    y = 70
    for i, s in enumerate(lines):
        typed_text(im, (70, y), s, 36, seed=40 + i); y += 54
    return im


def notebook_pages():
    W, H = 1024, 768     # 左半 = 左页，右半 = 右页
    im = paper(W, H, tint=(1.0, 0.97, 0.86), seed=9); d = ImageDraw.Draw(im, "RGBA")
    for x0 in (0, W // 2):
        for y in range(110, H - 30, 52):
            d.line([(x0 + 30, y), (x0 + W // 2 - 30, y)], fill=(90, 120, 150, 90), width=2)
        d.line([(x0 + 70, 40), (x0 + 70, H - 20)], fill=(170, 60, 60, 90), width=2)
    # 书脊阴影
    sh = Image.new("L", (W, H), 0); ImageDraw.Draw(sh).rectangle([W // 2 - 26, 0, W // 2 + 26, H], fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    im = Image.composite(Image.new("RGB", (W, H), (110, 85, 55)), im, sh)
    left = [("June 14 -  3 o'clock", 30), ("Clock stopped again.", 30), ("Piano: wrong note.", 30),
            ("Girl wipes the", 30), ("chipped glass.", 30)]
    right = [("She will say:", 30), ('"Everything is', 32), ('fine here."', 32), ("", 0), ("Draft VII.", 30), ("Martha  Nell", 30)]
    for col, lines, seed in ((0, left, 50), (W // 2, right, 60)):
        y = 70
        for i, (s, sz) in enumerate(lines):
            if s: hand_text(im, (col + 84, y), s, sz, seed=seed + i, wobble=1.5)
            y += 52
    # 把"Martha"划掉
    d = ImageDraw.Draw(im); d.line([(W // 2 + 82, 70 + 5 * 52 + 22), (W // 2 + 210, 70 + 5 * 52 + 18)], fill=INK, width=4)
    return im


KEYROWS = ["23456789-,", "QWE.TYIUOP", "ZSDFGHJKLM", "AX&CVBN?;R"]


def key_atlas():
    """8x5 格（128 px）；格 i 对应 KEYROWS 拼起来的第 i 个字。"""
    im = Image.new("RGB", (1024, 640), (20, 18, 16)); d = ImageDraw.Draw(im)
    chars = "".join(KEYROWS)
    for i, ch in enumerate(chars):
        cx, cy = (i % 8) * 128 + 64, (i // 8) * 128 + 64
        d.ellipse([cx - 62, cy - 62, cx + 62, cy + 62], fill=(30, 28, 26))
        d.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=(228, 220, 196))   # 象牙白字面
        d.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], outline=(160, 150, 120), width=3)
        f = font(56); bb = d.textbbox((0, 0), ch, font=f)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), ch, font=f, fill=(25, 22, 20))
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("calendar", calendar_page), ("letter", letter_page), ("typed_page", typed_page),
                     ("notebook_pages", notebook_pages), ("typewriter_keys", key_atlas)]:
        fn().save(OUT / f"{name}.png", optimize=True)
        print("wrote", OUT / f"{name}.png")


if __name__ == "__main__":
    main()
