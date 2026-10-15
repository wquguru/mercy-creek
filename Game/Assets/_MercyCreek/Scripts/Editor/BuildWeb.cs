using System;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.Rendering;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// 网页版（只用 WebGPU）：tools/build_web.sh，或
    /// Unity -batchmode -buildTarget WebGL -projectPath Game -executeMethod MercyCreek.EditorTools.BuildWeb.Run
    /// 输出 Game/Builds/Web/（Brotli 压缩 + 解压回退，普通静态服务器也能跑）
    /// </summary>
    public static class BuildWeb
    {
        public static void Run()
        {
            try
            {
                PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.WebGL, false);
                PlayerSettings.SetGraphicsAPIs(BuildTarget.WebGL, new[] { GraphicsDeviceType.WebGPU });
                PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Brotli;
                PlayerSettings.WebGL.decompressionFallback = true;
                PlayerSettings.WebGL.dataCaching = true;
                PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.ExplicitlyThrownExceptionsOnly;
                PlayerSettings.WebGL.memoryGrowthMode = WebGLMemoryGrowthMode.Geometric;
                PlayerSettings.WebGL.maximumMemorySize = 4096;
                PlayerSettings.WebGL.template = "PROJECT:MercyCreek";
                PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.WebGL, ManagedStrippingLevel.Minimal);
                PlayerSettings.runInBackground = true;

                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { "Assets/_MercyCreek/Scenes/Saloon.unity" },
                    locationPathName = "Builds/Web",
                    target = BuildTarget.WebGL,
                    options = BuildOptions.None,
                });
                var s = report.summary;
                Debug.Log($"[BuildWeb] {s.result} size={s.totalSize / (1024 * 1024)}MB time={s.totalTime} errors={s.totalErrors}");
                EditorApplication.Exit(s.result == BuildResult.Succeeded ? 0 : 1);
            }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }
    }
}
