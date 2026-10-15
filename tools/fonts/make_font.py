"""把 Noto Serif SC（SIL OFL）裁成只含游戏里用到的字，供 uGUI 动态字体使用（Mac / Web 都没有系统字体依赖）。

收集范围：Scripts/Runtime 下所有 .cs 里的字符串字面量 + ASCII + 常用标点。改了 Loc 文本要重跑：
    .venv/bin/python tools/fonts/make_font.py
"""
import re
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "art/source/fonts"
OUT = ROOT / "Game/Assets/_MercyCreek/Resources/Fonts"

chars = set(chr(c) for c in range(0x20, 0x7F))
chars |= set("，。、；：？！“”‘’（）《》【】……—·─▸◂◀▶✦★☆…«»–")
for f in (ROOT / "Game/Assets/_MercyCreek/Scripts/Runtime").rglob("*.cs"):
    for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', f.read_text(encoding="utf-8")):
        chars |= set(lit)
text = "".join(sorted(chars))

OUT.mkdir(parents=True, exist_ok=True)
for weight in ("Regular", "Bold"):
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = subset.load_font(str(SRC / f"NotoSerifSC-{weight}.otf"), opts)
    s = subset.Subsetter(opts)
    s.populate(text=text)
    s.subset(font)
    out = OUT / f"MercySerif-{weight}.otf"
    subset.save_font(font, str(out), opts)
    print(f"{out.name}: {len(text)} chars, {out.stat().st_size // 1024} KB")
(OUT / "OFL.txt").write_text("Noto Serif SC — Copyright 2017 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'.\n"
                             "Licensed under the SIL Open Font License, Version 1.1. https://openfontlicense.org\n"
                             "Subset by tools/fonts/make_font.py for Mercy Creek.\n", encoding="utf-8")
