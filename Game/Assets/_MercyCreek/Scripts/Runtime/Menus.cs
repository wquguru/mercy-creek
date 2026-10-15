using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace MercyCreek
{
    /// <summary>玩家设置，存在 PlayerPrefs。</summary>
    public static class Settings
    {
        public static float Sensitivity { get => PlayerPrefs.GetFloat("sens", 0.08f); set => PlayerPrefs.SetFloat("sens", Mathf.Clamp(value, 0.02f, 0.2f)); }
        public static float Master { get => PlayerPrefs.GetFloat("vol.master", 0.9f); set => PlayerPrefs.SetFloat("vol.master", Mathf.Clamp01(value)); }
        public static float Music { get => PlayerPrefs.GetFloat("vol.music", 0.9f); set => PlayerPrefs.SetFloat("vol.music", Mathf.Clamp01(value)); }
        public static bool InvertY { get => PlayerPrefs.GetInt("invert", 0) == 1; set => PlayerPrefs.SetInt("invert", value ? 1 : 0); }

        public static void Apply()
        {
            AudioListener.volume = Master;
            Sfx.MusicVolume = Music;
            var fpc = UnityEngine.Object.FindFirstObjectByType<FirstPersonController>();
            if (fpc) { fpc.lookSensitivity = Sensitivity; fpc.invertY = InvertY; }
        }
    }

    /// <summary>
    /// 标题画面、暂停、设置、结局后的按钮。没有 EventSystem：鼠标悬停 / 点击和键盘都在这里自己处理。
    /// </summary>
    public class Menus : MonoBehaviour
    {
        enum Screen { None, Title, Pause, Settings, Ending }

        public Font font;
        public Transform titleCameraFrom, titleCameraTo, titleLookAt, shareViewpoint;

        Screen _screen = Screen.None, _settingsReturn;
        Canvas _canvas;
        Text _title, _tagline, _hint, _note;
        Image _dim;
        readonly List<Text> _rows = new();
        readonly List<Item> _items = new();
        int _sel;
        float _titleT;
        Hud _hud;

        struct Item
        {
            public Func<string> label;
            public Action submit;
            public Action<int> adjust;
        }

        public static bool Paused { get; private set; }
        public static bool Blocking => !LoopMemory.Started || Paused;

        void Awake()
        {
            var args = Environment.GetCommandLineArgs();
            if (Array.IndexOf(args, "-autoshot") >= 0 || Array.IndexOf(args, "-autotest") >= 0) LoopMemory.Started = true;
            int lang = Array.IndexOf(args, "-lang");
            if (lang >= 0 && lang + 1 < args.Length) Loc.Current = args[lang + 1] == "zh" ? Loc.Lang.Zh : Loc.Lang.En;
            BuildUi();
        }

        void Start()
        {
            _hud = FindFirstObjectByType<Hud>();
            ShareCard.font = font;
            ShareCard.viewpoint = shareViewpoint;
            Settings.Apply();
            if (!LoopMemory.Started) ShowTitle();
            else Show(Screen.None);
            int shot = Array.IndexOf(Environment.GetCommandLineArgs(), "-titleshot");
            if (shot >= 0) StartCoroutine(TitleShot(Environment.GetCommandLineArgs()[shot + 1]));
        }

        /// <summary>评审：`-titleshot &lt;png&gt;` 拍标题画面和设置画面后退出。</summary>
        System.Collections.IEnumerator TitleShot(string path)
        {
            yield return new WaitForSeconds(5f);
            ScreenCapture.CaptureScreenshot(path);
            yield return new WaitForSeconds(0.5f);
            OpenSettings(Screen.Title);
            yield return new WaitForSeconds(0.5f);
            ScreenCapture.CaptureScreenshot(path.Replace(".png", "_settings.png"));
            yield return new WaitForSeconds(0.5f);
            Application.Quit();
        }

        // =====================================================================
        // 画面
        // =====================================================================

        Camera _titleCam;

        void ShowTitle()
        {
            _titleT = 0f;
            // 独立的标题相机（深度更高，盖在玩家相机上面），不去动玩家的头
            _titleCam = new GameObject("Title Camera").AddComponent<Camera>();
            _titleCam.depth = 10; _titleCam.fieldOfView = 55f; _titleCam.nearClipPlane = 0.05f; _titleCam.farClipPlane = 200f;
            UnityEngine.Rendering.Universal.CameraExtensions.GetUniversalAdditionalCameraData(_titleCam).renderPostProcessing = true;
            Show(Screen.Title);
            if (Sfx.I && Sfx.I.waltz != null && Sfx.I.waltz.Length > 0) Sfx.I.PlayMusic(Sfx.I.waltz[0], true);   // 标题画面放"弹对"的版本
        }

        void Show(Screen s)
        {
            _screen = s;
            _items.Clear();
            _sel = 0;
            switch (s)
            {
                case Screen.Title:
                    if (LoopMemory.HasSave)
                        _items.Add(new Item { label = () => Loc.T("menu.continue", LoopMemory.SavedLoop), submit = Continue });
                    _items.Add(new Item { label = () => Loc.T("menu.new"), submit = NewGame });
                    _items.Add(new Item { label = () => Loc.T("menu.settings"), submit = () => OpenSettings(Screen.Title) });
                    if (Application.platform != RuntimePlatform.WebGLPlayer)
                        _items.Add(new Item { label = () => Loc.T("menu.quit"), submit = Application.Quit });
                    break;
                case Screen.Pause:
                    _items.Add(new Item { label = () => Loc.T("menu.resume"), submit = Resume });
                    _items.Add(new Item { label = () => Loc.T("menu.settings"), submit = () => OpenSettings(Screen.Pause) });
                    _items.Add(new Item { label = () => Loc.T("menu.totitle"), submit = () => { LoopMemory.Save(); ToTitle(); } });
                    if (Application.platform != RuntimePlatform.WebGLPlayer)
                        _items.Add(new Item { label = () => Loc.T("menu.quit"), submit = () => { LoopMemory.Save(); Application.Quit(); } });
                    break;
                case Screen.Settings:
                    _items.Add(new Item { label = () => Loc.T("menu.sens", Mathf.RoundToInt(Settings.Sensitivity * 100)), adjust = d => Settings.Sensitivity += d * 0.01f });
                    _items.Add(new Item { label = () => Loc.T("menu.invert", Loc.T(Settings.InvertY ? "menu.on" : "menu.off")), adjust = _ => Settings.InvertY = !Settings.InvertY });
                    _items.Add(new Item { label = () => Loc.T("menu.master", Mathf.RoundToInt(Settings.Master * 100)), adjust = d => Settings.Master += d * 0.1f });
                    _items.Add(new Item { label = () => Loc.T("menu.music", Mathf.RoundToInt(Settings.Music * 100)), adjust = d => Settings.Music += d * 0.1f });
                    _items.Add(new Item { label = () => Loc.T("menu.lang"), adjust = _ => Loc.Current = Loc.Current == Loc.Lang.Zh ? Loc.Lang.En : Loc.Lang.Zh });
                    _items.Add(new Item { label = () => Loc.T("menu.back"), submit = () => Show(_settingsReturn) });
                    break;
                case Screen.Ending:
                    _items.Add(new Item { label = () => Loc.T("menu.share"), submit = SaveShareCard });
                    _items.Add(new Item { label = () => Loc.T("menu.totitle"), submit = () => { LoopMemory.Clear(); ToTitle(); } });
                    break;
            }
            bool title = s == Screen.Title;
            _title.gameObject.SetActive(title || s == Screen.Pause || s == Screen.Settings);
            _title.text = s == Screen.Pause ? Loc.T("menu.paused") : s == Screen.Settings ? Loc.T("menu.settings") : Loc.T("menu.title");
            _tagline.text = title ? Loc.T("menu.tagline") : "";
            _hint.text = title || s == Screen.Pause ? Loc.T("menu.hint") : "";
            _note.text = title ? Loc.T("menu.credits") : "";
            _dim.color = new Color(0, 0, 0, s == Screen.Pause || s == Screen.Settings && _settingsReturn == Screen.Pause ? 0.6f : 0f);
            if (_hud) _hud.HudVisible = s == Screen.None || s == Screen.Pause;
            bool menuOpen = s != Screen.None;
            Cursor.lockState = menuOpen ? CursorLockMode.None : CursorLockMode.Locked;
            Cursor.visible = menuOpen;
            Render();
        }

        void OpenSettings(Screen from) { _settingsReturn = from; Show(Screen.Settings); }

        void NewGame()
        {
            LoopMemory.Clear();
            LoopMemory.DeleteSave();
            Begin();
        }

        void Continue()
        {
            LoopMemory.Load();
            LoopMemory.Started = true;
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);   // 按存档的轮数重建这一轮
        }

        void Begin()
        {
            LoopMemory.Started = true;
            Sfx.I?.StopMusic(1.5f);
            if (_titleCam) Destroy(_titleCam.gameObject);
            Show(Screen.None);
        }

        void Resume()
        {
            Paused = false;
            Time.timeScale = 1f;
            AudioListener.pause = false;
            Show(Screen.None);
        }

        void ToTitle()
        {
            Paused = false;
            Time.timeScale = 1f;
            AudioListener.pause = false;
            LoopMemory.Started = false;
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
        }

        void SaveShareCard()
        {
            string path = ShareCard.Capture();
            if (path != null) _note.text = Loc.T("menu.saved", path);
        }

        // =====================================================================
        // 每帧
        // =====================================================================

        void Update()
        {
            var kb = Keyboard.current;
            if (_screen == Screen.Title) TitleCamera();
            if (_screen == Screen.None && _hud && _hud.EndingShown) { Show(Screen.Ending); return; }

            if (kb != null && kb.escapeKey.wasPressedThisFrame)
            {
                if (_screen == Screen.None && LoopMemory.Started && !(_hud && (_hud.ChoicesOpen || _hud.EndingShown)))
                {
                    Paused = true;
                    Time.timeScale = 0f;
                    AudioListener.pause = true;
                    Show(Screen.Pause);
                    return;
                }
                if (_screen == Screen.Pause) { Resume(); return; }
                if (_screen == Screen.Settings) { Show(_settingsReturn); return; }
            }
            if (_screen == Screen.None || _items.Count == 0) return;
            Navigate(kb, Mouse.current);
        }

        void Navigate(Keyboard kb, Mouse mouse)
        {
            int before = _sel;
            bool submit = false; int adjust = 0;
            if (kb != null)
            {
                if (kb.downArrowKey.wasPressedThisFrame || kb.sKey.wasPressedThisFrame) _sel = (_sel + 1) % _items.Count;
                if (kb.upArrowKey.wasPressedThisFrame || kb.wKey.wasPressedThisFrame) _sel = (_sel + _items.Count - 1) % _items.Count;
                if (kb.leftArrowKey.wasPressedThisFrame || kb.aKey.wasPressedThisFrame) adjust = -1;
                if (kb.rightArrowKey.wasPressedThisFrame || kb.dKey.wasPressedThisFrame) adjust = 1;
                if (kb.enterKey.wasPressedThisFrame || kb.spaceKey.wasPressedThisFrame || kb.eKey.wasPressedThisFrame) submit = true;
            }
            if (mouse != null)
            {
                Vector2 mp = mouse.position.ReadValue();
                for (int i = 0; i < _items.Count && i < _rows.Count; i++)
                {
                    var rt = _rows[i].rectTransform;
                    if (!RectTransformUtility.RectangleContainsScreenPoint(rt, mp, null)) continue;
                    if (mouse.delta.ReadValue().sqrMagnitude > 0) _sel = i;
                    if (mouse.leftButton.wasPressedThisFrame)
                    {
                        _sel = i;
                        if (_items[i].adjust != null)
                        {
                            RectTransformUtility.ScreenPointToLocalPointInRectangle(rt, mp, null, out var local);
                            adjust = local.x < 0 ? -1 : 1;
                        }
                        else submit = true;
                    }
                }
            }
            var item = _items[_sel];
            if (adjust != 0 && item.adjust != null) { item.adjust(adjust); Settings.Apply(); PlayerPrefs.Save(); Click(); }
            else if (submit && item.submit != null) { Click(); item.submit(); return; }
            else if (submit && item.adjust != null) { item.adjust(1); Settings.Apply(); Click(); }
            if (before != _sel || adjust != 0 || submit) Render();
        }

        static void Click() => Sfx.I?.Play2D(Sfx.I.click, 0.7f);

        void TitleCamera()
        {
            var cam = _titleCam;
            if (!cam || !titleCameraFrom || !titleCameraTo) return;
            _titleT += Time.unscaledDeltaTime;
            float k = 0.5f - 0.5f * Mathf.Cos(_titleT * 2f * Mathf.PI / 70f);   // 70 秒一个来回的缓慢推拉
            cam.transform.position = Vector3.Lerp(titleCameraFrom.position, titleCameraTo.position, k);
            cam.transform.rotation = Quaternion.LookRotation(titleLookAt.position - cam.transform.position);
        }

        // =====================================================================
        // UI 搭建
        // =====================================================================

        void BuildUi()
        {
            var go = new GameObject("Menu Canvas", typeof(Canvas), typeof(CanvasScaler));
            go.transform.SetParent(transform, false);
            _canvas = go.GetComponent<Canvas>();
            _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            _canvas.sortingOrder = 20;
            var scaler = go.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;

            _dim = new GameObject("Dim", typeof(RectTransform), typeof(Image)).GetComponent<Image>();
            _dim.transform.SetParent(go.transform, false);
            _dim.rectTransform.anchorMin = Vector2.zero; _dim.rectTransform.anchorMax = Vector2.one;
            _dim.rectTransform.offsetMin = _dim.rectTransform.offsetMax = Vector2.zero;
            _dim.raycastTarget = false;

            _title = MakeText(go.transform, 84, TextAnchor.MiddleLeft, new Vector2(160, 300), new Vector2(1400, 140), FontStyle.Bold);
            _tagline = MakeText(go.transform, 30, TextAnchor.MiddleLeft, new Vector2(164, 210), new Vector2(1400, 60), FontStyle.Italic);
            for (int i = 0; i < 7; i++)
                _rows.Add(MakeText(go.transform, 36, TextAnchor.MiddleLeft, new Vector2(164, 90 - i * 64), new Vector2(760, 58), FontStyle.Normal));
            _hint = MakeText(go.transform, 22, TextAnchor.LowerLeft, new Vector2(164, -440), new Vector2(1600, 40), FontStyle.Normal);
            _note = MakeText(go.transform, 20, TextAnchor.LowerLeft, new Vector2(164, -480), new Vector2(1600, 40), FontStyle.Normal);
        }

        Text MakeText(Transform parent, int size, TextAnchor anchor, Vector2 pos, Vector2 sizeDelta, FontStyle style)
        {
            var t = new GameObject("Text", typeof(RectTransform), typeof(Text)).GetComponent<Text>();
            t.transform.SetParent(parent, false);
            t.font = font; t.fontSize = size; t.alignment = anchor; t.fontStyle = style;
            t.color = new Color(1f, 0.93f, 0.8f, 1f);
            t.horizontalOverflow = HorizontalWrapMode.Overflow; t.verticalOverflow = VerticalWrapMode.Overflow;
            t.raycastTarget = false; t.supportRichText = true;
            var rt = t.rectTransform;
            rt.anchorMin = rt.anchorMax = new Vector2(0, 0.5f); rt.pivot = new Vector2(0, 0.5f);
            rt.anchoredPosition = pos; rt.sizeDelta = sizeDelta;
            t.gameObject.AddComponent<Shadow>().effectColor = new Color(0, 0, 0, 0.8f);
            return t;
        }

        void Render()
        {
            for (int i = 0; i < _rows.Count; i++)
            {
                bool on = i < _items.Count;
                _rows[i].gameObject.SetActive(on);
                if (!on) continue;
                string label = _items[i].label();
                _rows[i].text = i == _sel ? $"<b>▸ {label}</b>" : $"   <color=#b8a890>{label}</color>";
            }
        }
    }
}
