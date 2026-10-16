using UnityEngine;
using UnityEngine.InputSystem;

namespace MercyCreek
{
    /// <summary>第一人称：WASD 走、Shift 快走、鼠标看。走得慢，是酒馆不是战场。</summary>
    [RequireComponent(typeof(CharacterController))]
    public class FirstPersonController : MonoBehaviour
    {
        public Transform head;
        public float walkSpeed = 1.6f;
        public float fastSpeed = 2.8f;
        public float lookSensitivity = 0.08f;
        public float gravity = 9.8f;
        public bool invertY;

        public bool InputLocked { get; set; }

        CharacterController _cc;
        float _pitch, _vy, _bob, _stride;
        Vector3 _headRest;

        void Awake()
        {
            _cc = GetComponent<CharacterController>();
            if (head) _headRest = head.localPosition;
        }

        void OnEnable() { if (!Menus.Blocking) SetCursor(true); }
        void OnDisable() => SetCursor(false);

        static void SetCursor(bool locked)
        {
            if (PlayBot.Active) return;
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }

        /// <summary>自动试玩用：直接设朝向（代替鼠标）。</summary>
        public void SetLook(float yaw, float pitch)
        {
            transform.rotation = Quaternion.Euler(0f, yaw, 0f);
            _pitch = Mathf.Clamp(pitch, -80f, 80f);
            if (head) head.localRotation = Quaternion.Euler(_pitch, 0f, 0f);
        }

        public float Pitch => _pitch;

        void Update()
        {
            var kb = Keyboard.current;
            var mouse = Mouse.current;
            if (kb == null || mouse == null) return;

            // Esc 由 Menus 处理（暂停）；网页版里浏览器可能自己释放鼠标，点一下重新锁定
            if (!Menus.Blocking && mouse.leftButton.wasPressedThisFrame && Cursor.lockState != CursorLockMode.Locked) SetCursor(true);

            Vector2 move = Vector2.zero;
            if (!InputLocked && !Menus.Blocking)
            {
                if (Cursor.lockState == CursorLockMode.Locked)
                {
                    Vector2 d = mouse.delta.ReadValue() * lookSensitivity;
                    transform.Rotate(0f, d.x, 0f);
                    _pitch = Mathf.Clamp(_pitch + (invertY ? d.y : -d.y), -80f, 80f);
                    if (head) head.localRotation = Quaternion.Euler(_pitch, 0f, 0f);
                }
                if (kb.wKey.isPressed) move.y += 1;
                if (kb.sKey.isPressed) move.y -= 1;
                if (kb.dKey.isPressed) move.x += 1;
                if (kb.aKey.isPressed) move.x -= 1;
            }

            float speed = kb.leftShiftKey.isPressed ? fastSpeed : walkSpeed;
            Vector3 v = (transform.right * move.x + transform.forward * move.y).normalized * speed;
            _vy = _cc.isGrounded ? -1f : _vy - gravity * Time.deltaTime;
            v.y = _vy;
            _cc.Move(v * Time.deltaTime);

            // 轻微步伐起伏
            if (head)
            {
                float planar = new Vector2(_cc.velocity.x, _cc.velocity.z).magnitude;
                _bob += planar * Time.deltaTime * 5.5f;
                _stride += planar * Time.deltaTime;
                if (_stride > 0.72f && _cc.isGrounded) { _stride = 0f; Sfx.I?.Step(transform.position, 0.5f); }
                float amp = Mathf.Clamp01(planar / fastSpeed) * 0.025f;
                head.localPosition = _headRest + new Vector3(0f, Mathf.Sin(_bob) * amp, 0f);
            }
        }
    }
}
