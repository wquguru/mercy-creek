using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace MercyCreek
{
    /// <summary>
    /// 镜子的平面反射：把当前相机沿镜面翻过去渲染到一张 RT（网页版半分辨率），镜面按屏幕坐标采样（Mirror.shader）。
    /// 玩家第一人称没有身体，镜子里站着的是内尔的木头人偶（"镜中人偶"碎片的画面本身）：
    /// 它跟着玩家走、转头，只在反射相机里渲染。第 4 稿起它慢半拍（GAME_DESIGN.md 的轮次变化）。
    /// 只在玩家走近、镜面在画面里时才渲染，平时不花一帧。
    /// </summary>
    public class MirrorReflection : MonoBehaviour
    {
        public static MirrorReflection Instance { get; private set; }

        public Renderer surface;
        public Transform player;
        public FirstPersonController fps;
        public MannequinRig body;
        public float activeDistance = 7f;
        [Tooltip("第 4 稿起倒影落后的秒数")]
        public float lag = 0.45f;

        Camera _cam;
        RenderTexture _rt;
        Renderer[] _bodyRenderers;
        Material _mat;
        readonly Queue<(float t, Vector3 pos, float yaw, float pitch)> _hist = new();
        Vector3 _lastPos;
        float _wave;

        void Awake()
        {
            Instance = this;
            _mat = surface.material;
            var go = new GameObject("Mirror Camera");
            go.transform.SetParent(transform, false);
            _cam = go.AddComponent<Camera>();
            _cam.enabled = false;
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = false;   // 镜面画进主相机的 HDR 缓冲后再统一做色调映射
            data.antialiasing = AntialiasingMode.None;
            data.requiresDepthTexture = false;
            data.requiresColorTexture = false;
            if (body)
            {
                _bodyRenderers = body.GetComponentsInChildren<Renderer>(true);
                SetBodyVisible(false);
                _lastPos = body.transform.position;
            }
            RenderPipelineManager.beginCameraRendering += OnBegin;
            RenderPipelineManager.endCameraRendering += OnEnd;
        }

        void OnDestroy()
        {
            RenderPipelineManager.beginCameraRendering -= OnBegin;
            RenderPipelineManager.endCameraRendering -= OnEnd;
            if (_rt) _rt.Release();
            if (Instance == this) Instance = null;
        }

        /// <summary>和玩家一起抬手（看镜子时）。</summary>
        public void Wave() => _wave = 2.4f;

        void SetBodyVisible(bool v)
        {
            if (_bodyRenderers == null) return;
            foreach (var r in _bodyRenderers) r.forceRenderingOff = !v;
        }

        void OnBegin(ScriptableRenderContext ctx, Camera cam)
        {
            if (cam != _cam) return;
            GL.invertCulling = true;   // 镜像矩阵翻转了三角形绕序
            SetBodyVisible(true);
        }

        void OnEnd(ScriptableRenderContext ctx, Camera cam)
        {
            if (cam != _cam) return;
            GL.invertCulling = false;
            SetBodyVisible(false);
        }

        void LateUpdate()
        {
            UpdateBody();
            var src = Camera.main;
            if (!src || !surface) { _cam.enabled = false; return; }

            Vector3 n = surface.transform.forward, p = surface.transform.position;
            Vector3 toCam = src.transform.position - p;
            bool facing = Vector3.Dot(toCam, n) > 0.05f;
            bool near = toCam.magnitude < activeDistance;
            bool visible = surface.isVisible;
            _cam.enabled = facing && near && visible;
            if (!_cam.enabled) return;

            // 网页版半分辨率省 GPU；桌面版全分辨率 + 2×MSAA，镜中人偶的轮廓才不糊
            bool web = Application.platform == RuntimePlatform.WebGLPlayer;
            int div = web ? 2 : 1;
            int w = Mathf.Max(64, src.pixelWidth / div), h = Mathf.Max(64, src.pixelHeight / div);
            if (!_rt || _rt.width != w || _rt.height != h)
            {
                if (_rt) _rt.Release();
                _rt = new RenderTexture(w, h, 24, RenderTextureFormat.DefaultHDR) { name = "Mirror RT", antiAliasing = web ? 1 : 2 };
                _cam.targetTexture = _rt;
                _mat.SetTexture("_ReflTex", _rt);
            }

            // 镜像矩阵：沿镜面 (n, d) 反射
            float d = -Vector3.Dot(n, p);
            var R = new Matrix4x4();
            R.m00 = 1 - 2 * n.x * n.x; R.m01 = -2 * n.x * n.y; R.m02 = -2 * n.x * n.z; R.m03 = -2 * d * n.x;
            R.m10 = -2 * n.y * n.x; R.m11 = 1 - 2 * n.y * n.y; R.m12 = -2 * n.y * n.z; R.m13 = -2 * d * n.y;
            R.m20 = -2 * n.z * n.x; R.m21 = -2 * n.z * n.y; R.m22 = 1 - 2 * n.z * n.z; R.m23 = -2 * d * n.z;
            R.m33 = 1;

            _cam.CopyFrom(src);
            _cam.targetTexture = _rt;
            _cam.enabled = true;
            _cam.transform.position = R.MultiplyPoint(src.transform.position);
            _cam.worldToCameraMatrix = src.worldToCameraMatrix * R;
            // 斜裁剪面贴着镜面，镜子后面的墙不会挡住倒影
            var view = _cam.worldToCameraMatrix;
            Vector3 cp = view.MultiplyPoint(p + n * 0.01f), cn = view.MultiplyVector(n).normalized;
            _cam.projectionMatrix = src.CalculateObliqueMatrix(new Vector4(cn.x, cn.y, cn.z, -Vector3.Dot(cp, cn)));
        }

        /// <summary>人偶身体跟随玩家：位置、朝向、头的俯仰；走路速度喂给 MannequinRig，脚步按移动距离推进。</summary>
        void UpdateBody()
        {
            if (!body || !player) return;
            float now = Time.time;
            float pitch = fps ? fps.Pitch : 0f;
            _hist.Enqueue((now, player.position, player.eulerAngles.y, pitch));
            bool lagging = LoopMemory.Loop >= 4;
            float delay = lagging ? lag : 0f;
            var s = _hist.Peek();
            while (_hist.Count > 1 && _hist.Peek().t < now - delay) s = _hist.Dequeue();

            var t = body.transform;
            Vector3 flat = s.pos - _lastPos; flat.y = 0;
            t.SetPositionAndRotation(s.pos, Quaternion.Euler(0, s.yaw, 0));
            body.moved += flat.magnitude;
            body.speed = flat.magnitude / Mathf.Max(Time.deltaTime, 1e-4f);
            _lastPos = s.pos;
            body.headPitch = s.pitch;
            if (_wave > 0f) _wave -= Time.deltaTime;
            body.wave = _wave > 0f ? Mathf.Min(1f, _wave * 2f) : 0f;
        }
    }
}
