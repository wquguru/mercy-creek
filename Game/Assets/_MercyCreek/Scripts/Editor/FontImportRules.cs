using System.IO;
using UnityEditor;
using UnityEngine;

namespace MercyCreek.EditorTools
{
    /// <summary>
    /// 界面字体烘成静态图集：只含 tools/fonts/make_font.py 收集到的字。
    /// 动态字体在网页版（WebGPU）里图集扩容后会丢字，静态图集两端表现一致。
    /// </summary>
    public class FontImportRules : AssetPostprocessor
    {
        const string Folder = "Assets/_MercyCreek/Resources/Fonts/";

        void OnPreprocessAsset()
        {
            if (!assetPath.StartsWith(Folder) || !(assetImporter is TrueTypeFontImporter ti)) return;
            string charset = Path.Combine(Folder, "MercySerif.charset.txt");
            if (!File.Exists(charset)) return;
            ti.fontTextureCase = FontTextureCase.CustomSet;
            ti.customCharacters = File.ReadAllText(charset);
            ti.fontSize = 64;
            ti.characterPadding = 2;
            ti.fontRenderingMode = FontRenderingMode.Smooth;
            ti.includeFontData = false;
        }
    }
}
