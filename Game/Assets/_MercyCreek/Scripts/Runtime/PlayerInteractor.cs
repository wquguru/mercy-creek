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

        void Update()
        {
            if (hud.ChoicesOpen) { hud.SetPrompt(null); return; }
            Interactable target = null;
            var ray = new Ray(cam.transform.position, cam.transform.forward);
            if (Physics.Raycast(ray, out var hit, reach, ~0, QueryTriggerInteraction.Collide))
                target = hit.collider.GetComponentInParent<Interactable>();
            string prompt = target ? target.Prompt : null;
            if (prompt == null) target = null;

            hud.SetPrompt(target ? $"[E] {prompt}" : null);

            if (!target) return;
            bool use = (Keyboard.current?.eKey.wasPressedThisFrame ?? false)
                       || (Cursor.lockState == CursorLockMode.Locked && (Mouse.current?.leftButton.wasPressedThisFrame ?? false));
            if (use) { var text = target.Use(); if (text != null) hud.Say(text, 7f); }
        }
    }
}
