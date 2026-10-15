using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 窗口光柱：沿太阳方向平移窗口矩形，叠出若干张半透明切片（additive）。
    /// 比真正的体积光便宜得多，Web 端也能跑；太阳角度变化时每帧重建网格。
    /// 物体自身的位置 = 窗口中心，right / up = 窗口平面的两个轴，forward 指向室内。
    /// </summary>
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    [ExecuteAlways]
    public class LightShaft : MonoBehaviour
    {
        public Light sun;
        public Vector2 size = new(2.8f, 1.9f);
        public float length = 9f;
        [Range(4, 48)] public int slices = 28;
        public float intensity = 0.06f;

        Mesh _mesh;
        MeshRenderer _mr;
        MaterialPropertyBlock _mpb;
        static readonly int ColorId = Shader.PropertyToID("_ShaftColor");

        void OnEnable()
        {
            _mesh = new Mesh { name = "LightShaft" };
            _mesh.MarkDynamic();
            GetComponent<MeshFilter>().sharedMesh = _mesh;
            _mr = GetComponent<MeshRenderer>();
            _mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            _mr.receiveShadows = false;
            _mpb = new MaterialPropertyBlock();
        }

        void OnDisable()
        {
            if (_mesh) DestroyImmediate(_mesh);
        }

        void LateUpdate()
        {
            if (!sun) return;
            Vector3 dirWorld = sun.transform.forward;
            float facing = Vector3.Dot(dirWorld, transform.forward);   // 光要从窗外往里照
            _mr.enabled = facing > 0.05f;
            if (!_mr.enabled) return;

            Vector3 dir = transform.InverseTransformDirection(dirWorld);
            Build(dir);

            Color c = sun.color * sun.intensity * intensity * Mathf.Clamp01(facing * 2f) * 28f / slices;
            _mpb.SetColor(ColorId, c);
            _mr.SetPropertyBlock(_mpb);
        }

        void Build(Vector3 dir)
        {
            int n = slices;
            var v = new Vector3[n * 4];
            var uv = new Vector2[n * 4];
            var uv2 = new Vector2[n * 4];
            var tri = new int[n * 6];
            Vector2 h = size * 0.5f;
            Vector3[] corners = { new(-h.x, -h.y, 0), new(h.x, -h.y, 0), new(h.x, h.y, 0), new(-h.x, h.y, 0) };
            Vector2[] cuv = { new(0, 0), new(1, 0), new(1, 1), new(0, 1) };
            for (int i = 0; i < n; i++)
            {
                float t = (i + 0.5f) / n;
                Vector3 off = dir * (t * length);
                for (int k = 0; k < 4; k++)
                {
                    v[i * 4 + k] = corners[k] + off;
                    uv[i * 4 + k] = cuv[k];
                    uv2[i * 4 + k] = new Vector2(t, 0);
                }
                int b = i * 4, o = i * 6;
                tri[o] = b; tri[o + 1] = b + 2; tri[o + 2] = b + 1;
                tri[o + 3] = b; tri[o + 4] = b + 3; tri[o + 5] = b + 2;
            }
            _mesh.Clear();
            _mesh.vertices = v; _mesh.uv = uv; _mesh.uv2 = uv2; _mesh.triangles = tri;
            _mesh.bounds = new Bounds(dir * length * 0.5f, new Vector3(size.x, size.y, 0) + dir.Abs() * length + Vector3.one);
        }
    }

    static class VecExt
    {
        public static Vector3 Abs(this Vector3 v) => new(Mathf.Abs(v.x), Mathf.Abs(v.y), Mathf.Abs(v.z));
    }
}
