using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 驿站马车 + 两匹木头马：沿路点行驶（起步 / 停车有加减速），车轮按行驶距离转，车厢轻晃，马按速度走步。
    /// 本节点是马车的行驶根（原点在两轴中间的地面，前方 +Z）；模型、马、车夫都是子节点。
    /// 第 1 稿 Visible = false：看不见，只听得到马蹄和车轮（docs/GAME_DESIGN.md）。
    /// </summary>
    public class Coach : MonoBehaviour
    {
        public HorseRig[] horses;
        public AudioSource roll, hooves;
        public AudioClip stopClip;
        public AudioClip[] snorts;
        [Tooltip("Door_L 打开时的局部欧拉角（相对静止）")]
        public Vector3 doorOpenEuler = new(0, -100, 0);

        readonly List<(Transform t, float r)> _wheels = new();
        Transform _body, _door;
        Quaternion _bodyRest, _doorRest;
        readonly Queue<Vector3> _path = new();
        Action _onArrive;
        float _speed, _cruise, _doorK, _doorGoal, _nextSnort;
        bool _visible = true;

        public Transform Exit { get; private set; }
        public bool Moving => _path.Count > 0 || _speed > 0.01f;

        void Awake()
        {
            if (GetComponent<Collider>()) gameObject.AddComponent<InteractPassThrough>();
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                if (t.name.StartsWith("Wheel_"))
                {
                    var r = t.GetComponentsInChildren<Renderer>(true);
                    float radius = r.Length > 0 ? r.Max(x => x.bounds.extents.y) : 0.6f;
                    _wheels.Add((t, Mathf.Max(0.3f, radius)));
                }
                else if (t.name == "Body" && !_body) _body = t;
                else if (t.name == "Door_L") _door = t;
                else if (t.name == "PassengerExit_L") Exit = t;
            }
            if (_body) _bodyRest = _body.localRotation;
            if (_door) _doorRest = _door.localRotation;
            _nextSnort = Time.time + UnityEngine.Random.Range(6f, 14f);
        }

        public bool Visible
        {
            get => _visible;
            set
            {
                _visible = value;
                foreach (var r in GetComponentsInChildren<Renderer>(true)) r.enabled = value;
                foreach (var c in GetComponentsInChildren<Collider>(true)) c.enabled = value;
            }
        }

        public void Place(Vector3 pos, float yaw)
        {
            _path.Clear(); _onArrive = null; _speed = 0;
            transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
        }

        public void Drive(Vector3[] points, float speed, bool instant, Action onArrive = null)
        {
            if (instant)
            {
                var last = points[^1];
                var prev = points.Length > 1 ? points[^2] : transform.position;
                var dir = last - prev; dir.y = 0;
                Place(last, dir.sqrMagnitude > 0.01f ? Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg : transform.eulerAngles.y);
                onArrive?.Invoke();
                return;
            }
            _path.Clear();
            foreach (var p in points) _path.Enqueue(p);
            _cruise = speed; _onArrive = onArrive;
        }

        public void OpenDoor() => _doorGoal = 1f;

        void Update()
        {
            float dt = Time.deltaTime;
            float moved = 0f;
            if (_path.Count > 0)
            {
                // 剩余路程（含后面的路点）决定减速
                float remain = 0f; var from = transform.position;
                foreach (var p in _path) { remain += Vector3.Distance(Flat(from), Flat(p)); from = p; }
                float goal = Mathf.Min(_cruise, Mathf.Sqrt(2f * 0.45f * remain) + 0.05f);
                _speed = Mathf.MoveTowards(_speed, goal, (goal > _speed ? 0.6f : 1.2f) * dt);
                var target = _path.Peek();
                var d = Flat(target) - Flat(transform.position);
                float step = _speed * dt;
                if (d.magnitude <= step)
                {
                    transform.position = new Vector3(target.x, transform.position.y, target.z);
                    moved = d.magnitude;
                    _path.Dequeue();
                    if (_path.Count == 0) Arrive();
                }
                else
                {
                    transform.position += d.normalized * step;
                    var yaw = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
                    transform.rotation = Quaternion.Euler(0, Mathf.MoveTowardsAngle(transform.eulerAngles.y, yaw, 30f * dt), 0);
                    moved = step;
                }
            }
            else _speed = 0f;

            foreach (var (t, r) in _wheels) t.localRotation *= Quaternion.Euler(moved / r * Mathf.Rad2Deg, 0, 0);
            if (horses != null) foreach (var h in horses) if (h) { h.moved += moved; h.speed = dt > 0 ? moved / dt : 0; }

            // 车厢在牛皮吊带上轻晃：走起来前后摇、左右颠
            if (_body)
            {
                float v = _speed, tm = Time.time;
                var sway = Quaternion.Euler(1.6f * v * Mathf.Sin(tm * 2.1f) + 0.4f, 0, 1.1f * v * Mathf.Sin(tm * 1.3f + 0.7f));
                _body.localRotation = Quaternion.Slerp(_body.localRotation, _bodyRest * sway, 1f - Mathf.Exp(-dt * 6f));
            }
            if (_door && !Mathf.Approximately(_doorK, _doorGoal))
            {
                _doorK = Mathf.MoveTowards(_doorK, _doorGoal, dt * 1.4f);
                float s = _doorK * _doorK * (3f - 2f * _doorK);
                _door.localRotation = _doorRest * Quaternion.Euler(doorOpenEuler * s);
            }

            float k = Mathf.Clamp01(_speed / Mathf.Max(0.5f, _cruise));
            if (roll) { roll.volume = 0.8f * k * Sfx.EffectsVolume; if (k > 0.01f && !roll.isPlaying) roll.Play(); }
            if (hooves) { hooves.volume = 0.9f * k * Sfx.EffectsVolume; hooves.pitch = 0.85f + 0.2f * k; if (k > 0.01f && !hooves.isPlaying) hooves.Play(); }
            if (Time.time > _nextSnort && snorts != null && snorts.Length > 0 && horses != null && horses.Length > 0)
            {
                _nextSnort = Time.time + UnityEngine.Random.Range(9f, 20f);
                var h = horses[UnityEngine.Random.Range(0, horses.Length)];
                if (h && _visible) Sfx.I?.PlayAt(snorts[UnityEngine.Random.Range(0, snorts.Length)], h.transform.position + Vector3.up * 1.6f, 0.6f);
            }
        }

        void Arrive()
        {
            _speed = 0;
            if (stopClip) Sfx.I?.PlayAt(stopClip, transform.position + Vector3.up, 0.8f);
            var cb = _onArrive; _onArrive = null;
            cb?.Invoke();
        }

        static Vector3 Flat(Vector3 v) => new(v.x, 0, v.z);
    }
}
