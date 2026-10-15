#!/bin/zsh
# 网页版（WebGPU）构建，输出 Game/Builds/Web/；本地试玩：python3 -m http.server -d Game/Builds/Web 8700
set -u
ROOT=${0:A:h:h}
P=$ROOT/Game
U=/Applications/Unity/Hub/Editor/6000.3.26f1/Unity.app/Contents/MacOS/Unity
$U -batchmode -buildTarget WebGL -projectPath "$P" -executeMethod MercyCreek.EditorTools.BuildWeb.Run -logFile "$P/Logs/build_web.log" >/dev/null 2>&1
rc=$?
grep -E 'error CS|Exception:|\[BuildWeb\]' "$P/Logs/build_web.log" | head -20
du -sh "$P/Builds/Web" 2>/dev/null; ls -la "$P/Builds/Web/Build" 2>/dev/null
exit $rc
