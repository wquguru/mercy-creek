#!/bin/zsh
# 一键：重建场景 → Mac 开发构建 → 自动截图到 Reviews/unity/
# 用法：tools/review.sh [--no-setup] [--no-build] [--test]
# 排查画面：SHOT_ARGS="-debug noapv -only bar -times 8" tools/review.sh --no-setup --no-build
set -u
ROOT=${0:A:h:h}
P=$ROOT/Game
U=/Applications/Unity/Hub/Editor/6000.3.26f1/Unity.app/Contents/MacOS/Unity
R=$ROOT/Reviews/unity
# 自动运行会把窗口大小等写进玩家的 PlayerPrefs：跑完恢复
PREFS=(dev.mercycreek.game); PB=$ROOT/Reviews/.prefs_backup.plist
defaults export $PREFS "$PB" 2>/dev/null
trap 'if [[ -f "$PB" ]]; then defaults import $PREFS "$PB"; else defaults delete $PREFS 2>/dev/null; fi; rm -f "$PB"' EXIT
run_unity() {   # $1 = method, $2 = log name
  $U -batchmode -buildTarget OSXUniversal -projectPath "$P" -executeMethod "$1" -logFile "$P/Logs/$2.log" >/dev/null 2>&1
  local rc=$?
  grep -E 'error CS|Exception:|is not possible|\[SetupSaloon\] (done|.*not found)|\[BuildMac\]' "$P/Logs/$2.log" | head -20
  return $rc
}
[[ " $* " == *" --no-setup "* ]] || { echo "== setup"; run_unity MercyCreek.EditorTools.SetupSaloon.Run setup || exit 1; }
[[ " $* " == *" --no-build "* ]] || { echo "== build"; run_unity MercyCreek.EditorTools.BuildMac.Run build || exit 1; }
echo "== autoshot"
rm -rf "$R"; mkdir -p "$R"
# 默认拍第 3 稿（街道、墓地都已写出来，马车停在门口）；SHOT_ARGS 里给了 -loop 就用它的
LOOPARG=(-loop 3); [[ " ${SHOT_ARGS:-} " == *" -loop "* ]] && LOOPARG=()
"$P/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek" -autoshot "$R" $LOOPARG ${=SHOT_ARGS:-} -screen-width 1600 -screen-height 900 -screen-fullscreen 0 -logFile - > "$P/Logs/player.log" 2>&1 &
PID=$!
for i in {1..300}; do sleep 1; kill -0 $PID 2>/dev/null || break; done
kill $PID 2>/dev/null
grep -E 'Exception|\[AutoShot\]' "$P/Logs/player.log" | head -20
ls "$R"

# 标题画面（中 / 英）
for L in zh en; do
  "$P/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek" -titleshot "$R/title_$L.png" -lang $L -screen-width 1600 -screen-height 900 -screen-fullscreen 0 -logFile - > "$P/Logs/title_$L.log" 2>&1 &
  PID=$!
  for i in {1..40}; do sleep 1; kill -0 $PID 2>/dev/null || break; done
  kill $PID 2>/dev/null
  grep -E 'Exception' "$P/Logs/title_$L.log" | head -5
done

# 自动通关测试：三个结局各跑一遍，外加 town（马车 / 电报 / 墓地 → 觉醒）
if [[ " $* " == *" --test "* ]]; then
  T=$ROOT/Reviews/autotest; rm -rf "$T"; mkdir -p "$T"
  FAILED=0
  for E in awaken escape reset town walls; do
    echo "== autotest $E"
    EXTRA=(); [[ $E == walls ]] && EXTRA=(-loop 3)
    "$P/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek" -autotest "$T" -ending $E $EXTRA -lang $([[ $E == escape ]] && echo en || echo zh) -screen-width 1600 -screen-height 900 -screen-fullscreen 0 -logFile - > "$P/Logs/autotest_$E.log" 2>&1 &
    PID=$!
    for i in {1..400}; do sleep 1; kill -0 $PID 2>/dev/null || break; done
    kill $PID 2>/dev/null
    grep -E 'Exception|\[AutoTest\]|\[Story\]' "$P/Logs/autotest_$E.log" | head -40
    grep -q "\[AutoTest\] PASS" "$P/Logs/autotest_$E.log" && ! grep -q "\[AutoTest\] FAIL" "$P/Logs/autotest_$E.log" || FAILED=1
  done
  ls "$T"
  [[ $FAILED == 0 ]] && echo "AUTOTEST ALL PASS" || { echo "AUTOTEST FAILED"; exit 1; }
fi
