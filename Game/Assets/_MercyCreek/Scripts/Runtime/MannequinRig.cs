using System.Collections.Generic;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 木头人偶的程序动画。人偶没有蒙皮，层级就是骨架（docs/mannequin_rig.md）：静止时所有 localRotation 都是单位旋转，
    /// 所以这里直接写"相对静止"的角度。姿势之间平滑过渡；走路按实际移动距离推进步伐相位，脚不打滑。
    /// </summary>
    public class MannequinRig : MonoBehaviour
    {
        public enum Pose { Stand, Wipe, Pour, Lean, Piano, Sit, SitWrite }

        public Pose pose = Pose.Stand;
        [Tooltip("髋部前后摆幅（度）。穿长裙 / 围裙的角色要小，见 docs/mannequin_rig.md")]
        public float stride = 18f;
        public float seatHeight = 0.47f;

        /// <summary>由 Npc 每帧写入：这一帧在地面上走了多远、当前速度。</summary>
        [HideInInspector] public float moved, speed;
        [HideInInspector] public Transform lookTarget;
        [HideInInspector] public float lookWeight;
        /// <summary>说话时轻微点头 / 手势。</summary>
        [HideInInspector] public float talk;

        static readonly string[] Joints =
        {
            "Hips", "Spine", "Chest", "Neck", "Head",
            "L_UpperArm", "L_LowerArm", "L_Hand", "L_Fingers", "L_FingersTip", "L_Thumb",
            "R_UpperArm", "R_LowerArm", "R_Hand", "R_Fingers", "R_FingersTip", "R_Thumb",
            "L_UpperLeg", "L_LowerLeg", "L_Foot", "R_UpperLeg", "R_LowerLeg", "R_Foot",
        };

        readonly Dictionary<string, Transform> _t = new();
        static readonly Dictionary<string, int> Index = new();
        readonly Vector3[] _cur = new Vector3[Joints.Length], _goal = new Vector3[Joints.Length];

        static MannequinRig()
        {
            for (int i = 0; i < Joints.Length; i++) Index[Joints[i]] = i;
        }
        Vector3 _hipsRest, _hipsOffset;
        float _phase, _legLen, _walkBlend, _seed;

        void Awake()
        {
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (System.Array.IndexOf(Joints, t.name) >= 0 && !_t.ContainsKey(t.name)) _t[t.name] = t;
            if (_t.TryGetValue("Hips", out var hips)) _hipsRest = hips.localPosition;
            _legLen = _t.ContainsKey("L_UpperLeg") ? _t["L_UpperLeg"].position.y - transform.position.y : 0.9f;
            _seed = Random.value * 10f;
        }

        public bool Valid => _t.Count >= 20;

        void LateUpdate()
        {
            if (!Valid) return;
            float time = Time.time + _seed;
            System.Array.Clear(_goal, 0, _goal.Length);
            Vector3 hipsGoal = Vector3.zero;

            // ---------- 基础姿势 ----------
            switch (pose)
            {
                case Pose.Stand:
                    Arms(-4, -12, -4, -12);
                    break;
                case Pose.Wipe:   // 左手端杯，右手拿布在杯里打圈
                    Arms(-28, -78, -38, -70);
                    G("R_UpperArm") += new Vector3(6 * Mathf.Cos(time * 3.2f), 0, 7 * Mathf.Sin(time * 3.2f));
                    G("R_LowerArm") += new Vector3(8 * Mathf.Sin(time * 3.2f), 0, 0);
                    Grip("L", 55); Grip("R", 35);
                    G("Head") += new Vector3(14, 0, 0);
                    break;
                case Pose.Pour:   // 右手举瓶倾斜
                    Arms(-25, -70, -58, -48);
                    G("R_Hand") += new Vector3(0, 0, 35);
                    Grip("L", 55); Grip("R", 60);
                    G("Head") += new Vector3(18, 0, 0);
                    break;
                case Pose.Lean:   // 双肘撑在吧台上
                    Arms(-38, -82, -38, -82);
                    G("Spine") += new Vector3(8, 0, 0);
                    Grip("L", 25); Grip("R", 40);
                    break;
                case Pose.Piano:
                    Sit(ref hipsGoal);
                    Arms(-24, -66, -24, -66);
                    G("L_LowerArm") += new Vector3(0, 80, 0);
                    G("R_LowerArm") += new Vector3(0, -80, 0);
                    // 两只手沿琴键左右移动，手指交替按键
                    G("L_UpperArm") += new Vector3(0, 0, -8 + 6 * Mathf.Sin(time * 1.3f));
                    G("R_UpperArm") += new Vector3(0, 0, 8 + 6 * Mathf.Sin(time * 1.1f + 1));
                    G("L_Fingers") += new Vector3(0, 0, 25 + 20 * Mathf.Max(0, Mathf.Sin(time * 11f)));
                    G("R_Fingers") += new Vector3(0, 0, -25 - 20 * Mathf.Max(0, Mathf.Sin(time * 9f + 2)));
                    G("Chest") += new Vector3(4, 3 * Mathf.Sin(time * 1.86f), 0);   // 跟着 3/4 拍轻晃
                    G("Head") += new Vector3(12 + 3 * Mathf.Sin(time * 3.7f), 0, 0);
                    break;
                case Pose.Sit:
                    Sit(ref hipsGoal);
                    Arms(-30, -55, -30, -55);
                    break;
                case Pose.SitWrite:   // 左手按住本子，右手写字，低头
                    Sit(ref hipsGoal);
                    Arms(-26, -74, -30, -70);
                    G("R_Hand") += new Vector3(6 * Mathf.Sin(time * 7f), 0, 4 * Mathf.Sin(time * 3f));
                    G("R_UpperArm") += new Vector3(0, 0, 4 * Mathf.Sin(time * 0.7f));
                    Grip("R", 50);
                    G("Chest") += new Vector3(10, 0, 0);
                    G("Head") += new Vector3(24, 0, 0);
                    break;
            }

            // ---------- 走路（按移动距离推进相位） ----------
            float stepLen = 2f * _legLen * Mathf.Sin(stride * Mathf.Deg2Rad) * 2f;   // 一个完整步态周期 = 两步
            _phase += moved / Mathf.Max(0.2f, stepLen) * Mathf.PI * 2f;
            moved = 0f;
            _walkBlend = Mathf.MoveTowards(_walkBlend, speed > 0.05f ? 1f : 0f, Time.deltaTime * 4f);
            if (_walkBlend > 0f)
            {
                float w = _walkBlend, s = Mathf.Sin(_phase), c = Mathf.Cos(_phase);
                Leg("L", -stride * s, c, w);
                Leg("R", stride * s, -c, w);
                G("L_UpperArm") += new Vector3(stride * 0.7f * s, 0, 0) * w;
                G("R_UpperArm") += new Vector3(-stride * 0.7f * s, 0, 0) * w;
                G("L_LowerArm") += new Vector3(-10, 0, 0) * w;
                G("R_LowerArm") += new Vector3(-10, 0, 0) * w;
                G("Hips") += new Vector3(0, 5 * s, 0) * w;
                G("Chest") += new Vector3(2, -6 * s, 0) * w;
                hipsGoal.y += -0.022f * Mathf.Abs(Mathf.Cos(_phase)) * w;
            }

            // ---------- 呼吸 ----------
            G("Chest") += new Vector3(1.2f * Mathf.Sin(time * 1.4f), 0, 0);

            // ---------- 说话 ----------
            if (talk > 0f)
            {
                G("Head") += new Vector3(4 * Mathf.Sin(time * 5f) * talk, 0, 0);
                talk = Mathf.MoveTowards(talk, 0f, Time.deltaTime * 0.5f);
            }

            // ---------- 平滑过渡，写回骨骼 ----------
            float k = 1f - Mathf.Exp(-Time.deltaTime * 7f);
            for (int i = 0; i < Joints.Length; i++)
            {
                _cur[i] = Vector3.Lerp(_cur[i], _goal[i], k);
                if (_t.TryGetValue(Joints[i], out var tr)) tr.localRotation = Quaternion.Euler(_cur[i]);
            }
            _hipsOffset = Vector3.Lerp(_hipsOffset, hipsGoal, k);
            _t["Hips"].localPosition = _hipsRest + _hipsOffset;

            // ---------- 看向目标（叠加在动画之后，分给脖子和头） ----------
            if (lookTarget && lookWeight > 0.01f)
            {
                var head = _t["Head"];
                Vector3 local = transform.InverseTransformDirection(lookTarget.position - head.position);
                float yaw = Mathf.Clamp(Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg, -75f, 75f);
                float pitch = Mathf.Clamp(-Mathf.Atan2(local.y, new Vector2(local.x, local.z).magnitude) * Mathf.Rad2Deg, -30f, 35f);
                _t["Neck"].localRotation *= Quaternion.Euler(pitch * 0.3f * lookWeight, yaw * 0.4f * lookWeight, 0);
                // 头的目标覆盖掉姿势里的低头
                head.localRotation = Quaternion.Slerp(head.localRotation, Quaternion.Euler(pitch * 0.7f, yaw * 0.6f, 0), lookWeight);
            }
        }

        ref Vector3 G(string j) => ref _goal[Index[j]];

        void Arms(float lUp, float lLow, float rUp, float rLow)
        {
            G("L_UpperArm") += new Vector3(lUp, 0, 0); G("L_LowerArm") += new Vector3(lLow, 0, 0);
            G("R_UpperArm") += new Vector3(rUp, 0, 0); G("R_LowerArm") += new Vector3(rLow, 0, 0);
            Grip("L", 15); Grip("R", 15);
        }

        void Grip(string side, float deg)
        {
            float s = side == "L" ? 1f : -1f;
            G(side + "_Fingers") = new Vector3(0, 0, s * deg);
            G(side + "_FingersTip") = new Vector3(0, 0, s * deg * 0.9f);
            G(side + "_Thumb") = new Vector3(0, 0, s * deg * 0.5f);
        }

        void Sit(ref Vector3 hipsGoal)
        {
            // 髋关节落到椅面高度上方一点，大腿水平，小腿垂直
            hipsGoal.y = seatHeight + 0.06f - _hipsRest.y;
            hipsGoal.z = -0.05f;
            G("L_UpperLeg") += new Vector3(-88, 0, -3); G("R_UpperLeg") += new Vector3(-88, 0, 3);
            G("L_LowerLeg") += new Vector3(92, 0, 0); G("R_LowerLeg") += new Vector3(92, 0, 0);
            G("Spine") += new Vector3(3, 0, 0);
        }

        /// <param name="hip">屈髋角（负 = 向前）</param>
        /// <param name="swing">cos 相位：&gt;0 表示这条腿在向前摆（腾空期），膝盖弯</param>
        void Leg(string side, float hip, float swing, float w)
        {
            float knee = 6f + 48f * Mathf.Pow(Mathf.Max(0f, swing), 1.5f);
            float foot = -0.25f * knee + 10f * Mathf.Max(0f, -swing) * Mathf.Max(0f, hip / stride);
            G(side + "_UpperLeg") += new Vector3(hip, 0, 0) * w;
            G(side + "_LowerLeg") += new Vector3(knee, 0, 0) * w;
            G(side + "_Foot") += new Vector3(foot, 0, 0) * w;
        }
    }
}
