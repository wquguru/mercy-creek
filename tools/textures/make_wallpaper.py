"""程序生成维多利亚风大马士革花纹墙纸（自制，无外部版权）。

底纸的纸纹与霉斑借用 ambientCG Wallpaper002B（CC0），花纹本身完全由公式生成。
输出 art/generated/WallpaperDamask/WallpaperDamask_{Color,Roughness,NormalGL}.jpg，2048²，覆盖 1 m × 1 m。

    .venv/bin/python tools/textures/make_wallpaper.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "art/source/ambientcg/Wallpaper002B"
OUT = ROOT / "art/generated/WallpaperDamask"
N = 2048
REPEAT_X, REPEAT_Y = 6, 4          # 1 m 内横向 6 个、纵向 4 个花纹单元（半错位排列）

rng = np.random.default_rng(1882)


def smooth(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def motif(u, v):
    """单元内坐标 u∈[-1,1]（左右对称）、v∈[-1,1]，返回 0..1 的花纹覆盖度。"""
    x, y = np.abs(u), v
    aa = 0.008
    th = np.arctan2(y, x + 1e-6)
    # 1. 外圈：带扇贝边的椭圆环
    e = np.sqrt((x / 0.42) ** 2 + (y / 0.78) ** 2)
    scallop = 1 + 0.035 * np.cos(18 * th)
    ring = np.clip(smooth(scallop + aa * 2, scallop - aa * 2, e) - smooth(0.9 + aa * 2, 0.9 - aa * 2, e), 0, 1)
    ring2 = np.clip(smooth(0.8 + aa * 2, 0.8 - aa * 2, e) - smooth(0.76 + aa * 2, 0.76 - aa * 2, e), 0, 1)
    # 2. 中心三瓣花
    r = np.sqrt(x ** 2 + (y + 0.05) ** 2)
    a = np.arctan2(y + 0.05, x)
    petals = 0.12 + 0.12 * np.abs(np.cos(1.5 * (a - np.pi / 2)))
    flower = smooth(petals + aa, petals - aa, r)
    # 中心花的茎
    stem = smooth(0.03, 0.018, x) * smooth(-0.62, -0.58, y) * smooth(-0.05, -0.09, y)
    # 3. 外侧卷叶：沿正弦曲线的变宽带子
    t = (y + 1) / 2
    cx = 0.55 + 0.22 * np.sin(t * np.pi * 1.6 + 0.4)
    width = 0.028 * np.sin(np.clip(t, 0, 1) * np.pi) + 0.004
    leaf = smooth(width + aa, width - aa, np.abs(x - cx)) * smooth(0.0, 0.05, t) * smooth(1.0, 0.92, t)
    # 4. 上下尖顶
    tip_top = smooth(0.06, 0.04, x + (y - 0.95) * 0.35) * smooth(0.82, 0.86, y) * smooth(1.02, 0.98, y)
    tip_bot = smooth(0.06, 0.04, x - (y + 0.95) * 0.35) * smooth(-0.82, -0.86, y) * smooth(-1.02, -0.98, y)
    # 5. 小圆点
    dots = np.zeros_like(x)
    for (px, py, pr) in [(0.88, 0.0, 0.035), (0.25, 0.92, 0.025), (0.25, -0.92, 0.025), (0.0, 0.5, 0.03), (0.0, -0.42, 0.028)]:
        d = np.sqrt((x - px) ** 2 + (y - py) ** 2)
        dots = np.maximum(dots, smooth(pr + aa, pr - aa, d))
    return np.clip(np.maximum.reduce([ring, ring2, flower, stem, leaf, tip_top, tip_bot, dots]), 0, 1)


def pattern():
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) / N
    gx, gy = xx * REPEAT_X, yy * REPEAT_Y
    col = np.floor(gx)
    gy = gy + 0.5 * (col % 2)                       # 半错位
    u = (gx - col) * 2 - 1
    v = (gy - np.floor(gy)) * 2 - 1
    return motif(u * 1.15, v * 1.08)


def load(name, mode):
    f = next(SRC.glob(f"*_{name}.jpg"))
    return np.asarray(Image.open(f).convert(mode).resize((N, N), Image.LANCZOS), dtype=np.float32) / 255


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = pattern()
    paper = load("Color", "RGB")                     # 旧纸纹 + 霉斑
    paper_lum = paper.mean(axis=2, keepdims=True)
    grime = paper_lum / paper_lum.mean()

    ground = np.array([0.30, 0.075, 0.06])           # 牛血红底
    stripe = 0.94 + 0.06 * (np.sin(np.linspace(0, 2 * np.pi * 24, N)) > 0)   # 极淡竖条
    ink = np.array([0.46, 0.17, 0.10])               # 同色系暗纹（略亮略暖），靠光泽差区分
    edge = np.clip(m - np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255, 0, 1)
    c = ground * stripe[None, :, None] * (1 - m[..., None]) + ink * m[..., None]
    c = c * (1 - 0.35 * edge[..., None])
    # 做旧：纸纹调制、印刷不均、日晒褪色（上浅下深）
    blot = np.asarray(Image.fromarray((rng.random((64, 64)) * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC), np.float32) / 255
    c = c * (0.82 + 0.25 * grime) * (0.92 + 0.12 * blot[..., None])
    c = c * np.linspace(1.08, 0.9, N)[:, None, None]
    srgb = np.clip(c, 0, 1) ** (1 / 1.0)
    Image.fromarray((srgb * 255).astype(np.uint8)).save(OUT / "WallpaperDamask_Color.jpg", quality=92)

    rough = np.clip(load("Roughness", "L") * 0.5 + 0.45 - 0.3 * m, 0.3, 1)
    Image.fromarray((rough * 255).astype(np.uint8)).save(OUT / "WallpaperDamask_Roughness.jpg", quality=92)

    # 法线：纸纹法线 + 花纹压印（高度场求梯度）
    base_n = load("NormalGL", "RGB") * 2 - 1
    h = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    dy, dx = np.gradient(h)
    n = base_n + np.stack([-dx * 6, dy * 6, np.zeros_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).save(OUT / "WallpaperDamask_NormalGL.jpg", quality=92)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
