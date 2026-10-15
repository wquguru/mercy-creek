using System.Collections;
using System.IO;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 宣传片取景：`-trailer &lt;帧目录&gt;` 启动后按固定帧率（30fps，游戏时间与真实时间脱钩）逐帧截图，
    /// 镜头按 Shots 表推拉；tools/make_trailer.sh 再用 ffmpeg 合成配乐和字幕卡。
    /// </summary>
    public class Trailer : MonoBehaviour
    {
        const int Fps = 30;

        struct Shot
        {
            public float loopTime, seconds;
            public Vector3 fromPos, toPos, fromLook, toLook;
            public int loop;
        }

        // 循环时间点参考 Story（240 秒一轮）：3s 钢琴、27s 错音、~44s 马车从画布驶出、65s 克兰进门（第 4 轮 50s）、
        // 77s 要酒、92s 坐下写字、180s 上楼、228s 变红、240s 重置
        static readonly Shot[] Shots =
        {
            new() { loop = 1, loopTime = 6f,   seconds = 5f,   fromPos = new(-0.4f, 1.75f, 1.0f), toPos = new(0.3f, 1.9f, 3.4f), fromLook = new(1.2f, 1.5f, 9f), toLook = new(1.8f, 1.4f, 9f) },
            new() { loop = 1, loopTime = 24.5f, seconds = 4.5f, fromPos = new(2.3f, 1.35f, 8.2f), toPos = new(2.55f, 1.3f, 8.55f), fromLook = new(3.2f, 0.95f, 9.4f), toLook = new(3.25f, 0.95f, 9.45f) },
            // 马车从画布里驶出（快进会让马车瞬移，所以从它出发前 1 秒开拍）
            new() { loop = 2, loopTime = 43.5f, seconds = 6.5f, fromPos = new(-22.5f, 1.5f, -1.6f), toPos = new(-23.5f, 1.45f, -2.2f), fromLook = new(-33f, 1.8f, -5.4f), toLook = new(-29f, 1.5f, -5.4f) },
            new() { loop = 2, loopTime = 110f, seconds = 5f,   fromPos = new(-1.5f, 1.3f, 3.0f), toPos = new(-2.0f, 1.25f, 2.7f), fromLook = new(-3.0f, 1.0f, 1.2f), toLook = new(-3.0f, 0.95f, 1.15f) },
            // 玛莎的墓碑，旁边那块空白的
            new() { loop = 3, loopTime = 120f, seconds = 5f,  fromPos = new(31.0f, 1.55f, 1.6f), toPos = new(32.2f, 1.3f, 3.3f), fromLook = new(32.4f, 0.6f, 5f), toLook = new(32.6f, 0.55f, 5f) },
            new() { loop = 1, loopTime = 79f, seconds = 5f,    fromPos = new(-3.0f, 1.5f, 5.2f), toPos = new(-3.3f, 1.45f, 4.9f), fromLook = new(-5.4f, 1.2f, 4.0f), toLook = new(-5.5f, 1.15f, 4.1f) },
            // 街道尽头的画布
            new() { loop = 3, loopTime = 140f, seconds = 5f,  fromPos = new(-22f, 1.7f, -6.6f), toPos = new(-29.5f, 1.7f, -7.1f), fromLook = new(-34f, 2.6f, -7.3f), toLook = new(-34f, 2.2f, -7.3f) },
            new() { loop = 2, loopTime = 236.5f, seconds = 5.5f, fromPos = new(0.3f, 1.7f, 1.2f), toPos = new(0.3f, 1.75f, 2.2f), fromLook = new(0.6f, 1.6f, 9f), toLook = new(0.6f, 1.6f, 9f) },
        };

        IEnumerator Start()
        {
            string dir = Arg("-trailer");
            if (dir == null) { enabled = false; yield break; }
            Directory.CreateDirectory(dir);
            int shotIndex = int.Parse(Arg("-shot") ?? "0");
            var s = Shots[shotIndex];
            if (LoopMemory.Loop > s.loop) { Application.Quit(); yield break; }   // 镜头拍完后循环重置了，不再重拍
            if (LoopMemory.Loop != s.loop)
            {
                // 剧情按轮数变化（第 4 轮陌生人 45 秒进门），先跳到需要的那一轮
                while (LoopMemory.Loop < s.loop) LoopMemory.NextLoop();
                UnityEngine.SceneManagement.SceneManager.LoadScene(0);
                yield break;
            }

            var hud = FindFirstObjectByType<Hud>();
            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.enabled = false;
            var director = FindFirstObjectByType<LoopDirector>();
            yield return null;
            if (hud) { hud.HudVisible = false; hud.Fade = 0; }
            hud?.HideAll();
            director.Skip(s.loopTime);
            yield return new WaitForSeconds(0.5f);   // 让 instant 事件和 NPC 站位落定
            if (hud) hud.Fade = 0;

            var cam = Camera.main;
            cam.fieldOfView = 50f;
            Time.captureFramerate = Fps;
            int frames = Mathf.RoundToInt(s.seconds * Fps);
            for (int f = 0; f < frames; f++)
            {
                float k = Mathf.SmoothStep(0, 1, f / (float)(frames - 1));
                var pos = Vector3.Lerp(s.fromPos, s.toPos, k);
                cam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(Vector3.Lerp(s.fromLook, s.toLook, k) - pos));
                hud?.HideAll();
                yield return new WaitForEndOfFrame();
                ScreenCapture.CaptureScreenshot(Path.Combine(dir, $"s{shotIndex}_{f:0000}.png"));
                yield return null;
            }
            Time.captureFramerate = 0;
            Debug.Log($"[Trailer] shot {shotIndex} {frames} frames");
            yield return new WaitForSecondsRealtime(1f);
            Application.Quit();
        }

        public static int ShotCount => Shots.Length;

        static string Arg(string name)
        {
            var a = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
