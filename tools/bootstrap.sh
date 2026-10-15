#!/bin/zsh
# 新克隆后复原所有不进 Git 的产物：CC0 源资产 → Blender 酒馆 → Unity 场景 → Mac 构建。
set -eu
ROOT=${0:A:h:h}
cd "$ROOT"
python3 tools/fetch_assets.py
mkdir -p Game/Assets/_MercyCreek/Art/HDRI
cp -n art/source/polyhaven/hdris/goegap_road_2k.exr Game/Assets/_MercyCreek/Art/HDRI/ 2>/dev/null || true
[[ -x .venv/bin/python ]] || python3 -m venv .venv
.venv/bin/python -c "import PIL, numpy, fontTools" 2>/dev/null || .venv/bin/pip install -q pillow numpy fonttools
.venv/bin/python tools/textures/make_wallpaper.py
blender --background --python tools/blender/build_saloon.py -- --export Game/Assets/_MercyCreek/Art/Saloon/Saloon.gltf
# 独立资产：钢琴、木头人偶、道具、窗外街景（文字贴图需要 Pillow）
.venv/bin/python tools/gen_prop_textures.py
.venv/bin/python tools/gen_street_signs.py
blender --background --python tools/blender/build_piano.py -- --no-render
blender --background --python tools/blender/build_mannequin.py -- --no-render
blender --background --python tools/blender/build_props.py -- --no-render
blender --background --python tools/blender/build_street.py
[[ -x tools/build_audio.sh ]] && tools/build_audio.sh
tools/review.sh --test
