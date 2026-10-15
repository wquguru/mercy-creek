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
        Text _loop, _prompt, _say, _card, _choices;
        Image _fade, _crosshair;
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

            _card = MakeText(canvasGo.transform, "EndCard", 54, TextAnchor.MiddleCenter, new Color(1, 0.93f, 0.8f, 0));
            Stretch(_card.rectTransform);

            _fade.transform.SetAsLastSibling();
            _card.transform.SetAsLastSibling();
            Fade = 1f;
        }

        void Update()
        {
            _loop.text = Loc.T("ui.loop", LoopMemory.Loop) + "\n" + Loc.T("ui.memory", LoopMemory.Fragments.Count);
            if (Time.time > _sayUntil) _say.text = "";
            UpdateChoices();
        }

        // ---------- 对话选项 ----------
        List<(string label, Action pick)> _opts;
        Npc _talkingTo;
        int _sel, _openedFrame;

        public bool ChoicesOpen => _opts != null;

        public void ShowChoices(Npc npc, List<(string label, Action pick)> options)
        {
            _talkingTo = npc; _opts = options; _sel = 0; _openedFrame = Time.frameCount;
            _opts.Add((Loc.T("ui.leave"), null));
            RenderChoices();
        }

        public void CloseChoices() { _opts = null; _talkingTo = null; _choices.text = ""; }

        void RenderChoices()
        {
            var sb = new System.Text.StringBuilder();
            sb.Append($"<color=#e8c48a>{_talkingTo.DisplayName}</color>\n");
            for (int i = 0; i < _opts.Count; i++)
                sb.Append(i == _sel ? $"<color=#ffe2a8>▸ {i + 1}. {_opts[i].label}</color>\n" : $"   {i + 1}. <color=#c8b8a0>{_opts[i].label}</color>\n");
            _choices.text = sb.ToString();
        }

        void UpdateChoices()
        {
            if (_opts == null || Time.frameCount == _openedFrame) return;   // 打开选项的那一下 E 不算选择
            var kb = Keyboard.current; var mouse = Mouse.current;
            var cam = Camera.main;
            if (!_talkingTo || !_talkingTo.isActiveAndEnabled || (cam && Vector3.Distance(cam.transform.position, _talkingTo.transform.position + Vector3.up * 1.4f) > 3.6f))
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

        public void SetPrompt(string s) => _prompt.text = s ?? "";

        public string Saying => _say.text;

        public void Say(string s, float seconds = 5f)
        {
            if (string.IsNullOrEmpty(s)) return;
            _say.text = s;
            _sayUntil = Time.time + seconds;
        }

        public void ShowEnding(string title, string sub)
        {
            CloseChoices();
            _card.text = $"{title}\n\n<size=30>{sub}</size>";
            _card.supportRichText = true;
            StartCoroutine(EndingRoutine());
        }

        public bool EndingShown { get; private set; }

        System.Collections.IEnumerator EndingRoutine()
        {
            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.InputLocked = true;
            yield return new WaitForSeconds(2f);
            for (float t = 0; t < 1; t += Time.deltaTime / 3f)
            {
                Fade = t;
                _card.color = new Color(1, 0.93f, 0.8f, t);
                yield return null;
            }
            Fade = 1; _card.color = new Color(1, 0.93f, 0.8f, 1);
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
