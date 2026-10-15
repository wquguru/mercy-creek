using UnityEngine;

namespace MercyCreek
{
    /// <summary>可以看 / 用 / 对话的东西。具体行为全在 Story 里按 id 分派，这里只是一个碰撞体上的标签。</summary>
    public class Interactable : MonoBehaviour
    {
        public string id;

        public string Prompt => Story.I ? Story.I.Prompt(id) : null;

        public string Use() => Story.I ? Story.I.Use(id) : null;
    }
}
