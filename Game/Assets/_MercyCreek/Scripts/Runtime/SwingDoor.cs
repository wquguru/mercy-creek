using UnityEngine;

namespace MercyCreek
{
    /// <summary>绕铰链转开的门。本节点就是铰链，门板是子节点。</summary>
    public class SwingDoor : MonoBehaviour
    {
        public float openAngle = -100f;
        public float speed = 1.6f;
        public Collider blocker;

        float _k, _goal;
        Quaternion _rest = Quaternion.identity;
        bool _init;

        // 门可能是导入模型里的节点（不能改父级），静止朝向不一定是单位旋转：以载入时的朝向为准
        void Awake() => Init();
        void Init() { if (_init) return; _init = true; _rest = transform.localRotation; }

        public bool IsOpen => _goal > 0.5f;

        public void Open(bool instant = false) { _goal = 1f; if (instant) _k = 1f; Apply(); if (blocker) blocker.enabled = false; }
        public void Close(bool instant = false) { _goal = 0f; if (instant) _k = 0f; Apply(); if (blocker) blocker.enabled = true; }

        void Update()
        {
            if (Mathf.Approximately(_k, _goal)) return;
            _k = Mathf.MoveTowards(_k, _goal, Time.deltaTime * speed);
            Apply();
        }

        void Apply()
        {
            Init();
            float s = _k * _k * (3f - 2f * _k);
            transform.localRotation = _rest * Quaternion.Euler(0, openAngle * s, 0);
        }
    }
}
