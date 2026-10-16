#!/bin/zsh
# 自动试玩（静音、后台窗口、不抢鼠标）：tools/playbot.sh [awaken escape reset]
# 先构建：tools/review.sh --no-setup 或 BuildMac。截图和日志在 Reviews/playbot/<路线>/。
# 会临时清空并在结束后恢复玩家的 PlayerPrefs（存档 / 设置）。
set -u
ROOT=${0:A:h:h}
APP="$ROOT/Game/Builds/Mac/MercyCreek.app"
DOMAIN="dev.mercycreek.game"   # = Bundle Identifier
B=$ROOT/Reviews/playbot
mkdir -p "$B"
defaults export "$DOMAIN" "$B/prefs_backup.plist" 2>/dev/null
ROUTES=($@); (( $# )) || ROUTES=(awaken escape reset)   # zsh 不做分词：默认值不能写成 ${@:-a b c}
FAILED=0
for R in $ROUTES; do
  D=$B/$R; rm -rf "$D"; mkdir -p "$D"
  defaults delete "$DOMAIN" 2>/dev/null
  echo "== playbot $R"
  open -g -n "$APP" --args -playbot "$D" -route $R ${=PLAYBOT_ARGS:-} -mute -lang zh -screen-width 1600 -screen-height 900 -screen-fullscreen 0 -logFile "$D/player.log"
  sleep 3
  for i in {1..1500}; do pgrep -f "playbot $D" >/dev/null || break; sleep 1; done
  pkill -f "playbot $D" 2>/dev/null
  grep -E '\[PlayBot\] (ISSUE|DONE|ok|=====)|Exception' "$D/player.log" | head -80
  grep -q "\[PlayBot\] DONE.*issues=0" "$D/player.log" || FAILED=1
done
if [[ -f "$B/prefs_backup.plist" ]]; then defaults import "$DOMAIN" "$B/prefs_backup.plist"; rm -f "$B/prefs_backup.plist"; else defaults delete "$DOMAIN" 2>/dev/null; fi
[[ $FAILED == 0 ]] && echo "PLAYBOT ALL CLEAN" || { echo "PLAYBOT FOUND ISSUES"; exit 1; }
