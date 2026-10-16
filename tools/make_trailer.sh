#!/bin/zsh
# 约 85 秒发布预告片（三幕：华尔兹与错音 → 一切都一模一样 → 重置、撕开、醒来 → 片名）。
# 镜头（Trailer.cs，30fps 逐帧 + 2 倍超采样 + 同步游戏声）→ 配乐与混音（score.py）→ 响度母带（master.sh）
# → 调色 / 2.39:1 / 颗粒 / 字幕合成（edit.py）。剪辑表在 tools/trailer/edl.py。需要先构建 Mac 版。
# 输出 Reviews/trailer/：mercy_creek_trailer.mp4（母版）、mercy_creek_trailer_share.mp4（约 8 Mbps）、poster.jpg
# 用法：tools/make_trailer.sh [--reuse]（--reuse = 已拍过的镜头不重拍）
set -eu
ROOT=${0:A:h:h}
OUT=$ROOT/Reviews/trailer; SHOTS=$OUT/shots
PY=$ROOT/.venv/bin/python
[[ " $* " == *" --reuse "* ]] || rm -rf "$OUT"
mkdir -p "$OUT"
"$ROOT/tools/trailer/shoot.sh" "$SHOTS"
"$PY" "$ROOT/tools/trailer/score.py" "$SHOTS" "$OUT/score.wav"
"$ROOT/tools/trailer/master.sh" "$OUT/score.wav.f32" "$OUT/master.wav"
"$PY" "$ROOT/tools/trailer/edit.py" "$SHOTS" "$OUT/mercy_creek_trailer.mp4" --audio "$OUT/master.wav"
ffmpeg -loglevel error -y -i "$OUT/mercy_creek_trailer.mp4" -c:v libx264 -preset slow -crf 22 -maxrate 10M -bufsize 20M \
  -tune film -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$OUT/mercy_creek_trailer_share.mp4"
ffmpeg -loglevel error -y -ss 76.5 -i "$OUT/mercy_creek_trailer.mp4" -frames:v 1 -q:v 2 "$OUT/poster.jpg"
ls -la "$OUT"/*.mp4 "$OUT"/poster.jpg
