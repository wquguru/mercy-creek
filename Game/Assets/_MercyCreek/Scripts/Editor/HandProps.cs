using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MercyCreek.EditorTools
{
    public static partial class SetupSaloon
    {
        /// <summary>
        /// 人偶的手持道具：格斯擦杯（左手杯、右手布）、倒酒（右手瓶、左手杯），克兰写字（右手笔）。
        /// 道具挂在手掌节点下，握持轴沿手的局部 +Z（手臂下垂时手心朝内，握住的东西前后走向；前臂抬平后就竖起来），
        /// 中心偏向手心一侧。MannequinRig 按当前姿势开关。形状用基本体拼，和木头人偶的"还没画完"一致。
        /// </summary>
        static void AttachHandProps(GameObject saloon, Npc gus, Npc crane)
        {
            var glassMat = FindMaterialByName(saloon, "DirtyGlass");
            var bottleMat = FindMaterialByName(saloon, "wine_bottles_01_glass_green");
            var corkMat = FindMaterialByName(saloon, "wine_bottles_01_seal_cork");
            var brass = FindMaterialByName(saloon, "Brass");
            var wood = FindMaterialByName(saloon, "Trim");
            var cloth = gus.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).FirstOrDefault(m => m && m.name.Contains("ApronCotton"));

            var gusR = Find(gus.gameObject, "R_Hand"); var gusL = Find(gus.gameObject, "L_Hand");
            var craneR = Find(crane.gameObject, "R_Hand");
            if (!gusR || !gusL || !craneR) { Debug.LogWarning("[HandProps] hands not found"); return; }

            // 手心一侧：右手是 -X，左手是 +X
            GameObject Glass(Transform hand, float side)
            {
                var g = Holder(hand, "Prop_Glass", new Vector3(side * 0.046f, -0.082f, 0.0f));
                Piece(g, PrimitiveType.Cylinder, glassMat, new Vector3(0, 0, 0.012f), new Vector3(0.064f, 0.045f, 0.064f));
                return g;
            }

            var pour = new[]
            {
                Bottle(Holder(gusR, "Prop_Bottle", new Vector3(-0.05f, -0.082f, 0.0f))),
                Glass(gusL, 1f),
            };
            GameObject Bottle(GameObject g)
            {
                Piece(g, PrimitiveType.Cylinder, bottleMat, new Vector3(0, 0, 0.03f), new Vector3(0.07f, 0.1f, 0.07f));
                Piece(g, PrimitiveType.Sphere, bottleMat, new Vector3(0, 0, 0.13f), new Vector3(0.07f, 0.07f, 0.05f));
                Piece(g, PrimitiveType.Cylinder, bottleMat, new Vector3(0, 0, 0.18f), new Vector3(0.024f, 0.045f, 0.024f));
                Piece(g, PrimitiveType.Cylinder, corkMat, new Vector3(0, 0, 0.23f), new Vector3(0.02f, 0.01f, 0.02f));
                return g;
            }

            var rag = Holder(gusR, "Prop_Rag", new Vector3(-0.035f, -0.09f, 0.0f));
            Piece(rag, PrimitiveType.Sphere, cloth, Vector3.zero, new Vector3(0.05f, 0.07f, 0.085f));
            Piece(rag, PrimitiveType.Cube, cloth, new Vector3(0, -0.05f, -0.02f), new Vector3(0.008f, 0.08f, 0.06f));
            var wipe = new[] { Glass(gusL, 1f), rag };

            var pen = Holder(craneR, "Prop_Pen", new Vector3(-0.022f, -0.11f, 0.03f));
            pen.transform.localRotation = Quaternion.Euler(-30, 0, 0);   // 笔尖朝前下方，落在纸上
            Piece(pen, PrimitiveType.Cylinder, wood, new Vector3(0, 0, 0.0f), new Vector3(0.008f, 0.075f, 0.008f));
            Piece(pen, PrimitiveType.Cylinder, brass, new Vector3(0, 0, 0.085f), new Vector3(0.006f, 0.012f, 0.006f));

            gus.rig.propsPour = pour;
            gus.rig.propsWipe = wipe;
            crane.rig.propsWrite = new[] { pen };
        }

        static GameObject Holder(Transform hand, string name, Vector3 local)
        {
            var g = new GameObject(name);
            g.transform.SetParent(hand, false);
            g.transform.localPosition = local;
            g.SetActive(false);
            return g;
        }

        /// <summary>基本体圆柱 / 球的轴是 Y：转到握持轴 +Z 上。</summary>
        static void Piece(GameObject holder, PrimitiveType type, Material mat, Vector3 pos, Vector3 size)
        {
            var p = GameObject.CreatePrimitive(type);
            Object.DestroyImmediate(p.GetComponent<Collider>());
            p.transform.SetParent(holder.transform, false);
            p.transform.localPosition = pos;
            p.transform.localRotation = Quaternion.Euler(90, 0, 0);
            p.transform.localScale = type == PrimitiveType.Cube ? new Vector3(size.x, size.z, size.y) : new Vector3(size.x, size.y, size.z);
            var r = p.GetComponent<MeshRenderer>();
            if (mat) r.sharedMaterial = mat;
            r.shadowCastingMode = ShadowCastingMode.Off;
            r.receiveGI = ReceiveGI.LightProbes;
        }

        static Material FindMaterialByName(GameObject saloon, string name) =>
            saloon.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).FirstOrDefault(m => m && m.name == name);
    }
}
