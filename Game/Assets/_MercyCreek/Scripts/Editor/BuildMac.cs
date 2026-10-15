using System;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// 开发构建（Mono，编译快）：Unity -batchmode -projectPath Game -executeMethod MercyCreek.EditorTools.BuildMac.Run
    /// 输出 Game/Builds/Mac/MercyCreek.app
    /// </summary>
    public static class BuildMac
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
                    locationPathName = "Builds/Mac/MercyCreek.app",
                    target = BuildTarget.StandaloneOSX,
                    options = BuildOptions.None,
                });
                var s = report.summary;
                Debug.Log($"[BuildMac] {s.result} size={s.totalSize / (1024 * 1024)}MB time={s.totalTime} errors={s.totalErrors}");
                EditorApplication.Exit(s.result == BuildResult.Succeeded ? 0 : 1);
            }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }
    }
}
