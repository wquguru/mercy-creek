"""宣传片画面合成：python tools/trailer/edit.py <镜头目录> <输出 mp4> [--audio master.wav] [--from 秒 --to 秒] [--stills 目录]

按 edl.py 逐帧取素材 → 调色 → 2.39:1 黑边 → 暗角 + 胶片颗粒 → 字幕 / 字卡 / 片名，原始 RGB 直接管道给 ffmpeg。
ffmpeg 没编 drawtext，文字全部用 Pillow 画（思源宋体 / IM Fell，都是 OFL）。
"""
import argparse
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import edl

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "art/source/fonts"
W, H = 1920, 1080
BAR_H = 138                      # 2.39:1 → 画面高 803
PIC0, PIC1 = BAR_H, H - BAR_H
INK = (238, 228, 210)
FPS = edl.FPS


@lru_cache(None)
def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


ZH = "NotoSerifSC-Regular.otf"
ZH_B = "NotoSerifSC-Bold.otf"
FELL = "IMFeENsc28P.ttf"


# ---------------------------------------------------------------- 文字

def spaced(draw, text, fnt, track):
    """逐字排，字距 = track × 字号。返回 [(字, x偏移)], 总宽。"""
    xs, x = [], 0.0
    for ch in text:
        xs.append((ch, x))
        x += draw.textlength(ch, font=fnt) + track * fnt.size
    return xs, x - track * fnt.size


def text_layer(text, fnt, track, cy, alpha, color=INK, shadow=0.0, glow=0.0, cx=W / 2):
    """一行居中文字的 RGBA 图层（整帧大小）。shadow / glow = 柔和投影 / 辉光强度。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if alpha <= 0 or not text:
        return layer
    d = ImageDraw.Draw(layer)
    glyphs, tw = spaced(d, text, fnt, track)
    x0 = cx - tw / 2
    asc, desc = fnt.getmetrics()
    y0 = cy - (asc + desc) / 2
    a = int(255 * min(1.0, alpha))
    if shadow > 0 or glow > 0:
        s = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(s)
        col = (0, 0, 0, int(a * shadow)) if shadow > 0 else (*color, int(a * glow))
        for ch, x in glyphs:
            sd.text((x0 + x, y0 + (3 if shadow else 0)), ch, font=fnt, fill=col)
        s = s.filter(ImageFilter.GaussianBlur(fnt.size * (0.18 if shadow else 0.35)))
        layer = Image.alpha_composite(layer, s)
        d = ImageDraw.Draw(layer)
    for ch, x in glyphs:
        d.text((x0 + x, y0), ch, font=fnt, fill=(*color, a))
    return layer


def env(t, t0, t1, fin=0.35, fout=0.35):
    if t < t0 or t > t1:
        return 0.0
    k = min(1.0, (t - t0) / fin if fin else 1.0, (t1 - t) / fout if fout else 1.0)
    return k * k * (3 - 2 * k)


def typed(text, t, t0):
    n = int((t - t0) / edl.TYPE_RATE) + 1
    return text[:max(0, n)]


def draw_texts(img, t):
    """img: PIL RGB。返回叠好文字的图。"""
    over = None
    for (t0, t1, kind, text) in edl.TEXTS:
        if not (t0 - 0.01 <= t <= t1 + 0.01):
            continue
        if kind == "card":
            L = text_layer(text, font(ZH, 50), 0.16, H / 2, env(t, t0, t1, 0.45, 0.4))
        elif kind == "type_card":
            L = text_layer(typed(text, t, t0), font(ZH, 46), 0.14, H / 2, env(t, t0, t1, 0.01, 0.45))
        elif kind == "over":
            L = text_layer(text, font(ZH, 36), 0.16, PIC1 + BAR_H / 2, env(t, t0, t1, 0.4, 0.35))
        elif kind == "type":
            L = text_layer(typed(text, t, t0), font(ZH, 36), 0.14, PIC1 + BAR_H / 2, env(t, t0, t1, 0.01, 0.4))
        elif kind == "sub":
            L = text_layer(text, font(ZH, 33), 0.06, PIC1 + BAR_H / 2, env(t, t0, t1, 0.12, 0.12), color=(228, 220, 204))
        elif kind == "draft":
            # 稿数闪现：大字 + 一点红青错位（像重置时画面撕裂）
            fnt = font(ZH_B, 96)
            a = 1.0
            r = text_layer(text, fnt, 0.2, H / 2, a, color=(200, 40, 30), cx=W / 2 - 5)
            c = text_layer(text, fnt, 0.2, H / 2, a, color=(30, 160, 170), cx=W / 2 + 5)
            L = Image.alpha_composite(Image.alpha_composite(r, c), text_layer(text, fnt, 0.2, H / 2, a, color=(242, 234, 220)))
        elif kind == "title":
            # 片名：慢慢拉开字距（0.22 → 0.30 em），带一点暖色辉光
            k = (t - t0) / (t1 - t0)
            L = text_layer(text, font(FELL, 148), 0.22 + 0.08 * k, H / 2 - 40, env(t, t0, t1, 1.6, 0.8), color=(242, 230, 206), glow=0.55)
        elif kind == "tagline":
            L = text_layer(text, font(ZH, 38), 0.22, H / 2 + 95, env(t, t0, t1, 0.9, 0.8), shadow=0.6)
        elif kind == "endcard":
            a = env(t, t0, t1, 0.8, 0.9)
            L = text_layer("MERCY CREEK", font(FELL, 96), 0.26, H / 2 - 70, a, color=(242, 230, 206), glow=0.35)
            for txt, f, tr, y, col in (("第几稿，你才会醒来？", font(ZH, 34), 0.2, H / 2 + 30, INK),
                                       ("macOS  ·  网页版", font(ZH, 30), 0.12, H / 2 + 110, (200, 186, 160)),
                                       ("即 将 推 出", font(ZH, 26), 0.3, H / 2 + 160, (200, 186, 160)),
                                       ("游戏实机画面", font(ZH, 20), 0.2, H - 60, (130, 122, 110))):
                L = Image.alpha_composite(L, text_layer(txt, f, tr, y, a, color=col))
        else:
            continue
        over = L if over is None else Image.alpha_composite(over, L)
    if over is None:
        return img
    base = img.convert("RGBA")
    return Image.alpha_composite(base, over).convert("RGB")


# ---------------------------------------------------------------- 画面

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
R2 = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
VIGNETTE = (1 - 0.30 * np.clip(R2, 0, 2) ** 1.3)[..., None]
GRAIN = [np.random.default_rng(k).normal(0, 1, (H // 2, W // 2)).astype(np.float32) for k in range(16)]


def grain(k):
    g = GRAIN[k % 16]
    g = np.kron(g, np.ones((2, 2), np.float32))   # 颗粒稍大一点，像 35mm 而不是数字噪点
    return np.roll(g, (k * 37) % H, axis=0)[..., None]


def grade(x, preset):
    """x: float32 0..1。底色：轻微 S 曲线、暗部一点点青、高光偏暖、饱和度略收。"""
    luma = (x @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    if preset == "red":
        x = x * np.array([1.25, 0.72, 0.62], np.float32)
    elif preset == "haze":
        x = np.clip((x - 0.06) * 1.12, 0, 1)
    elif preset == "title":
        x = x * 0.5 * np.array([1.06, 0.95, 0.85], np.float32)
    x = np.clip((x - 0.025) / 0.985, 0, 1)
    s = x * x * (3 - 2 * x)
    x = x + 0.45 * (s - x)
    x = luma + 0.97 * (x - luma)
    x = x + np.array([-0.004, 0.006, 0.014], np.float32) * (1 - luma) ** 3
    x = x * (1 + np.array([0.035, 0.0, -0.04], np.float32) * luma ** 2)
    return x


class Frames:
    def __init__(self, shots):
        self.shots = shots

    @lru_cache(maxsize=8)
    def get(self, name, i):
        d = self.shots / name
        n = len(list(d.glob("*.jpg"))) if not hasattr(self, "_n") or name not in self._n else self._n[name]
        self.__dict__.setdefault("_n", {})[name] = n
        i = int(np.clip(i, 0, n - 1))
        return np.asarray(Image.open(d / f"{i:04d}.jpg").convert("RGB"), np.float32) / 255


def src_time(t, clip):
    a, b, name, src, opt = clip
    if "ramp" in opt:
        r0, r1 = opt["ramp"]
        if t > r0:
            # 与磁带停转同一条速率曲线：rate = (1-u)^1.6，积分得位移
            u = min(1.0, (t - r0) / (r1 - r0))
            moved = (r1 - r0) * (1 - (1 - u) ** 2.6) / 2.6
            return src + (r0 - a) + moved
    return src + (t - a)


def frame(t, frames, k):
    clip = next((c for c in edl.CLIPS if c[0] <= t < c[1]), None)
    out = np.zeros((H, W, 3), np.float32)
    if clip:
        a, b, name, src, opt = clip
        x = frames.get(name, round(src_time(t, clip) * FPS))
        x = grade(x, opt.get("grade"))
        if "ramp" in opt:   # 停下来的同时褪色
            r0, r1 = opt["ramp"]
            u = np.clip((t - r0) / (r1 - r0), 0, 1)
            l = (x @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
            x = x + u * (l * np.array([0.95, 0.98, 1.05], np.float32) * 0.85 - x)
        f = 1.0
        if opt.get("fin"):
            f = min(f, (t - a) / opt["fin"])
        if opt.get("fout"):
            f = min(f, (b - t) / opt["fout"])
        f = float(np.clip(f, 0, 1)) ** 1.5
        top = int(np.clip(BAR_H + opt.get("dy", 0), 0, 2 * BAR_H))
        out[PIC0:PIC1] = x[top:top + (PIC1 - PIC0)] * f
        out *= VIGNETTE
    out += grain(k) * 0.022 * (0.35 + out.mean(axis=2, keepdims=True))
    out[:PIC0] = 0
    out[PIC1:] = 0
    img = Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))
    return draw_texts(img, t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots")
    ap.add_argument("out")
    ap.add_argument("--audio")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=edl.END)
    ap.add_argument("--stills", help="只出这些时间点的静帧（逗号分隔）到 out 目录")
    a = ap.parse_args()
    frames = Frames(Path(a.shots))
    if a.stills:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        for s in a.stills.split(","):
            t = float(s)
            frame(t, frames, int(t * FPS)).save(Path(a.out) / f"still_{t:06.2f}.jpg", quality=92)
        return
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if a.audio:
        cmd += ["-ss", str(a.t0), "-t", str(a.t1 - a.t0), "-i", a.audio]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "14", "-tune", "film", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-movflags", "+faststart"]
    if a.audio:
        cmd += ["-c:a", "aac", "-b:a", "320k", "-shortest"]
    cmd += [a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = round(a.t0 * FPS), round(a.t1 * FPS)
    for k in range(n0, n1):
        p.stdin.write(frame(k / FPS, frames, k).tobytes())
        if k % 150 == 0:
            print(f"  {k / FPS:5.1f}s", flush=True)
    p.stdin.close()
    p.wait()
    print("video", a.out)


if __name__ == "__main__":
    main()
