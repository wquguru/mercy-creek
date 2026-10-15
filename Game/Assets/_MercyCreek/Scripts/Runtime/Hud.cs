using UnityEngine;
using UnityEngine.UI;

namespace MercyCreek
{
    /// <summary>
    /// 代码搭的极简 HUD：循环计数、准星、交互提示、内心独白、全屏淡入淡出、结局卡。
    /// 中文用系统字体（仅 macOS / Windows 原生版有效；Web 版要换 TMP + 思源黑体，见 docs/TECH.md）。
    /// </summary>
    public class Hud : MonoBehaviour
    {
        Text _loop, _prompt, _say, _card;
        Image _fade;
        float _sayUntil;
        Font _font;

        public float Fade { get => _fade.color.a; set => _fade.color = new Color(0, 0, 0, value); }

        void Awake()
        {
            _font = Font.CreateDynamicFontFromOSFont(new[] { "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Arial Unicode MS" }, 32);

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

            var dot = MakeImage(canvasGo.transform, "Crosshair", new Color(1, 1, 1, 0.55f));
            Anchor(dot.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(5, 5));

            _prompt = MakeText(canvasGo.transform, "Prompt", 26, TextAnchor.MiddleCenter, new Color(1, 0.95f, 0.85f, 0.9f));
            Anchor(_prompt.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -60), new Vector2(600, 50));

            _say = MakeText(canvasGo.transform, "Say", 32, TextAnchor.LowerCenter, new Color(1, 0.96f, 0.88f, 1));
            Anchor(_say.rectTransform, new Vector2(0.5f, 0f), new Vector2(0, 120), new Vector2(1400, 200));
            _say.supportRichText = true;
            var shadow = _say.gameObject.AddComponent<Shadow>();
            shadow.effectColor = new Color(0, 0, 0, 0.8f);
            shadow.effectDistance = new Vector2(2, -2);

            _card = MakeText(canvasGo.transform, "EndCard", 54, TextAnchor.MiddleCenter, new Color(1, 0.93f, 0.8f, 0));
            Stretch(_card.rectTransform);

            _fade.transform.SetAsLastSibling();
            _card.transform.SetAsLastSibling();
            Fade = 1f;
        }

        void Update()
        {
            _loop.text = $"Mercy Creek · 第 {LoopMemory.Loop} 次\n记忆 {LoopMemory.Fragments.Count}";
            if (Time.time > _sayUntil) _say.text = "";
        }

        public void SetPrompt(string s) => _prompt.text = s ?? "";

        public void Say(string s, float seconds = 5f)
        {
            if (string.IsNullOrEmpty(s)) return;
            _say.text = s;
            _sayUntil = Time.time + seconds;
        }

        public void ShowEnding()
        {
            int secs = Mathf.FloorToInt(LoopMemory.TotalSeconds);
            _card.text = $"觉 醒\n\n<size=30>第 {LoopMemory.Loop} 次循环 · 你在 {secs / 60} 分 {secs % 60} 秒后醒来</size>";
            _card.supportRichText = true;
            StartCoroutine(EndingRoutine());
        }

        System.Collections.IEnumerator EndingRoutine()
        {
            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.InputLocked = true;
            yield return new WaitForSeconds(4f);
            for (float t = 0; t < 1; t += Time.deltaTime / 3f)
            {
                Fade = t;
                _card.color = new Color(1, 0.93f, 0.8f, t);
                yield return null;
            }
            Fade = 1; _card.color = new Color(1, 0.93f, 0.8f, 1);
            var director = FindFirstObjectByType<LoopDirector>();
            if (director) director.enabled = false;
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
