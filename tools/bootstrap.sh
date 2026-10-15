#!/bin/zsh
# 新克隆后复原所有不进 Git 的产物：CC0 源资产 → Blender 酒馆 → Unity 场景 → Mac 构建。
set -eu
ROOT=${0:A:h:h}
cd "$ROOT"
python3 tools/fetch_assets.py
mkdir -p Game/Assets/_MercyCreek/Art/HDRI
cp -n art/source/polyhaven/hdris/goegap_road_2k.exr Game/Assets/_MercyCreek/Art/HDRI/ 2>/dev/null || true
blender --background --python tools/blender/build_saloon.py -- --export Game/Assets/_MercyCreek/Art/Saloon/Saloon.glb
[[ -x tools/build_audio.sh ]] && tools/build_audio.sh
tools/review.sh --test
