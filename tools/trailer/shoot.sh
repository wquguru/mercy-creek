#!/bin/zsh
# 拍宣传片镜头：每个镜头单独起一次游戏（30fps 逐帧 + 2 倍超采样 + 同步游戏声）。
# 用法：tools/trailer/shoot.sh <输出目录> [镜头名 ...]（不给名字 = 全部；已拍过的跳过，删掉目录重拍）
set -u
ROOT=${0:A:h:h:h}
APP="$ROOT/Game/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek"
OUT=${1:?输出目录}; shift
mkdir -p "$OUT"
# 自动运行会把窗口大小写进玩家的 PlayerPrefs：跑完恢复
PREFS=(dev.mercycreek.game); PB=$OUT/.prefs_backup.plist
defaults export $PREFS "$PB" 2>/dev/null
trap 'if [[ -f "$PB" ]]; then defaults import $PREFS "$PB"; else defaults delete $PREFS 2>/dev/null; fi; rm -f "$PB"' EXIT
WIN=(-lang zh -screen-width 1920 -screen-height 1080 -screen-fullscreen 0)
"$APP" -trailer "$OUT" -shot list $WIN -logFile /dev/null >/dev/null 2>&1
NAMES=($@); (( $#NAMES )) || NAMES=($(cut -f1 "$OUT/shots.tsv"))
for n in $NAMES; do
  [[ -f "$OUT/$n.txt" ]] && continue
  rm -rf "$OUT/$n"
  "$APP" -trailer "$OUT" -shot $n $WIN -logFile - > "$OUT/$n.log" 2>&1
  grep -E "\[Trailer\]|Exception" "$OUT/$n.log" | head -3
done
