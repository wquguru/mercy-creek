#!/bin/zsh
# 组装落地页到 dist/site：index.html + 宣传片 + 分享图 + 网页版（play/）。只在本地组装，发布前要人确认。
set -eu
ROOT=${0:A:h:h}
D=$ROOT/dist/site
rm -rf "$D"; mkdir -p "$D/play"
cp "$ROOT/site/index.html" "$D/"
cp "$ROOT/Reviews/trailer/mercy_creek_trailer.mp4" "$D/trailer.mp4"
ffmpeg -loglevel error -y -ss 76.5 -i "$D/trailer.mp4" -frames:v 1 -vf scale=1200:-1 "$D/share.png"
cp -R "$ROOT/Game/Builds/Web/." "$D/play/"
du -sh "$D"; echo "本地预览：python3 -m http.server -d $D 8800 → http://localhost:8800/"
