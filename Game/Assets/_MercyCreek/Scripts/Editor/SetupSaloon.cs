using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// 从 Blender 导出的 Saloon.glb 生成可玩场景 Saloon.unity：碰撞、灯光、光柱、后期、玩家、交互点、循环导演。
    /// 可重复执行（整份场景重建）。坐标约定：导入后根节点转 180°，于是 Unity (x, y, z) = Blender (x, z, y)。
    ///
    /// Unity -batchmode -projectPath Game -executeMethod MercyCreek.EditorTools.SetupSaloon.Run
    /// </summary>
    public static partial class SetupSaloon
    {
        const string Root = "Assets/_MercyCreek";
        const string ScenePath = Root + "/Scenes/Saloon.unity";

        public static void Run()
        {
            try { Build(); EditorApplication.Exit(0); }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        }

        [MenuItem("Mercy Creek/Rebuild Saloon Scene")]
        public static void Build()
        {
            SetupPipeline();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // ---------- 场景几何 ----------
            var glb = AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/Art/Saloon/Saloon.gltf")
                      ?? throw new Exception("Saloon.gltf not imported");
            var saloon = (GameObject)PrefabUtility.InstantiatePrefab(glb);
            saloon.name = "Saloon";
            saloon.transform.rotation = Quaternion.Euler(0, 180, 0);
            foreach (var mf in saloon.GetComponentsInChildren<MeshFilter>())
            {
                var mc = mf.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
                GameObjectUtility.SetStaticEditorFlags(mf.gameObject,
                    StaticEditorFlags.ContributeGI | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic | StaticEditorFlags.ReflectionProbeStatic | StaticEditorFlags.BatchingStatic);
                // 间接光只走 APV，不烘光照贴图：太阳会动，光照贴图里的固定阳光是错的
                mf.GetComponent<MeshRenderer>().receiveGI = ReceiveGI.LightProbes;
            }
            // 玻璃不挡阳光（窗玻璃、酒瓶、灯罩）
            // 薄墙（0.2 m）单面投影会被法线偏移"穿透"，墙根、梁下出现亮线：一律双面投影
            foreach (var r in saloon.GetComponentsInChildren<MeshRenderer>())
                r.shadowCastingMode = r.sharedMaterials.Any(m => m && m.name.ToLower().Contains("glass"))
                    ? ShadowCastingMode.Off : ShadowCastingMode.TwoSided;
            LogBounds(saloon, "BarTop", "Floor", "Ceiling");   // 校验坐标约定

            // ---------- 光 ----------
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 0.92f;
            sun.shadowBias = 0.05f; sun.shadowNormalBias = 0.08f;
            sun.transform.rotation = Quaternion.Euler(26, 18, 0);
            sun.color = new Color(1f, 0.86f, 0.68f); sun.intensity = 3.2f;
            sun.lightmapBakeType = LightmapBakeType.Mixed;   // 直接光实时，间接光烘进 APV

            var lamps = new List<Light>();
            foreach (var t in saloon.GetComponentsInChildren<Transform>().Where(t => t.name.ToLower().Contains("lantern") && t.name.EndsWith("_root")))
            {
                var b = WorldBounds(t.gameObject);
                lamps.Add(PointLight($"Lamp ({t.name})", b.center + Vector3.up * 0.05f, 6f, new Color(1f, 0.66f, 0.36f), true));
            }
            lamps.Add(PointLight("Lamp (bar)", new Vector3(-5.6f, 2.5f, 5.4f), 8f, new Color(1f, 0.64f, 0.34f), true));
            // 后墙壁灯：把墙纸照出来，也是黄昏时大厅的主要光源
            foreach (var x in new[] { -3.4f, 0.6f, 4.6f })
                lamps.Add(PointLight($"Sconce ({x})", new Vector3(x, 2.25f, 9.7f), 4.5f, new Color(1f, 0.62f, 0.33f), false));
            lamps.Add(PointLight("Lamp (balcony)", new Vector3(-2.5f, 5.3f, 8.8f), 7f, new Color(1f, 0.6f, 0.32f), false));
            // 模拟墙面反弹的暖色补光（无阴影）
            var fill = PointLight("Bounce Fill", new Vector3(0f, 2.6f, 4.5f), 14f, new Color(0.95f, 0.72f, 0.52f), false);
            fill.intensity = 0.15f;                          // APV 之后只留一点点，避免死角全黑
            fill.lightmapBakeType = LightmapBakeType.Realtime;

            RenderSettings.sun = sun;
            RenderSettings.ambientMode = AmbientMode.Skybox;   // 天光从窗户进来，由 APV 烘焙
            RenderSettings.ambientIntensity = 0.7f;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = 0.007f;   // 街道上要看得到 60 m 外的画布和教堂
            RenderSettings.fogColor = new Color(0.36f, 0.28f, 0.2f);
            RenderSettings.skybox = SkyboxMaterial();

            // 探针盒必须完整包住房间：盒外的表面会退回去反射明亮的天空盒，墙和天花板发灰发亮
            var probe = ReflectionProbeAt("Reflection Probe", new Vector3(0, 2.2f, 5f), new Vector3(0, 3.2f, 5f), new Vector3(14.4f, 6.8f, 10.4f));
            var probe4 = ReflectionProbeAt("Reflection Probe Room 4", new Vector3(0, 4.6f, 11.7f), new Vector3(0, 4.7f, 11.7f), new Vector3(4.2f, 3.2f, 3.2f));
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
            RenderSettings.reflectionIntensity = 0.5f;   // 只影响室外

            // ---------- 光柱 ----------
            var shaftMat = ShaftMaterial();
            var shafts = new GameObject("Light Shafts").transform;
            Shaft(shafts, shaftMat, sun, "Front L", new Vector3(-4f, 1.85f, 0.02f), Vector3.forward, new Vector2(2.8f, 1.9f), 9f);
            Shaft(shafts, shaftMat, sun, "Front R", new Vector3(4f, 1.85f, 0.02f), Vector3.forward, new Vector2(2.8f, 1.9f), 9f);
            Shaft(shafts, shaftMat, sun, "Front L Upper", new Vector3(-4f, 4.8f, 0.02f), Vector3.forward, new Vector2(2.0f, 1.6f), 11f);
            Shaft(shafts, shaftMat, sun, "Front R Upper", new Vector3(4f, 4.8f, 0.02f), Vector3.forward, new Vector2(2.0f, 1.6f), 11f);
            Shaft(shafts, shaftMat, sun, "Right Lower", new Vector3(6.98f, 1.75f, 3.8f), Vector3.left, new Vector2(1.6f, 1.7f), 8f);
            Shaft(shafts, shaftMat, sun, "Right Upper", new Vector3(6.98f, 4.7f, 6.4f), Vector3.left, new Vector2(1.6f, 1.4f), 9f);
            Shaft(shafts, shaftMat, sun, "Left", new Vector3(-6.98f, 1.9f, 1.9f), Vector3.right, new Vector2(1.4f, 1.4f), 8f);

            // ---------- 浮尘 ----------
            Dust(new Vector3(0, 2.2f, 4.5f), new Vector3(12f, 4f, 8.5f));

            // ---------- 后期 ----------
            var grade = new GameObject("Grade Volume").AddComponent<Volume>();
            grade.isGlobal = true; grade.priority = 0;
            grade.sharedProfile = GradeProfile();
            var reset = new GameObject("Reset Volume").AddComponent<Volume>();
            reset.isGlobal = true; reset.priority = 10; reset.weight = 0;
            reset.sharedProfile = ResetProfile();

            // ---------- HUD / 玩家 ----------
            var uiFont = AssetDatabase.LoadAssetAtPath<Font>(Root + "/Resources/Fonts/MercySerif-Regular.otf")
                         ?? throw new Exception("missing font（先跑 .venv/bin/python tools/fonts/make_font.py）");
            var hud = new GameObject("HUD").AddComponent<Hud>();
            hud.font = uiFont;

            var player = new GameObject("Player");
            player.transform.SetPositionAndRotation(new Vector3(-5.85f, 0.05f, 4.6f), Quaternion.Euler(0, 75, 0));
            var cc = player.AddComponent<CharacterController>();
            cc.height = 1.7f; cc.radius = 0.28f; cc.center = new Vector3(0, 0.85f, 0); cc.stepOffset = 0.35f; cc.slopeLimit = 50;
            var head = new GameObject("Head").transform;
            head.SetParent(player.transform, false);
            head.localPosition = new Vector3(0, 1.58f, 0);
            var cam = head.gameObject.AddComponent<Camera>();
            cam.tag = "MainCamera";
            cam.nearClipPlane = 0.05f; cam.farClipPlane = 200f; cam.fieldOfView = 68f;
            var camData = cam.GetUniversalAdditionalCameraData();
            camData.renderPostProcessing = true;
            camData.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            head.gameObject.AddComponent<AudioListener>();
            var fps = player.AddComponent<FirstPersonController>();
            fps.head = head;
            var interactor = player.AddComponent<PlayerInteractor>();
            interactor.cam = cam; interactor.hud = hud;

            // ---------- 声音 ----------
            SetupAudio(saloon);

            // ---------- 循环 ----------
            var loop = new GameObject("Loop Director").AddComponent<LoopDirector>();
            loop.sun = sun; loop.lamps = lamps.ToArray(); loop.resetVolume = reset; loop.hud = hud;

            // ---------- 外景、钢琴、道具、人偶、剧情 ----------
            var street = PlaceGlb("Art/Street/StreetBackdrop.gltf", "Street Backdrop", Vector3.zero, 180, false);
            foreach (var r in street.GetComponentsInChildren<MeshRenderer>())
            {
                r.receiveGI = ReceiveGI.LightProbes;
                // 第 2 稿起能走上街：路面、栈道、房子都要碰撞；远山不用
                if (!r.name.StartsWith("Hills")) r.gameObject.AddComponent<MeshCollider>().sharedMesh = r.GetComponent<MeshFilter>().sharedMesh;
            }
            // 街上的大反射探针（室外）
            // 盒子不能伸进酒馆 / 电报局（室内会反射到街景，发灰发亮）：z 只到北侧门脸 -0.3
            ReflectionProbeAt("Reflection Probe Street", new Vector3(0, 2.0f, -7.3f), new Vector3(0, 6f, -7.5f), new Vector3(80f, 16f, 14.4f)).intensity = 0.8f;

            var piano = PlaceGlb("Art/Props/PlayerPiano.gltf", "Player Piano", new Vector3(3.2f, 0, 9.65f), 180, true);
            var stool = Find(piano, "PianoStool");
            var stoolBounds = WorldBounds(stool.gameObject);

            var story = new GameObject("Story").AddComponent<Story>();
            story.director = loop; story.hud = hud; story.player = player.transform;
            story.profSeat = new Vector3(stoolBounds.center.x, 0, stoolBounds.center.z + 0.06f);
            story.clock = Find(saloon, "vintage_grandfather_clock_01_root");

            story.gus = MakeNpc("Gus", "npc.gus", "name.gus", 13f);
            story.prof = MakeNpc("Professor", "npc.prof", "name.prof", 15f);
            story.prof.rig.seatHeight = stoolBounds.max.y;
            story.crane = MakeNpc("Crane", "npc.crane", "name.crane", 24f);
            story.crane.rig.seatHeight = 0.46f;
            story.crane.walkSpeed = 1.15f;

            // 物件碎片
            Interact(saloon, "vintage_grandfather_clock_01_root", "clock");
            Interact(saloon, "ornate_mirror_01_root", "mirror");
            Interact(saloon, "dartboard_root", "dartboard");
            Interact(saloon, "wine_bottles_01_root", "bottles");
            float barTop = WorldBounds(Find(saloon, "BarTop").gameObject).max.y;
            var glass = PlaceGlb("Art/Props/WhiskeyGlass.gltf", "Chipped Glass", new Vector3(-4.8f, barTop, 4.35f), 0, false);
            InteractBox(glass, "glass", 0.12f);
            var calendar = PlaceGlb("Art/Props/Calendar.gltf", "Calendar", new Vector3(-5.5f, 1.4f, 0.02f), 0, false);
            InteractBox(calendar, "calendar", 0.08f);
            float backBarTop = WorldBounds(Find(saloon, "BackBarTop").gameObject).max.y;
            story.letter = PlaceGlb("Art/Props/Letter.gltf", "Letter", new Vector3(-6.62f, backBarTop, 4.1f), 75, false);
            var drawer = new GameObject("Interact Drawer");
            drawer.transform.position = new Vector3(-6.62f, 0.72f, 4.1f);
            var dbox = drawer.AddComponent<BoxCollider>(); dbox.isTrigger = true; dbox.size = new Vector3(0.7f, 0.55f, 0.9f);
            drawer.AddComponent<Interactable>().id = "letter";

            // 陌生人的窗边桌（build_saloon.py 里 round_wooden_table_02 在 (-3.0, 1.9)）
            var craneTable = saloon.GetComponentsInChildren<Transform>()
                .Where(t => t.name.StartsWith("round_wooden_table_02") && t.name.EndsWith("_root"))
                .OrderBy(t => Vector3.Distance(t.position, new Vector3(-3f, 0, 1.9f))).First();
            float tableTop = WorldBounds(craneTable.gameObject).max.y;
            story.notebook = PlaceGlb("Art/Props/Notebook.gltf", "Crane Notebook", new Vector3(-3.0f, tableTop, 1.58f), 180, false);
            InteractBox(story.notebook, "notebook", 0.1f);

            // 前门：第 1 稿挡住，只能看（"街像画在布上"）；第 2 稿起由 Story 关掉
            var door = new GameObject("Front Door");
            door.transform.position = new Vector3(0, 1.35f, 0.1f);
            door.AddComponent<BoxCollider>().size = new Vector3(1.8f, 2.7f, 0.3f);
            door.AddComponent<Interactable>().id = "door";
            story.frontDoorBlock = door;

            // 二楼 4 号房 + 后门：可开的门
            var doorMat = FindMaterial(saloon, "BarBody");
            story.room4Door = MakeDoor("Room 4 Door", new Vector3(-0.6f, 3.2f, 10.1f), 1.2f, 2.3f, doorMat, "room4");
            story.backDoor = MakeDoor("Back Door", new Vector3(5.6f, 0f, 10.1f), 1.0f, 2.3f, doorMat, "backdoor");

            // 4 号房：书桌 + 自己在打字的打字机
            var desk = PlaceGlb("Art/Props/Desk.gltf", "Room 4 Desk", new Vector3(0.3f, 3.2f, 12.6f), 180, true);
            var deskTop = WorldBounds(Find(desk, "Desk").gameObject);
            var typewriter = PlaceGlb("Art/Props/Typewriter.gltf", "Typewriter", new Vector3(deskTop.center.x, deskTop.max.y, deskTop.center.z + 0.05f), 180, false);
            story.typewriterPaper = Find(typewriter, "Paper") ?? typewriter.transform;
            InteractBox(typewriter, "typewriter", 0.25f);
            PointLight("Room 4 Lamp", new Vector3(0.6f, 4.6f, 12.2f), 4f, new Color(1f, 0.7f, 0.42f), true).intensity = 1.2f;

            // 乐谱：教授圈出的错音
            var sheet = new GameObject("Interact sheet");
            sheet.transform.position = new Vector3(3.2f, 1.45f, 9.55f);
            var sbox = sheet.AddComponent<BoxCollider>(); sbox.isTrigger = true; sbox.size = new Vector3(0.7f, 0.35f, 0.25f);
            sheet.AddComponent<Interactable>().id = "sheet";

            // 主街、电报局、教堂墓地、画布与虚空、马车、镇民（SetupTown.cs）
            BuildTown(story, hud);

            // ---------- 评审机位 ----------
            var shots = new GameObject("Review Viewpoints").transform;
            var autoShot = shots.gameObject.AddComponent<AutoShot>();
            autoShot.loopTimes = new[] { 8f, 75f, 200f };
            shots.gameObject.AddComponent<AutoTest>();
            shots.gameObject.AddComponent<Trailer>();
            autoShot.viewpoints = new[]
            {
                Viewpoint(shots, "entrance", new Vector3(0.3f, 1.65f, 0.6f), new Vector3(0.5f, 1.6f, 8f)),
                Viewpoint(shots, "balcony", new Vector3(5.6f, 4.8f, 8.4f), new Vector3(-2f, 0.6f, 3f)),
                Viewpoint(shots, "bar", new Vector3(-2.7f, 1.45f, 2.2f), new Vector3(-6.7f, 1.3f, 6.5f)),
                Viewpoint(shots, "shafts", new Vector3(4.3f, 1.7f, 8.0f), new Vector3(-2.5f, 0.6f, 1.5f)),
                Viewpoint(shots, "corner", new Vector3(-2.2f, 1.45f, 3.6f), new Vector3(-3.0f, 0.95f, 1.2f)),
                Viewpoint(shots, "piano", new Vector3(1.4f, 1.55f, 7.0f), new Vector3(3.2f, 1.0f, 9.4f)),
                Viewpoint(shots, "street_west", new Vector3(3.0f, 1.65f, -4.0f), new Vector3(-30f, 2.2f, -7.3f)),
                Viewpoint(shots, "street_east", new Vector3(-4.0f, 1.65f, -6.0f), new Vector3(30f, 4.5f, -7.3f)),
                Viewpoint(shots, "saloon_front", new Vector3(-3.5f, 1.7f, -11.5f), new Vector3(0.5f, 3.2f, 0f)),
                Viewpoint(shots, "coach", new Vector3(5.5f, 1.6f, -9.5f), new Vector3(0f, 1.2f, -5.4f)),
                Viewpoint(shots, "telegraph", new Vector3(-10.0f, 1.6f, 0.8f), new Vector3(-13.5f, 1.0f, 5.5f)),
                Viewpoint(shots, "graveyard", new Vector3(28.0f, 1.65f, 0.5f), new Vector3(32f, 0.8f, 5f)),
                Viewpoint(shots, "canvas", new Vector3(-26.0f, 1.65f, -6.5f), new Vector3(-34f, 2.4f, -7.3f)),
            };

            // 探针只放在室内（墙内侧），否则墙外被天光照亮的探针会沿墙根漏光
            ProbeVolumeAt("APV Hall", new Vector3(0, 3.2f, 5f), new Vector3(13.9f, 6.35f, 9.9f));
            ProbeVolumeAt("APV Room 4", new Vector3(0, 4.7f, 11.7f), new Vector3(3.9f, 2.9f, 2.9f));

            // ---------- 菜单（标题画面镜头、分享卡片底图机位） ----------
            var menus = new GameObject("Menus").AddComponent<Menus>();
            menus.font = uiFont;
            var cams = new GameObject("Menu Cameras").transform;
            menus.titleCameraFrom = Viewpoint(cams, "Title From", new Vector3(-0.6f, 1.7f, 0.9f), new Vector3(0.8f, 1.6f, 9f));
            menus.titleCameraTo = Viewpoint(cams, "Title To", new Vector3(0.4f, 2.2f, 3.8f), new Vector3(0.8f, 1.6f, 9f));
            menus.titleLookAt = Viewpoint(cams, "Title Look", new Vector3(0.8f, 1.5f, 9f), new Vector3(0.8f, 1.5f, 10f));
            menus.shareViewpoint = Viewpoint(cams, "Share Card", new Vector3(5.2f, 4.7f, 2.4f), new Vector3(-2.2f, 1.0f, 6.5f));

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            if (!Application.isBatchMode || !Environment.GetCommandLineArgs().Contains("-nobake"))
                BakeGI(scene, loop);
            Lightmapping.BakeReflectionProbe(probe, Root + "/Scenes/Saloon/ReflectionProbe.exr");
            Lightmapping.BakeReflectionProbe(probe4, Root + "/Scenes/Saloon/ReflectionProbeRoom4.exr");
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            Debug.Log("[SetupSaloon] done: " + ScenePath);
        }

        // ================= 声音 =================

        static AudioClip Clip(string name) =>
            AssetDatabase.LoadAssetAtPath<AudioClip>($"{Root}/Audio/{name}.wav") ?? throw new Exception("missing audio " + name + "（先跑 tools/build_audio.sh）");

        static void SetupAudio(GameObject saloon)
        {
            var sfx = new GameObject("Audio").AddComponent<Sfx>();
            sfx.ambience = Clip("amb_saloon_loop"); sfx.wind = Clip("amb_wind_loop"); sfx.voidHum = Clip("void_hum_loop");
            sfx.resetSting = Clip("reset_sting"); sfx.endingTheme = Clip("ending_theme");
            sfx.remember = Clip("ui_remember"); sfx.denied = Clip("ui_denied"); sfx.click = Clip("ui_click");
            sfx.tick = Clip("clock_tick"); sfx.tock = Clip("clock_tock");
            sfx.doorOpen = Clip("door_open"); sfx.doorClose = Clip("door_close");
            sfx.glassClink = Clip("glass_clink"); sfx.glassPour = Clip("glass_pour"); sfx.bottleSet = Clip("bottle_set");
            sfx.typeBell = Clip("typewriter_bell"); sfx.typeReturn = Clip("typewriter_return");
            sfx.steps = Enumerable.Range(1, 6).Select(i => Clip($"step_wood_{i:00}")).ToArray();
            sfx.typeKeys = Enumerable.Range(1, 4).Select(i => Clip($"typewriter_key_{i:00}")).ToArray();
            sfx.waltz = new[] { "correct", "C", "A", "G", "E" }.Select(v => Clip("piano_waltz_" + v)).ToArray();
            sfx.streetAmbience = Clip("amb_street_loop");
            sfx.stepsDirt = Enumerable.Range(1, 6).Select(i => Clip($"step_dirt_{i:00}")).ToArray();
            sfx.stepsBoardwalk = Enumerable.Range(1, 6).Select(i => Clip($"step_boardwalk_{i:00}")).ToArray();

            sfx.piano = Source3D(sfx.transform, "Piano", new Vector3(3.2f, 1.0f, 9.5f), 3f, 30f);
            sfx.clock = Source3D(sfx.transform, "Clock", new Vector3(-1.6f, 1.6f, 9.6f), 1f, 12f);
            sfx.windows = new[]
            {
                Source3D(sfx.transform, "Wind Front L", new Vector3(-4f, 1.8f, 0.1f), 1.5f, 10f),
                Source3D(sfx.transform, "Wind Front R", new Vector3(4f, 1.8f, 0.1f), 1.5f, 10f),
                Source3D(sfx.transform, "Wind Door", new Vector3(0f, 1.4f, 0.1f), 1.5f, 10f),
            };
            foreach (var c in sfx.waltz.Concat(new[] { sfx.ambience, sfx.wind, sfx.voidHum, sfx.endingTheme, sfx.streetAmbience }))
                StreamClip(c);
        }

        static AudioSource Source3D(Transform parent, string name, Vector3 pos, float min, float max)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.position = pos;
            var s = go.AddComponent<AudioSource>();
            s.spatialBlend = 1f; s.minDistance = min; s.maxDistance = max; s.rolloffMode = AudioRolloffMode.Logarithmic;
            s.playOnAwake = false; s.dopplerLevel = 0f;
            return s;
        }

        /// <summary>长音频走流式 + Vorbis，避免构建体积和内存爆炸。</summary>
        static void StreamClip(AudioClip c)
        {
            var imp = (AudioImporter)AssetImporter.GetAtPath(AssetDatabase.GetAssetPath(c));
            var s = imp.defaultSampleSettings;
            if (s.loadType == AudioClipLoadType.Streaming && s.compressionFormat == AudioCompressionFormat.Vorbis) return;
            s.loadType = AudioClipLoadType.Streaming; s.compressionFormat = AudioCompressionFormat.Vorbis; s.quality = 0.6f;
            imp.defaultSampleSettings = s;
            imp.SaveAndReimport();
        }

        // ================= GI =================

        /// <summary>
        /// 烘两个 APV 光照情景：午后（循环开始）和黄昏（循环结束）。运行时 LoopDirector 按进度在两者之间混合。
        /// </summary>
        static void BakeGI(UnityEngine.SceneManagement.Scene scene, LoopDirector loop)
        {
            var ls = new LightingSettings
            {
                name = "Saloon Lighting",
                bakedGI = true, realtimeGI = false,
                mixedBakeMode = MixedLightingMode.IndirectOnly,
                lightmapper = LightingSettings.Lightmapper.ProgressiveGPU,
                directSampleCount = 32, indirectSampleCount = 512, environmentSampleCount = 256,
                maxBounces = 4, lightmapResolution = 10,
            };
            const string lsPath = Root + "/Settings/SaloonLighting.lighting";
            AssetDatabase.DeleteAsset(lsPath);
            AssetDatabase.CreateAsset(ls, lsPath);
            Lightmapping.lightingSettings = ls;

            const string setPath = Root + "/Settings/Saloon Baking Set.asset";
            var set = AssetDatabase.LoadAssetAtPath<ProbeVolumeBakingSet>(setPath);
            if (!set)
            {
                set = ScriptableObject.CreateInstance<ProbeVolumeBakingSet>();
                set.name = "Saloon Baking Set";
                typeof(ProbeVolumeBakingSet).GetMethod("SetDefaults", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)?.Invoke(set, null);
                AssetDatabase.CreateAsset(set, setPath);
            }
            set.TryAddScene(AssetDatabase.AssetPathToGUID(ScenePath));
            set.minDistanceBetweenProbes = 0.5f;
            set.simplificationLevels = 2;
            foreach (var s in Scenarios) set.TryAddScenario(s.name);
            EditorUtility.SetDirty(set);
            AssetDatabase.SaveAssets();
            ProbeReferenceVolume.instance.SetActiveBakingSet(set);

            foreach (var (name, k) in Scenarios)
            {
                loop.ApplyTime(k);
                // 场景刚新建时 ProbeReferenceVolume 可能还没挂上这个 baking set，直接设到 set 上
                typeof(ProbeVolumeBakingSet).GetMethod("SetActiveScenario", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                    ?.Invoke(set, new object[] { name, true });
                ProbeReferenceVolume.instance.lightingScenario = name;
                var t0 = DateTime.Now;
                bool ok = Lightmapping.Bake();
                Debug.Log($"[SetupSaloon] bake {name}: {(ok ? "ok" : "FAILED")} in {(DateTime.Now - t0).TotalSeconds:F0}s");
            }
            loop.ApplyTime(0f);
            ProbeReferenceVolume.instance.lightingScenario = Scenarios[0].name;
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
        }

        public static readonly (string name, float k)[] Scenarios = { ("Afternoon", 0f), ("Dusk", 1f) };

        // ================= helpers =================

        static void SetupPipeline()
        {
            var rp = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(Root + "/Settings/PC_RPAsset.asset");
            // APV 的开关在 URP 资产里是 internal setter，走序列化字段
            var so = new SerializedObject(rp);
            so.FindProperty("m_LightProbeSystem").intValue = (int)LightProbeSystem.ProbeVolumes;
            so.FindProperty("m_SupportProbeVolumeScenarios").boolValue = true;
            so.FindProperty("m_SupportProbeVolumeScenarioBlending").boolValue = true;
            so.FindProperty("m_ProbeVolumeSHBands").intValue = (int)ProbeVolumeSHBands.SphericalHarmonicsL2;
            so.ApplyModifiedPropertiesWithoutUndo();
            GraphicsSettings.defaultRenderPipeline = rp;
            int keep = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = rp;
            }
            QualitySettings.SetQualityLevel(QualitySettings.names.Length - 1, true);
            var rso = new SerializedObject(rp);
            rso.FindProperty("m_ShadowDistance").floatValue = 70f;   // 街道纵深 70 m
            rso.ApplyModifiedPropertiesWithoutUndo();
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;   // 评审截图时窗口不在前台
        }

        static ReflectionProbe ReflectionProbeAt(string name, Vector3 capture, Vector3 boxCentre, Vector3 size)
        {
            var p = new GameObject(name).AddComponent<ReflectionProbe>();
            p.transform.position = capture;
            p.center = boxCentre - capture;
            p.size = size;
            p.boxProjection = true;
            p.mode = ReflectionProbeMode.Baked;
            p.resolution = 256;
            p.intensity = 0.55f;
            return p;
        }

        static void ProbeVolumeAt(string name, Vector3 centre, Vector3 size)
        {
            var pv = new GameObject(name).AddComponent<ProbeVolume>();
            pv.mode = ProbeVolume.Mode.Local;
            pv.transform.position = centre;
            pv.size = size;
        }

        static Light PointLight(string name, Vector3 pos, float range, Color color, bool shadows)
        {
            var l = new GameObject(name).AddComponent<Light>();
            l.type = LightType.Point; l.transform.position = pos; l.range = range; l.color = color; l.intensity = 1f;
            l.shadows = shadows ? LightShadows.Soft : LightShadows.None;
            l.lightmapBakeType = LightmapBakeType.Mixed;
            return l;
        }

        static void Shaft(Transform parent, Material mat, Light sun, string name, Vector3 pos, Vector3 inward, Vector2 size, float length)
        {
            var go = new GameObject("Shaft " + name, typeof(MeshFilter), typeof(MeshRenderer), typeof(LightShaft));
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(inward, Vector3.up));
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            var s = go.GetComponent<LightShaft>();
            s.sun = sun; s.size = size; s.length = length;
        }

        static Material ShaftMaterial()
        {
            const string path = Root + "/Materials/LightShaft.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m) return m;
            m = new Material(Shader.Find("MercyCreek/LightShaft"));
            AssetDatabase.CreateAsset(m, path);
            return m;
        }

        static Material SkyboxMaterial()
        {
            const string path = Root + "/Materials/Sky_Goegap.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!m)
            {
                m = new Material(Shader.Find("Skybox/Panoramic"));
                AssetDatabase.CreateAsset(m, path);
            }
            m.SetTexture("_MainTex", AssetDatabase.LoadAssetAtPath<Texture>(Root + "/Art/HDRI/goegap_road_2k.exr"));
            m.SetFloat("_Exposure", 1.1f);
            m.SetFloat("_Rotation", 140f);
            return m;
        }

        static void Dust(Vector3 centre, Vector3 size)
        {
            var go = new GameObject("Dust Motes");
            go.transform.position = centre;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.loop = true; main.prewarm = true;
            main.startLifetime = 14f; main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.008f, 0.02f);
            main.startColor = new Color(1f, 0.9f, 0.75f, 0.5f);
            main.maxParticles = 1500;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission; em.rateOverTime = 100f;
            var shape = ps.shape; shape.shapeType = ParticleSystemShapeType.Box; shape.scale = size;
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.06f; noise.frequency = 0.25f; noise.scrollSpeed = 0.05f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
                      new[] { new GradientAlphaKey(0, 0), new GradientAlphaKey(1, 0.2f), new GradientAlphaKey(1, 0.8f), new GradientAlphaKey(0, 1) });
            col.color = g;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Particle.mat");
            var lit = Shader.Find("Universal Render Pipeline/Particles/Simple Lit");
            if (lit)
            {
                const string path = Root + "/Materials/Dust.mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (!m) { m = new Material(lit); AssetDatabase.CreateAsset(m, path); }
                m.SetFloat("_Surface", 1); m.SetFloat("_Blend", 0);
                m.SetColor("_BaseColor", new Color(1, 0.95f, 0.85f, 0.6f));
                m.SetTexture("_BaseMap", AssetDatabase.GetBuiltinExtraResource<Texture2D>("Default-Particle.psd"));
                m.renderQueue = 3000;
                m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                m.SetOverrideTag("RenderType", "Transparent");
                m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha); m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha); m.SetFloat("_ZWrite", 0);
                r.sharedMaterial = m;
            }
        }

        static VolumeProfile GradeProfile()
        {
            var p = NewProfile("Grade");
            var tone = Add<Tonemapping>(p); tone.mode.Override(TonemappingMode.ACES);
            var ca = Add<ColorAdjustments>(p);
            ca.postExposure.Override(1.1f); ca.contrast.Override(14f); ca.saturation.Override(-10f);
            ca.colorFilter.Override(new Color(1f, 0.97f, 0.92f));
            var wb = Add<WhiteBalance>(p); wb.temperature.Override(8f);
            var smh = Add<ShadowsMidtonesHighlights>(p);
            smh.shadows.Override(new Vector4(0.97f, 1f, 1.03f, 0f));
            smh.highlights.Override(new Vector4(1.05f, 1f, 0.94f, 0f));
            var bloom = Add<Bloom>(p); bloom.threshold.Override(1.0f); bloom.intensity.Override(0.5f); bloom.scatter.Override(0.65f);
            var vig = Add<Vignette>(p); vig.intensity.Override(0.3f); vig.smoothness.Override(0.45f);
            var grain = Add<FilmGrain>(p); grain.type.Override(FilmGrainLookup.Medium2); grain.intensity.Override(0.28f); grain.response.Override(0.7f);
            var chrom = Add<ChromaticAberration>(p); chrom.intensity.Override(0.06f);
            var apv = Add<ProbeVolumesOptions>(p);
            apv.leakReductionMode.Override(APVLeakReductionMode.Quality);
            apv.normalBias.Override(0.2f); apv.viewBias.Override(0.25f);
            apv.samplingNoise.Override(0.05f);
            Save(p);
            return p;
        }

        static VolumeProfile ResetProfile()
        {
            var p = NewProfile("Reset");
            var ca = Add<ColorAdjustments>(p);
            ca.saturation.Override(-95f); ca.contrast.Override(25f); ca.postExposure.Override(-0.3f);
            ca.colorFilter.Override(new Color(0.72f, 0.92f, 1f));
            var chrom = Add<ChromaticAberration>(p); chrom.intensity.Override(1f);
            var lens = Add<LensDistortion>(p); lens.intensity.Override(-0.35f);
            Save(p);
            return p;
        }

        static VolumeProfile NewProfile(string name)
        {
            string path = $"{Root}/Settings/{name}Profile.asset";
            AssetDatabase.DeleteAsset(path);
            var p = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(p, path);
            return p;
        }

        static T Add<T>(VolumeProfile p) where T : VolumeComponent
        {
            var c = p.Add<T>(true);
            c.name = typeof(T).Name;
            AssetDatabase.AddObjectToAsset(c, p);
            return c;
        }

        static void Save(VolumeProfile p) { EditorUtility.SetDirty(p); AssetDatabase.SaveAssets(); }

        static Transform Viewpoint(Transform parent, string name, Vector3 pos, Vector3 target)
        {
            var t = new GameObject(name).transform;
            t.SetParent(parent, false);
            t.SetPositionAndRotation(pos, Quaternion.LookRotation(target - pos, Vector3.up));
            return t;
        }

        static void Interact(GameObject saloon, string objectName, string id)
        {
            var t = Find(saloon, objectName);
            if (!t) { Debug.LogWarning("[SetupSaloon] interactable target not found: " + objectName); return; }
            var b = WorldBounds(t.gameObject);
            var go = new GameObject("Interact " + id);
            go.transform.position = b.center;
            var box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.size = b.size + Vector3.one * 0.1f;
            go.AddComponent<Interactable>().id = id;
        }

        static void InteractBox(GameObject target, string id, float pad)
        {
            var b = WorldBounds(target);
            var box = target.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.center = target.transform.InverseTransformPoint(b.center);
            box.size = b.size + Vector3.one * pad;
            target.AddComponent<Interactable>().id = id;
        }

        static Transform Find(GameObject root, string name) =>
            root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == name);

        static GameObject PlaceGlb(string relPath, string name, Vector3 pos, float yaw, bool colliders)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>($"{Root}/{relPath}") ?? throw new Exception("missing " + relPath + "（先跑 tools/bootstrap.sh）");
            var go = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            go.name = name;
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                if (colliders) r.gameObject.AddComponent<MeshCollider>().sharedMesh = r.GetComponent<MeshFilter>().sharedMesh;
                if (r.sharedMaterials.Any(m => m && m.name.ToLower().Contains("glass"))) r.shadowCastingMode = ShadowCastingMode.Off;
            }
            return go;
        }

        static Npc MakeNpc(string file, string id, string nameKey, float stride)
        {
            var go = PlaceGlb($"Art/Characters/Mannequin_{file}.gltf", file, Vector3.zero, 0, false);
            var rig = go.AddComponent<MannequinRig>();
            rig.stride = stride;
            var npc = go.AddComponent<Npc>();
            npc.id = id; npc.nameKey = nameKey; npc.rig = rig;
            var cap = go.AddComponent<CapsuleCollider>();
            cap.center = new Vector3(0, 0.9f, 0); cap.height = 1.8f; cap.radius = 0.3f;
            go.AddComponent<Interactable>().id = id;
            return npc;
        }

        static SwingDoor MakeDoor(string name, Vector3 hinge, float width, float height, Material mat, string id)
        {
            var root = new GameObject(name);
            root.transform.position = hinge;
            var panel = GameObject.CreatePrimitive(PrimitiveType.Cube);
            panel.name = name + " Panel";
            panel.transform.SetParent(root.transform, false);
            panel.transform.localPosition = new Vector3(width / 2, height / 2, 0);
            panel.transform.localScale = new Vector3(width - 0.02f, height - 0.02f, 0.06f);
            if (mat) panel.GetComponent<MeshRenderer>().sharedMaterial = mat;
            panel.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.TwoSided;
            panel.AddComponent<Interactable>().id = id;
            var knob = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            knob.name = "Knob";
            UnityEngine.Object.DestroyImmediate(knob.GetComponent<Collider>());
            knob.transform.SetParent(root.transform, false);
            knob.transform.localPosition = new Vector3(width - 0.12f, 1.0f, -0.05f);
            knob.transform.localScale = Vector3.one * 0.06f;
            var brass = AssetDatabase.LoadAllAssetsAtPath($"{Root}/Art/Saloon/Saloon.gltf").OfType<Material>().FirstOrDefault(m => m.name == "Brass");
            if (brass) knob.GetComponent<MeshRenderer>().sharedMaterial = brass;
            var d = root.AddComponent<SwingDoor>();
            d.openAngle = -100f;
            return d;
        }

        /// <summary>出逃结局的"虚空"：画布后面（x &lt; canvasX）一个没有朝东那面的大盒子，铺满格子纸网格。</summary>
        static GameObject MakeVoid(float canvasX)
        {
            // 在"东西向"的局部坐标里搭（沿用原来朝 +Z 的盒子），最后整体转 -90°：局部 +Z → 世界 -X
            const float x0 = -26.4f, x1 = 27f, y0 = 0.01f, y1 = 13.8f, z0 = 0f, z1 = 60f;   // 宽、高都收在画布（y -34..20、高 14）后面
            Vector3[] v =
            {
                new Vector3(x0, y0, z0), new Vector3(x1, y0, z0), new Vector3(x1, y0, z1), new Vector3(x0, y0, z1),
                new Vector3(x0, y1, z0), new Vector3(x1, y1, z0), new Vector3(x1, y1, z1), new Vector3(x0, y1, z1),
            };
            var mesh = new Mesh { name = "Void Box" };
            var verts = new List<Vector3>(); var tris = new List<int>(); var normals = new List<Vector3>();
            void Quad(int a, int b, int c, int d, Vector3 n)
            {
                int i = verts.Count;
                verts.AddRange(new[] { v[a], v[b], v[c], v[d] }); normals.AddRange(new[] { n, n, n, n });
                tris.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
            }
            Quad(0, 1, 2, 3, Vector3.up); Quad(4, 7, 6, 5, Vector3.down);
            Quad(3, 2, 6, 7, Vector3.back); Quad(0, 3, 7, 4, Vector3.right); Quad(1, 5, 6, 2, Vector3.left);
            // 朝东（朝街）的那一面不封：画布挡着，只有撕开的口子看得进来
            mesh.SetVertices(verts); mesh.SetNormals(normals); mesh.SetTriangles(tris, 0); mesh.RecalculateBounds();
            const string meshPath = Root + "/Materials/VoidBox.asset";
            AssetDatabase.DeleteAsset(meshPath);
            AssetDatabase.CreateAsset(mesh, meshPath);

            var go = new GameObject("Void", typeof(MeshFilter), typeof(MeshRenderer));
            go.transform.SetPositionAndRotation(new Vector3(canvasX, 0, -7.3f), Quaternion.Euler(0, -90, 0));
            go.GetComponent<MeshFilter>().sharedMesh = mesh;
            const string matPath = Root + "/Materials/VoidGrid.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            if (!mat) { mat = new Material(Shader.Find("MercyCreek/VoidGrid")); AssetDatabase.CreateAsset(mat, matPath); }
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = mat; r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            var floor = go.AddComponent<BoxCollider>();
            floor.center = new Vector3((x0 + x1) / 2, -0.05f, (z0 + z1) / 2);
            floor.size = new Vector3(x1 - x0, 0.1f, z1 - z0);
            return go;
        }

        static Bounds WorldBounds(GameObject go)
        {
            var rs = go.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(go.transform.position, Vector3.one * 0.5f);
            var b = rs[0].bounds;
            foreach (var r in rs) b.Encapsulate(r.bounds);
            return b;
        }

        static Material FindMaterial(GameObject saloon, string objectName)
        {
            var t = saloon.GetComponentsInChildren<Transform>().FirstOrDefault(x => x.name == objectName);
            return t ? t.GetComponent<Renderer>()?.sharedMaterial : null;
        }

        static void LogBounds(GameObject saloon, params string[] names)
        {
            foreach (var n in names)
            {
                var t = saloon.GetComponentsInChildren<Transform>().FirstOrDefault(x => x.name == n);
                Debug.Log(t ? $"[SetupSaloon] {n} bounds {WorldBounds(t.gameObject)}" : $"[SetupSaloon] {n} not found");
            }
        }
    }
}
