#!/bin/zsh
# Windows 64 位构建（Mono），输出 Game/Builds/Win/，并打包成 Game/Builds/MercyCreek-win64.zip
# 在 Mac 上只能构建、不能运行验证；首次需要装 Windows Mono 模块（见 docs/TECH.md）
set -u
ROOT=${0:A:h:h}
P=$ROOT/Game
U=/Applications/Unity/Hub/Editor/6000.3.26f1/Unity.app/Contents/MacOS/Unity
rm -rf "$P/Builds/Win"
$U -batchmode -buildTarget Win64 -projectPath "$P" -executeMethod MercyCreek.EditorTools.BuildWin.Run -logFile "$P/Logs/build_win.log" >/dev/null 2>&1
rc=$?
grep -E 'error CS|Exception:|\[BuildWin\]' "$P/Logs/build_win.log" | head -20
if [[ $rc == 0 ]]; then
  rm -rf "$P"/Builds/Win/*_BurstDebugInformation_DoNotShip
  (cd "$P/Builds" && rm -f MercyCreek-win64.zip && zip -qr MercyCreek-win64.zip Win)
  du -sh "$P/Builds/Win" "$P/Builds/MercyCreek-win64.zip"
fi
exit $rc
