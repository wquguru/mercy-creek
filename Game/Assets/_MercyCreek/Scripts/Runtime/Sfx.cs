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
        [Header("街道")]
        public AudioClip streetAmbience;
        public AudioClip[] stepsDirt, stepsBoardwalk;
        [Tooltip("0 = 弹对，1..4 = 错音 C / A / G / E")]
        public AudioClip[] waltz;

        [Header("场景里的声源")]
        public AudioSource piano, clock;
        public AudioSource[] windows;

        /// <summary>华尔兹里错音的位置（秒，见 docs/audio_waltz.md）。</summary>
        public const float WrongNoteAt = 24.107f;
        public const float WaltzLength = 57.857f;

        AudioSource _ambience, _street, _music;
        Transform _listener;
        float _outdoors;
        float _nextTick;
        bool _tock;

        public static string WrongNoteName(int loop) => loop switch { 1 => "C", 2 => "A", 3 => "G", _ => "E" };

        void Awake()
        {
            I = this;
            _ambience = Source2D(ambience, true, 0.55f);
            _street = Source2D(streetAmbience, true, 0f);
            if (streetAmbience) _street.Play();
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

            // 室内酒馆的嘈杂 ↔ 街上的风：按玩家在不在屋里交叉淡变
            if (!_listener && Camera.main) _listener = Camera.main.transform;
            if (_listener && _street.clip && !_ambienceOverride)
            {
                _outdoors = Mathf.MoveTowards(_outdoors, Indoors(_listener.position) ? 0f : 1f, Time.deltaTime / 1.5f);
                _ambience.volume = 0.55f * (1f - 0.8f * _outdoors);
                _street.volume = 0.6f * (0.25f + 0.75f * _outdoors);
            }
        }

        bool _ambienceOverride;

        /// <summary>屋里 = 酒馆大厅 / 4 号房 / 电报局（docs/GAME_DESIGN.md 主街布局）。</summary>
        public static bool Indoors(Vector3 p) =>
            (p.z > -0.15f && p.z < 13.5f && p.x > -7.2f && p.x < 7.2f) || (p.z > -0.15f && p.z < 7f && p.x > -15.5f && p.x < -9f);

        public void StartPiano(int loop)
        {
            if (!piano || waltz == null || waltz.Length < 5) return;
            piano.clip = waltz[loop switch { 1 => 1, 2 => 2, 3 => 3, _ => 4 }];
            piano.loop = true;
            piano.Play();
        }

        public float PianoTime => piano && piano.isPlaying ? piano.time : -1f;

        public void StopPiano(float fade = 0.4f) { if (piano) StartCoroutine(FadeOut(piano, fade)); }

        public void FadeAmbience(float to, float seconds)
        {
            _ambienceOverride = true;
            StartCoroutine(FadeTo(_ambience, to, seconds));
            if (_street) StartCoroutine(FadeTo(_street, to, seconds));
        }

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

        /// <summary>脚步：屋里木地板、街上土路、栈道（比路面高）各一套。</summary>
        public void Step(Vector3 pos, float volume = 0.7f)
        {
            var set = steps;
            if (!Indoors(pos))
            {
                bool boardwalk = pos.y > 0.12f && pos.y < 0.6f;
                var outdoor = boardwalk ? stepsBoardwalk : stepsDirt;
                if (outdoor != null && outdoor.Length > 0) set = outdoor;
            }
            if (set == null || set.Length == 0) return;
            PlayAt(set[Random.Range(0, set.Length)], pos, volume * Random.Range(0.8f, 1f), 0.08f);
        }

        public void Type(Vector3 pos)
        {
            if (typeKeys == null || typeKeys.Length == 0) return;
            PlayAt(typeKeys[Random.Range(0, typeKeys.Length)], pos, 0.8f, 0.05f);
        }

        /// <summary>开场 / 稿数卡的打字声（不跟空间位置走）。</summary>
        public void TypeKey2D()
        {
            if (typeKeys == null || typeKeys.Length == 0) return;
            _music.PlayOneShot(typeKeys[Random.Range(0, typeKeys.Length)], 0.35f * EffectsVolume);
        }

        public void TypeReturn2D() { if (typeReturn) _music.PlayOneShot(typeReturn, 0.4f * EffectsVolume); }

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
