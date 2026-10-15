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
        public float loopSeconds = 180f;
        public Light sun;
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

        IEnumerator Start()
        {
            if (LoopMemory.Loop > 1) hud.Say(Loc.T("ui.again"), 4f);
            if (LoopMemory.Started) LoopMemory.Save();
            ApplyTime(0f);
            for (float f = 1; f > 0; f -= Time.deltaTime / 1.6f) { hud.Fade = f; yield return null; }
            hud.Fade = 0;
        }

        bool _pianoStarted;

        void Update()
        {
            if (_resetting || !LoopMemory.Started) return;
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
            if (clockMinuteHand) clockMinuteHand.localRotation = Quaternion.Euler(0, 0, -k * 360f * 0.5f);
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
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
        }
    }
}
