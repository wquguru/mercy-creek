using System;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;

namespace MercyCreek
{
    /// <summary>
    /// 通关分享卡片 1200×630：酒馆一角做底图（带后期），叠上结局名、第几稿、用时、记住的碎片。
    /// Mac 存到桌面；Web 触发浏览器下载（Plugins/WebGL/MercyDownload.jslib）。
    /// </summary>
    public static class ShareCard
    {
        public const int W = 1200, H = 630;
        public static Transform viewpoint;
        public static Font font;

#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] static extern void MercyDownload(byte[] data, int length, string fileName);
#endif

        /// <returns>保存位置（给界面显示），失败返回 null。</returns>
        public static string Capture(string forcePath = null)
        {
            var png = Render();
            if (png == null) return null;
            string name = $"MercyCreek_{LoopMemory.LastEnding ?? "Card"}_{DateTime.Now:yyyyMMdd_HHmmss}.png";
#if UNITY_WEBGL && !UNITY_EDITOR
            MercyDownload(png, png.Length, name);
            return name;
#else
            string path = forcePath ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), name);
            File.WriteAllBytes(path, png);
            Debug.Log("[ShareCard] " + path);
            return path;
#endif
        }

        static byte[] Render()
        {
            var rt = RenderTexture.GetTemporary(W, H, 24, RenderTextureFormat.ARGB32);
            var camGo = new GameObject("Share Card Camera");
            var canvasGo = new GameObject("Share Card Canvas", typeof(Canvas), typeof(CanvasScaler));
            try
            {
                var cam = camGo.AddComponent<Camera>();
                if (viewpoint) camGo.transform.SetPositionAndRotation(viewpoint.position, viewpoint.rotation);
                cam.fieldOfView = 55f; cam.nearClipPlane = 0.05f; cam.farClipPlane = 200f;
                cam.targetTexture = rt;
                cam.GetUniversalAdditionalCameraData().renderPostProcessing = true;

                var canvas = canvasGo.GetComponent<Canvas>();
                canvas.renderMode = RenderMode.ScreenSpaceCamera;
                canvas.worldCamera = cam;
                canvas.planeDistance = 0.5f;
                var scaler = canvasGo.GetComponent<CanvasScaler>();
                scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
                scaler.referenceResolution = new Vector2(W, H);

                var shade = new GameObject("Shade", typeof(RectTransform), typeof(Image)).GetComponent<Image>();
                shade.transform.SetParent(canvasGo.transform, false);
                Stretch(shade.rectTransform);
                shade.color = new Color(0.03f, 0.02f, 0.015f, 0.55f);

                string ending = LoopMemory.LastEnding ?? "Awaken";
                int secs = Mathf.FloorToInt(LoopMemory.TotalSeconds);
                string title = Loc.T("end." + ending.ToLower());
                // 觉醒 / 真相的副标题带稿数和用时，其余是固定一句
                string sub = ending is "Awaken" or "Truth"
                    ? Loc.T("end." + ending.ToLower() + ".sub", LoopMemory.Draft, secs / 60, secs % 60)
                    : Loc.T("end." + ending.ToLower() + ".sub");
                var frags = LoopMemory.Fragments.Select(f => "✦ " + Loc.T("frag." + f)).ToArray();

                Text(canvasGo.transform, "MERCY CREEK", 26, new Vector2(70, -60), TextAnchor.UpperLeft, new Color(0.91f, 0.77f, 0.54f));
                Text(canvasGo.transform, title, 88, new Vector2(70, -150), TextAnchor.UpperLeft, Color.white);
                Text(canvasGo.transform, sub, 30, new Vector2(74, -290), TextAnchor.UpperLeft, new Color(1f, 0.93f, 0.8f));
                if (frags.Length > 0)
                {
                    Text(canvasGo.transform, Loc.T("share.memories"), 22, new Vector2(74, -380), TextAnchor.UpperLeft, new Color(0.91f, 0.77f, 0.54f));
                    Text(canvasGo.transform, string.Join("    ", frags), 24, new Vector2(74, -420), TextAnchor.UpperLeft, new Color(1f, 0.93f, 0.8f));
                }
                Text(canvasGo.transform, Loc.T("menu.tagline"), 22, new Vector2(74, -560), TextAnchor.UpperLeft, new Color(1f, 0.93f, 0.8f, 0.7f));

                Canvas.ForceUpdateCanvases();
                cam.Render();
                var prev = RenderTexture.active;
                RenderTexture.active = rt;
                var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                tex.Apply();
                RenderTexture.active = prev;
                var png = tex.EncodeToPNG();
                UnityEngine.Object.Destroy(tex);
                return png;
            }
            catch (Exception e) { Debug.LogException(e); return null; }
            finally
            {
                UnityEngine.Object.Destroy(camGo);
                UnityEngine.Object.Destroy(canvasGo);
                RenderTexture.ReleaseTemporary(rt);
            }
        }

        static void Text(Transform parent, string s, int size, Vector2 pos, TextAnchor anchor, Color color, FontStyle style = FontStyle.Normal)
        {
            var t = new GameObject("T", typeof(RectTransform), typeof(Text)).GetComponent<Text>();
            t.transform.SetParent(parent, false);
            t.font = font; t.text = s; t.fontSize = size; t.alignment = anchor; t.color = color; t.fontStyle = style;
            t.horizontalOverflow = HorizontalWrapMode.Wrap; t.verticalOverflow = VerticalWrapMode.Overflow;
            var rt = t.rectTransform;
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0, 1);
            rt.anchoredPosition = pos; rt.sizeDelta = new Vector2(W - 140, size * 2.5f);
            t.gameObject.AddComponent<Shadow>().effectColor = new Color(0, 0, 0, 0.7f);
        }

        static void Stretch(RectTransform r) { r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one; r.offsetMin = r.offsetMax = Vector2.zero; }
    }
}
