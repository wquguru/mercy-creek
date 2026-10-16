using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MercyCreek.EditorTools
{
    public static partial class SetupSaloon
    {
        /// <summary>
        /// 楼梯旁的 ornate_mirror_01（Poly Haven）只有一张材质，玻璃和框是同一个网格。
        /// 在玻璃凹面（网格局部 z = 0.007，下方矩形 + 拱顶，量自 Saloon.gltf）前 1.5 毫米贴一张同形状的面片做反射面；
        /// 内尔的人偶放进场景，只给反射相机看（MirrorReflection）。
        /// </summary>
        static void SetupMirror(GameObject saloon, GameObject player, FirstPersonController fps)
        {
            var node = Find(saloon, "ornate_mirror_01");
            if (!node) { Debug.LogWarning("[SetupMirror] ornate_mirror_01 not found"); return; }

            const float hw = 0.2186f, y0 = -0.3855f, ySide = 0.17f, yTop = 0.299f, z = 0.0085f;
            var outline = new List<Vector2> { new(-hw, y0), new(hw, y0) };
            const int arc = 16;
            for (int i = 0; i <= arc; i++)
            {
                float x = Mathf.Lerp(hw, -hw, i / (float)arc);
                float y = ySide + (yTop - ySide) * Mathf.Pow(Mathf.Max(0f, 1f - (x / hw) * (x / hw)), 0.35f);
                outline.Add(new Vector2(x, y));
            }
            var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var tris = new List<int>();
            var center = new Vector2(0, (y0 + yTop) * 0.5f);
            verts.Add(new Vector3(center.x, center.y, 0)); uvs.Add(new Vector2(0.5f, (center.y - y0) / (yTop - y0)));
            foreach (var o in outline) { verts.Add(new Vector3(o.x, o.y, 0)); uvs.Add(new Vector2((o.x + hw) / (2 * hw), (o.y - y0) / (yTop - y0))); }
            for (int i = 1; i <= outline.Count; i++) tris.AddRange(new[] { 0, i, i % outline.Count + 1 });
            var mesh = new Mesh { name = "Mirror Glass" };
            mesh.SetVertices(verts); mesh.SetUVs(0, uvs); mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals(); mesh.RecalculateBounds();
            const string meshPath = Root + "/Materials/MirrorGlass.asset";
            var old = AssetDatabase.LoadAssetAtPath<Mesh>(meshPath);
            if (old) { EditorUtility.CopySerialized(mesh, old); mesh = old; } else AssetDatabase.CreateAsset(mesh, meshPath);

            const string matPath = Root + "/Materials/Mirror.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            if (!mat) { mat = new Material(Shader.Find("MercyCreek/Mirror")); AssetDatabase.CreateAsset(mat, matPath); }

            var glass = new GameObject("Mirror Glass", typeof(MeshFilter), typeof(MeshRenderer));
            glass.transform.SetParent(node, false);
            glass.transform.localPosition = new Vector3(0, 0, z);
            // 网格局部 +Z 应该朝向房间里；万一导入轴向不同就翻过来
            var room = new Vector3(0, 1.5f, 0);
            if (Vector3.Dot(glass.transform.forward, room - glass.transform.position) < 0)
            {
                glass.transform.localPosition = new Vector3(0, 0, -z);
                glass.transform.localRotation = Quaternion.Euler(0, 180, 0);
            }
            glass.GetComponent<MeshFilter>().sharedMesh = mesh;
            var mr = glass.GetComponent<MeshRenderer>();
            mr.sharedMaterial = mat; mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
            mr.lightProbeUsage = LightProbeUsage.Off;

            var nell = PlaceGlb("Art/Characters/Mannequin_Nell.gltf", "Nell (Reflection)", player.transform.position, player.transform.eulerAngles.y, false);
            SkinLegCloth(nell, "Nell");
            var rig = nell.AddComponent<MannequinRig>();
            rig.stride = 16f;

            var refl = glass.AddComponent<MirrorReflection>();
            refl.surface = mr; refl.player = player.transform; refl.fps = fps; refl.body = rig;
            Debug.Log($"[SetupMirror] glass at {glass.transform.position} facing {glass.transform.forward}");
        }
    }
}
