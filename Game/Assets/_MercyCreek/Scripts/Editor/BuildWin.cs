using System;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// Windows 64 位构建（Mono：在 Mac 上交叉编译只能用 Mono，IL2CPP 需要 Windows 主机上的 VS 工具链）：
    /// Unity -batchmode -buildTarget Win64 -projectPath Game -executeMethod MercyCreek.EditorTools.BuildWin.Run
    /// 输出 Game/Builds/Win/MercyCreek.exe
    /// </summary>
    public static class BuildWin
    {
        public static void Run()
        {
            try
            {
                PlayerSettings.runInBackground = true;
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { "Assets/_MercyCreek/Scenes/Saloon.unity" },
                    locationPathName = "Builds/Win/MercyCreek.exe",
                    target = BuildTarget.StandaloneWindows64,
                    options = BuildOptions.None,
                });
                var s = report.summary;
                Debug.Log($"[BuildWin] {s.result} size={s.totalSize / (1024 * 1024)}MB time={s.totalTime} errors={s.totalErrors}");
                EditorApplication.Exit(s.result == BuildResult.Succeeded ? 0 : 1);
            }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }
    }
}
