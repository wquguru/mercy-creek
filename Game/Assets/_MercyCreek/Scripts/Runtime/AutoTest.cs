using System.Collections;
using System.IO;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 自动通关测试：`-autotest &lt;截图目录&gt; -ending awaken|escape|reset|truth|town|walls`。
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
                        Log("room4 with 4: " + story.Use("room4"));
                        Expect(!story.room4Door.IsOpen, "room 4 needs 5 fragments");
                        Log("hint: " + story.NextHint());
                        Expect(story.NextHint() == Loc.T("hint.room4", 4), "hint counts toward room 4 (4/5)");
                    }
                    else
                    {
                        Log(story.Use("clock"));
                        Expect(LoopMemory.Fragments.Count == 5, "5 fragments by draft 16");
                        Log("hint: " + story.NextHint());
                        Log("room4: " + story.Use("room4"));
                        Expect(story.room4Door.IsOpen, "room 4 opens with 5 fragments incl. letter");
                        yield return new WaitForSeconds(2.5f);
                        Shot("room4_open");
                        story.Use("typewriter");
                        Expect(!FindFirstObjectByType<Hud>().ChoicesOpen, "no typewriter choice without the truth pieces");
                        yield return WaitEnding("Awaken");
                        yield break;
                    }
                    break;

                case "escape":
                    if (loop == 1)
                    {
                        Expect(story.frontDoorBlock && story.frontDoorBlock.activeSelf, "draft 1: front door blocked");
                        Log(story.Use("door"));
                        Log("backdoor: " + story.Use("backdoor"));
                    }
                    else if (loop == 2)
                    {
                        Expect(story.frontDoorBlock && !story.frontDoorBlock.activeSelf, "draft 2: street written, front door open");
                        Log("canvas before calendar: " + story.Use("canvas"));
                        Expect(!story.CanvasTorn, "canvas needs door + calendar");
                        Log(story.Use("calendar"));
                        Log("canvas in draft 13: " + story.Use("canvas"));
                        Expect(!story.CanvasTorn, "canvas cannot be torn before draft 14");
                        Log("hint: " + story.NextHint());
                    }
                    else
                    {
                        Log("canvas: " + story.Use("canvas"));
                        Expect(story.CanvasTorn, "canvas torn");
                        yield return new WaitForSeconds(2f);
                        Shot("canvas_torn");
                        story.DebugEnterVoid();
                        yield return WaitEnding("Escape");
                        yield break;
                    }
                    break;

                case "town":
                    // 街道上的东西：马车送来克兰、电报、墓地按稿数开放，最后走觉醒
                    if (loop == 1)
                    {
                        Expect(story.coach && !story.coach.Visible, "draft 1: coach invisible");
                        Log(story.Use("clock"));
                    }
                    else if (loop == 2)
                    {
                        yield return SkipTo(director, story.CraneEnters + 0.5f);
                        Expect(story.coach && story.coach.Visible, "draft 2: coach visible");
                        Expect(story.coach && Vector3.Distance(story.coach.transform.position, story.coachStop) < 0.5f, "coach stopped at the saloon");
                        Expect(story.crane.gameObject.activeSelf, "crane got off the coach");
                        Expect(story.graveGate && !story.graveGate.IsOpen, "draft 2: graveyard not written yet");
                        Log("gate: " + story.Use("graveyardgate"));
                        Log(story.Use("telegraph"));
                        Expect(LoopMemory.Has("telegram"), "telegram fragment");
                        yield return new WaitForSeconds(0.5f);
                        Shot("town_coach");
                    }
                    else if (loop == 3)
                    {
                        Expect(story.graveGate && story.graveGate.IsOpen, "draft 3: graveyard open");
                        Log(story.Use("grave"));
                        Expect(LoopMemory.Has("grave"), "grave fragment");
                        Log("gus: " + story.Choose("npc.gus", "d.gus.grave"));
                    }
                    else if (loop == 4)
                    {
                        Log(story.Use("canvas"));
                        Expect(LoopMemory.Has("door"), "door fragment from the canvas");
                        Log("hint: " + story.NextHint());
                        var hud = FindFirstObjectByType<Hud>();
                        hud.ShowBook(true);
                        yield return new WaitForSeconds(0.3f);
                        Shot("memory_book");
                        yield return null;
                        hud.ShowBook(false);
                    }
                    else if (loop == 5)
                    {
                        Log(story.Use("calendar"));
                        Log("room4 with 5 but no letter: " + story.Use("room4"));
                        Expect(LoopMemory.Fragments.Count == 5 && !story.room4Door.IsOpen, "room 4 stays locked without the letter");
                    }
                    else if (loop == 6) Log(story.Use("glass"));
                    else
                    {
                        Log(story.Use("letter"));
                        Log("hint: " + story.NextHint());
                        Expect(story.NextHint() == Loc.T("hint.awaken", Loc.T("hint.more.cage")), "hint points at the missing truth piece (cage)");
                        Log("room4: " + story.Use("room4"));
                        Expect(story.room4Door.IsOpen, "room 4 opens once the letter is found");
                        yield return new WaitForSeconds(2.5f);
                        story.Use("typewriter");
                        yield return WaitEnding("Awaken");
                        yield break;
                    }
                    break;

                case "truth":
                    // 最短真相路线：错音 → 杯子 → 信 → 笼子 → 电报 → 墓碑，第 6 稿在打字机前自己写下一句
                    if (loop == 1)
                    {
                        yield return SkipTo(director, 30f);
                        Log("prof: " + story.Choose("npc.prof", "d.prof.wrong"));
                        Expect(LoopMemory.Has("piano"), "piano fragment");
                    }
                    else if (loop == 2) Log(story.Use("glass"));
                    else if (loop == 3)
                    {
                        Log(story.Use("letter"));
                        Log("cage too early: " + story.Choose("npc.prof", "d.prof.onpurpose"));
                        Expect(!LoopMemory.Has("cage"), "cage needs draft 15");
                    }
                    else if (loop == 4)
                    {
                        Log("prof: " + story.Choose("npc.prof", "d.prof.onpurpose"));
                        Expect(LoopMemory.Has("cage"), "cage fragment from draft 15");
                    }
                    else if (loop == 5)
                    {
                        Log(story.Use("telegraph"));
                        Expect(story.NextHint() == Loc.T("hint.awaken", Loc.T("hint.more.grave")), "hint points at the grave");
                    }
                    else
                    {
                        Log(story.Use("grave"));
                        Expect(Story.TruthKnown, "all truth pieces");
                        Log("hint: " + story.NextHint());
                        Expect(story.NextHint() == Loc.T("hint.truth"), "truth hint");
                        Log("room4: " + story.Use("room4"));
                        Expect(story.room4Door.IsOpen, "room 4 open");
                        yield return new WaitForSeconds(2.5f);
                        var hud = FindFirstObjectByType<Hud>();
                        // 选项走远了会自动关：先像玩家一样站到 4 号房里、打字机前
                        var cc = FindFirstObjectByType<FirstPersonController>().GetComponent<CharacterController>();
                        cc.enabled = false; cc.transform.position = Story.IntoRoom4[1]; cc.enabled = true;
                        yield return null;
                        story.Use("typewriter");
                        yield return null;
                        Expect(hud.ChoicesOpen && !story.Ended, "typewriter waits and offers a choice");
                        Shot("truth_choice");
                        hud.CloseChoices();
                        Log("typewriter: " + story.Choose("typewriter", "d.type.write"));
                        for (float t = 0; t < 15f && !hud.Typing; t += Time.deltaTime) yield return null;
                        Expect(hud.Typing, "player types the last line");
                        yield return new WaitForSecondsRealtime(6.5f);   // 打到最后一行、停留期间
                        Shot("truth_typing");
                        yield return WaitEnding("Truth");
                        yield break;
                    }
                    break;

                case "reset":
                    if (loop == 1) Log(story.Use("clock"));
                    else
                    {
                        yield return SkipTo(director, 120f);
                        Expect(story.CraneSeated, "crane seated at 120s");
                        Log("crane: " + story.Choose("npc.crane", "d.crane.writing"));
                        Expect(LoopMemory.Has("notebook"), "notebook fragment via Crane");
                        Log("crane: " + story.Choose("npc.crane", "d.crane.fine"));
                        yield return WaitEnding("Reset");
                        Expect(LoopMemory.Loop == 1 && LoopMemory.Fragments.Count == 0, "reset ending clears memory");
                        yield break;
                    }
                    break;
            }

            if (ending == "walls") { yield return Walls(); yield break; }

            // 快进到循环末尾
            director.Skip(director.loopSeconds - 0.05f);
            yield return new WaitForSecondsRealtime(1.2f);
            if (loop == 1 && ending == "awaken") Shot("reset");
        }

        /// <summary>
        /// 隐形墙：从街上各处朝外硬走 4 秒，确认出不了"写出来"的范围（需要 -loop 3：街道、墓地都开放）。
        /// </summary>
        IEnumerator Walls()
        {
            var cc = FindFirstObjectByType<FirstPersonController>().GetComponent<CharacterController>();
            var probes = new (string name, Vector3 from, Vector3 dir, System.Func<Vector3, bool> ok)[]
            {
                ("west to canvas", new(-20, 0.3f, -7.3f), Vector3.left, p => p.x > -34.05f),
                ("east to church", new(10, 0.3f, -7.3f), Vector3.right, p => p.x < 30.3f),
                ("south facades", new(-10.7f, 0.5f, -10f), Vector3.back, p => p.z > -14.35f),
                ("south far west", new(-30, 0.5f, -10f), Vector3.back, p => p.z > -14.35f),
                ("south far east", new(27, 0.5f, -10f), Vector3.back, p => p.z > -14.35f),
                ("north west sand", new(-28, 0.5f, -5f), Vector3.forward, p => p.z < 0.1f),
                ("north alley", new(-8.1f, 0.5f, -3f), Vector3.forward, p => p.z < 0.3f),
                ("north alley east", new(8.1f, 0.5f, -3f), Vector3.forward, p => p.z < 0.3f),
                ("gap church/graveyard", new(29.5f, 0.5f, -5f), new Vector3(1, 0, 1).normalized, p => p.x < 30.4f || p.z < -1.4f),
                ("graveyard north", new(32, 0.5f, 3f), Vector3.forward, p => p.z < 12.7f),
                ("graveyard east", new(32, 0.5f, 3f), Vector3.right, p => p.x < 40.7f),
                ("graveyard west", new(30, 0.5f, 3f), Vector3.left, p => p.x > 24.1f),
                ("telegraph back", new(-12.25f, 0.5f, -1.5f), Vector3.forward, p => p.z < 7.1f),
                ("saloon back door", new(5.5f, 0.3f, 8.5f), Vector3.forward, p => p.z < 10.2f),
            };
            foreach (var pr in probes)
            {
                cc.enabled = false; cc.transform.position = pr.from; cc.enabled = true;
                float vy = 0;
                for (float t = 0; t < 4f; t += Time.deltaTime)
                {
                    vy = cc.isGrounded ? -1f : vy - 9.8f * Time.deltaTime;
                    cc.Move((pr.dir * 4f + Vector3.up * vy) * Time.deltaTime);
                    yield return null;
                }
                var p = cc.transform.position;
                Expect(pr.ok(p) && p.y > -0.5f, $"wall {pr.name} (ended at {p.x:F1},{p.y:F1},{p.z:F1})");
            }
            Log("PASS walls");
            yield return new WaitForSeconds(0.3f);
            Application.Quit();
        }

        IEnumerator SkipTo(LoopDirector director, float t)
        {
            if (director.Elapsed < t) director.Skip(t);
            yield return new WaitForSeconds(0.6f);   // 让快进补上的事件和 NPC 站位生效
        }

        IEnumerator WaitEnding(string expected)
        {
            var hud = FindFirstObjectByType<Hud>();
            for (float t = 0; t < 45f && !hud.EndingShown; t += Time.deltaTime) yield return null;   // 真相要先打完一页字
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
