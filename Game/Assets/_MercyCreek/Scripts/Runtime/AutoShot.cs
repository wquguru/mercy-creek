using System.Collections;
using System.IO;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 自动评审截图：游戏以 `-autoshot <目录>` 启动时，在若干固定时间点截图后退出。
    /// 让 AI 不用人看屏幕也能验证画面（CLAUDE.md：视觉改动必须出图）。
    /// </summary>
    public class AutoShot : MonoBehaviour
    {
        public Transform[] viewpoints;
        public float[] loopTimes = { 8f, 150f };

        IEnumerator Start()
        {
            string dir = Arg("-autoshot");
            if (dir == null) { enabled = false; yield break; }
            Directory.CreateDirectory(dir);

            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.enabled = false;
            var director = FindFirstObjectByType<LoopDirector>();
            var hud = FindFirstObjectByType<Hud>();
            var cam = Camera.main;

            foreach (float lt in loopTimes)
            {
                if (director) { while (director.Elapsed < Mathf.Min(lt, 9f)) yield return null; }
                if (director && lt > 9f)
                {
                    director.Skip(lt);   // 快进到目标时间点，免得真等
                    yield return new WaitForSeconds(0.3f);
                }
                if (hud) hud.Fade = 0;
                for (int i = 0; i < viewpoints.Length; i++)
                {
                    cam.transform.SetPositionAndRotation(viewpoints[i].position, viewpoints[i].rotation);
                    yield return new WaitForSeconds(0.4f);
                    yield return new WaitForEndOfFrame();
                    string path = Path.Combine(dir, $"game_{viewpoints[i].name}_t{lt:000}.png");
                    ScreenCapture.CaptureScreenshot(path);
                    yield return null;
                    Debug.Log("[AutoShot] " + path);
                }
            }
            yield return new WaitForSeconds(0.5f);
            Application.Quit();
        }

        static string Arg(string name)
        {
            var a = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
