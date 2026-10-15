#!/bin/zsh
# 重新生成全部程序合成音频（确定性，固定种子）→ Game/Assets/_MercyCreek/Audio/
#   tools/build_audio.sh            全部
#   tools/build_audio.sh --only step_wood piano_waltz   只生成指定前缀
#   tools/build_audio.sh --review   生成后出波形 / 频谱图到 Reviews/audio/
set -eu
ROOT=${0:A:h:h}
cd "$ROOT"
if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import numpy, scipy' 2>/dev/null; then
  python3 -m venv .venv
  .venv/bin/pip install -q numpy scipy
fi
REVIEW=0
ARGS=()
for a in "$@"; do
  if [[ $a == --review ]]; then REVIEW=1; else ARGS+=("$a"); fi
done
.venv/bin/python tools/audio/build_audio.py "${ARGS[@]}"
if (( REVIEW )); then
  .venv/bin/python tools/audio/review_audio.py
fi
