using System.Collections;
using System.IO;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 自动通关测试：`-autotest &lt;截图目录&gt; -ending awaken|escape|reset`。
    /// 每轮做一件事（记一个碎片 / 走一段对话）→ 快进到循环末尾 → 场景重载后本组件重新 Start，进度在 LoopMemory。
    /// 达成结局后截图，输出 `[AutoTest] PASS &lt;结局&gt;` 或 FAIL。
    /// </summary>
    public class AutoTest : MonoBehaviour
    {
        const int MaxLoops = 8;
        string _dir;

        IEnumerator Start()
        {
            _dir = Arg("-autotest");
            if (_dir == null) { enabled = false; yield break; }
            Directory.CreateDirectory(_dir);
            string ending = Arg("-ending") ?? "awaken";

            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.enabled = false;
            var director = FindFirstObjectByType<LoopDirector>();
            var story = Story.I;
            yield return new WaitForSeconds(1.5f);
            int loop = LoopMemory.Loop;
            Log($"[{ending}] loop {loop} start, fragments=[{string.Join(",", LoopMemory.Fragments)}]");
            if (loop > MaxLoops) { Fail("too many loops"); yield break; }

            switch (ending)
            {
                case "awaken":
                    // 碎片走不同的系统：对话（教授 / 格斯）、物件、需要前置碎片的物件
                    if (loop == 1)
                    {
                        Log("room4 locked: " + story.Use("room4"));
                        yield return SkipTo(director, 30f);
                        Expect(story.HeardWrongNote, "heard wrong note by 30s");
                        Log("prof: " + story.Choose("npc.prof", "d.prof.wrong"));
                        Expect(LoopMemory.Has("piano"), "piano fragment via dialogue");
                        Log("second fragment same loop: " + story.Use("clock"));
                        Expect(!LoopMemory.Has("clock"), "only one fragment per loop");
                    }
                    else if (loop == 2)
                    {
                        yield return SkipTo(director, 20f);
                        Log("gus: " + story.Choose("npc.gus", "d.gus.martha"));
                        Expect(LoopMemory.Has("name"), "name fragment via Gus slip");
                    }
                    else if (loop == 3)
                    {
                        Log("letter before glass: " + story.Use("letter"));
                        Expect(!LoopMemory.Has("letter"), "letter needs glass");
                        Log(story.Use("glass"));
                    }
                    else if (loop == 4)
                    {
                        Log(story.Use("letter"));
                        Expect(LoopMemory.Has("letter"), "letter fragment");
                    }
                    else
                    {
                        Log("room4: " + story.Use("room4"));
                        yield return new WaitForSeconds(2.5f);
                        Shot("room4_open");
                        story.Use("typewriter");
                        yield return WaitEnding("Awaken");
                        yield break;
                    }
                    break;

                case "escape":
                    if (loop == 1) { Log(story.Use("door")); Log("backdoor: " + story.Use("backdoor")); }
                    else if (loop == 2) Log(story.Use("calendar"));
                    else
                    {
                        Log("backdoor: " + story.Use("backdoor"));
                        yield return new WaitForSeconds(2f);
                        Shot("backdoor_open");
                        story.DebugEnterVoid();
                        yield return WaitEnding("Escape");
                        yield break;
                    }
                    break;

                case "reset":
                    if (loop == 1) Log(story.Use("clock"));
                    else
                    {
                        yield return SkipTo(director, 100f);
                        Expect(story.CraneSeated, "crane seated at 100s");
                        Log("crane: " + story.Choose("npc.crane", "d.crane.writing"));
                        Expect(LoopMemory.Has("notebook"), "notebook fragment via Crane");
                        Log("crane: " + story.Choose("npc.crane", "d.crane.fine"));
                        yield return WaitEnding("Reset");
                        Expect(LoopMemory.Loop == 1 && LoopMemory.Fragments.Count == 0, "reset ending clears memory");
                        yield break;
                    }
                    break;
            }

            // 快进到循环末尾
            director.Skip(director.loopSeconds - 0.05f);
            yield return new WaitForSecondsRealtime(1.2f);
            if (loop == 1 && ending == "awaken") Shot("reset");
        }

        IEnumerator SkipTo(LoopDirector director, float t)
        {
            if (director.Elapsed < t) director.Skip(t);
            yield return new WaitForSeconds(0.6f);   // 让快进补上的事件和 NPC 站位生效
        }

        IEnumerator WaitEnding(string expected)
        {
            var hud = FindFirstObjectByType<Hud>();
            for (float t = 0; t < 20f && !hud.EndingShown; t += Time.deltaTime) yield return null;
            Shot("ending_" + expected.ToLower());
            yield return null;
            ShareCard.Capture(Path.Combine(_dir, "share_" + expected.ToLower() + ".png"));
            if (hud.EndingShown && LoopMemory.LastEnding == expected) Log($"PASS {expected} at loop {LoopMemory.Loop}");
            else Fail($"ending {LoopMemory.LastEnding ?? "none"} shown={hud.EndingShown}, expected {expected}");
            yield return new WaitForSeconds(0.5f);
            Application.Quit();
        }

        void Shot(string name) => ScreenCapture.CaptureScreenshot(Path.Combine(_dir, name + ".png"));

        static void Expect(bool ok, string what) { if (!ok) Debug.Log("[AutoTest] FAIL expect: " + what); else Log("ok: " + what); }

        static void Fail(string why) { Debug.Log("[AutoTest] FAIL " + why); Application.Quit(); }

        static void Log(string s) => Debug.Log("[AutoTest] " + (s ?? "(null)").Replace("\n", " / "));

        static string Arg(string name)
        {
            var a = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
