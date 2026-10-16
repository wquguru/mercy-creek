using System.Collections;
using System.IO;
using System.Text;
using Unity.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MercyCreek
{
    /// <summary>
    /// 宣传片取景：`-trailer &lt;帧目录&gt; -shot &lt;名字&gt;` 拍一个镜头（30fps 逐帧，游戏时间与真实时间脱钩），
    /// `-shot list` 只写出镜头表 shots.tsv。每帧 2 倍超采样渲染再缩到窗口尺寸（抗锯齿），存 JPG；
    /// 同时用 AudioRenderer 录下这个镜头的游戏声（钢琴静音，配乐在后期另做），给 tools/trailer/edit.py 剪辑。
    /// </summary>
    public class Trailer : MonoBehaviour
    {
        const int Fps = 30;

        enum Fx { None, Reset, Tear, Torn, Room4 }

        class Shot
        {
            public string name;
            public int loop = 1;
            public float at, preroll = 0.6f, seconds = 4f;
            public Vector3 fromPos, toPos, fromLook, toLook;
            public float fovFrom = 45f, fovTo = 45f, rollFrom, rollTo;
            public float ease = 0.35f;     // 0 = 匀速（剪进剪出都在动），1 = 首尾停稳
            public float shake;            // 手持感（米 / 度量级很小）
            public string[] mem;           // 需要先记住的碎片（每稿只能记一个，按稿依次记）
            public Fx fx;
            public float fxAt;             // 特效在镜头内的起始秒数
        }

        static Shot S(string name, int loop, float at, float seconds, Vector3 fp, Vector3 fl, Vector3 tp, Vector3 tl) =>
            new() { name = name, loop = loop, at = at, seconds = seconds, fromPos = fp, fromLook = fl, toPos = tp, toLook = tl };

        // 循环时间点参考 Story（240 秒一轮）：1s 钟声、12s / 18s 格斯说话、27s 错音、30s 电报机、
        // 马车 e−15s 从画布驶出、e = 65s 克兰下车（第 4 稿起 50s）、e+27s 坐下写字、228s 变红
        // 事件按"跳过的时间点比事件晚 1 秒以上就瞬间完成"处理，所以要拍的事件都从它之前 preroll 进来
        static readonly Shot[] Shots =
        {
            // —— 第一幕：一个好天气的下午 ——
            new() { name = "town_wide", loop = 2, at = 4f, seconds = 5.5f, fovFrom = 58, fovTo = 55,
                fromPos = new(-3.4f, 1.0f, -11.4f), fromLook = new(0.5f, 3.4f, 0f), toPos = new(-2.6f, 1.8f, -11.0f), toLook = new(0.6f, 3.9f, 0f) },
            new() { name = "street_east", loop = 2, at = 6f, seconds = 4.5f, fovFrom = 42, fovTo = 42, ease = 0.1f,
                fromPos = new(-5.0f, 1.55f, -5.6f), fromLook = new(30f, 4.0f, -7.3f), toPos = new(-2.6f, 1.6f, -6.2f), toLook = new(30f, 4.2f, -7.3f) },
            new() { name = "hall_shafts", loop = 1, at = 6f, seconds = 4.5f, fovFrom = 46, fovTo = 44, ease = 0.1f,
                fromPos = new(-0.4f, 1.65f, 0.7f), fromLook = new(0.6f, 1.5f, 8f), toPos = new(0.4f, 1.7f, 1.6f), toLook = new(0.9f, 1.5f, 8f) },
            new() { name = "gus_line", loop = 1, at = 10.5f, preroll = 1.0f, seconds = 4.5f, fovFrom = 34, fovTo = 31, ease = 0.1f,
                fromPos = new(-3.3f, 1.55f, 5.6f), fromLook = new(-5.85f, 1.4f, 6.6f), toPos = new(-3.6f, 1.52f, 5.8f), toLook = new(-5.85f, 1.42f, 6.6f) },
            new() { name = "gus_again", loop = 1, at = 16.5f, preroll = 1.0f, seconds = 4.5f, fovFrom = 34, fovTo = 31, ease = 0.1f,
                fromPos = new(-3.3f, 1.55f, 5.6f), fromLook = new(-5.85f, 1.4f, 6.6f), toPos = new(-3.6f, 1.52f, 5.8f), toLook = new(-5.85f, 1.42f, 6.6f) },
            new() { name = "piano", loop = 1, at = 24f, seconds = 5f, fovFrom = 40, fovTo = 34, ease = 0.2f,
                fromPos = new(1.0f, 1.5f, 6.6f), fromLook = new(3.2f, 1.05f, 9.4f), toPos = new(1.9f, 1.42f, 7.6f), toLook = new(3.2f, 1.0f, 9.5f) },

            // —— 第二幕：一切都一模一样 ——
            // 马车 40 秒从画布后面出发，44 秒破布而出
            new() { name = "coach_canvas", loop = 2, at = 38.5f, preroll = 4.5f, seconds = 6.5f, fovFrom = 38, fovTo = 36, ease = 0.2f,
                fromPos = new(-22.5f, 1.3f, -2.2f), fromLook = new(-33f, 1.9f, -5.6f), toPos = new(-23.3f, 1.25f, -2.6f), toLook = new(-30f, 1.5f, -5.4f) },
            new() { name = "coach_arrive", loop = 3, at = 38f, preroll = 18f, seconds = 6f, fovFrom = 40, fovTo = 40, ease = 0.2f,
                fromPos = new(6.2f, 0.55f, -9.8f), fromLook = new(-4f, 1.3f, -5.4f), toPos = new(5.6f, 0.65f, -9.3f), toLook = new(0f, 1.4f, -5.4f) },
            // 克兰 65 秒下车，69 秒推门进来，72 秒在门口停下来看你（第 3 稿起）
            new() { name = "crane_door", loop = 3, at = 64.5f, preroll = 3f, seconds = 6f, fovFrom = 36, fovTo = 32, ease = 0.2f,
                fromPos = new(0.9f, 1.6f, 5.6f), fromLook = new(0.1f, 1.5f, 0.2f), toPos = new(0.8f, 1.6f, 5.0f), toLook = new(0.1f, 1.55f, 0.6f) },
            new() { name = "crane_writes", loop = 3, at = 110f, seconds = 4.5f, fovFrom = 34, fovTo = 28, ease = 0.2f,
                fromPos = new(-1.7f, 1.5f, 3.4f), fromLook = new(-3.0f, 0.95f, 1.3f), toPos = new(-2.1f, 1.4f, 2.9f), toLook = new(-3.0f, 0.9f, 1.4f) },
            new() { name = "telegraph", loop = 2, at = 29.5f, preroll = 1.0f, seconds = 4.5f, fovFrom = 36, fovTo = 30, ease = 0.2f,
                fromPos = new(-12.1f, 1.35f, 5.2f), fromLook = new(-13.0f, 0.9f, 6.42f), toPos = new(-12.5f, 1.2f, 5.7f), toLook = new(-13.0f, 0.88f, 6.42f) },
            new() { name = "graves", loop = 3, at = 120f, seconds = 5f, fovFrom = 36, fovTo = 32, ease = 0.2f,
                fromPos = new(30.6f, 1.05f, 2.2f), fromLook = new(32.1f, 0.6f, 5f), toPos = new(31.9f, 0.95f, 2.6f), toLook = new(33.3f, 0.55f, 5f) },
            // 第 3 稿起，走近镇民会一个个转头
            new() { name = "townsfolk", loop = 3, at = 80f, preroll = 1.7f, seconds = 5f, fovFrom = 34, fovTo = 30, ease = 0.3f,
                fromPos = new(-24.0f, 1.6f, -11.8f), fromLook = new(-13.5f, 1.5f, -8.2f), toPos = new(-17.5f, 1.6f, -10.5f), toLook = new(-13.5f, 1.5f, -8.2f) },
            new() { name = "gus_slip", loop = 2, at = 16.5f, preroll = 1.0f, seconds = 4.5f, fovFrom = 26, fovTo = 22, ease = 0.1f, shake = 0.3f,
                fromPos = new(-4.3f, 1.62f, 6.2f), fromLook = new(-5.85f, 1.55f, 6.6f), toPos = new(-4.6f, 1.6f, 6.3f), toLook = new(-5.85f, 1.55f, 6.6f) },
            new() { name = "canvas_walk", loop = 3, at = 140f, seconds = 4.5f, fovFrom = 44, fovTo = 44, ease = 0.0f, shake = 0.4f,
                fromPos = new(-23f, 1.65f, -6.6f), fromLook = new(-34f, 2.4f, -7.3f), toPos = new(-29.5f, 1.65f, -7.0f), toLook = new(-34f, 2.0f, -7.3f) },

            // —— 第三幕：重置、撕开、醒来 ——
            new() { name = "red", loop = 2, at = 229f, seconds = 3f, fovFrom = 40, fovTo = 36, ease = 0.1f,
                fromPos = new(0.3f, 1.65f, 0.9f), fromLook = new(0.5f, 1.6f, 8f), toPos = new(0.3f, 1.65f, 1.8f), toLook = new(0.5f, 1.6f, 8f) },
            new() { name = "reset", loop = 2, at = 236f, seconds = 3f, fovFrom = 44, fovTo = 38, ease = 0.0f, fx = Fx.Reset, fxAt = 0.2f,
                fromPos = new(-2.7f, 1.45f, 2.2f), fromLook = new(-6.7f, 1.3f, 6.5f), toPos = new(-3.1f, 1.45f, 2.7f), toLook = new(-6.7f, 1.3f, 6.5f) },
            new() { name = "tear", loop = 3, at = 140f, seconds = 4f, fovFrom = 42, fovTo = 38, ease = 0.2f, fx = Fx.Tear, fxAt = 0.6f,
                mem = new[] { "door", "calendar" },
                fromPos = new(-28.0f, 1.65f, -6.0f), fromLook = new(-34f, 1.8f, -7.3f), toPos = new(-29.3f, 1.65f, -6.5f), toLook = new(-34f, 1.8f, -7.3f) },
            new() { name = "void", loop = 3, at = 140f, preroll = 2.5f, seconds = 5f, fovFrom = 44, fovTo = 40, ease = 0.2f, fx = Fx.Torn,
                mem = new[] { "door", "calendar" },
                fromPos = new(-41.5f, 1.6f, -8.2f), fromLook = new(-34f, 1.8f, -7.3f), toPos = new(-39.5f, 1.6f, -7.6f), toLook = new(-34f, 1.7f, -7.3f) },
            new() { name = "room4", loop = 4, at = 200f, seconds = 4.5f, fovFrom = 44, fovTo = 40, ease = 0.2f, fx = Fx.Room4, fxAt = 0.6f,
                fromPos = new(0f, 4.8f, 8.0f), fromLook = new(0f, 4.5f, 12f), toPos = new(0f, 4.75f, 9.0f), toLook = new(0.1f, 4.4f, 12f) },
            new() { name = "typewriter", loop = 4, at = 200f, seconds = 6f, fovFrom = 40, fovTo = 30, ease = 0.4f, fx = Fx.Room4,
                fromPos = new(0.3f, 4.75f, 11.0f), fromLook = new(0.3f, 4.0f, 12.6f), toPos = new(0.3f, 4.45f, 11.75f), toLook = new(0.3f, 3.98f, 12.6f) },
            // 片尾字卡底图：黄昏的酒馆门脸
            new() { name = "dusk", loop = 3, at = 222f, seconds = 7f, fovFrom = 56, fovTo = 53, ease = 0.3f,
                fromPos = new(0.9f, 1.5f, -11.4f), fromLook = new(0.3f, 3.0f, 0f), toPos = new(0.6f, 1.65f, -10.6f), toLook = new(0.3f, 3.2f, 0f) },
        };

        static bool _prepared;

        IEnumerator Start()
        {
            string dir = Arg("-trailer");
            if (dir == null) { enabled = false; yield break; }
            Directory.CreateDirectory(dir);
            string which = Arg("-shot") ?? "list";
            if (which == "list")
            {
                var sb = new StringBuilder();
                foreach (var x in Shots) sb.Append(x.name).Append('\t').Append(x.seconds).Append('\n');
                File.WriteAllText(Path.Combine(dir, "shots.tsv"), sb.ToString());
                Application.Quit(); yield break;
            }
            var s = System.Array.Find(Shots, x => x.name == which) ?? Shots[int.Parse(which)];

            if (!_prepared)
            {
                // 碎片每稿只能记一个：从第 1 稿起依次记，再跳到要拍的那一稿
                _prepared = true;
                LoopMemory.Clear();
                if (s.mem != null) for (int k = 0; k < s.mem.Length; k++) { LoopMemory.SetLoop(k + 1); LoopMemory.TryRemember(s.mem[k]); }
                LoopMemory.SetLoop(s.loop);
                SceneManager.LoadScene(0);
                yield break;
            }

            var hud = FindFirstObjectByType<Hud>();
            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.enabled = false;
            var director = FindFirstObjectByType<LoopDirector>();
            var story = Story.I;
            yield return null;
            Time.captureFramerate = Fps;
            director.Skip(s.at);
            if (s.fx == Fx.Torn && story) story.Use("canvas");
            if (s.fx == Fx.Room4 && s.fxAt <= 0f && story) story.room4Door.Open(true);
            var cam = Camera.main;
            // preroll：让事件、NPC 走位和开场淡入在镜头外落定
            for (int f = 0; f < Mathf.RoundToInt(s.preroll * Fps); f++) { Pose(cam, s, 0f, 0f); Quiet(hud); yield return null; }

            var frameDir = Path.Combine(dir, s.name);
            Directory.CreateDirectory(frameDir);
            AudioRenderer.Start();
            var audio = new FileStream(Path.Combine(dir, s.name + ".f32"), FileMode.Create);
            int channels = AudioSettings.speakerMode == AudioSpeakerMode.Mono ? 1 : 2;
            NativeArray<float> buf = default;
            var rt = new RenderTexture(Screen.width, Screen.height, 0, RenderTextureFormat.ARGB32);
            var read = new Texture2D(Screen.width, Screen.height, TextureFormat.RGB24, false);
            var eof = new WaitForEndOfFrame();
            int frames = Mathf.RoundToInt(s.seconds * Fps);
            bool fxDone = false;
            for (int f = 0; f < frames; f++)
            {
                float t = f / (float)Fps;
                if (!fxDone && t >= s.fxAt) { fxDone = true; StartFx(s, story, director); }
                Pose(cam, s, f / (float)(frames - 1), t);
                Quiet(hud);
                yield return eof;
                // 2 倍超采样：高分辨率重渲染后双线性缩半（正好 2×2 平均）
                var big = ScreenCapture.CaptureScreenshotAsTexture(2);
                Graphics.Blit(big, rt);
                Destroy(big);
                var prev = RenderTexture.active; RenderTexture.active = rt;
                read.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0); read.Apply(false);
                RenderTexture.active = prev;
                File.WriteAllBytes(Path.Combine(frameDir, $"{f:0000}.jpg"), read.EncodeToJPG(95));

                int n = AudioRenderer.GetSampleCountForCaptureFrame() * channels;
                if (!buf.IsCreated || buf.Length != n) { if (buf.IsCreated) buf.Dispose(); buf = new NativeArray<float>(n, Allocator.Persistent); }
                AudioRenderer.Render(buf);
                var bytes = new byte[n * 4];
                System.Buffer.BlockCopy(buf.ToArray(), 0, bytes, 0, bytes.Length);
                audio.Write(bytes, 0, bytes.Length);
            }
            AudioRenderer.Stop();
            audio.Dispose();
            if (buf.IsCreated) buf.Dispose();
            File.WriteAllText(Path.Combine(dir, s.name + ".txt"), $"rate={AudioSettings.outputSampleRate} channels={channels} frames={frames}\n");
            Time.captureFramerate = 0;
            Debug.Log($"[Trailer] shot {s.name} {frames} frames {Screen.width}x{Screen.height}");
            yield return new WaitForSecondsRealtime(0.5f);
            Application.Quit();
        }

        static void StartFx(Shot s, Story story, LoopDirector director)
        {
            switch (s.fx)
            {
                case Fx.Tear: if (story) story.Use("canvas"); break;
                case Fx.Room4: if (story) story.room4Door.Open(); break;
                case Fx.Reset: if (director) director.StartCoroutine(ResetLook(director, s.seconds - s.fxAt)); break;
            }
        }

        // 只要重置那一下的画面（去饱和、冷色、时间变慢），不真的重载场景
        static IEnumerator ResetLook(LoopDirector d, float seconds)
        {
            for (float w = 0; w < 1f; w += Time.deltaTime / Mathf.Max(0.1f, seconds * 0.8f))
            {
                if (d.resetVolume) d.resetVolume.weight = w;
                Time.timeScale = Mathf.Lerp(1f, 0.2f, w);
                yield return null;
            }
        }

        void Quiet(Hud hud)
        {
            if (hud) { hud.HudVisible = false; hud.Fade = 0; hud.HideAll(); }
            if (Sfx.I && Sfx.I.piano) Sfx.I.piano.mute = true;   // 钢琴在后期按剪辑点重新铺
        }

        static void Pose(Camera cam, Shot s, float u, float t)
        {
            float k = Mathf.Lerp(u, Mathf.SmoothStep(0, 1, u), s.ease);
            var pos = Vector3.Lerp(s.fromPos, s.toPos, k);
            var look = Vector3.Lerp(s.fromLook, s.toLook, k);
            var rot = Quaternion.LookRotation(look - pos) * Quaternion.Euler(0, 0, Mathf.Lerp(s.rollFrom, s.rollTo, k));
            if (s.shake > 0f)
            {
                // 低频噪声做的手持感：位置几毫米、角度零点几度
                float a = s.shake;
                pos += new Vector3(Mathf.PerlinNoise(t * 0.7f, 1.3f) - 0.5f, Mathf.PerlinNoise(t * 0.9f, 7.1f) - 0.5f, 0) * 0.03f * a;
                rot *= Quaternion.Euler((Mathf.PerlinNoise(t * 0.6f, 3.7f) - 0.5f) * 1.2f * a, (Mathf.PerlinNoise(t * 0.5f, 9.2f) - 0.5f) * 1.2f * a, 0);
            }
            cam.transform.SetPositionAndRotation(pos, rot);
            cam.fieldOfView = Mathf.Lerp(s.fovFrom, s.fovTo, k);
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
