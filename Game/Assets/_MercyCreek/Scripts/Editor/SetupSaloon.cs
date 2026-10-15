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
    public static class SetupSaloon
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
            var glb = AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/Art/Saloon/Saloon.glb")
                      ?? throw new Exception("Saloon.glb not imported");
            var saloon = (GameObject)PrefabUtility.InstantiatePrefab(glb);
            saloon.name = "Saloon";
            saloon.transform.rotation = Quaternion.Euler(0, 180, 0);
            foreach (var mf in saloon.GetComponentsInChildren<MeshFilter>())
            {
                var mc = mf.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
                GameObjectUtility.SetStaticEditorFlags(mf.gameObject,
                    StaticEditorFlags.ContributeGI | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic | StaticEditorFlags.ReflectionProbeStatic | StaticEditorFlags.BatchingStatic);
            }
            // 玻璃不挡阳光（窗玻璃、酒瓶、灯罩）
            foreach (var r in saloon.GetComponentsInChildren<MeshRenderer>())
                if (r.sharedMaterials.Any(m => m && m.name.ToLower().Contains("glass")))
                    r.shadowCastingMode = ShadowCastingMode.Off;
            LogBounds(saloon, "BarTop", "Floor", "Ceiling");   // 校验坐标约定

            // ---------- 光 ----------
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 0.92f;
            sun.shadowBias = 0.02f; sun.shadowNormalBias = 0.25f;
            sun.transform.rotation = Quaternion.Euler(26, 18, 0);
            sun.color = new Color(1f, 0.86f, 0.68f); sun.intensity = 3.2f;

            var lamps = new List<Light>();
            foreach (var t in saloon.GetComponentsInChildren<Transform>().Where(t => t.name.ToLower().Contains("lantern") && t.name.EndsWith("_root")))
            {
                var b = WorldBounds(t.gameObject);
                lamps.Add(PointLight($"Lamp ({t.name})", b.center + Vector3.up * 0.05f, 6f, new Color(1f, 0.66f, 0.36f), true));
            }
            lamps.Add(PointLight("Lamp (bar)", new Vector3(-5.6f, 2.5f, 5.4f), 8f, new Color(1f, 0.64f, 0.34f), true));
            lamps.Add(PointLight("Lamp (balcony)", new Vector3(-2.5f, 5.3f, 8.8f), 7f, new Color(1f, 0.6f, 0.32f), false));
            // 模拟墙面反弹的暖色补光（无阴影）
            var fill = PointLight("Bounce Fill", new Vector3(0f, 2.6f, 4.5f), 14f, new Color(0.95f, 0.72f, 0.52f), false);
            fill.intensity = 0.8f;

            RenderSettings.sun = sun;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.44f, 0.41f, 0.39f);
            RenderSettings.ambientEquatorColor = new Color(0.34f, 0.27f, 0.2f);
            RenderSettings.ambientGroundColor = new Color(0.11f, 0.08f, 0.06f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = 0.018f;
            RenderSettings.fogColor = new Color(0.36f, 0.28f, 0.2f);
            RenderSettings.skybox = SkyboxMaterial();

            var probe = new GameObject("Reflection Probe").AddComponent<ReflectionProbe>();
            probe.transform.position = new Vector3(0, 2.2f, 5f);
            probe.size = new Vector3(14f, 6.4f, 10f);
            probe.boxProjection = true;
            probe.mode = ReflectionProbeMode.Baked;
            probe.resolution = 256;
            probe.intensity = 0.6f;

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
            var hud = new GameObject("HUD").AddComponent<Hud>();

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

            // ---------- 循环 ----------
            var loop = new GameObject("Loop Director").AddComponent<LoopDirector>();
            loop.sun = sun; loop.lamps = lamps.ToArray(); loop.resetVolume = reset; loop.hud = hud;

            // ---------- 交互点（记忆碎片）----------
            Interact(saloon, "vintage_grandfather_clock_01_root", "看那座钟", "clock",
                "落地钟停在三点整。你从来没见过它走动。", "三点整。永远是三点整。");
            Interact(saloon, "ornate_mirror_01_root", "看镜子", "mirror",
                "镜子里的你眨了一下眼——比你慢了半拍。", "你不敢再看镜子太久。");
            Interact(saloon, "PlayerPiano_Blockout", "听钢琴", "piano",
                "琴键自己在动。纸卷上的每一个孔，你闭着眼都能背出来。", "这首曲子只有一种结尾。你从没听到过结尾。");
            Interact(saloon, "dartboard", "看飞镖靶", null, "三支飞镖扎在同一个洞里。每天都是。", null);
            Interact(saloon, "wine_bottles_01_root", "看酒瓶", null, "标签上的字你每天都读，却从来想不起写的是什么。", null);

            // 前门：挡住，只能看
            var door = new GameObject("Front Door");
            door.transform.position = new Vector3(0, 1.35f, 0.1f);
            door.AddComponent<BoxCollider>().size = new Vector3(1.8f, 2.7f, 0.3f);
            var di = door.AddComponent<Interactable>();
            di.prompt = "推门"; di.fragmentId = "door";
            di.firstText = "门外的街道在阳光里一动不动，像一幅画。你没有迈出去。";
            di.rememberedText = "你知道外面什么都没有。";

            // 二楼上锁的房间：集齐 4 个碎片才开
            var lockedDoor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            lockedDoor.name = "Locked Door";
            lockedDoor.transform.position = new Vector3(0, 3.2f + 1.15f, 9.96f);
            lockedDoor.transform.localScale = new Vector3(1.2f, 2.3f, 0.08f);
            var doorMat = FindMaterial(saloon, "BarBody");
            if (doorMat) lockedDoor.GetComponent<MeshRenderer>().sharedMaterial = doorMat;
            var li = lockedDoor.AddComponent<Interactable>();
            li.prompt = "开门"; li.requiredFragments = 4; li.isEnding = true;
            li.lockedText = "门锁着。门缝里有很轻的、规律的咔哒声，像打字机。";
            li.firstText = "门开了。屋里只有一张桌子，桌上摊着一叠打印出来的剧本。\n第一页写着：《Mercy Creek》—— 第 {loop} 稿，由 AI 生成。";

            // ---------- 评审机位 ----------
            var shots = new GameObject("Review Viewpoints").transform;
            var autoShot = shots.gameObject.AddComponent<AutoShot>();
            shots.gameObject.AddComponent<AutoTest>();
            autoShot.viewpoints = new[]
            {
                Viewpoint(shots, "entrance", new Vector3(0.3f, 1.65f, 0.6f), new Vector3(0.5f, 1.6f, 8f)),
                Viewpoint(shots, "balcony", new Vector3(5.6f, 4.8f, 8.4f), new Vector3(-2f, 0.6f, 3f)),
                Viewpoint(shots, "bar", new Vector3(-2.7f, 1.45f, 2.2f), new Vector3(-6.7f, 1.3f, 6.5f)),
                Viewpoint(shots, "shafts", new Vector3(4.3f, 1.7f, 8.0f), new Vector3(-2.5f, 0.6f, 1.5f)),
            };

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            Lightmapping.BakeReflectionProbe(probe, Root + "/Scenes/Saloon/ReflectionProbe.exr");
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            Debug.Log("[SetupSaloon] done: " + ScenePath);
        }

        // ================= helpers =================

        static void SetupPipeline()
        {
            var rp = AssetDatabase.LoadAssetAtPath<RenderPipelineAsset>(Root + "/Settings/PC_RPAsset.asset");
            GraphicsSettings.defaultRenderPipeline = rp;
            int keep = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = rp;
            }
            QualitySettings.SetQualityLevel(QualitySettings.names.Length - 1, true);
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;   // 评审截图时窗口不在前台
        }

        static Light PointLight(string name, Vector3 pos, float range, Color color, bool shadows)
        {
            var l = new GameObject(name).AddComponent<Light>();
            l.type = LightType.Point; l.transform.position = pos; l.range = range; l.color = color; l.intensity = 1f;
            l.shadows = shadows ? LightShadows.Soft : LightShadows.None;
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
            ca.postExposure.Override(0.75f); ca.contrast.Override(14f); ca.saturation.Override(-10f);
            ca.colorFilter.Override(new Color(1f, 0.97f, 0.92f));
            var wb = Add<WhiteBalance>(p); wb.temperature.Override(8f);
            var smh = Add<ShadowsMidtonesHighlights>(p);
            smh.shadows.Override(new Vector4(0.92f, 1f, 1.06f, 0f));
            smh.highlights.Override(new Vector4(1.05f, 1f, 0.94f, 0f));
            var bloom = Add<Bloom>(p); bloom.threshold.Override(1.0f); bloom.intensity.Override(0.5f); bloom.scatter.Override(0.65f);
            var vig = Add<Vignette>(p); vig.intensity.Override(0.3f); vig.smoothness.Override(0.45f);
            var grain = Add<FilmGrain>(p); grain.type.Override(FilmGrainLookup.Medium2); grain.intensity.Override(0.28f); grain.response.Override(0.7f);
            var chrom = Add<ChromaticAberration>(p); chrom.intensity.Override(0.06f);
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

        static void Interact(GameObject saloon, string objectName, string prompt, string fragment, string first, string remembered)
        {
            var t = saloon.GetComponentsInChildren<Transform>().FirstOrDefault(x => x.name == objectName);
            if (!t) { Debug.LogWarning("[SetupSaloon] interactable target not found: " + objectName); return; }
            var b = WorldBounds(t.gameObject);
            var go = new GameObject("Interact " + objectName);
            go.transform.position = b.center;
            var box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.size = b.size + Vector3.one * 0.1f;
            var i = go.AddComponent<Interactable>();
            i.prompt = prompt; i.fragmentId = fragment; i.firstText = first; i.rememberedText = remembered;
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
