using System.Collections;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace MercyCreek
{
    /// <summary>
    /// 一个下午 = 一轮循环。太阳从午后落到黄昏，油灯渐亮；时间到了，世界褪色、断裂、重来。
    /// </summary>
    public class LoopDirector : MonoBehaviour
    {
        public float loopSeconds = 240f;
        public Light sun;
        [Tooltip("西头画布上画的街景：画的是午后的光，黄昏时跟着天色一起变暖变暗")]
        public Renderer[] paintedCanvas;
        public Color canvasDusk = new(1f, 0.66f, 0.48f);
        public Light[] lamps;
        public Volume resetVolume;          // 重置瞬间：去饱和 + 冷色
        public Hud hud;
        public Transform clockMinuteHand;   // 可选：座钟分针

        [Header("太阳：仰角 / 方位（度）")]
        public float elevationStart = 26f, elevationEnd = 8f;
        public float azimuth = 18f;         // 0 = 光朝 +Z（从前窗射入），正值 = 偏向 +X（光斑落进大厅中央）
        public Color sunStart = new(1f, 0.86f, 0.68f), sunEnd = new(1f, 0.52f, 0.25f);
        public float sunIntensityStart = 3.2f, sunIntensityEnd = 1.6f;
        public float lampIntensityStart = 0.4f, lampIntensityEnd = 2.2f;

        float _t;
        bool _resetting;

        public float Elapsed => _t;

        /// <summary>评审截图用：直接跳到某个时间点。</summary>
        public void Skip(float seconds) { _t = seconds; ApplyTime(Mathf.Clamp01(_t / loopSeconds)); }

        public enum Card { None, Reset, Continue }

        /// <summary>下一次场景载入时要在黑场上打的稿数卡（重置 / 读档时设置）。</summary>
        public static Card PendingCard;

        /// <summary>打字页期间时间不走。</summary>
        public bool Holding { get; set; }

        IEnumerator Start()
        {
            if (LoopMemory.Started) LoopMemory.Save();
            ApplyTime(0f);
            hud.Fade = 1f;
            var card = PendingCard; PendingCard = Card.None;
            if (LoopMemory.Started && !LoopMemory.Automated && card != Card.None)
            {
                Holding = true;
                yield return null;
                var lines = card == Card.Reset
                    ? new[] { Loc.T("card.void", LoopMemory.DraftOf(LoopMemory.Loop - 1)), Loc.T("card.draft", LoopMemory.Draft) }
                    : new[] { Loc.T("card.draft", LoopMemory.Draft) };
                yield return hud.TypeCard(lines, 1.0f);
                Holding = false;
            }
            for (float f = 1; f > 0; f -= Time.deltaTime / 1.6f) { hud.Fade = f; yield return null; }
            hud.Fade = 0;
        }

        /// <summary>暂停菜单"结束这个下午"。</summary>
        public void EndAfternoon() { if (!_resetting) StartCoroutine(ResetLoop()); }

        bool _pianoStarted;

        [Header("雾：屋里的暖色薄雾是酒馆氛围的一部分；街上要看得远")]
        public float fogIndoor = 0.018f, fogOutdoor = 0.006f;
        float _outdoors = -1f;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (!cam) return;
            float goal = Sfx.Indoors(cam.transform.position) ? 0f : 1f;
            _outdoors = _outdoors < 0f ? goal : Mathf.MoveTowards(_outdoors, goal, Time.unscaledDeltaTime / 1.2f);
            RenderSettings.fogDensity = Mathf.Lerp(fogIndoor, fogOutdoor, _outdoors);
        }

        void Update()
        {
            if (_resetting || !LoopMemory.Started || Holding) return;
            _t += Time.deltaTime;
            if (!_pianoStarted && _t >= Story.WaltzStart) { _pianoStarted = true; StartPiano(); }
            LoopMemory.TotalSeconds += Time.deltaTime;
            ApplyTime(Mathf.Clamp01(_t / loopSeconds));

            if (_t >= loopSeconds) StartCoroutine(ResetLoop());
        }

        /// <summary>k = 循环进度 0..1。编辑器烘焙光照情景时也会调用。</summary>
        public void ApplyTime(float k)
        {
            // APV：午后 → 黄昏两个烘焙情景之间混合（场景没烘过时静默跳过）
            if (Application.isPlaying && ProbeReferenceVolume.instance.isInitialized)
            {
                if (ProbeReferenceVolume.instance.lightingScenario != "Afternoon")
                    ProbeReferenceVolume.instance.lightingScenario = "Afternoon";
                ProbeReferenceVolume.instance.BlendLightingScenario("Dusk", Smooth(k));
            }
            float e = Mathf.Lerp(elevationStart, elevationEnd, Smooth(k));
            if (sun)
            {
                sun.transform.rotation = Quaternion.Euler(e, azimuth, 0f);
                sun.color = Color.Lerp(sunStart, sunEnd, Smooth(k));
                sun.intensity = Mathf.Lerp(sunIntensityStart, sunIntensityEnd, k);
            }
            if (lamps != null)
                foreach (var l in lamps)
                    if (l) l.intensity = Mathf.Lerp(lampIntensityStart, lampIntensityEnd, Smooth(k)) * (1f + 0.04f * Mathf.Sin(Time.time * 9f + l.GetInstanceID()));
            TintCanvas(Smooth(k));
            if (clockMinuteHand) clockMinuteHand.localRotation = Quaternion.Euler(0, 0, -k * 360f * 0.5f);
        }

        static readonly string[] CanvasColorProps = { "baseColorFactor", "_BaseColor", "emissiveFactor", "_EmissionColor" };
        MaterialPropertyBlock _mpb;
        Color[][] _canvasBase;

        void TintCanvas(float k)
        {
            if (paintedCanvas == null || paintedCanvas.Length == 0) return;
            _mpb ??= new MaterialPropertyBlock();
            if (_canvasBase == null)
            {
                // 记下原始颜色（glTFast 和 URP Lit 的属性名不同，有哪个用哪个）
                _canvasBase = new Color[paintedCanvas.Length][];
                for (int i = 0; i < paintedCanvas.Length; i++)
                {
                    var m = paintedCanvas[i] ? paintedCanvas[i].sharedMaterial : null;
                    _canvasBase[i] = new Color[CanvasColorProps.Length];
                    for (int j = 0; j < CanvasColorProps.Length; j++)
                        _canvasBase[i][j] = m && m.HasProperty(CanvasColorProps[j]) ? m.GetColor(CanvasColorProps[j]) : Color.clear;
                }
            }
            Color tint = Color.Lerp(Color.white, canvasDusk, k);
            for (int i = 0; i < paintedCanvas.Length; i++)
            {
                var r = paintedCanvas[i];
                if (!r) continue;
                r.GetPropertyBlock(_mpb);
                for (int j = 0; j < CanvasColorProps.Length; j++)
                {
                    var c0 = _canvasBase[i][j];
                    if (c0.a <= 0f && c0.maxColorComponent <= 0f) continue;
                    _mpb.SetColor(CanvasColorProps[j], new Color(c0.r * tint.r, c0.g * tint.g, c0.b * tint.b, c0.a));
                }
                r.SetPropertyBlock(_mpb);
            }
        }

        void StartPiano() => Sfx.I?.StartPiano(LoopMemory.Loop);

        static float Smooth(float x) => x * x * (3f - 2f * x);

        IEnumerator ResetLoop()
        {
            _resetting = true;
            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.InputLocked = true;
            hud.Say(Loc.T("ui.ellipsis"), 3f);
            if (Sfx.I) { Sfx.I.StopPiano(1.2f); Sfx.I.FadeAmbience(0f, 1.5f); Sfx.I.Play2D(Sfx.I.resetSting, 0.9f); }
            // 世界先冻结褪色，再黑场
            for (float w = 0; w < 1; w += Time.unscaledDeltaTime / 1.8f)
            {
                if (resetVolume) resetVolume.weight = w;
                Time.timeScale = Mathf.Lerp(1f, 0.15f, w);
                yield return null;
            }
            for (float f = 0; f < 1; f += Time.unscaledDeltaTime / 0.8f) { hud.Fade = f; yield return null; }
            hud.Fade = 1;
            Time.timeScale = 1f;
            LoopMemory.NextLoop();
            PendingCard = Card.Reset;
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
        }
    }
}
