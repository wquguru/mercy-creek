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
            Interactable target = null;
            var ray = new Ray(cam.transform.position, cam.transform.forward);
            if (Physics.Raycast(ray, out var hit, reach, ~0, QueryTriggerInteraction.Collide))
                target = hit.collider.GetComponentInParent<Interactable>();

            hud.SetPrompt(target ? $"[E] {target.prompt}" : null);

            if (!target) return;
            bool use = (Keyboard.current?.eKey.wasPressedThisFrame ?? false)
                       || (Cursor.lockState == CursorLockMode.Locked && (Mouse.current?.leftButton.wasPressedThisFrame ?? false));
            if (use) hud.Say(target.Use());
        }
    }
}
