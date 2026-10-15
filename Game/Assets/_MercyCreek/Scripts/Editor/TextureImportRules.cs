using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// Art/Textures 下的贴图（Blender 导出 glTF 时共用的贴图目录）按平台压缩：
    /// Mac 最大 2048、BC7；Web 最大 1024、DXT Crunch。
    /// 颜色空间看 glTF 里谁在用它：法线 / 粗糙度金属度 / AO 是线性，其余 sRGB。glTFast 直接用这些贴图资源，不再自己解码。
    /// </summary>
    public class TextureImportRules : AssetPostprocessor
    {
        const string Folder = "Assets/_MercyCreek/Art/Textures/";

        void OnPreprocessTexture()
        {
            if (!assetPath.StartsWith(Folder)) return;
            var ti = (TextureImporter)assetImporter;
            string file = Path.GetFileName(assetPath);
            bool linear = LinearImages().Contains(file);
            ti.textureType = TextureImporterType.Default;
            ti.sRGBTexture = !linear;
            ti.mipmapEnabled = true;
            ti.anisoLevel = 4;
            ti.alphaSource = TextureImporterAlphaSource.FromInput;
            ti.alphaIsTransparency = false;
            ti.maxTextureSize = 2048;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
            ti.SetPlatformTextureSettings(new TextureImporterPlatformSettings
            {
                name = "Standalone", overridden = true, maxTextureSize = 2048,
                format = TextureImporterFormat.BC7, textureCompression = TextureImporterCompression.CompressedHQ,
            });
            ti.SetPlatformTextureSettings(new TextureImporterPlatformSettings
            {
                name = "WebGL", overridden = true, maxTextureSize = 1024,
                format = ti.DoesSourceTextureHaveAlpha() ? TextureImporterFormat.DXT5Crunched : TextureImporterFormat.DXT1Crunched,
                compressionQuality = 60, crunchedCompression = true,
            });
        }

        // ---------- 从所有 glTF 里收集"线性"贴图 ----------

        [Serializable] class TexInfo { public int index = -1; }
        [Serializable] class Pbr { public TexInfo baseColorTexture; public TexInfo metallicRoughnessTexture; }
        [Serializable] class Mat { public Pbr pbrMetallicRoughness; public TexInfo normalTexture; public TexInfo occlusionTexture; }
        [Serializable] class Tex { public int source = -1; }
        [Serializable] class Img { public string uri; }
        [Serializable] class Gltf { public Mat[] materials; public Tex[] textures; public Img[] images; }

        static HashSet<string> _linear;
        static double _stamp;

        static HashSet<string> LinearImages()
        {
            // 同一次导入批次里只扫一遍
            if (_linear != null && EditorApplication.timeSinceStartup - _stamp < 30) return _linear;
            _linear = new HashSet<string>();
            _stamp = EditorApplication.timeSinceStartup;
            foreach (var f in Directory.GetFiles("Assets/_MercyCreek/Art", "*.gltf", SearchOption.AllDirectories))
            {
                Gltf g;
                try { g = JsonUtility.FromJson<Gltf>(File.ReadAllText(f)); } catch { continue; }
                if (g?.materials == null || g.textures == null || g.images == null) continue;
                void Add(TexInfo t)
                {
                    if (t == null || t.index < 0 || t.index >= g.textures.Length) return;
                    int src = g.textures[t.index].source;
                    if (src >= 0 && src < g.images.Length && !string.IsNullOrEmpty(g.images[src].uri))
                        _linear.Add(Path.GetFileName(Uri.UnescapeDataString(g.images[src].uri)));
                }
                foreach (var m in g.materials)
                {
                    Add(m.normalTexture); Add(m.occlusionTexture);
                    Add(m.pbrMetallicRoughness?.metallicRoughnessTexture);
                }
            }
            return _linear;
        }
    }
}
