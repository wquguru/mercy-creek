using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 自动通关测试：`-autotest <截图目录>` 启动。
    /// 每轮记住一个新碎片 → 快进到循环结束 → 场景重载后继续（本组件随场景重建，状态在 LoopMemory）。
    /// 集齐后开上锁的门，等结局卡出现，截图并输出 PASS / FAIL。
    /// </summary>
    public class AutoTest : MonoBehaviour
    {
        const int MaxLoops = 8;

        IEnumerator Start()
        {
            string dir = Arg("-autotest");
            if (dir == null) { enabled = false; yield break; }
            Directory.CreateDirectory(dir);

            var player = FindFirstObjectByType<FirstPersonController>();
            if (player) player.enabled = false;
            var director = FindFirstObjectByType<LoopDirector>();
            var hud = FindFirstObjectByType<Hud>();
            var all = FindObjectsByType<Interactable>(FindObjectsSortMode.None);
            yield return new WaitForSeconds(2f);

            Log($"loop {LoopMemory.Loop} start, fragments={LoopMemory.Fragments.Count}");

            // 上锁的门：碎片够了就开
            var locked = all.FirstOrDefault(i => i.requiredFragments > 0);
            if (locked && LoopMemory.Fragments.Count >= locked.requiredFragments)
            {
                Log("open locked door: " + locked.Use().Replace("\n", " / "));
                yield return new WaitForSeconds(8f);
                ScreenCapture.CaptureScreenshot(Path.Combine(dir, "ending.png"));
                yield return null;
                Log(director && !director.enabled ? "PASS ending reached" : "FAIL director still running after ending");
                yield return new WaitForSeconds(0.5f);
                Application.Quit();
                yield break;
            }

            if (LoopMemory.Loop > MaxLoops) { Log("FAIL too many loops"); Application.Quit(); yield break; }

            // 先验证"已用名额"分支：同一轮第二个碎片应被拒绝
            var fresh = all.Where(i => !string.IsNullOrEmpty(i.fragmentId) && !LoopMemory.Has(i.fragmentId)).ToList();
            if (locked) Log("locked door says: " + locked.Use());
            if (fresh.Count > 0)
            {
                Log($"use {fresh[0].fragmentId}: " + fresh[0].Use().Replace("\n", " / "));
                if (fresh.Count > 1)
                {
                    string second = fresh[1].Use();
                    Log($"use {fresh[1].fragmentId} (same loop): " + second.Replace("\n", " / "));
                    if (LoopMemory.Has(fresh[1].fragmentId)) Log("FAIL remembered two fragments in one loop");
                }
            }

            // 快进到循环末尾，截一张重置特效
            director.Skip(director.loopSeconds - 0.05f);
            yield return new WaitForSecondsRealtime(1.2f);
            if (LoopMemory.Loop == 1) ScreenCapture.CaptureScreenshot(Path.Combine(dir, "reset.png"));
        }

        static void Log(string s) => Debug.Log("[AutoTest] " + s);

        static string Arg(string name)
        {
            var a = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
