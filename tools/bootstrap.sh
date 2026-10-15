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
# 木头人偶马（Horse / Horse_B）+ 驿站马车（--no-render 时不需要先有马和车夫的 .gltf）
blender --background --python tools/blender/build_horse.py -- --no-render
blender --background --python tools/blender/build_coach.py -- --no-render
blender --background --python tools/blender/build_props.py -- --no-render
blender --background --python tools/blender/build_street.py
blender --background --python tools/blender/build_town.py
# 街道两头：教堂、墓地、西头画布（画布底稿在 Blender 里渲染，再用 Pillow 加工成手绘布景）
.venv/bin/python tools/gen_edge_textures.py
blender --background --python tools/blender/build_edges.py -- --paint
[[ -x tools/build_audio.sh ]] && tools/build_audio.sh
tools/review.sh --test
