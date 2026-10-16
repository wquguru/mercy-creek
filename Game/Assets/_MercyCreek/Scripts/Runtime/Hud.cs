using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace MercyCreek
{
    /// <summary>
    /// 代码搭的极简 HUD：循环计数、准星、交互提示、内心独白、全屏淡入淡出、结局卡。
    /// 字体：Resources/Fonts/MercySerif（Noto Serif SC 子集，tools/fonts/make_font.py 生成）。
    /// </summary>
    public class Hud : MonoBehaviour
    {
        Text _loop, _prompt, _say, _card, _cardSub, _choices, _typed, _book, _bookTitle;
        Image _fade, _crosshair, _bookBg;
        float _sayUntil;
        Font _font;

        public Font font;

        /// <summary>标题 / 设置画面时隐藏 HUD 文字（黑场层不受影响）。</summary>
        public bool HudVisible { set { if (_loop) { _loop.enabled = value; _prompt.enabled = value; _crosshair.enabled = value; } } }

        public float Fade { get => _fade.color.a; set => _fade.color = new Color(0, 0, 0, value); }

        void Awake()
        {
            _font = font ? font : Font.CreateDynamicFontFromOSFont(new[] { "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Arial Unicode MS" }, 32);

            var canvasGo = new GameObject("HUD Canvas", typeof(Canvas), typeof(CanvasScaler));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;

            _fade = MakeImage(canvasGo.transform, "Fade", Color.black);
            Stretch(_fade.rectTransform);

            _loop = MakeText(canvasGo.transform, "Loop", 26, TextAnchor.UpperLeft, new Color(0.93f, 0.86f, 0.72f, 0.75f));
            Anchor(_loop.rectTransform, new Vector2(0, 1), new Vector2(40, -36), new Vector2(700, 80));

            var dot = _crosshair = MakeImage(canvasGo.transform, "Crosshair", new Color(1, 1, 1, 0.55f));
            Anchor(dot.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(5, 5));

            _prompt = MakeText(canvasGo.transform, "Prompt", 26, TextAnchor.MiddleCenter, new Color(1, 0.95f, 0.85f, 0.9f));
            Anchor(_prompt.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -60), new Vector2(600, 50));

            _say = MakeText(canvasGo.transform, "Say", 32, TextAnchor.LowerCenter, new Color(1, 0.96f, 0.88f, 1));
            Anchor(_say.rectTransform, new Vector2(0.5f, 0f), new Vector2(0, 120), new Vector2(1400, 200));
            _say.supportRichText = true;
            var shadow = _say.gameObject.AddComponent<Shadow>();
            shadow.effectColor = new Color(0, 0, 0, 0.8f);
            shadow.effectDistance = new Vector2(2, -2);

            _choices = MakeText(canvasGo.transform, "Choices", 28, TextAnchor.LowerLeft, new Color(1, 0.93f, 0.8f, 1));
            Anchor(_choices.rectTransform, new Vector2(0.5f, 0f), new Vector2(-330, 330), new Vector2(900, 260));
            _choices.supportRichText = true;
            _choices.gameObject.AddComponent<Shadow>().effectColor = new Color(0, 0, 0, 0.85f);

            // 静态字体图集不支持富文本 <size>（会整段不显示），大小不同的字一律分开放
            _card = MakeText(canvasGo.transform, "EndCard", 54, TextAnchor.MiddleCenter, new Color(1, 0.93f, 0.8f, 0));
            Anchor(_card.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 40), new Vector2(1600, 120));
            _cardSub = MakeText(canvasGo.transform, "EndCardSub", 30, TextAnchor.MiddleCenter, new Color(1, 0.93f, 0.8f, 0));
            Anchor(_cardSub.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -50), new Vector2(1600, 80));

            // 记忆本：Tab 开关，时间照常流逝
            _bookBg = MakeImage(canvasGo.transform, "BookBg", new Color(0.05f, 0.035f, 0.02f, 0.82f));
            Anchor(_bookBg.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1180, 760));
            _book = MakeText(canvasGo.transform, "Book", 28, TextAnchor.UpperLeft, new Color(1, 0.94f, 0.82f, 1));
            Anchor(_book.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -10), new Vector2(1060, 680));
            _book.supportRichText = true; _book.lineSpacing = 1.15f;
            _bookTitle = MakeText(canvasGo.transform, "BookTitle", 40, TextAnchor.UpperLeft, new Color(1, 0.94f, 0.82f, 1));
            Anchor(_bookTitle.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 300), new Vector2(1060, 60));
            _bookBg.enabled = _book.enabled = _bookTitle.enabled = false;

            // 黑场上的打字页（开场、稿数卡）
            _typed = MakeText(canvasGo.transform, "Typed", 36, TextAnchor.MiddleLeft, new Color(0.95f, 0.9f, 0.8f, 1));
            Anchor(_typed.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 0), new Vector2(1300, 600));
            _typed.supportRichText = true; _typed.lineSpacing = 1.5f;

            _fade.transform.SetAsLastSibling();
            _typed.transform.SetAsLastSibling();
            _card.transform.SetAsLastSibling();
            _cardSub.transform.SetAsLastSibling();
            Fade = 1f;
        }

        void Update()
        {
            _loop.text = Loc.T("ui.loop", LoopMemory.Draft) + "\n" + Loc.T("ui.memory", LoopMemory.Fragments.Count);
            if (Time.time > _sayUntil) _say.text = "";
            UpdateChoices();
            UpdateBook();
        }

        // ---------- 对话选项 ----------
        List<(string label, Action pick)> _opts;
        // 选项的对象：NPC，或者打字机这样的物件（走远了 / 对象消失就自动关闭）
        Transform _anchor;
        Vector3 _anchorOffset;
        string _choiceTitle;
        int _sel, _openedFrame;

        public bool ChoicesOpen => _opts != null;

        public void ShowChoices(Npc npc, List<(string label, Action pick)> options) =>
            ShowChoices(npc.DisplayName, npc.transform, options, Vector3.up * 1.4f);

        public void ShowChoices(string title, Transform anchor, List<(string label, Action pick)> options, Vector3 offset = default)
        {
            _choiceTitle = title; _anchor = anchor; _anchorOffset = offset;
            _opts = options; _sel = 0; _openedFrame = Time.frameCount;
            _opts.Add((Loc.T("ui.leave"), null));
            RenderChoices();
        }

        public void CloseChoices() { _opts = null; _anchor = null; _choices.text = ""; }

        void RenderChoices()
        {
            var sb = new System.Text.StringBuilder();
            sb.Append($"<color=#e8c48a>{_choiceTitle}</color>\n");
            for (int i = 0; i < _opts.Count; i++)
                sb.Append(i == _sel ? $"<color=#ffe2a8>▸ {i + 1}. {_opts[i].label}</color>\n" : $"   {i + 1}. <color=#c8b8a0>{_opts[i].label}</color>\n");
            _choices.text = sb.ToString();
        }

        void UpdateChoices()
        {
            if (_opts == null || Time.frameCount == _openedFrame) return;   // 打开选项的那一下 E 不算选择
            var kb = Keyboard.current; var mouse = Mouse.current;
            var cam = Camera.main;
            if (!_anchor || !_anchor.gameObject.activeInHierarchy || (cam && Vector3.Distance(cam.transform.position, _anchor.position + _anchorOffset) > 3.6f))
            { CloseChoices(); return; }
            int pick = -1;
            if (kb != null)
            {
                for (int i = 0; i < Mathf.Min(_opts.Count, 9); i++)
                    if (kb[Key.Digit1 + i].wasPressedThisFrame) pick = i;
                if (kb.downArrowKey.wasPressedThisFrame) { _sel = (_sel + 1) % _opts.Count; RenderChoices(); }
                if (kb.upArrowKey.wasPressedThisFrame) { _sel = (_sel + _opts.Count - 1) % _opts.Count; RenderChoices(); }
                if (kb.eKey.wasPressedThisFrame || kb.enterKey.wasPressedThisFrame) pick = _sel;
                if (kb.escapeKey.wasPressedThisFrame) { CloseChoices(); return; }
            }
            if (mouse != null)
            {
                float wheel = mouse.scroll.ReadValue().y;
                if (Mathf.Abs(wheel) > 0.1f) { _sel = (_sel + (wheel < 0 ? 1 : _opts.Count - 1)) % _opts.Count; RenderChoices(); }
                if (mouse.leftButton.wasPressedThisFrame) pick = _sel;
            }
            if (pick < 0) return;
            var act = _opts[pick].pick;
            CloseChoices();
            act?.Invoke();
        }

        // ---------- 记忆本 ----------
        public bool BookOpen => _book.enabled;

        public void ShowBook(bool on) { _book.enabled = _bookBg.enabled = _bookTitle.enabled = on; if (on) RenderBook(); }

        void UpdateBook()
        {
            var kb = Keyboard.current;
            bool can = LoopMemory.Started && !Menus.Paused && !EndingShown && !Typing && Fade < 0.5f;
            if (kb != null && kb.tabKey.wasPressedThisFrame && can) ShowBook(!BookOpen);
            if (BookOpen && !can) ShowBook(false);
            if (BookOpen) RenderBook();
        }

        void RenderBook()
        {
            var sb = new System.Text.StringBuilder();
            _bookTitle.text = Loc.T("book.title");
            sb.Append("\n\n");
            var dir = Story.I ? Story.I.director : null;
            int left = dir ? Mathf.Max(0, Mathf.CeilToInt(dir.loopSeconds - dir.Elapsed)) : 0;
            sb.Append($"<color=#b8a890>{Loc.T("book.time", LoopMemory.Draft, left / 60, left % 60)}</color>\n\n");
            if (LoopMemory.Fragments.Count == 0) sb.Append($"<color=#b8a890>{Loc.T("book.empty")}</color>\n");
            foreach (var f in LoopMemory.Fragments)
                sb.Append($"<color=#e8c48a>◆ {Loc.T("frag." + f)}</color>　<color=#d8ccb8>{Loc.T("frag." + f + ".d")}</color>\n");
            if (Story.I) sb.Append($"\n<color=#e8c48a>{Loc.T("book.next")}</color>\n<color=#d4c2a2>{Story.I.NextHint()}</color>\n");
            sb.Append($"\n<color=#8a7c68>{Loc.T("book.close")}</color>");
            _book.text = sb.ToString();
        }

        // ---------- 打字页 ----------
        public bool Typing { get; private set; }

        /// <summary>黑场上逐字打出几行字（打字机声）；任意键先补全、再结束。调用前后黑场由调用方负责。</summary>
        public System.Collections.IEnumerator TypeCard(string[] lines, float hold = 1.6f)
        {
            Typing = true;
            Fade = 1f;
            HudVisible = false;
            var kb = Keyboard.current;
            bool skip = false;
            string shown = "";
            yield return null;
            for (int l = 0; l < lines.Length && !skip; l++)
            {
                string line = lines[l];
                for (int i = 0; i <= line.Length && !skip; i++)
                {
                    // 富文本标签整段跳过，不逐字打
                    if (i < line.Length && line[i] == '<') { int end = line.IndexOf('>', i); if (end > i) i = end; }
                    _typed.text = shown + line.Substring(0, Mathf.Min(i, line.Length));
                    if (i < line.Length && line[i] != ' ') Sfx.I?.TypeKey2D();
                    if (AnyKey(kb)) skip = true;
                    yield return new WaitForSecondsRealtime(i < line.Length && "，。,.—".IndexOf(line[i]) >= 0 ? 0.16f : 0.045f);
                }
                shown += line + "\n";
                if (!skip) { Sfx.I?.TypeReturn2D(); yield return new WaitForSecondsRealtime(0.45f); }
            }
            _typed.text = string.Join("\n", lines);
            for (float t = 0; t < (skip ? 0.4f : hold); t += Time.unscaledDeltaTime)
            {
                if (!skip && t > 0.2f && AnyKey(kb)) break;
                yield return null;
            }
            _typed.text = "";
            HudVisible = true;
            Typing = false;
        }

        static bool AnyKey(Keyboard kb) =>
            (kb != null && kb.anyKey.wasPressedThisFrame) || (Mouse.current?.leftButton.wasPressedThisFrame ?? false);

        public void SetPrompt(string s) => _prompt.text = s ?? "";

        public string Saying => _say.text;
        public string PromptText => _prompt.text;
        public string ChoicesText => _choices.text;

        /// <summary>宣传片取景：除黑场外全部隐藏。</summary>
        public void HideAll() { HudVisible = false; _say.enabled = false; _choices.enabled = false; ShowBook(false); }

        public void ClearSay() { _say.text = ""; _sayUntil = 0f; }

        public void Say(string s, float seconds = 5f)
        {
            if (string.IsNullOrEmpty(s)) return;
            _say.text = s;
            _sayUntil = Time.time + seconds;
        }

        public void ShowEnding(string title, string sub)
        {
            CloseChoices();
            ShowBook(false);
            _card.text = title;
            _cardSub.text = sub;
            StartCoroutine(EndingRoutine());
        }

        public bool EndingShown { get; private set; }

        System.Collections.IEnumerator EndingRoutine()
        {
            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.InputLocked = true;
            yield return new WaitForSeconds(2f);
            float from = Fade;   // 真相结局从黑场打字页直接接过来，不能先闪回画面
            for (float t = 0; t < 1; t += Time.deltaTime / 3f)
            {
                Fade = Mathf.Max(from, t);
                _card.color = _cardSub.color = new Color(1, 0.93f, 0.8f, t);
                yield return null;
            }
            Fade = 1; _card.color = _cardSub.color = new Color(1, 0.93f, 0.8f, 1);
            EndingShown = true;
        }

        Text MakeText(Transform parent, string name, int size, TextAnchor anchor, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Text));
            go.transform.SetParent(parent, false);
            var t = go.GetComponent<Text>();
            t.font = _font; t.fontSize = size; t.alignment = anchor; t.color = color;
            t.horizontalOverflow = HorizontalWrapMode.Wrap; t.verticalOverflow = VerticalWrapMode.Overflow;
            t.raycastTarget = false;
            return t;
        }

        static Image MakeImage(Transform parent, string name, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = color; img.raycastTarget = false;
            return img;
        }

        static void Stretch(RectTransform r)
        {
            r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one; r.offsetMin = r.offsetMax = Vector2.zero;
        }

        static void Anchor(RectTransform r, Vector2 anchor, Vector2 pos, Vector2 size)
        {
            r.anchorMin = r.anchorMax = anchor; r.pivot = anchor; r.anchoredPosition = pos; r.sizeDelta = size;
        }
    }
}
