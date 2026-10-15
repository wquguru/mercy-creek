using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 全部声音的入口。音频都是 tools/build_audio.sh 程序合成的（docs/ASSETS.md），由 SetupSaloon 把剪辑挂上来。
    /// 钢琴每轮弹错一个音：第 1 轮 C、第 2 轮 A、第 3 轮 G、之后 E（docs/GAME_DESIGN.md）。
    /// </summary>
    public class Sfx : MonoBehaviour
    {
        public static Sfx I { get; private set; }

        /// <summary>设置菜单写这两个值（M6）。</summary>
        public static float MusicVolume = 1f, EffectsVolume = 1f;

        [Header("循环")]
        public AudioClip ambience, wind, voidHum, resetSting, endingTheme;
        [Header("界面")]
        public AudioClip remember, denied, click;
        [Header("物件")]
        public AudioClip tick, tock, doorOpen, doorClose, glassClink, glassPour, bottleSet, typeBell, typeReturn;
        public AudioClip[] steps, typeKeys;
        [Tooltip("0 = 弹对，1..4 = 错音 C / A / G / E")]
        public AudioClip[] waltz;

        [Header("场景里的声源")]
        public AudioSource piano, clock;
        public AudioSource[] windows;

        /// <summary>华尔兹里错音的位置（秒，见 docs/audio_waltz.md）。</summary>
        public const float WrongNoteAt = 24.107f;
        public const float WaltzLength = 57.857f;

        AudioSource _ambience, _music;
        float _nextTick;
        bool _tock;

        public static string WrongNoteName(int loop) => loop switch { 1 => "C", 2 => "A", 3 => "G", _ => "E" };

        void Awake()
        {
            I = this;
            _ambience = Source2D(ambience, true, 0.55f);
            _music = Source2D(null, false, 1f);
            foreach (var w in windows) if (w) { w.clip = wind; w.loop = true; w.volume = 0.35f; w.Play(); }
            _ambience.Play();
            if (clock) clock.volume = 0.6f;
        }

        void OnDestroy() { if (I == this) I = null; }

        AudioSource Source2D(AudioClip clip, bool loop, float volume)
        {
            var s = gameObject.AddComponent<AudioSource>();
            s.clip = clip; s.loop = loop; s.volume = volume; s.spatialBlend = 0f; s.playOnAwake = false;
            return s;
        }

        void Update()
        {
            // 座钟：钟摆一直在走，指针停在三点
            if (clock && Time.time >= _nextTick)
            {
                clock.PlayOneShot(_tock ? tock : tick, EffectsVolume);
                _tock = !_tock;
                _nextTick = Time.time + 1f;
            }
            if (piano) piano.volume = 0.9f * MusicVolume;
        }

        public void StartPiano(int loop)
        {
            if (!piano || waltz == null || waltz.Length < 5) return;
            piano.clip = waltz[loop switch { 1 => 1, 2 => 2, 3 => 3, _ => 4 }];
            piano.loop = true;
            piano.Play();
        }

        public float PianoTime => piano && piano.isPlaying ? piano.time : -1f;

        public void StopPiano(float fade = 0.4f) { if (piano) StartCoroutine(FadeOut(piano, fade)); }

        public void FadeAmbience(float to, float seconds) => StartCoroutine(FadeTo(_ambience, to, seconds));

        public void PlayMusic(AudioClip clip, bool loop = false)
        {
            _music.clip = clip; _music.loop = loop; _music.volume = 0.8f * MusicVolume; _music.Play();
        }

        public void StopMusic(float fade = 1f) { if (_music.isPlaying) StartCoroutine(FadeOut(_music, fade)); }

        public void Play2D(AudioClip clip, float volume = 1f)
        {
            if (clip) _music.PlayOneShot(clip, volume * EffectsVolume);
        }

        public void PlayAt(AudioClip clip, Vector3 pos, float volume = 1f, float pitchJitter = 0f)
        {
            if (!clip) return;
            var go = new GameObject("One Shot " + clip.name);
            go.transform.position = pos;
            var s = go.AddComponent<AudioSource>();
            s.clip = clip; s.spatialBlend = 1f; s.volume = volume * EffectsVolume;
            s.pitch = 1f + Random.Range(-pitchJitter, pitchJitter);
            s.minDistance = 1.5f; s.maxDistance = 25f; s.rolloffMode = AudioRolloffMode.Logarithmic;
            s.Play();
            Destroy(go, clip.length / Mathf.Max(0.5f, s.pitch) + 0.1f);
        }

        public void Step(Vector3 pos, float volume = 0.7f)
        {
            if (steps == null || steps.Length == 0) return;
            PlayAt(steps[Random.Range(0, steps.Length)], pos, volume * Random.Range(0.8f, 1f), 0.08f);
        }

        public void Type(Vector3 pos)
        {
            if (typeKeys == null || typeKeys.Length == 0) return;
            PlayAt(typeKeys[Random.Range(0, typeKeys.Length)], pos, 0.8f, 0.05f);
        }

        static System.Collections.IEnumerator FadeOut(AudioSource s, float seconds)
        {
            float v = s.volume;
            for (float t = 0; t < seconds; t += Time.unscaledDeltaTime) { s.volume = v * (1 - t / seconds); yield return null; }
            s.Stop(); s.volume = v;
        }

        static System.Collections.IEnumerator FadeTo(AudioSource s, float to, float seconds)
        {
            float from = s.volume;
            for (float t = 0; t < seconds; t += Time.unscaledDeltaTime) { s.volume = Mathf.Lerp(from, to, t / seconds); yield return null; }
            s.volume = to;
        }
    }
}
