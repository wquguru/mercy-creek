using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MercyCreek.EditorTools
{
    public static partial class SetupSaloon
    {
        /// <summary>挂在 Hips 上、垂到腿部的布料（长裙、围裙、风衣后摆）。</summary>
        static readonly string[] LegCloth = { "Cloth_Skirt", "Cloth_Apron", "Cloth_Coat_Tail" };

        /// <summary>
        /// 人偶没有蒙皮（docs/mannequin_rig.md），长裙原先是挂在 Hips 上的刚体壳，迈步时被腿顶穿。
        /// 这里把这几件布料换成蒙皮网格：骨骼直接用人偶已有的关节节点，权重按顶点位置程序生成——
        /// 越往下、越靠一侧，越跟那条腿走；正中间两腿各一半，迈步时裙摆被拉开而不是被刺穿。
        /// 原网格只关掉渲染（导入的 glTF 是 Prefab 实例，不能改层级），蒙皮网格放在它下面的新子节点里。
        /// </summary>
        static void SkinLegCloth(GameObject mannequin, string file)
        {
            var hips = Find(mannequin, "Hips");
            var bones = new[] { "Hips", "L_UpperLeg", "L_LowerLeg", "R_UpperLeg", "R_LowerLeg" }.Select(n => Find(mannequin, n)).ToArray();
            if (!hips || bones.Any(b => !b)) return;
            // 关节在 Hips 局部空间里的位置（静止姿势、所有旋转为单位）
            float legY = hips.InverseTransformPoint(bones[1].position).y;
            float thigh = legY - hips.InverseTransformPoint(bones[2].position).y;
            float halfHip = Mathf.Abs(hips.InverseTransformPoint(bones[1].position).x);

            foreach (var name in LegCloth)
            {
                var node = Find(mannequin, name);
                if (!node || node.parent != hips) continue;
                var mf = node.GetComponent<MeshFilter>(); var mr = node.GetComponent<MeshRenderer>();
                if (!mf || !mr || !mf.sharedMesh) continue;

                var mesh = Object.Instantiate(mf.sharedMesh);
                mesh.name = $"{file}_{name}_Skinned";
                var v = mesh.vertices;
                var w = new BoneWeight[v.Length];
                // 风衣后摆比裙子挺：跟腿少一点
                float gMax = name == "Cloth_Coat_Tail" ? 0.55f : 0.8f;
                for (int i = 0; i < v.Length; i++)
                {
                    Vector3 p = hips.InverseTransformPoint(node.TransformPoint(v[i]));
                    float d = (legY - p.y) / thigh;                                // 0 = 髋关节高度，1 = 膝盖
                    float g = gMax * Mathf.Pow(Mathf.Clamp01(d), 1.3f);            // 跟腿的总比例
                    float h = Mathf.Clamp01((d - 0.9f) / 0.8f) * 0.6f;             // 膝盖以下分一部分给小腿
                    float f = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(0.5f - p.x / (4f * halfHip)));   // 1 = 全跟左腿
                    w[i] = new BoneWeight
                    {
                        boneIndex0 = 0, weight0 = 1f - g,
                        boneIndex1 = 1, weight1 = g * f * (1f - h),
                        boneIndex2 = 2, weight2 = g * f * h,
                        boneIndex3 = 3, weight3 = g * (1f - f) * (1f - h),
                    };
                    // BoneWeight 只有 4 个槽：右小腿那一份并进右大腿（Unity 每顶点默认最多 4 骨骼）
                    w[i].weight3 += g * (1f - f) * h;
                }
                mesh.boneWeights = w;

                var skin = new GameObject(name + "_Skin");
                skin.transform.SetParent(node, false);
                mesh.bindposes = bones.Select(b => b.worldToLocalMatrix * skin.transform.localToWorldMatrix).ToArray();
                mesh.RecalculateBounds();

                string path = $"{Root}/Materials/Skinned/{mesh.name}.asset";
                System.IO.Directory.CreateDirectory(System.IO.Path.GetDirectoryName(path)!);
                var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
                if (existing) { EditorUtility.CopySerialized(mesh, existing); mesh = existing; }   // 保留 GUID，.meta 不变
                else AssetDatabase.CreateAsset(mesh, path);

                var smr = skin.AddComponent<SkinnedMeshRenderer>();
                smr.sharedMesh = mesh;
                smr.bones = bones;
                smr.rootBone = hips;
                smr.sharedMaterials = mr.sharedMaterials;
                smr.shadowCastingMode = mr.shadowCastingMode;
                smr.quality = SkinQuality.Bone4;
                // 迈大步时裙摆会超出静止包围盒
                smr.localBounds = new Bounds(mesh.bounds.center, mesh.bounds.size + Vector3.one * 0.4f);
                mr.enabled = false;
            }
        }
    }
}
