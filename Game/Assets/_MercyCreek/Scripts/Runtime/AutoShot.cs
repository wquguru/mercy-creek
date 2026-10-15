using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

namespace MercyCreek
{
    /// <summary>
    /// 自动评审截图：游戏以 `-autoshot <目录>` 启动时，在若干固定时间点截图后退出。
    /// 让 AI 不用人看屏幕也能验证画面（AGENTS.md：视觉改动必须出图）。
    /// 排查画面问题：`-debug nosun,noprobe,noapv,noshaft,nolamps,nopost` 关掉对应光照成分；
    /// `-only bar,entrance` 只拍指定机位；`-times 8,150` 指定循环时间点。
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
            ApplyDebug(Arg("-debug"));
            var only = Arg("-only")?.Split(',');
            var times = Arg("-times");
            if (times != null) loopTimes = times.Split(',').Select(float.Parse).ToArray();

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
                    if (only != null && !only.Contains(viewpoints[i].name)) continue;
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

        static void ApplyDebug(string flags)
        {
            if (string.IsNullOrEmpty(flags)) return;
            var f = flags.Split(',');
            Debug.Log("[AutoShot] debug " + flags);
            var director = FindFirstObjectByType<LoopDirector>();
            if (f.Contains("nosun") && director && director.sun) director.sun.enabled = false;
            if (f.Contains("nolamps"))
                foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None))
                    if (l.type != LightType.Directional) l.enabled = false;
            if (f.Contains("noprobe"))
            {
                foreach (var p in FindObjectsByType<ReflectionProbe>(FindObjectsSortMode.None)) p.enabled = false;
                RenderSettings.reflectionIntensity = 0;
                RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
            }
            if (f.Contains("noshaft"))
                foreach (var s in FindObjectsByType<LightShaft>(FindObjectsSortMode.None)) s.gameObject.SetActive(false);
            if (f.Contains("nopost"))
                foreach (var v in FindObjectsByType<Volume>(FindObjectsSortMode.None)) v.enabled = false;
            if (f.Contains("noapv"))
            {
                var profile = ScriptableObject.CreateInstance<VolumeProfile>();
                var o = profile.Add<ProbeVolumesOptions>(true);
                o.intensityMultiplier.Override(0f);
                var v = new GameObject("Debug APV Off").AddComponent<Volume>();
                v.isGlobal = true; v.priority = 100; v.sharedProfile = profile;
            }
        }

        static string Arg(string name)
        {
            var a = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
