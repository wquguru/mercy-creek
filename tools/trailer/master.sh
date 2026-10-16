#!/bin/zsh
# 混音母带：配乐 f32 → 响度对齐到 -14 LUFS（流媒体平台的常用基准）→ 限幅到约 -2.6 dBFS（AAC 编码会过冲约 1.5 dB，成片峰值才能 ≤ -1 dBFS）
set -eu
IN=$1 OUT=$2
I=$(ffmpeg -hide_banner -f f32le -ar 48000 -ac 2 -i "$IN" -af ebur128 -f null - 2>&1 | awk '/Integrated loudness/{f=1} f&&/I:/{print $2; exit}')
G=$(echo "-14 - ($I)" | bc -l)
ffmpeg -loglevel error -y -f f32le -ar 48000 -ac 2 -i "$IN" -af "aresample=192000,volume=${G}dB,alimiter=limit=0.74:attack=2:release=60:level=false,aresample=48000" -c:a pcm_s24le "$OUT"
echo "in $I LUFS, gain $G dB"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak|LRA):"
