using System.Collections.Generic;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 木头人偶马的程序动画（docs/horse_rig.md）：没有蒙皮，层级就是骨架，静止时 localRotation 都是单位旋转。
    /// 四拍慢步（左后 → 左前 → 右后 → 右前），相位按实际移动距离推进，蹄子不打滑；停下来时低头、甩尾、偶尔跺蹄。
    /// 角度约定：绕局部 X 转，负值 = 往前摆（与人偶相同，面朝 +Z）。
    /// </summary>
    public class HorseRig : MonoBehaviour
    {
        [Tooltip("一个完整步态周期（四拍）走过的距离，米")]
        public float cycleLength = 1.2f;   // docs/horse_rig.md：±20° 时一个周期约 1.15 m
        public float upperAmp = 20f, lowerFlex = 50f, pasternFlex = 40f;
        [Tooltip("前腿 / 后腿膝关节弯曲方向（前腿腕关节向后弯，后腿飞节向前弯）")]
        public float foreKneeSign = 1f, hindKneeSign = -1f;

        const float Stance = 0.62f;

        [HideInInspector] public float moved, speed;

        static readonly string[] Legs = { "FL", "FR", "HL", "HR" };
        // 四拍慢步的相位偏移（周期 0..1）：左后 0、左前 0.25、右后 0.5、右前 0.75
        static readonly Dictionary<string, float> Offset = new() { ["HL"] = 0f, ["FL"] = 0.25f, ["HR"] = 0.5f, ["FR"] = 0.75f };

        readonly Dictionary<string, Transform> _t = new();
        readonly Dictionary<Transform, Quaternion> _rest = new();
        float _phase, _blend, _seed;

        void Awake()
        {
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (!_t.ContainsKey(t.name)) { _t[t.name] = t; _rest[t] = t.localRotation; }
            _seed = Random.value * 10f;
        }

        void LateUpdate()
        {
            float dt = Time.deltaTime, tm = Time.time + _seed;
            _phase += moved / Mathf.Max(0.5f, cycleLength);
            moved = 0f;
            _blend = Mathf.MoveTowards(_blend, speed > 0.05f ? 1f : 0f, dt * 2.5f);

            foreach (var leg in Legs)
            {
                bool fore = leg[0] == 'F';
                // 着地往后推（占 62%，docs/horse_rig.md），其余抬腿往前摆
                float p = Mathf.Repeat(_phase + Offset[leg], 1f);
                float swing = p < Stance ? Mathf.Lerp(-1f, 1f, p / Stance) : Mathf.Lerp(1f, -1f, (p - Stance) / (1f - Stance));
                float lift = p >= Stance ? Mathf.Sin((p - Stance) / (1f - Stance) * Mathf.PI) : 0f;
                float up = upperAmp * swing * (fore ? 0.85f : 1f);
                float low = lowerFlex * lift * (fore ? foreKneeSign : hindKneeSign);
                float past = pasternFlex * lift * (fore ? 1f : 0.8f);
                Set(leg + "_Upper", new Vector3(up * _blend, 0, 0));
                Set(leg + "_Lower", new Vector3(low * _blend, 0, 0));
                Set(leg + "_Pastern", new Vector3(past * _blend, 0, 0));
            }

            // 走路时头颈随步点头；停下来低头、偶尔甩头
            float nod = Mathf.Sin(_phase * Mathf.PI * 4f);
            float idleHead = 8f + 3f * Mathf.Sin(tm * 0.4f) + 6f * Mathf.Max(0, Mathf.Sin(tm * 0.23f) - 0.8f) * 5f;
            Set("Neck", new Vector3(Mathf.Lerp(idleHead, 4f * nod, _blend), 2f * Mathf.Sin(tm * 0.3f), 0));
            Set("Head", new Vector3(Mathf.Lerp(4f, 3f * nod, _blend), 0, 0));
            Set("Tail", new Vector3(8f + 4f * Mathf.Sin(tm * 1.1f), 14f * Mathf.Sin(tm * 0.9f) * (1f - 0.6f * _blend), 0));
            Set("Body", new Vector3(0.8f * nod * _blend, 0, 1.2f * Mathf.Sin(_phase * Mathf.PI * 2f) * _blend));
        }

        void Set(string joint, Vector3 euler)
        {
            if (!_t.TryGetValue(joint, out var t)) return;
            var goal = _rest[t] * Quaternion.Euler(euler);
            t.localRotation = Quaternion.Slerp(t.localRotation, goal, 1f - Mathf.Exp(-Time.deltaTime * 14f));
        }
    }
}
