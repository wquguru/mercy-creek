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
# 封面：片名 + 标语落在黄昏门脸上的那一帧
COVER=76.5
ffmpeg -loglevel error -y -ss $COVER -i "$OUT/mercy_creek_trailer.mp4" -frames:v 1 -q:v 2 "$OUT/poster.jpg"
# 片子从黑场打字开场，X / 微信 / Telegram 等直接拿第一帧当缩略图就是一片黑：
# 分享版开头先放 0.6 秒封面再淡到黑（声音整体后移），母版不动；两版都内嵌封面图（Finder / QuickTime / 播放器列表用）
LEAD=0.6; HALF=0.3; LEAD_MS=600
ffmpeg -loglevel error -y -i "$OUT/mercy_creek_trailer.mp4" -loop 1 -framerate 30 -t $LEAD -i "$OUT/poster.jpg" -i "$OUT/poster.jpg" -filter_complex "\
[1:v]format=yuv420p,fade=out:st=${HALF}:d=${HALF},setsar=1[c];[0:v]setsar=1[m];[c][m]concat=n=2:v=1:a=0[v];\
[0:a]adelay=${LEAD_MS}:all=1[a]" -map "[v]" -map "[a]" -map 2:v \
  -c:v:0 libx264 -preset slow -crf 22 -maxrate 10M -bufsize 20M -tune film -pix_fmt yuv420p -c:v:1 mjpeg -disposition:v:1 attached_pic \
  -c:a aac -b:a 192k -movflags +faststart "$OUT/mercy_creek_trailer_share.mp4"
ffmpeg -loglevel error -y -i "$OUT/mercy_creek_trailer.mp4" -i "$OUT/poster.jpg" -map 0 -map 1 -c copy -c:v:1 mjpeg -disposition:v:1 attached_pic \
  "$OUT/cover.mp4" && mv "$OUT/cover.mp4" "$OUT/mercy_creek_trailer.mp4"
ls -la "$OUT"/*.mp4 "$OUT"/poster.jpg
