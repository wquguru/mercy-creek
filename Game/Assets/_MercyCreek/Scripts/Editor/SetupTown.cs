using System;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// 主街部分（第 2 稿起写出来的世界）：北侧一排房子 + 电报局室内、东头教堂墓地、西头画布、驿站马车、镇民、隐形墙。
    /// 布局见 docs/GAME_DESIGN.md「主街布局」；节点名是 build_town.py / build_edges.py / build_coach.py 约定好的。
    /// </summary>
    public static partial class SetupSaloon
    {
        static void BuildTown(Story story, Hud hud)
        {
            // ---------- 建筑 ----------
            var town = PlaceGlb("Art/Town/Town.gltf", "Town", Vector3.zero, 180, false);
            var edges = PlaceGlb("Art/Town/TownEdges.gltf", "Town Edges", Vector3.zero, 180, false);
            foreach (var root in new[] { town, edges })
                foreach (var mf in root.GetComponentsInChildren<MeshFilter>())
                {
                    var r = mf.GetComponent<MeshRenderer>();
                    r.receiveGI = ReceiveGI.LightProbes;
                    r.shadowCastingMode = r.sharedMaterials.Any(m => m && m.name.ToLower().Contains("glass")) ? ShadowCastingMode.Off : ShadowCastingMode.TwoSided;
                    GameObjectUtility.SetStaticEditorFlags(mf.gameObject, StaticEditorFlags.ContributeGI | StaticEditorFlags.ReflectionProbeStatic | StaticEditorFlags.BatchingStatic);
                    if (!HasNoColPrefix(mf.transform, root.transform)) mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                }
            // 画布那一片会被撕开，不能 static batching
            var flap = Find(edges, "Canvas_Flap");
            if (flap)
                foreach (var r in flap.GetComponentsInChildren<MeshRenderer>(true))
                {
                    GameObjectUtility.SetStaticEditorFlags(r.gameObject, 0);
                    if (!r.GetComponent<Collider>()) r.gameObject.AddComponent<MeshCollider>().sharedMesh = r.GetComponent<MeshFilter>().sharedMesh;
                }
            story.canvasFlap = flap;

            // ---------- 电报局 ----------
            var machine = Find(town, "Telegraph_Machine");
            if (machine)
            {
                InteractAround(machine.gameObject, "telegraph", 0.25f);
                var src = new GameObject("Telegraph Sound").AddComponent<AudioSource>();
                src.transform.position = WorldBounds(machine.gameObject).center;
                src.clip = Clip("telegraph_loop"); src.loop = true; src.playOnAwake = false;
                src.spatialBlend = 1f; src.minDistance = 1.2f; src.maxDistance = 22f; src.rolloffMode = AudioRolloffMode.Logarithmic; src.volume = 0.8f;
                story.telegraph = src;
            }
            else Debug.LogWarning("[SetupSaloon] Telegraph_Machine not found");
            var lampPos = Find(town, "Telegraph_LampPos");
            var tlamp = PointLight("Telegraph Lamp", lampPos ? lampPos.position : new Vector3(-12.25f, 3.0f, 3.5f), 7f, new Color(1f, 0.66f, 0.36f), true);
            tlamp.intensity = 1.6f;
            ProbeVolumeAt("APV Telegraph", new Vector3(-12.25f, 2.05f, 3.5f), new Vector3(6.1f, 3.5f, 6.8f));
            ReflectionProbeAt("Reflection Probe Telegraph", new Vector3(-12.25f, 1.6f, 3.5f), new Vector3(-12.25f, 2.0f, 3.5f), new Vector3(6.6f, 3.9f, 7.3f));

            // ---------- "待写"纸条 ----------
            foreach (var t in town.GetComponentsInChildren<Transform>().Concat(edges.GetComponentsInChildren<Transform>()).Where(t => t.name.StartsWith("TBD_")))
            {
                if (t.name == "TBD_Graveyard") continue;   // 挂在墓地门上，跟门一起处理
                InteractAround(t.gameObject, "tbd", 0.35f);
            }

            // ---------- 墓地 ----------
            var gateMesh = Find(edges, "Graveyard_Gate");
            if (gateMesh)
            {
                // 门的原点就在铰链上（build_edges.py）。导入模型里的节点不能改父级，SwingDoor 直接挂在门上
                foreach (var r in gateMesh.GetComponentsInChildren<MeshRenderer>(true))
                {
                    GameObjectUtility.SetStaticEditorFlags(r.gameObject, 0);
                    if (!r.GetComponent<Collider>()) r.gameObject.AddComponent<MeshCollider>().sharedMesh = r.GetComponent<MeshFilter>().sharedMesh;
                }
                var gate = gateMesh.gameObject.AddComponent<SwingDoor>();
                gate.openAngle = GateOpenAngle;
                gateMesh.gameObject.AddComponent<Interactable>().id = "graveyardgate";
                story.graveGate = gate;
                story.graveGateNote = Find(edges, "TBD_Graveyard")?.gameObject;
            }
            else Debug.LogWarning("[SetupSaloon] Graveyard_Gate not found");
            var martha = Find(edges, "Grave_Martha"); if (martha) InteractAround(martha.gameObject, "grave", 0.3f);
            var blank = Find(edges, "Grave_Blank"); if (blank) InteractAround(blank.gameObject, "graveblank", 0.3f);

            // ---------- 教堂钟 ----------
            var bellPos = Find(edges, "Church_BellPos") ?? Find(edges, "Church_Bell");
            var bell = new GameObject("Church Bell Sound").AddComponent<AudioSource>();
            bell.transform.position = bellPos ? bellPos.position : new Vector3(31f, 12f, -7.3f);
            bell.spatialBlend = 0.6f; bell.minDistance = 20f; bell.maxDistance = 200f; bell.rolloffMode = AudioRolloffMode.Linear; bell.playOnAwake = false;
            story.bell = bell;
            story.bellThree = Clip("church_bell_three");

            // ---------- 画布 + 后面的虚空 ----------
            var canvasMain = Find(edges, "Canvas_Main");
            var canvasPos = Find(edges, "Canvas_Pos");
            var cTrig = new GameObject("Interact canvas");
            cTrig.transform.position = canvasPos ? canvasPos.position + Vector3.right * 0.3f : new Vector3(story.canvasX + 0.3f, 1.7f, -7.3f);
            var cbox = cTrig.AddComponent<BoxCollider>(); cbox.isTrigger = true; cbox.size = new Vector3(0.5f, 3.4f, 9.8f);
            cTrig.AddComponent<Interactable>().id = "canvas";
            story.canvasX = canvasMain ? WorldBounds(canvasMain.gameObject).center.x : -34f;
            story.voidEndX = story.canvasX - 10f;
            story.canvasTear = Clip("canvas_tear");
            story.voidRoot = MakeVoid(story.canvasX - 0.15f);

            // ---------- 驿站马车 ----------
            story.coach = MakeCoach(story, out var driver);
            story.driver = driver;

            // ---------- 镇民（定格的群演） ----------
            story.townsfolk = new[]
            {
                MakeTownsfolk("Townsman", "Townsfolk Crossing", new Vector3(-13.5f, 0f, -8.2f), 205f, MannequinRig.Pose.Step),
                MakeTownsfolk("Townswoman", "Townsfolk Storefront", new Vector3(-6.2f, 0.35f, -12.75f), 8f, MannequinRig.Pose.Stand),
                MakeTownsfolk("Townsman", "Townsfolk Hitching Rail", new Vector3(14.3f, 0f, -11.15f), 180f, MannequinRig.Pose.Lean),
            };

            // ---------- 隐形墙：把玩家关在写出来的范围里 ----------
            var walls = new GameObject("Invisible Walls").transform;
            void Wall(string n, Vector3 a, Vector3 b)   // a、b 为对角（x, z），高 8 m
            {
                var w = new GameObject("Wall " + n).AddComponent<BoxCollider>();
                w.transform.SetParent(walls, false);
                w.center = new Vector3((a.x + b.x) / 2, 4f, (a.z + b.z) / 2);
                w.size = new Vector3(Mathf.Max(0.2f, Mathf.Abs(b.x - a.x)), 8f, Mathf.Max(0.2f, Mathf.Abs(b.z - a.z)));
            }
            Wall("South", new Vector3(-34, 0, -14.25f), new Vector3(30, 0, -14.25f));       // 对街房子立面之间的缝
            Wall("North West", new Vector3(-34, 0, -0.1f), new Vector3(-24, 0, -0.1f));    // 殡仪馆以西
            Wall("East South Gap", new Vector3(30.2f, 0, -14.3f), new Vector3(30.2f, 0, -11.0f));
            Wall("East North Gap", new Vector3(30.2f, 0, -3.6f), new Vector3(30.2f, 0, -1.6f));
            Wall("East Steps", new Vector3(28.6f, 0, -11.0f), new Vector3(28.6f, 0, -3.6f));
            Wall("Graveyard Back", new Vector3(23, 0, 12.5f), new Vector3(41, 0, 12.5f));
            Wall("Graveyard East", new Vector3(40.5f, 0, -1.6f), new Vector3(40.5f, 0, 12.5f));
            Wall("Graveyard West", new Vector3(24.3f, 0, -1.6f), new Vector3(24.3f, 0, 12.5f));
        }

        /// <summary>墓地门打开的角度（绕铰链的 Y 轴，向墓地里开），按 build_edges.py 的报告。</summary>
        const float GateOpenAngle = -100f;

        static bool HasNoColPrefix(Transform t, Transform root)
        {
            for (var x = t; x && x != root; x = x.parent) if (x.name.StartsWith("NoCol_")) return true;
            return false;
        }

        /// <summary>在一组网格外包一个触发盒，挂交互 id（不改原网格的碰撞）。</summary>
        static void InteractAround(GameObject target, string id, float pad)
        {
            var b = WorldBounds(target);
            var go = new GameObject($"Interact {id} ({target.name})");
            go.transform.position = b.center;
            var box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.size = b.size + Vector3.one * pad;
            go.AddComponent<Interactable>().id = id;
        }

        static Coach MakeCoach(Story story, out Npc driver)
        {
            var root = new GameObject("Stagecoach");
            var model = PlaceGlb("Art/Vehicles/Stagecoach.gltf", "Stagecoach Model", Vector3.zero, 0, false);
            model.transform.SetParent(root.transform, false);
            foreach (var r in model.GetComponentsInChildren<MeshRenderer>()) r.receiveGI = ReceiveGI.LightProbes;
            var coach = root.AddComponent<Coach>();

            // 车身一个大碰撞盒（不用网格碰撞：会动）+ 交互
            var b = WorldBounds(model);
            var col = root.AddComponent<BoxCollider>();
            col.center = b.center; col.size = new Vector3(b.size.x * 0.9f, b.size.y, b.size.z * 0.9f);
            var body = Find(model, "Body");
            if (body) InteractAround(body.gameObject, "coach", 0.05f);
            foreach (var it in UnityEngine.Object.FindObjectsByType<Interactable>(FindObjectsSortMode.None).Where(x => x.id == "coach"))
                it.transform.SetParent(root.transform, true);

            // 两匹马站在 Hitch_L / Hitch_R
            var horses = new System.Collections.Generic.List<HorseRig>();
            foreach (var (hitch, file) in new[] { ("Hitch_L", "Horse"), ("Hitch_R", HorseBExists ? "Horse_B" : "Horse") })
            {
                var h = Find(model, hitch);
                var horse = PlaceGlb($"Art/Characters/{file}.gltf", "Horse " + hitch, Vector3.zero, 0, false);
                horse.transform.SetParent(root.transform, false);
                if (h) horse.transform.SetPositionAndRotation(h.position, h.rotation);
                foreach (var r in horse.GetComponentsInChildren<MeshRenderer>()) r.receiveGI = ReceiveGI.LightProbes;
                horses.Add(horse.AddComponent<HorseRig>());
                var hb = WorldBounds(horse);
                var hc = horse.AddComponent<BoxCollider>();
                hc.center = horse.transform.InverseTransformPoint(hb.center); hc.size = new Vector3(0.7f, hb.size.y, hb.size.z * 0.9f);
                var trig = new GameObject("Interact horse");
                trig.transform.SetParent(horse.transform, false);
                var tb = trig.AddComponent<BoxCollider>(); tb.isTrigger = true; tb.center = hc.center; tb.size = hc.size + Vector3.one * 0.2f;
                trig.AddComponent<Interactable>().id = "horse";
            }
            coach.horses = horses.ToArray();

            // 车夫坐在驾座上
            var seat = Find(model, "DriverSeat");
            driver = MakeNpc("Driver", "driver", "name.driver", 12f);
            // DriverSeat 在 Body 下面：车夫跟着车厢晃。它的位置是"髋部保持静止高度时脚落在踏板上"的根节点位置
            driver.transform.SetParent(seat ? seat : root.transform, false);
            driver.transform.localPosition = Vector3.zero; driver.transform.localRotation = Quaternion.identity;
            driver.rig.pose = MannequinRig.Pose.Drive;
            UnityEngine.Object.DestroyImmediate(driver.GetComponent<CapsuleCollider>());
            var dc = driver.gameObject.AddComponent<BoxCollider>(); dc.isTrigger = true; dc.center = new Vector3(0, 0.6f, 0); dc.size = new Vector3(0.6f, 1.2f, 0.6f);
            var dn = driver.GetComponent<Npc>(); dn.enabled = false;   // 车夫不走路、不转身：跟着马车

            // 声音：车轮 + 马蹄（第 1 稿看不见马车时也照样响）
            coach.roll = Loop3D(root.transform, "Coach Roll", Clip("coach_roll_loop"), new Vector3(0, 0.8f, 0));
            coach.hooves = Loop3D(root.transform, "Coach Hooves", Clip("hooves_walk_loop"), new Vector3(0, 0.9f, 3.5f));
            coach.stopClip = Clip("coach_stop");
            coach.snorts = new[] { Clip("horse_snort_01"), Clip("horse_snort_02") };
            coach.doorOpenEuler = CoachDoorOpen;
            return coach;
        }

        /// <summary>Door_L 打开的局部欧拉角，按 build_coach.py 的报告。</summary>
        static readonly Vector3 CoachDoorOpen = new(0, -80, 0);   // docs/horse_rig.md：Door_L 绕局部 Y 负向打开

        static bool HorseBExists => AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/Art/Characters/Horse_B.gltf");

        static AudioSource Loop3D(Transform parent, string name, AudioClip clip, Vector3 local)
        {
            var s = new GameObject(name).AddComponent<AudioSource>();
            s.transform.SetParent(parent, false);
            s.transform.localPosition = local;
            s.clip = clip; s.loop = true; s.playOnAwake = false; s.volume = 0f;
            s.spatialBlend = 1f; s.minDistance = 3f; s.maxDistance = 60f; s.rolloffMode = AudioRolloffMode.Logarithmic; s.dopplerLevel = 0f;
            return s;
        }

        static Npc MakeTownsfolk(string file, string name, Vector3 pos, float yaw, MannequinRig.Pose pose)
        {
            var npc = MakeNpc(file, "townsfolk", "name.townsfolk", 14f);
            npc.name = name;
            npc.transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
            npc.rig.pose = pose;
            npc.gameObject.AddComponent<Townsfolk>();
            foreach (var r in npc.GetComponentsInChildren<MeshRenderer>()) r.receiveGI = ReceiveGI.LightProbes;
            return npc;
        }
    }
}
