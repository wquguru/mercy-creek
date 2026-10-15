using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 可以"看"的东西。带 fragmentId 的是记忆碎片：每轮只能记住一个。
    /// 需要先记住若干碎片才会回应的（requiredFragments），用于终局的上锁房间。
    /// </summary>
    public class Interactable : MonoBehaviour
    {
        public string prompt = "查看";
        [TextArea] public string firstText;
        [TextArea] public string rememberedText;
        public string fragmentId;
        public int requiredFragments;
        [TextArea] public string lockedText;
        public bool isEnding;

        public string Use()
        {
            if (requiredFragments > 0 && LoopMemory.Fragments.Count < requiredFragments)
                return lockedText;

            if (isEnding)
            {
                var hud = FindFirstObjectByType<Hud>();
                if (hud) hud.ShowEnding();
                return firstText.Replace("{loop}", LoopMemory.Loop.ToString());
            }

            if (string.IsNullOrEmpty(fragmentId)) return firstText;
            if (LoopMemory.Has(fragmentId)) return rememberedText;
            if (LoopMemory.TryRemember(fragmentId))
            {
                Sfx.I?.Play2D(Sfx.I.remember, 0.8f);
                return firstText + "\n<i>（你决定记住这个。）</i>";
            }
            Sfx.I?.Play2D(Sfx.I.denied, 0.6f);
            return firstText + "\n<i>（你隐约知道，这一轮记不住更多了。）</i>";
        }
    }
}
