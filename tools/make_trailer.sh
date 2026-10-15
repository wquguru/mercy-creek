#!/bin/zsh
# 约 42 秒宣传片：逐镜头取景（Trailer.cs，30fps 逐帧）→ ffmpeg 合成配乐、转场、片尾字卡。
# 输出 Reviews/trailer/mercy_creek_trailer.mp4（以及 1:1 竖屏备用版）。需要先构建 Mac 版。
set -eu
ROOT=${0:A:h:h}
APP="$ROOT/Game/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek"
OUT=$ROOT/Reviews/trailer; F=$OUT/frames
AUDIO=$ROOT/Game/Assets/_MercyCreek/Audio
FONT=$ROOT/art/source/fonts/NotoSerifSC-Regular.otf
[[ " $* " == *" --reuse "* ]] || rm -rf "$OUT"
mkdir -p "$F"
SHOTS=8   # = Trailer.ShotCount
for i in $(seq 0 $((SHOTS - 1))); do
  ls "$F"/s${i}_0000.png >/dev/null 2>&1 && continue
  "$APP" -trailer "$F" -shot $i -lang zh -screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -logFile - > "$OUT/shot$i.log" 2>&1 || true
  grep -E "\[Trailer\]|Exception" "$OUT/shot$i.log" | head -3
done
# 每个镜头做成片段，首尾 0.35 秒淡入淡出
LIST=$OUT/list.txt; : > "$LIST"
for i in $(seq 0 $((SHOTS - 1))); do
  n=$(ls "$F"/s${i}_*.png | wc -l | tr -d ' ')
  d=$(echo "scale=3; $n / 30" | bc)
  ffmpeg -loglevel error -y -framerate 30 -i "$F/s${i}_%04d.png" -vf "fade=in:st=0:d=0.35,fade=out:st=$(echo "$d - 0.35" | bc):d=0.35,format=yuv420p" -c:v libx264 -crf 17 -preset slow "$OUT/shot$i.mp4"
  echo "file 'shot$i.mp4'" >> "$LIST"
done
# 片尾字卡 3.5 秒
"$ROOT/.venv/bin/python" "$ROOT/tools/trailer_card.py" "$F" 3.5
ffmpeg -loglevel error -y -framerate 30 -i "$F/card_%04d.png" -vf format=yuv420p -c:v libx264 -crf 17 "$OUT/card.mp4"
echo "file 'card.mp4'" >> "$LIST"
ffmpeg -loglevel error -y -f concat -safe 0 -i "$LIST" -c copy "$OUT/video.mp4"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/video.mp4")
# 配乐：错音版华尔兹从头放，重置音效对上最后一个镜头里的重置（片尾字卡前约 1.1 秒），片尾接结局主题
V=$(echo "$DUR - 3.5" | bc)                     # 字卡之前的画面长度
MS() { printf "%.0f" $(echo "($1) * 1000" | bc); }
ffmpeg -loglevel error -y -i "$OUT/video.mp4" -i "$AUDIO/piano_waltz_E.wav" -i "$AUDIO/reset_sting.wav" -i "$AUDIO/ending_theme.wav" -filter_complex "\
[1:a]atrim=0:$(echo "$V - 0.8" | bc),afade=out:st=$(echo "$V - 1.6" | bc):d=0.8,volume=0.9[w];\
[2:a]adelay=$(MS "$V - 1.1")|$(MS "$V - 1.1"),volume=0.9[s];\
[3:a]atrim=0:6,afade=in:st=0:d=0.5,afade=out:st=4.5:d=1.5,adelay=$(MS "$V + 1.5")|$(MS "$V + 1.5"),volume=0.8[e];\
[w][s][e]amix=inputs=3:normalize=0,atrim=0:${DUR}[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k "$OUT/mercy_creek_trailer.mp4"
# 1:1 版（社交平台）
ffmpeg -loglevel error -y -i "$OUT/mercy_creek_trailer.mp4" -vf "crop=1080:1080:420:0" -c:v libx264 -crf 19 -c:a copy "$OUT/mercy_creek_trailer_square.mp4"
ls -la "$OUT"/*.mp4
