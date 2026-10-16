using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.SceneManagement;

namespace MercyCreek
{
    /// <summary>
    /// 自动试玩：`-playbot &lt;截图目录&gt; -route awaken|escape|reset [-mute]`。
    /// 和 AutoTest 不同，这里像真人一样玩：从标题画面按键开始、看完开场打字页、用虚拟键盘走路（运行时烘的 NavMesh 寻路）、
    /// 转头对准物件、等准星提示出现再按 E、对话用数字键选、Esc 菜单"结束这个下午"。时间不快进跳拍，只在干等时加速。
    /// 屏幕上出现的每一句字都记进日志；走不动、找不到提示、掉出世界、缺文本、异常都记为 ISSUE。
    /// </summary>
    public class PlayBot : MonoBehaviour
    {
        public static bool Active { get; private set; }

        string _dir, _route;
        Keyboard _kb;
        readonly HashSet<Key> _held = new();
        NavMeshDataInstance _nav;
        int _shots, _issues;
        bool _reloaded, _done;
        float _realStart;
        string _lastSay = "", _lastPrompt = "", _lastChoices = "";
        readonly List<string> _issueList = new();
        readonly List<string> _saidThisLoop = new();
        bool Said(string key) => _saidThisLoop.Any(x => x.Contains(Clean(Loc.T(key))));

        Hud H; Story S; LoopDirector D; FirstPersonController P; CharacterController CC; Camera Cam;
        int Loop => LoopMemory.Loop;
        float Now => D ? D.Elapsed : 0f;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            if (Arg("-playbot") == null) return;
            Active = true;
            var go = new GameObject("PlayBot");
            DontDestroyOnLoad(go);
            go.AddComponent<PlayBot>();
        }

        void Awake()
        {
            _dir = Arg("-playbot");
            _route = Arg("-route") ?? "awaken";
            Directory.CreateDirectory(_dir);
            InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            _kb = InputSystem.AddDevice<Keyboard>("PlayBotKeyboard");
            _kb.MakeCurrent();
            Application.logMessageReceived += OnLog;
            SceneManager.sceneLoaded += (_, _) => _reloaded = true;
            _realStart = Time.realtimeSinceStartup;
        }

        void OnLog(string msg, string stack, LogType type)
        {
            if (msg.StartsWith("[PlayBot]")) return;
            if (type == LogType.Exception || type == LogType.Error) Issue($"{type}: {msg.Split('\n')[0]}");
            else if (msg.StartsWith("[Loc] missing")) Issue(msg);
        }

        // =====================================================================
        // 总流程：标题 → 开场 → 每轮一段脚本（场景重载就换下一段）→ 结局
        // =====================================================================

        IEnumerator Start()
        {
            Log($"route={_route} lang={Loc.Current}");
            yield return Refresh();
            yield return Title();
            while (!_done)
            {
                _reloaded = false;
                _saidThisLoop.Clear();
                yield return Refresh();
                yield return WaitPlayable();
                int loop = Loop;
                Log($"===== loop {loop}（第 {LoopMemory.Draft} 稿）fragments=[{string.Join(",", LoopMemory.Fragments)}] =====");
                NavReport();
                var co = StartCoroutine(Guard(RunLoop(loop)));
                while (!_reloaded && !_done) yield return null;
                StopCoroutine(co);
                ReleaseAll();
                if (_reloaded && !_done) yield return LoadCard();
                if (Loop > 8 && !_done) { Issue("too many loops"); break; }
            }
            float real = Time.realtimeSinceStartup - _realStart;
            Log($"DONE route={_route} ending={LoopMemory.LastEnding ?? "none"} real={real:F0}s issues={_issues}");
            foreach (var i in _issueList) Log("  issue: " + i);
            yield return new WaitForSecondsRealtime(1f);
            Application.Quit();
        }

        /// <summary>每轮脚本里的异常不要让机器人整个停掉。</summary>
        IEnumerator Guard(IEnumerator body)
        {
            while (true)
            {
                object cur;
                try { if (!body.MoveNext()) yield break; cur = body.Current; }
                catch (Exception e) { Issue("bot exception: " + e.Message); yield break; }
                yield return cur;
            }
        }

        IEnumerator Refresh()
        {
            yield return null;
            for (int i = 0; i < 60 && !(Story.I && FindFirstObjectByType<Hud>()); i++) yield return null;
            H = FindFirstObjectByType<Hud>(); S = Story.I; D = FindFirstObjectByType<LoopDirector>();
            P = FindFirstObjectByType<FirstPersonController>(); CC = P ? P.GetComponent<CharacterController>() : null;
            Cam = P ? P.GetComponentInChildren<Camera>() : Camera.main;
            if (_nav.valid) _nav.Remove();
        }

        IEnumerator Title()
        {
            yield return new WaitForSecondsRealtime(4f);
            Shot("title");
            yield return Tap(Key.Enter);          // 没有存档：第一项是"新的一天"
            yield return new WaitForSecondsRealtime(5f);
            Shot("intro_typing");
            // 让开场打完，不按键跳过（看真人第一次看到的完整节奏）
            float t0 = Time.realtimeSinceStartup;
            while (!LoopMemory.Started) yield return null;
            Log($"intro took {Time.realtimeSinceStartup - t0 + 5f:F1}s");
            // 调试：-startloop N -frags a,b 直接从第 N 轮开始（碎片按轮依次记住）
            var sl = Arg("-startloop");
            if (sl != null)
            {
                var frags = (Arg("-frags") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries);
                for (int i = 0; i < frags.Length; i++) { LoopMemory.SetLoop(i + 1); LoopMemory.TryRemember(frags[i]); }
                LoopMemory.SetLoop(int.Parse(sl));
                Log($"start at loop {sl} with [{string.Join(",", frags)}]");
                SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
                yield return null; yield return null;
            }
        }

        IEnumerator LoadCard()
        {
            yield return Refresh();
            if (_done) yield break;
            yield return new WaitForSecondsRealtime(2.5f);
            if (D && D.Holding) Shot($"l{Loop}_card");
        }

        IEnumerator WaitPlayable()
        {
            while (!D || D.Holding || H.Typing || H.Fade > 0.1f || Menus.Blocking) { yield return null; if (_reloaded) yield break; }
        }

        // =====================================================================
        // 路线
        // =====================================================================

        IEnumerator RunLoop(int loop)
        {
            switch (_route)
            {
                case "awaken": return Awaken(loop);
                case "escape": return Escape(loop);
                case "reset": return ResetRoute(loop);
                case "probe": return Probe();
            }
            Issue("unknown route " + _route);
            _done = true;
            return null;
        }

        /// <summary>像第一次玩的人：先到处看，再一轮一轮把街道、电报、墓地、画布、4 号房走完，最后打字机觉醒。</summary>
        IEnumerator Awaken(int loop)
        {
            if (loop == 1)
            {
                Shot("l1_start");
                yield return Book("l1_book");
                yield return Use("door");                     // 第 1 稿：前门 = 第一个碎片
                Expect(LoopMemory.Has("door"), "draft 1 front door gives the door fragment");
                yield return Use("clock");
                Expect(!LoopMemory.Has("clock"), "only one fragment per loop");
                yield return Use("mirror");
                yield return Use("sheet");
                yield return Talk("npc.prof", "d.prof.hello");
                yield return Use("backdoor");
                yield return Use("room4");
                Shot("l1_balcony");
                yield return Use("dartboard");
                yield return WaitTime(S.CraneEnters + 6f);
                Shot("l1_crane_enters");
                yield return Talk("npc.gus", null);           // 打开选项再离开
                yield return WaitTime(D.loopSeconds - 11f);
                Shot("l1_red");
                yield return WaitTime(999f);                  // 自然走到下午结束
            }
            else if (loop == 2)
            {
                Shot("l2_start");
                yield return Use("telegraph");
                Expect(LoopMemory.Has("telegram"), "telegram fragment");
                Shot("l2_telegraph");
                yield return Use("townsfolk");
                yield return WaitTime(S.CraneEnters - 10f);
                yield return GoTo(new Vector3(-2.5f, 0f, -9.5f));
                LookAt(S.coach ? S.coach.transform.position + Vector3.up * 1.4f : Vector3.zero);
                yield return Wait(1f);
                Shot("l2_coach_arriving");
                yield return WaitTime(S.CraneEnters + 2f);
                Expect(S.coach && Vector3.Distance(S.coach.transform.position, S.coachStop) < 0.6f, "coach stopped at the saloon");
                Shot("l2_crane_gets_off");
                yield return Use("horse");
                yield return Use("driver");
                yield return Use("coach");
                yield return Use("graveyardgate");
                Shot("l2_gate");
                yield return Use("canvas");
                Shot("l2_canvas");
                yield return EndAfternoonViaMenu();
            }
            else if (loop == 3)
            {
                yield return Use("grave");
                Expect(LoopMemory.Has("grave"), "grave fragment");
                Shot("l3_grave");
                yield return Use("graveblank");
                yield return GoTo(new Vector3(14.3f, 0f, -9.0f));    // 走近拴马桩旁边的镇民
                yield return Wait(2f);
                Expect(Said("ev.townsfolk"), "townsfolk notice line shows");
                Expect(!_saidThisLoop.Any(x => x.Contains(Clean(Loc.T("ev.door")))), "saloon narration not shown out here");
                Shot("l3_townsfolk");
                yield return Talk("npc.gus", "d.gus.grave");
                yield return WaitTime(S.CraneEnters + 27f);
                while (!S.CraneSeated && Now < 150f) yield return WaitTime(Now + 1f);
                yield return Talk("npc.crane", "d.crane.telegram");
                Shot("l3_crane");
                yield return WaitTime(999f);
            }
            else if (loop == 4)
            {
                yield return Use("canvas");
                yield return Book("l4_book");
                yield return Use("sheet");
                while (!S.HeardWrongNote) yield return WaitTime(Now + 1f);
                yield return Talk("npc.prof", "d.prof.wrong");
                Expect(LoopMemory.Fragments.Count >= 4, "4 fragments by draft 15");
                yield return Use("room4");
                Expect(S.room4Door.IsOpen, "room 4 opens with 4 fragments");
                yield return Wait(2f);
                Shot("l4_room4");
                yield return Use("typewriter");
                yield return WaitEnding("Awaken");
            }
            else { yield return Book($"l{loop}_book"); Issue("awaken route should have ended by loop 4"); _done = true; }
        }

        /// <summary>画布出逃：日历 → 画布（门）→ 撕开画布、走进虚空。</summary>
        IEnumerator Escape(int loop)
        {
            if (loop == 1)
            {
                yield return Use("calendar");
                Expect(LoopMemory.Has("calendar"), "calendar fragment");
                yield return Use("door");
                yield return EndAfternoonViaMenu();
            }
            else if (loop == 2)
            {
                yield return Use("canvas");
                Expect(LoopMemory.Has("door"), "door fragment from the canvas");
                yield return Book("l2_book");
                yield return EndAfternoonViaMenu();
            }
            else
            {
                yield return Use("canvas");
                Expect(S.CanvasTorn, "canvas torn");
                yield return Wait(2.5f);
                Shot("canvas_torn");
                // 穿过画布往西走，直到结局
                float t0 = Time.time;
                while (!H.EndingShown && !S.Ended && Time.time - t0 < 40f)
                {
                    P.SetLook(-90f, 0f);
                    Hold(Key.W, true);
                    if (P.transform.position.x < S.canvasX - 3f && _shots < 99 && !_voidShot) { _voidShot = true; Hold(Key.W, false); yield return Wait(0.5f); Shot("void"); }
                    yield return null;
                }
                ReleaseAll();
                Expect(S.Ended, $"reached the void end (x={P.transform.position.x:F1}, ahead: {Blocker()})");
                yield return WaitEnding("Escape");
            }
        }
        bool _voidShot;

        /// <summary>调试：从街上直走进墓地门（需要 -startloop 3）。</summary>
        IEnumerator Probe()
        {
            foreach (var x in new[] { 27.7f, 27.3f, 28.1f })
            {
                Teleport(new Vector3(x, 0, -4f), 0f);
                P.SetLook(0f, 10f);
                yield return Wait(0.3f);
                Shot($"probe_gate_{x:F1}_before");
                Hold(Key.W, true);
                yield return Wait(4f);
                Hold(Key.W, false);
                Log($"probe gate x={x}: ended at {Fmt(P.transform.position)} ahead: {Blocker()}");
                Shot($"probe_gate_{x:F1}_after");
            }
            _done = true;
        }

        /// <summary>重置：跟克兰说"一切都好"。</summary>
        IEnumerator ResetRoute(int loop)
        {
            if (loop == 1)
            {
                yield return Use("clock");
                yield return EndAfternoonViaMenu();
            }
            else
            {
                yield return WaitTime(S.CraneEnters + 27f);
                while (!S.CraneSeated && Now < 150f) yield return WaitTime(Now + 1f);
                Expect(S.CraneSeated, $"crane seated (at {Now:F0}s)");
                yield return Talk("npc.crane", "d.crane.writing");
                yield return Talk("npc.crane", "d.crane.fine");
                yield return WaitEnding("Reset");
                Expect(LoopMemory.Loop == 1 && LoopMemory.Fragments.Count == 0, "reset clears memory");
            }
        }

        // =====================================================================
        // 动作
        // =====================================================================

        IEnumerator Book(string shot)
        {
            yield return Tap(Key.Tab);
            yield return Wait(0.6f);
            Expect(H.BookOpen, "Tab opens the memory book");
            Shot(shot);
            yield return Tap(Key.Tab);
            yield return Wait(0.3f);
            Expect(!H.BookOpen, "Tab closes the memory book");
        }

        IEnumerator EndAfternoonViaMenu()
        {
            yield return Tap(Key.Escape);
            yield return new WaitForSecondsRealtime(0.5f);
            Expect(Menus.Paused, "Esc pauses");
            Shot($"l{Loop}_pause");
            yield return Tap(Key.DownArrow);
            yield return Tap(Key.Enter);
            float t0 = Time.realtimeSinceStartup;
            while (!_reloaded && Time.realtimeSinceStartup - t0 < 10f) yield return null;
            if (!_reloaded) Issue("\"end this afternoon\" did not reset the loop");
        }

        IEnumerator WaitEnding(string expected)
        {
            float t0 = Time.realtimeSinceStartup;
            while (!H.EndingShown && Time.realtimeSinceStartup - t0 < 25f) yield return null;
            yield return new WaitForSecondsRealtime(1.5f);
            Shot("ending_" + expected.ToLower());
            Expect(H.EndingShown && LoopMemory.LastEnding == expected, $"ending {expected} (got {LoopMemory.LastEnding ?? "none"})");
            _done = true;
        }

        /// <summary>交互：找到物件 → 寻路走到能看见它的地方 → 转头对准 → 等提示 → 按 E。</summary>
        IEnumerator Use(string id)
        {
            var it = Targets(id).OrderBy(x => Vector3.Distance(x.bounds.center, P.transform.position)).FirstOrDefault();
            if (!it) { Issue($"[{id}] no active interactable"); yield break; }
            Vector3 aim = AimPoint(it);
            yield return Approach(aim, it, id);
            if (_reloaded) yield break;
            yield return Turn(aim);
            yield return null; yield return null;
            string prompt = H.PromptText;
            if (string.IsNullOrEmpty(prompt))
            {
                // 换几个瞄准点再试
                var b = it.bounds;
                foreach (var off in new[] { Vector3.up * 0.25f, Vector3.down * 0.25f, Vector3.up * 0.5f, Vector3.down * 0.5f })
                {
                    LookAt(aim + Vector3.Scale(off, b.extents * 2f));
                    yield return null; yield return null;
                    if (!string.IsNullOrEmpty(H.PromptText)) break;
                }
                prompt = H.PromptText;
            }
            if (string.IsNullOrEmpty(prompt))
            {
                var hit = Physics.Raycast(Cam.transform.position, Cam.transform.forward, out var h, 5f, ~0, QueryTriggerInteraction.Collide) ? $"{h.collider.name} at {h.distance:F2}m" : "nothing";
                Issue($"[{id}] no prompt from {Fmt(P.transform.position)}; ray hits {hit}");
                Shot($"l{Loop}_noprompt_{id}");
                yield break;
            }
            yield return Tap(Key.E);
            yield return Wait(1.2f);
            if (H.Saying.Length > 0) yield return Read(H.Saying);
        }

        /// <summary>对话：E 打开选项，用数字键选；optionKey = null 时选"离开"。</summary>
        IEnumerator Talk(string npcId, string optionKey)
        {
            var it = Targets(npcId).FirstOrDefault();
            if (!it) { Issue($"[{npcId}] not present"); yield break; }
            Vector3 aim = AimPoint(it);
            yield return Approach(aim, it, npcId);
            if (_reloaded) yield break;
            yield return Turn(aim);
            yield return null; yield return null;
            foreach (var dy in new[] { -0.2f, 0.2f, -0.45f })
            {
                if (!string.IsNullOrEmpty(H.PromptText) || H.ChoicesOpen) break;
                LookAt(aim + Vector3.up * dy); yield return null; yield return null;
            }
            if (string.IsNullOrEmpty(H.PromptText))
            {
                var hit = Physics.Raycast(Cam.transform.position, Cam.transform.forward, out var h, 5f, ~0, QueryTriggerInteraction.Collide) ? $"{h.collider.name} at {h.distance:F2}m" : "nothing";
                Issue($"[{npcId}] no talk prompt from {Fmt(P.transform.position)}; ray hits {hit}; choices open={H.ChoicesOpen}");
                Shot($"l{Loop}_noprompt_{npcId}");
                yield break;
            }
            var keys = S.OptionsFor(npcId).Select(o => o.key).ToList();
            yield return Tap(Key.E);
            yield return Wait(0.5f);
            if (!H.ChoicesOpen) { Issue($"[{npcId}] choices did not open"); yield break; }
            Shot($"l{Loop}_talk_{npcId.Substring(4)}");
            int idx = optionKey == null ? keys.Count : keys.IndexOf(optionKey);
            if (idx < 0) { Issue($"[{npcId}] option {optionKey} not offered (has {string.Join(",", keys)})"); idx = keys.Count; }
            yield return Tap(Key.Digit1 + idx);
            yield return Wait(1.0f);
            Expect(!H.ChoicesOpen, $"[{npcId}] choices close after picking");
            if (H.Saying.Length > 0) yield return Read(H.Saying);
        }

        /// <summary>按字数停一会儿，像人在读字。</summary>
        IEnumerator Read(string s) { yield return Wait(Mathf.Clamp(s.Length * 0.06f, 1.5f, 6f)); }

        IEnumerable<Collider> Targets(string id) =>
            FindObjectsByType<Interactable>(FindObjectsSortMode.None)
                .Where(x => x.id == id && x.isActiveAndEnabled)
                .Select(x => x.GetComponentsInChildren<Collider>().FirstOrDefault(c => c.enabled) ?? x.GetComponentInParent<Collider>())
                .Where(c => c && c.enabled);

        static Vector3 AimPoint(Collider c)
        {
            var npc = c.GetComponentInParent<Npc>();
            if (npc) return npc.transform.position + Vector3.up * 1.35f;
            return c.bounds.center;
        }

        // ---------- 寻路 ----------

        Npc _ignoreNpc;   // 走向某个人时，他自己不算障碍

        void BuildNav()
        {
            var bounds = new Bounds(new Vector3(-2f, 3f, 0f), new Vector3(96f, 16f, 44f));
            var src = new List<NavMeshBuildSource>();
            NavMeshBuilder.CollectSources(bounds, ~0, NavMeshCollectGeometry.PhysicsColliders, 0, new List<NavMeshBuildMarkup>(), src);
            src.RemoveAll(s => s.component is Collider c && (c.isTrigger || c.transform.IsChildOf(P.transform) || (_ignoreNpc && c.GetComponentInParent<Npc>() == _ignoreNpc)));
            var st = NavMesh.GetSettingsByID(0);
            // 半径接近玩家胶囊（0.28）：太小会贴着路灯柱走、被角色碰撞卡住
            st.agentRadius = 0.26f; st.agentHeight = 1.7f; st.agentClimb = 0.34f; st.agentSlope = 45f;
            var data = NavMeshBuilder.BuildNavMeshData(st, src, bounds, Vector3.zero, Quaternion.identity);
            if (_nav.valid) _nav.Remove();
            _nav = NavMesh.AddNavMeshData(data);
        }

        /// <summary>在目标周围找一个够得着、看得见、走得到的站位。</summary>
        IEnumerator Approach(Vector3 aim, Collider target, string id)
        {
            _ignoreNpc = target.GetComponentInParent<Npc>();
            BuildNav();
            _ignoreNpc = null;
            var from = NavPos(P.transform.position);
            float floorY = aim.y > 3.0f ? 3.2f : P.transform.position.y < 2f ? 0f : 3.2f;
            if (aim.y > 3.0f) floorY = 3.2f; else if (aim.y < 2.6f) floorY = 0f;
            NavMeshPath best = null; float bestLen = float.MaxValue;
            int nSample = 0, nReach = 0, nLos = 0, nPath = 0; string losBlock = "";
            var path = new NavMeshPath();
            foreach (float r in new[] { 0.9f, 1.3f, 1.7f })
                for (int a = 0; a < 360; a += 20)
                {
                    var p = new Vector3(aim.x + r * Mathf.Cos(a * Mathf.Deg2Rad), floorY, aim.z + r * Mathf.Sin(a * Mathf.Deg2Rad));
                    if (!NavMesh.SamplePosition(p, out var hit, 0.7f, NavMesh.AllAreas)) continue;
                    nSample++;
                    var eye = hit.position + Vector3.up * 1.6f;
                    if ((target.ClosestPoint(eye) - eye).magnitude > 2.2f) continue;
                    nReach++;
                    if (Physics.Raycast(eye, (aim - eye).normalized, out var los, 2.6f, ~0, QueryTriggerInteraction.Collide)
                        && los.collider != target && !los.collider.transform.IsChildOf(target.transform) && !target.transform.IsChildOf(los.collider.transform)
                        && los.collider.GetComponentInParent<Interactable>() != target.GetComponentInParent<Interactable>()) { losBlock = los.collider.name; continue; }
                    nLos++;
                    if (!NavMesh.CalculatePath(from, hit.position, NavMesh.AllAreas, path) || path.status != NavMeshPathStatus.PathComplete) continue;
                    nPath++;
                    float len = 0; for (int i = 1; i < path.corners.Length; i++) len += Vector3.Distance(path.corners[i - 1], path.corners[i]);
                    if (len < bestLen) { bestLen = len; best = path; path = new NavMeshPath(); }
                }
            if (best == null)
            {
                Issue($"[{id}] no reachable standing spot near {Fmt(aim)} from {Fmt(P.transform.position)} (navmesh pts {nSample}, in reach {nReach}, visible {nLos} [blocked by {losBlock}], path {nPath}; navmesh tris {NavMesh.CalculateTriangulation().indices.Length / 3})");
                Shot($"l{Loop}_unreachable_{id}");
                Teleport(aim + (P.transform.position - aim).normalized * 1.2f, floorY);
                yield break;
            }
            yield return Follow(best.corners, id);
        }

        IEnumerator GoTo(Vector3 dest)
        {
            BuildNav();
            var path = new NavMeshPath();
            if (!NavMesh.SamplePosition(dest, out var hit, 1.5f, NavMesh.AllAreas)
                || !NavMesh.CalculatePath(NavPos(P.transform.position), hit.position, NavMesh.AllAreas, path)
                || path.status != NavMeshPathStatus.PathComplete)
            { Issue($"no path to {Fmt(dest)}"); Teleport(dest, dest.y); yield break; }
            yield return Follow(path.corners, Fmt(dest));
        }

        void NavReport()
        {
            BuildNav();
            var pts = new (string, Vector3)[] { ("hall", new(0, 0, 4)), ("bar front", new(-3, 0, 4)), ("entry", new(0, 0, 1)), ("piano", new(1.5f, 0, 8)),
                ("balcony", new(6.2f, 3.2f, 5)), ("boardwalk", new(0, 0.25f, -1.2f)), ("street", new(0, 0, -8)), ("canvas", new(-31, 0, -7.3f)),
                ("telegraph", new(-12.25f, 0.3f, 3)), ("street east", new(14, 0, -8)), ("church front", new(26, 0, -6)), ("graveyard", new(30, 0.3f, 3)) };
            var me = NavPos(P.transform.position);
            Log($"nav: player {Fmt(P.transform.position)} → navmesh {Fmt(me)}");
            var path = new NavMeshPath();
            foreach (var (n, p) in pts)
            {
                bool s = NavMesh.SamplePosition(p, out var h, 1f, NavMesh.AllAreas);
                NavMesh.CalculatePath(me, s ? h.position : p, NavMesh.AllAreas, path);
                bool s2 = NavMesh.SamplePosition(new Vector3(0, 0, 4), out var hh, 1f, NavMesh.AllAreas);
                var p2 = new NavMeshPath(); NavMesh.CalculatePath(hh.position, s ? h.position : p, NavMesh.AllAreas, p2);
                string end = path.status == NavMeshPathStatus.PathPartial && path.corners.Length > 0 ? $" (stops at {Fmt(path.corners[^1])})" : "";
                Log($"nav: {n} sample={s} {Fmt(h.position)} from player={path.status}{end} from hall={p2.status}");
            }
        }

        Vector3 NavPos(Vector3 p) => NavMesh.SamplePosition(p, out var h, 2f, NavMesh.AllAreas) ? h.position : p;

        /// <summary>按住 W（街上加 Shift）沿路径角点走；卡住先左右挪一下，再不行记 ISSUE 并瞬移过去。</summary>
        IEnumerator Follow(Vector3[] corners, string what)
        {
            for (int i = 1; i < corners.Length; i++)
            {
                var c = corners[i];
                float lastCheck = Time.time; var lastPos = P.transform.position; int stuck = 0;
                while (Flat(c - P.transform.position).magnitude > 0.3f)
                {
                    if (_reloaded || !P) { ReleaseAll(); yield break; }
                    if (Menus.Blocking || P.InputLocked || H.ChoicesOpen) { ReleaseAll(); yield return null; continue; }
                    var d = Flat(c - P.transform.position);
                    float yaw = Mathf.MoveTowardsAngle(P.transform.eulerAngles.y, Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg, 300f * Time.deltaTime);
                    P.SetLook(yaw, Mathf.MoveTowards(P.Pitch, 4f, 60f * Time.deltaTime));
                    Hold(Key.W, true);
                    Hold(Key.LeftShift, !Sfx.Indoors(P.transform.position));
                    if (P.transform.position.y < -1f) { Issue($"fell out of the world at {Fmt(P.transform.position)}"); Teleport(c, c.y); }
                    if (Time.time - lastCheck > 2f)
                    {
                        if (Flat(P.transform.position - lastPos).magnitude < 0.25f)
                        {
                            stuck++;
                            if (stuck == 1) { Shot($"l{Loop}_stuck"); }
                            if (stuck >= 3)
                            {
                                Issue($"stuck walking to {what} at {Fmt(P.transform.position)} (corner {Fmt(c)}; ahead: {Blocker()})");
                                Teleport(c, c.y);
                                break;
                            }
                            Hold(Key.W, false);
                            var side = stuck % 2 == 1 ? Key.A : Key.D;
                            Hold(side, true); yield return Wait(0.5f); Hold(side, false);
                            if (_reloaded || !P) { ReleaseAll(); yield break; }
                        }
                        lastCheck = Time.time; lastPos = P.transform.position;
                    }
                    yield return null;
                }
            }
            Hold(Key.W, false); Hold(Key.LeftShift, false);
            yield return Wait(0.15f);
        }

        string Blocker()
        {
            var p = P.transform.position;
            return Physics.CapsuleCast(p + Vector3.up * 0.4f, p + Vector3.up * 1.4f, 0.27f, P.transform.forward, out var h, 1f, ~0, QueryTriggerInteraction.Ignore)
                ? $"{h.collider.name} [{PathOf(h.collider.transform)}] at {Fmt(h.point)}" : "nothing";
        }

        static string PathOf(Transform t) => t.parent ? PathOf(t.parent) + "/" + t.name : t.name;

        void Teleport(Vector3 p, float y)
        {
            CC.enabled = false;
            P.transform.position = new Vector3(p.x, y + 0.05f, p.z);
            CC.enabled = true;
        }

        IEnumerator Turn(Vector3 aim)
        {
            var (yaw, pitch) = YawPitch(aim);
            for (float t = 0; t < 0.4f; t += Time.deltaTime)
            {
                P.SetLook(Mathf.LerpAngle(P.transform.eulerAngles.y, yaw, 0.25f), Mathf.Lerp(P.Pitch, pitch, 0.25f));
                yield return null;
            }
            P.SetLook(yaw, pitch);
        }

        void LookAt(Vector3 aim) { var (y, p) = YawPitch(aim); P.SetLook(y, p); }

        (float, float) YawPitch(Vector3 aim)
        {
            var d = aim - Cam.transform.position;
            float yaw = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
            float pitch = -Mathf.Atan2(d.y, Flat(d).magnitude) * Mathf.Rad2Deg;
            return (yaw, pitch);
        }

        // ---------- 时间 ----------

        /// <summary>干等到本轮某个时间点：只有这时候加速（×4），一动手就恢复 ×1。</summary>
        IEnumerator WaitTime(float t)
        {
            while (Now < t)
            {
                if (_reloaded) yield break;
                if (!Menus.Paused && Time.timeScale >= 0.99f && D.Elapsed < D.loopSeconds - 0.5f) Time.timeScale = 4f;
                yield return null;
            }
            if (Time.timeScale > 1.01f) Time.timeScale = 1f;
        }

        IEnumerator Wait(float s) { for (float t = 0; t < s; t += Time.unscaledDeltaTime) { if (_reloaded) yield break; yield return null; } }

        // ---------- 键盘 ----------

        void Hold(Key k, bool on)
        {
            if (on ? _held.Add(k) : _held.Remove(k)) InputSystem.QueueStateEvent(_kb, new KeyboardState(_held.ToArray()));
        }

        void ReleaseAll() { _held.Clear(); if (_kb != null) InputSystem.QueueStateEvent(_kb, new KeyboardState()); }

        IEnumerator Tap(Key k)
        {
            Hold(k, true); yield return null; yield return null;
            Hold(k, false); yield return null; yield return null;
        }

        // =====================================================================
        // 观察：屏幕上的字、提示、对话选项，逐条记日志
        // =====================================================================

        void Update()
        {
            if (!H) return;
            string say = H.Saying, prompt = H.PromptText, ch = H.ChoicesText;
            string where = D ? $"L{Loop} {Now,6:F1}s" : "title";
            if (say != _lastSay && say.Length > 0) { Log($"SAY   {where} | {Clean(say)}"); _saidThisLoop.Add(Clean(say)); }
            if (prompt != _lastPrompt && prompt.Length > 0) Log($"PROMPT{where} | {Clean(prompt)}");
            if (ch != _lastChoices && ch.Length > 0) Log($"CHOICE{where} | {Clean(ch)}");
            _lastSay = say; _lastPrompt = prompt; _lastChoices = ch;
        }

        // ---------- 工具 ----------

        void Shot(string name)
        {
            string file = Path.Combine(_dir, $"{++_shots:00}_{name}.png");
            ScreenCapture.CaptureScreenshot(file);
            Log("shot " + Path.GetFileName(file));
        }

        void Expect(bool ok, string what) { if (ok) Log("ok: " + what); else Issue("expect failed: " + what); }

        void Issue(string s) { _issues++; _issueList.Add(s); Debug.Log("[PlayBot] ISSUE " + s); }

        static void Log(string s) => Debug.Log("[PlayBot] " + s);

        static string Clean(string s) => System.Text.RegularExpressions.Regex.Replace(s, "<[^>]+>", "").Replace("\n", " / ");

        static string Fmt(Vector3 v) => $"({v.x:F1},{v.y:F1},{v.z:F1})";

        static Vector3 Flat(Vector3 v) => new(v.x, 0, v.z);

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
