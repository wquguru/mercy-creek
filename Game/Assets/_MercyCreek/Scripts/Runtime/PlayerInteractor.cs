using UnityEngine;
using UnityEngine.InputSystem;

namespace MercyCreek
{
    /// <summary>准星对准 Interactable 时显示提示，按 E / 左键使用。</summary>
    public class PlayerInteractor : MonoBehaviour
    {
        public Camera cam;
        public float reach = 2.4f;
        public Hud hud;

        readonly RaycastHit[] _hits = new RaycastHit[16];
        static readonly System.Collections.Generic.IComparer<RaycastHit> HitOrder = System.Collections.Generic.Comparer<RaycastHit>.Create((a, b) => a.distance.CompareTo(b.distance));

        void Update()
        {
            if (hud.ChoicesOpen || hud.BookOpen) { hud.SetPrompt(null); return; }   // 记忆本打开时不显示、也不响应 E
            Interactable target = null;
            var ray = new Ray(cam.transform.position, cam.transform.forward);
            // 由近到远：第一个有提示的可交互物；碰到实心的东西就停（标了 InteractPassThrough 的粗碰撞盒除外）
            string prompt = null;
            int n = Physics.RaycastNonAlloc(ray, _hits, reach, ~0, QueryTriggerInteraction.Collide);
            System.Array.Sort(_hits, 0, n, HitOrder);
            for (int i = 0; i < n; i++)
            {
                var c = _hits[i].collider;
                var it = c.GetComponentInParent<Interactable>();
                if (it && (prompt = it.Prompt) != null) { target = it; break; }
                if (!c.isTrigger && !c.GetComponent<InteractPassThrough>()) break;
            }

            hud.SetPrompt(target ? $"[E] {prompt}" : null);

            if (!target) return;
            bool use = (Keyboard.current?.eKey.wasPressedThisFrame ?? false)
                       || (Cursor.lockState == CursorLockMode.Locked && (Mouse.current?.leftButton.wasPressedThisFrame ?? false));
            if (use) { var text = target.Use(); if (text != null) hud.Say(text, 7f); }
        }
    }
}
