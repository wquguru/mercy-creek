#!/bin/zsh
# 一键：重建场景 → Mac 开发构建 → 自动截图到 Reviews/unity/
# 用法：tools/review.sh [--no-setup] [--no-build] [--test]
# 排查画面：SHOT_ARGS="-debug noapv -only bar -times 8" tools/review.sh --no-setup --no-build
set -u
ROOT=${0:A:h:h}
P=$ROOT/Game
U=/Applications/Unity/Hub/Editor/6000.3.26f1/Unity.app/Contents/MacOS/Unity
R=$ROOT/Reviews/unity
run_unity() {   # $1 = method, $2 = log name
  $U -batchmode -projectPath "$P" -executeMethod "$1" -logFile "$P/Logs/$2.log" >/dev/null 2>&1
  local rc=$?
  grep -E 'error CS|Exception:|\[SetupSaloon\] (done|.*not found)|\[BuildMac\]' "$P/Logs/$2.log" | head -20
  return $rc
}
[[ " $* " == *" --no-setup "* ]] || { echo "== setup"; run_unity MercyCreek.EditorTools.SetupSaloon.Run setup || exit 1; }
[[ " $* " == *" --no-build "* ]] || { echo "== build"; run_unity MercyCreek.EditorTools.BuildMac.Run build || exit 1; }
echo "== autoshot"
rm -rf "$R"; mkdir -p "$R"
"$P/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek" -autoshot "$R" ${=SHOT_ARGS:-} -screen-width 1600 -screen-height 900 -screen-fullscreen 0 -logFile - > "$P/Logs/player.log" 2>&1 &
PID=$!
for i in {1..150}; do sleep 1; kill -0 $PID 2>/dev/null || break; done
kill $PID 2>/dev/null
grep -E 'Exception|\[AutoShot\]' "$P/Logs/player.log" | head -20
ls "$R"

# 自动通关测试：tools/review.sh --no-setup --no-build 之后单独跑也行
if [[ " $* " == *" --test "* ]]; then
  echo "== autotest"
  T=$ROOT/Reviews/autotest; rm -rf "$T"; mkdir -p "$T"
  "$P/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek" -autotest "$T" -screen-width 1600 -screen-height 900 -screen-fullscreen 0 -logFile - > "$P/Logs/autotest.log" 2>&1 &
  PID=$!
  for i in {1..240}; do sleep 1; kill -0 $PID 2>/dev/null || break; done
  kill $PID 2>/dev/null
  grep -E 'Exception|\[AutoTest\]' "$P/Logs/autotest.log" | head -40
  ls "$T"
fi
