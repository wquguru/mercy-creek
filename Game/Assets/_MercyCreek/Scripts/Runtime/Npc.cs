using System;
using System.Collections.Generic;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 一个人偶角色：沿路点走（可以上楼梯，y 按路点线性插值）、到点换姿势、转身、看人、说话。
    /// 剧情由 Story 调用；instant = true 时直接落到终点（评审 / 测试快进用）。
    /// </summary>
    public class Npc : MonoBehaviour
    {
        public string id;
        public string nameKey;
        public MannequinRig rig;
        public float walkSpeed = 1.1f;

        readonly Queue<Vector3> _path = new();
        Action _onArrive;
        MannequinRig.Pose _endPose;
        float? _endYaw;
        float _yawGoal, _lookUntil;
        Transform _player;

        public bool Walking => _path.Count > 0;
        public string DisplayName => Loc.T(nameKey);

        void Awake()
        {
            if (!rig) rig = GetComponentInChildren<MannequinRig>();
            _yawGoal = transform.eulerAngles.y;
        }

        void Start() => _player = Camera.main ? Camera.main.transform : null;

        public void Place(Vector3 pos, float yaw, MannequinRig.Pose pose)
        {
            _path.Clear(); _onArrive = null;
            transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
            _yawGoal = yaw;
            if (rig) { rig.pose = pose; rig.speed = 0; }
        }

        public void WalkTo(Vector3[] points, MannequinRig.Pose endPose, float? endYaw, bool instant, Action onArrive = null)
        {
            if (instant || points.Length == 0)
            {
                var last = points.Length > 0 ? points[^1] : transform.position;
                float yaw = endYaw ?? (points.Length > 1 ? Yaw(points[^2], last) : transform.eulerAngles.y);
                Place(last, yaw, endPose);
                onArrive?.Invoke();
                return;
            }
            _path.Clear();
            foreach (var p in points) _path.Enqueue(p);
            _endPose = endPose; _endYaw = endYaw; _onArrive = onArrive;
            if (rig) rig.pose = MannequinRig.Pose.Stand;
        }

        public void Face(float yaw) => _yawGoal = yaw;

        public void SetPose(MannequinRig.Pose pose) { if (rig) rig.pose = pose; }

        public void LookAtPlayer(float seconds) { if (rig) rig.lookTarget = _player; _lookUntil = Time.time + seconds; }

        public void LookAt(Transform t, float seconds) { if (rig) rig.lookTarget = t; _lookUntil = Time.time + seconds; }

        /// <summary>在字幕里说一句话，同时点头、看向玩家。</summary>
        public void Say(Hud hud, string key, float seconds = 5f, params object[] args)
        {
            hud.Say(Loc.Line(nameKey, key, args), seconds);
            if (rig) rig.talk = 1f;
            LookAtPlayer(seconds);
        }

        void Update()
        {
            float dt = Time.deltaTime;
            float moved = 0f;
            if (_path.Count > 0)
            {
                var target = _path.Peek();
                var pos = transform.position;
                var flat = new Vector3(target.x - pos.x, 0, target.z - pos.z);
                float step = walkSpeed * dt;
                if (flat.magnitude <= step)
                {
                    moved = flat.magnitude;
                    transform.position = target;
                    _path.Dequeue();
                    if (_path.Count == 0) Arrive();
                }
                else
                {
                    // y 跟着水平进度插值（楼梯）
                    float frac = step / flat.magnitude;
                    transform.position = new Vector3(pos.x + flat.x * frac, Mathf.Lerp(pos.y, target.y, frac), pos.z + flat.z * frac);
                    _yawGoal = Mathf.Atan2(flat.x, flat.z) * Mathf.Rad2Deg;
                    moved = step;
                }
            }
            if (rig)
            {
                rig.moved += moved;
                rig.speed = dt > 0 ? moved / dt : 0f;
                rig.lookWeight = Mathf.MoveTowards(rig.lookWeight, Time.time < _lookUntil && rig.lookTarget ? 1f : 0f, dt * 2f);
            }
            float yaw = Mathf.MoveTowardsAngle(transform.eulerAngles.y, _yawGoal, 240f * dt);
            transform.rotation = Quaternion.Euler(0, yaw, 0);
        }

        void Arrive()
        {
            if (rig) rig.pose = _endPose;
            if (_endYaw.HasValue) _yawGoal = _endYaw.Value;
            var cb = _onArrive; _onArrive = null;
            cb?.Invoke();
        }

        static float Yaw(Vector3 from, Vector3 to) => Mathf.Atan2(to.x - from.x, to.z - from.z) * Mathf.Rad2Deg;
    }
}
