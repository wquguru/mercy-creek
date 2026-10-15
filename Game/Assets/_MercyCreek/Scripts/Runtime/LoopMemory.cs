using System.Collections.Generic;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 跨循环保留的东西。场景每轮重新加载，只有这里的数据活下来。
    /// 规则（docs/GAME_DESIGN.md）：每轮最多记住 1 个新碎片。
    /// </summary>
    public static class LoopMemory
    {
        public static int Loop { get; private set; } = 1;
        public static float TotalSeconds { get; set; }
        public static bool RememberedThisLoop { get; private set; }

        static readonly List<string> _fragments = new();
        public static IReadOnlyList<string> Fragments => _fragments;

        public static bool Has(string id) => _fragments.Contains(id);

        /// <returns>true = 这一轮记住了它；false = 已经记得，或本轮名额已用</returns>
        public static bool TryRemember(string id)
        {
            if (Has(id) || RememberedThisLoop) return false;
            _fragments.Add(id);
            RememberedThisLoop = true;
            return true;
        }

        public static void NextLoop()
        {
            Loop++;
            RememberedThisLoop = false;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetForPlayMode()
        {
            // 编辑器关掉域重载时，静态数据会残留到下一次 Play
            Loop = 1; TotalSeconds = 0; RememberedThisLoop = false; _fragments.Clear();
        }
    }
}
