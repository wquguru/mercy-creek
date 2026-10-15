using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

namespace MercyCreek.EditorTools
{
    // Unity -batchmode -executeMethod MercyCreek.EditorTools.AddPackages.Run （不要加 -quit，完成后自行退出）
    public static class AddPackages
    {
        static readonly string[] Packages =
        {
            "com.unity.render-pipelines.universal",
            "com.unity.inputsystem",
            "com.unity.timeline",
            "com.unity.cloud.gltfast",
            "com.unity.ugui",
            "com.unity.ai.navigation",
        };

        static AddAndRemoveRequest _req;

        public static void Run()
        {
            _req = Client.AddAndRemove(Packages, null);
            EditorApplication.update += Poll;
        }

        static void Poll()
        {
            if (!_req.IsCompleted) return;
            EditorApplication.update -= Poll;
            if (_req.Status == StatusCode.Success)
            {
                foreach (var p in _req.Result) Debug.Log($"[AddPackages] {p.name}@{p.version}");
                EditorApplication.Exit(0);
            }
            else
            {
                Debug.LogError($"[AddPackages] failed: {_req.Error?.message}");
                EditorApplication.Exit(1);
            }
        }
    }
}
