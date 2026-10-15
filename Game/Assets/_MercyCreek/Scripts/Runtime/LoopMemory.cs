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

        /// <summary>玩家看到的"第 N 稿"：第一轮就是第 12 稿（玛莎是第 11 稿的人，见 GAME_DESIGN.md）。</summary>
        public static int Draft => Loop + 11;
        public static int DraftOf(int loop) => loop + 11;

        /// <summary>评审 / 测试 / 宣传片启动：跳过开场打字页和稿数卡。</summary>
        public static bool Automated { get; set; }

        /// <summary>评审截图用：`-loop N` 直接从第 N 轮开始。</summary>
        public static void SetLoop(int loop) { Loop = Mathf.Max(1, loop); RememberedThisLoop = false; }
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

        /// <summary>上一次达成的结局（Story.Ending 的名字），给标题画面 / 分享卡片用。</summary>
        public static string LastEnding { get; set; }

        /// <summary>重置结局：一切归零，从第 1 稿重新开始。</summary>
        public static void Clear()
        {
            Loop = 1; TotalSeconds = 0; RememberedThisLoop = false; _fragments.Clear();
        }

        /// <summary>标题画面按过"开始 / 继续"之后为 true；评审 / 测试启动时直接为 true。</summary>
        public static bool Started { get; set; }

        // ---------- 存档：每轮开始时自动保存，结局后清除 ----------
        const string SaveKey = "save.v1";

        [System.Serializable]
        class SaveData { public int loop; public float total; public string[] fragments; }

        public static bool HasSave => PlayerPrefs.HasKey(SaveKey);

        public static int SavedLoop => HasSave ? JsonUtility.FromJson<SaveData>(PlayerPrefs.GetString(SaveKey)).loop : 0;

        public static void Save()
        {
            if (Loop <= 1 && _fragments.Count == 0) return;
            PlayerPrefs.SetString(SaveKey, JsonUtility.ToJson(new SaveData { loop = Loop, total = TotalSeconds, fragments = _fragments.ToArray() }));
            PlayerPrefs.Save();
        }

        public static void Load()
        {
            if (!HasSave) return;
            var d = JsonUtility.FromJson<SaveData>(PlayerPrefs.GetString(SaveKey));
            Loop = Mathf.Max(1, d.loop); TotalSeconds = d.total; RememberedThisLoop = false;
            _fragments.Clear(); _fragments.AddRange(d.fragments ?? new string[0]);
        }

        public static void DeleteSave() { PlayerPrefs.DeleteKey(SaveKey); PlayerPrefs.Save(); }

        public static void NextLoop()
        {
            Loop++;
            RememberedThisLoop = false;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetForPlayMode()
        {
            // 编辑器关掉域重载时，静态数据会残留到下一次 Play
            Clear(); LastEnding = null; Started = false; Automated = false;
        }
    }
}
