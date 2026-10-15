using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 剧本的唯一实现：每轮时间表、碎片、对话、三个结局、按稿数解锁的地点。规则见 docs/GAME_DESIGN.md，文本见 Loc。
    /// 场景引用由 SetupSaloon 填好。时间表按 LoopDirector.Elapsed 触发；快进（Skip）时错过的事件以 instant 方式补上。
    /// </summary>
    public class Story : MonoBehaviour
    {
        public static Story I { get; private set; }

        [Header("系统")]
        public LoopDirector director;
        public Hud hud;
        public Transform player;

        [Header("角色")]
        public Npc gus, prof, crane;
        public Vector3 profSeat;

        [Header("道具")]
        public GameObject notebook, letter;
        public SwingDoor room4Door, backDoor;
        public Transform clock, typewriterPaper;

        [Header("街道（第 2 稿起）")]
        public GameObject frontDoorBlock;          // 第 1 稿挡住前门（带 "door" 交互）
        public Coach coach;
        public Npc driver;
        public Npc[] townsfolk;
        public AudioSource telegraph, bell;
        public AudioClip bellThree;
        public SwingDoor graveGate;
        public GameObject graveGateNote;
        public Transform canvasFlap;               // 画布上能撕开的那一块（原点在铰链边）
        public float canvasFlapOpenAngle = -110f;
        public GameObject voidRoot;
        public AudioClip canvasTear;

        // ---------- 场地坐标（Unity，见 docs/TECH.md 坐标约定） ----------
        public static readonly Vector3 GusSpot = new(-5.85f, 0, 6.6f);
        public static readonly Vector3 GusPour = new(-5.6f, 0, 4.1f);
        public static readonly Vector3 CraneDoor = new(0, 0, 1.0f), CraneBar = new(-3.8f, 0, 4.1f);
        /// <summary>第 1 稿没有马车：克兰直接出现在门外栈道上。</summary>
        public static readonly Vector3 CraneBoardwalk = new(0, 0.25f, -1.2f);
        public static readonly Vector3 CraneSeat = new(-3.0f, 0, 1.1f);
        public static readonly Vector3[] ToSeat = { new(-2.0f, 0, 2.8f), new(-2.0f, 0, 1.0f), CraneSeat };
        public static readonly Vector3[] ToRoom4 =
        {
            new(-2.0f, 0, 0.95f), new(0.5f, 0, 1.45f), new(5.5f, 3.2f, 1.45f), new(6.2f, 3.2f, 1.7f),
            new(6.2f, 3.2f, 8.7f), new(0f, 3.2f, 8.7f), new(0f, 3.2f, 9.5f),
        };
        public static readonly Vector3[] IntoRoom4 = { new(0f, 3.2f, 10.4f), new(0.3f, 3.2f, 11.6f) };

        /// <summary>马车从西头画布里驶出，沿北侧车道往东，停在酒馆门口。</summary>
        public Vector3 coachStart = new(-33f, 0, -5.4f), coachStop = new(1.5f, 0, -5.4f);
        public float coachSpeed = 1.8f;
        /// <summary>画布所在的 x；再往西就是虚空。</summary>
        public float canvasX = -34f, voidEndX = -44f;

        public float CraneEnters => LoopMemory.Loop >= 4 ? 50f : 65f;
        public float CoachSetsOff => CraneEnters - Vector3.Distance(coachStart, coachStop) / coachSpeed - 1f;
        public const float WaltzStart = 3f;

        /// <summary>第几轮起写出来：街道 + 电报局 2，墓地 3。</summary>
        public static bool StreetWritten => LoopMemory.Loop >= 2;
        public static bool GraveyardWritten => LoopMemory.Loop >= 3;

        /// <summary>本轮状态（每轮场景重载后归零）。</summary>
        public bool CraneSeated { get; private set; }
        public bool CraneGone { get; private set; }
        public bool HeardWrongNote { get; private set; }
        public bool HeardSlip { get; private set; }
        public bool CanvasTorn { get; private set; }
        public bool Ended { get; private set; }

        struct Beat { public float t; public Action<bool> act; }
        readonly List<Beat> _beats = new();
        int _next;
        bool _inVoid, _townsfolkNoticed;

        float Now => director ? director.Elapsed : 0f;
        int Loop => LoopMemory.Loop;

        void Awake() { I = this; }
        void OnDestroy() { if (I == this) I = null; }

        void Start()
        {
            gus.Place(GusSpot, 90, MannequinRig.Pose.Wipe);
            prof.Place(profSeat, 0, MannequinRig.Pose.Piano);
            crane.Place(CraneBoardwalk, 0, MannequinRig.Pose.Stand);
            crane.gameObject.SetActive(false);
            if (notebook) notebook.SetActive(false);
            if (letter) letter.SetActive(LoopMemory.Has("glass"));
            if (voidRoot) voidRoot.SetActive(false);
            room4Door.Close(true);
            backDoor.Close(true);

            // 按稿数写出世界：第 1 稿门外是"画"，没有人也没有马车
            if (frontDoorBlock) frontDoorBlock.SetActive(!StreetWritten);
            if (coach)
            {
                coach.Place(coachStart, 90f);
                coach.Visible = StreetWritten;
            }
            if (driver) driver.gameObject.SetActive(StreetWritten);
            if (townsfolk != null) foreach (var t in townsfolk) if (t) t.gameObject.SetActive(StreetWritten);
            if (graveGate)
            {
                if (GraveyardWritten) graveGate.Open(true); else graveGate.Close(true);
                if (graveGateNote) graveGateNote.SetActive(!GraveyardWritten);
            }
            BuildSchedule();
        }

        // =====================================================================
        // 时间表
        // =====================================================================

        void At(float t, Action<bool> act) => _beats.Add(new Beat { t = t, act = act });

        void BuildSchedule()
        {
            float e = CraneEnters, end = director.loopSeconds;
            At(0.5f, i =>
            {
                if (i) return;
                hud.Say(Loc.T(Loop == 1 ? "ev.start" : Loop == 2 ? "ev.street" : "ui.again"), Loop == 2 ? 6f : 5f);
            });
            At(1f, i => { if (!i && bell && bellThree) bell.PlayOneShot(bellThree, Sfx.EffectsVolume); });
            At(12f, i => { if (!i) gus.Say(hud, "ev.gus.day", 4.5f); });
            At(18f, i =>
            {
                HeardSlip = Loop >= 2;
                if (i) return;
                gus.Say(hud, Loop >= 2 ? "ev.gus.slip" : "ev.gus.day", 4.5f);
            });
            At(23f, i => { if (!i && Loop == 1) hud.Say(Loc.T("ev.repeat"), 4f); });

            // 钢琴错音：每次弹到第 16 小节
            for (float w = WaltzStart + Sfx.WrongNoteAt; w < end; w += Sfx.WaltzLength)
            {
                bool first = w < 40f;
                At(w, i =>
                {
                    HeardWrongNote = true;
                    if (!i && first && Loop <= 2) hud.Say(Loc.T("ev.wrongnote"), 4f);
                    if (!i) prof.rig.talk = 0.6f;
                });
            }

            // 电报局：电报机自己响起来（第 2 稿起）
            if (StreetWritten) At(30f, _ => { if (telegraph && !telegraph.isPlaying) telegraph.Play(); });

            // 驿站马车 → 陌生人
            if (coach)
                At(CoachSetsOff, i => coach.Drive(new[] { coachStop }, coachSpeed, i));
            if (!StreetWritten) At(e - 2f, i => { if (!i) hud.Say(Loc.T("ev.hooves"), 4f); });
            At(e, i =>
            {
                crane.gameObject.SetActive(true);
                var from = StreetWritten && coach && coach.Exit ? coach.Exit.position : CraneBoardwalk;
                crane.Place(StreetWritten ? new Vector3(from.x, 0f, from.z) : from, 0, MannequinRig.Pose.Stand);
                if (!i && coach) coach.OpenDoor();
                var path = new List<Vector3>();
                if (StreetWritten) path.AddRange(new[] { new Vector3(0.45f, 0f, -2.8f), new Vector3(0.35f, 0.25f, -2.2f) });
                path.AddRange(new[] { new Vector3(0.1f, 0.25f, -0.5f), new Vector3(0f, 0f, 0.3f), CraneDoor, CraneBar });
                crane.WalkTo(path.ToArray(), MannequinRig.Pose.Lean, -90, i);
            });
            At(e + 4f, i =>
            {
                if (!i) Sfx.I?.PlayAt(Sfx.I.doorOpen, new Vector3(0, 1.4f, 0.2f), 0.7f);
                if (!i) hud.Say(Loc.T("ev.door"), 4.5f);
            });
            if (Loop >= 3) At(e + 7f, i => { if (!i) { hud.Say(Loc.T("ev.crane.glance"), 4f); crane.LookAtPlayer(3f); } });
            At(e + 12f, i =>
            {
                if (!i) crane.Say(hud, "ev.crane.order", 3f);
                gus.WalkTo(new[] { GusPour }, MannequinRig.Pose.Pour, 90, i);
            });
            At(e + 15f, i => { if (!i) Sfx.I?.PlayAt(Sfx.I.glassPour, GusPour + Vector3.up * 1.1f + Vector3.right * 0.8f, 0.8f); });
            At(e + 19f, i => gus.WalkTo(new[] { GusSpot }, MannequinRig.Pose.Wipe, 90, i));
            if (Loop >= 5) At(e + 22f, i => { if (!i) crane.Say(hud, "ev.crane.early", 4.5f); });
            At(e + 27f, i => crane.WalkTo(ToSeat, MannequinRig.Pose.SitWrite, 0, i, () =>
            {
                CraneSeated = true;
                if (notebook) notebook.SetActive(true);
            }));
            At(150f, i =>
            {
                if (i || !CraneSeated) return;
                crane.Say(hud, "ev.crane.clock", 4f);
                crane.LookAt(clock, 5f);
            });
            At(180f, i =>
            {
                CraneSeated = false;
                crane.WalkTo(ToRoom4, MannequinRig.Pose.Stand, 0, i, () =>
                {
                    room4Door.Open(i);
                    crane.WalkTo(IntoRoom4, MannequinRig.Pose.Stand, null, i, () =>
                    {
                        room4Door.Close(i);
                        crane.gameObject.SetActive(false);
                        CraneGone = true;
                        if (!i) Sfx.I?.PlayAt(Sfx.I.doorClose, new Vector3(0, 4.3f, 10f), 0.7f);
                    });
                });
            });
            At(184f, i => { if (!i) hud.Say(Loc.T("ev.crane.leave"), 5f); });
            At(end - 12f, i => { if (!i) hud.Say(Loc.T(Loop == 1 ? "ev.red1" : "ev.red"), 7f); });
            _beats.Sort((a, b) => a.t.CompareTo(b.t));
        }

        void Update()
        {
            if (Ended) return;
            float now = Now;
            while (_next < _beats.Count && _beats[_next].t <= now)
            {
                var b = _beats[_next++];
                b.act(now - b.t > 1f);
            }
            if (CanvasTorn && player) CheckVoid();
        }

        /// <summary>第 3 稿起，玩家第一次走近镇民时提示一句（由 Townsfolk 调用）。</summary>
        public void NoticeTownsfolk()
        {
            if (_townsfolkNoticed || Ended) return;
            _townsfolkNoticed = true;
            hud.Say(Loc.T("ev.townsfolk"), 4.5f);
        }

        // =====================================================================
        // 交互：Interactable.id → 提示 / 结果
        // =====================================================================

        bool CanTear => StreetWritten && LoopMemory.Has("door") && LoopMemory.Has("calendar") && !CanvasTorn;

        /// <summary>返回 null 表示现在不能交互。</summary>
        public string Prompt(string id) => id switch
        {
            "npc.gus" => Loc.T("ui.talk", gus.DisplayName),
            "npc.prof" => Loc.T("ui.talk", prof.DisplayName),
            "npc.crane" => Loc.T("ui.talk", crane.DisplayName),
            "notebook" => notebook && notebook.activeInHierarchy ? Loc.T("p.notebook") : null,
            "room4" => room4Door.IsOpen ? null : Loc.T("p.room4"),
            "backdoor" => Loc.T("p.backdoor"),
            "typewriter" => room4Door.IsOpen ? Loc.T("p.typewriter") : null,
            "canvas" => CanvasTorn ? null : Loc.T(CanTear ? "p.canvas.tear" : "p.canvas"),
            "graveyardgate" => GraveyardWritten ? null : Loc.T("p.tbd"),
            "driver" or "townsfolk" => Loc.T("p." + id),
            _ => Loc.Has("p." + id) ? Loc.T("p." + id) : null,
        };

        /// <summary>返回要显示的文字（对话等返回 null，由选项界面处理）。</summary>
        public string Use(string id)
        {
            if (Ended) return null;
            switch (id)
            {
                case "clock": return Remember("clock", "f.clock");
                case "mirror": return Remember("mirror", Loop >= 4 && !LoopMemory.Has("mirror") ? "f.mirror.lag" : "f.mirror");
                case "door": return Remember("door", "f.door");
                case "canvas":
                    if (CanTear) { StartCoroutine(TearCanvas()); return Loc.T("f.canvas.tear"); }
                    return Remember("door", "f.canvas");
                case "glass":
                    {
                        string s = Remember("glass", "f.glass");
                        if (LoopMemory.Has("glass") && letter) letter.SetActive(true);
                        return s;
                    }
                case "calendar": return Remember("calendar", "f.calendar");
                case "letter": return LoopMemory.Has("glass") ? Remember("letter", "f.letter") : Loc.T("f.letter.locked");
                case "notebook": return Remember("notebook", "f.notebook");
                case "telegraph": return Remember("telegram", "f.telegram", LoopMemory.DraftOf(Loop - 1), LoopMemory.Draft);
                case "grave": return Remember("grave", "f.grave");
                case "graveblank": return Loc.T("f.graveblank");
                case "tbd": case "graveyardgate": return Loc.T("f.tbd");
                case "coach": return Loc.T("f.coach");
                case "horse": return Loc.T("f.horse");
                case "driver": return Loc.T("f.driver");
                case "townsfolk": return Loc.T(Loop >= 3 ? "f.townsfolk.3" : "f.townsfolk");
                case "sheet": return SheetMusic();
                case "dartboard": return Loc.T("f.dartboard");
                case "bottles": return Loc.T("f.bottles");
                case "room4": return UseRoom4();
                case "typewriter": StartCoroutine(AwakenEnding()); return null;
                case "backdoor": return Loc.T("f.backdoor.locked");
                case "npc.gus": OpenDialogue(gus, GusOptions()); return null;
                case "npc.prof": OpenDialogue(prof, ProfOptions()); return null;
                case "npc.crane": OpenDialogue(crane, CraneOptions()); return null;
            }
            return null;
        }

        string Remember(string id, string textKey, params object[] args)
        {
            string text = Loc.T(textKey, args);
            if (LoopMemory.Has(id)) return Loc.Has(textKey + ".r") ? Loc.T(textKey + ".r") : text;
            if (LoopMemory.TryRemember(id))
            {
                Sfx.I?.Play2D(Sfx.I.remember, 0.8f);
                return text + "\n" + Loc.T("ui.remembered");
            }
            Sfx.I?.Play2D(Sfx.I.denied, 0.6f);
            return text + "\n" + Loc.T("ui.full");
        }

        /// <summary>乐谱上圈出教授已经弹错过的音（含这一稿，如果已经听到了）。</summary>
        string SheetMusic()
        {
            int upto = Mathf.Min(HeardWrongNote ? Loop : Loop - 1, 4);
            if (upto < 1) return Loc.T("f.sheet.empty");
            var notes = Enumerable.Range(1, upto).Select(Sfx.WrongNoteName);
            return Loc.T("f.sheet", string.Join(Loc.Current == Loc.Lang.Zh ? "、" : ", ", notes));
        }

        string UseRoom4()
        {
            if (LoopMemory.Fragments.Count < 4)
                return Loc.T(CraneGone ? "f.room4.crane" : "f.room4.locked");
            room4Door.Open();
            Sfx.I?.PlayAt(Sfx.I.doorOpen, new Vector3(0, 4.3f, 10f), 0.8f);
            StartCoroutine(TypewriterClicks());
            return Loc.T("f.room4.open");
        }

        IEnumerator TypewriterClicks()
        {
            var pos = typewriterPaper ? typewriterPaper.position : new Vector3(0, 4f, 12.5f);
            while (!Ended)
            {
                Sfx.I?.Type(pos);
                yield return new WaitForSeconds(UnityEngine.Random.Range(0.09f, 0.28f));
                if (UnityEngine.Random.value < 0.04f) { Sfx.I?.PlayAt(Sfx.I.typeBell, pos, 0.6f); yield return new WaitForSeconds(0.6f); }
            }
        }

        IEnumerator TearCanvas()
        {
            CanvasTorn = true;
            if (voidRoot) voidRoot.SetActive(true);
            var at = canvasFlap ? canvasFlap.position : new Vector3(canvasX, 1.7f, -7.3f);
            if (canvasTear) Sfx.I?.PlayAt(canvasTear, at, 1f);
            if (!canvasFlap) yield break;
            var rest = canvasFlap.localRotation;
            var col = canvasFlap.GetComponentInChildren<Collider>();
            if (col) col.enabled = false;
            for (float t = 0; t < 1f; t += Time.deltaTime / 1.4f)
            {
                float k = 1f - (1f - t) * (1f - t);
                canvasFlap.localRotation = rest * Quaternion.Euler(0, canvasFlapOpenAngle * k, 0);
                yield return null;
            }
        }

        // =====================================================================
        // 记忆本"下一步"（GAME_DESIGN.md 的顺序）
        // =====================================================================

        public string NextHint()
        {
            int n = LoopMemory.Fragments.Count;
            if (n == 0) return Loc.T("hint.none");
            if (n >= 4) return Loc.T("hint.awaken");
            bool door = LoopMemory.Has("door"), cal = LoopMemory.Has("calendar");
            if (door && cal && StreetWritten) return Loc.T("hint.escape");
            if (door && !cal && StreetWritten) return Loc.T("hint.calendar");
            if (StreetWritten && !door) return Loc.T("hint.street");
            return Loc.T("hint.count", n);
        }

        // =====================================================================
        // 对话
        // =====================================================================

        public struct Option
        {
            public string key;
            public Func<string> pick;   // 返回回应文本（已带说话人）
        }

        Option Opt(string key, Func<string> pick) => new() { key = key, pick = pick };

        public List<Option> OptionsFor(string npcId) => npcId switch
        {
            "npc.gus" => GusOptions(),
            "npc.prof" => ProfOptions(),
            "npc.crane" => CraneOptions(),
            _ => new List<Option>(),
        };

        List<Option> GusOptions()
        {
            var o = new List<Option> { Opt("d.gus.hello", () => Loc.Line("name.gus", "r.gus.hello")) };
            if (HeardSlip && !LoopMemory.Has("name"))
                o.Add(Opt("d.gus.martha", () => Loc.Line("name.gus", "r.gus.martha") + "\n" + Remember("name", "f.name")));
            if (LoopMemory.Has("name"))
                o.Add(Opt("d.gus.who", () => Loc.Line("name.gus", "r.gus.who")));
            if (LoopMemory.Has("grave"))
                o.Add(Opt("d.gus.grave", () => Loc.Line("name.gus", "r.gus.grave")));
            return o;
        }

        List<Option> ProfOptions()
        {
            string note = Sfx.WrongNoteName(Loop);
            var o = new List<Option> { Opt("d.prof.hello", () => Loc.Line("name.prof", "r.prof.hello")) };
            if (HeardWrongNote && !LoopMemory.Has("piano"))
                o.Add(Opt("d.prof.wrong", () => Loc.Line("name.prof", "r.prof.wrong", note) + "\n" + Remember("piano", "f.piano", note)));
            if (LoopMemory.Has("piano") && !LoopMemory.Has("cage"))
            {
                if (Loop >= 4) o.Add(Opt("d.prof.onpurpose", () => Loc.Line("name.prof", "r.prof.onpurpose") + "\n" + Remember("cage", "f.cage")));
                else o.Add(Opt("d.prof.notyet", () => Loc.Line("name.prof", "r.prof.notyet")));
            }
            return o;
        }

        List<Option> CraneOptions()
        {
            var o = new List<Option>();
            if (CraneSeated && !LoopMemory.Has("notebook"))
                o.Add(Opt("d.crane.writing", () => Loc.Line("name.crane", "r.crane.writing") + "\n" + Remember("notebook", "f.notebook.r")));
            else
                o.Add(Opt("d.crane.hello", () => Loc.Line("name.crane", "r.crane.hello")));
            if (LoopMemory.Has("notebook") || Loop >= 5)
                o.Add(Opt("d.crane.you", () => Loc.Line("name.crane", "r.crane.you")));
            if (LoopMemory.Has("telegram"))
                o.Add(Opt("d.crane.telegram", () => Loc.Line("name.crane", "r.crane.telegram")));
            if (LoopMemory.Fragments.Count >= 2)
                o.Add(Opt("d.crane.room4", () => Loc.Line("name.crane", "r.crane.room4")));
            if (LoopMemory.Fragments.Count >= 1)
                o.Add(Opt("d.crane.fine", () => { StartCoroutine(ResetEnding()); return Loc.Line("name.crane", "r.crane.fine"); }));
            return o;
        }

        void OpenDialogue(Npc npc, List<Option> options)
        {
            npc.LookAtPlayer(8f);
            hud.ShowChoices(npc, options.Select(o => (Loc.T(o.key), (Action)(() =>
            {
                Sfx.I?.Play2D(Sfx.I.click, 0.6f);
                hud.Say(o.pick(), 7f);
                if (npc.rig) npc.rig.talk = 1f;
            }))).ToList());
        }

        /// <summary>测试用：直接选某个选项。</summary>
        public string Choose(string npcId, string optionKey)
        {
            var o = OptionsFor(npcId).FirstOrDefault(x => x.key == optionKey);
            return o.pick?.Invoke();
        }

        // =====================================================================
        // 结局
        // =====================================================================

        public enum Ending { None, Reset, Escape, Awaken }

        IEnumerator ResetEnding()
        {
            Ended = true;
            yield return new WaitForSeconds(4.5f);
            LoopMemory.Clear();
            Finish(Ending.Reset, Loc.T("end.reset"), Loc.T("end.reset.sub"));
        }

        void CheckVoid()
        {
            var p = player.position;
            if (!_inVoid && p.x < canvasX - 0.5f)
            {
                _inVoid = true;
                hud.Say(Loc.T("f.void"), 6f);
                Sfx.I?.StopPiano(2f);
                Sfx.I?.FadeAmbience(0f, 2f);
                Sfx.I?.PlayMusic(Sfx.I.voidHum, true);
            }
            if (_inVoid && !Ended && p.x < voidEndX)
            {
                Ended = true;
                Finish(Ending.Escape, Loc.T("end.escape"), Loc.T("end.escape.sub"));
            }
        }

        IEnumerator AwakenEnding()
        {
            Ended = true;
            hud.Say(Loc.T("f.typewriter", LoopMemory.Draft), 9f);
            yield return new WaitForSeconds(5f);
            int secs = Mathf.FloorToInt(LoopMemory.TotalSeconds);
            Finish(Ending.Awaken, Loc.T("end.awaken"), Loc.T("end.awaken.sub", LoopMemory.Draft, secs / 60, secs % 60));
        }

        /// <summary>测试用：在虚空里直接走到终点。</summary>
        public void DebugEnterVoid()
        {
            if (!player) return;
            var cc = player.GetComponent<CharacterController>();
            if (cc) cc.enabled = false;
            player.position = new Vector3(voidEndX - 1f, 0.05f, -7.3f);
            if (cc) cc.enabled = true;
            CheckVoid(); CheckVoid();
        }

        void Finish(Ending ending, string title, string sub)
        {
            Ended = true;
            LoopMemory.LastEnding = ending.ToString();
            LoopMemory.DeleteSave();
            if (director) director.enabled = false;
            Sfx.I?.StopPiano(1.5f);
            Sfx.I?.FadeAmbience(0f, 2f);
            if (telegraph) telegraph.Stop();
            if (ending != Ending.Escape) Sfx.I?.PlayMusic(Sfx.I.endingTheme);
            hud.ShowEnding(title, sub);
            Debug.Log($"[Story] ending {ending} loop={Loop} fragments={string.Join(",", LoopMemory.Fragments)}");
        }
    }
}
