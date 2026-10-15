# 技术

## 版本
- Unity **6000.3.26f1**（6.3 LTS），装在 `/Applications/Unity/Hub/Editor/6000.3.26f1/`，含 Mac (IL2CPP) 与 Web 模块
  - Hub 在国内会自动走 `download.unitychina.cn` 镜像，该镜像缺文件会 404。要装别的版本 / 模块：从 `download.unity3d.com` 手动下 pkg（aria2 多线程）后解包到上述目录
- URP 17.3（Forward+、SSAO、HDR、MSAA 4x），Input System 1.20（仅新输入系统），Timeline、glTFast 6.20、AI Navigation
- Blender 5.2

## 目录
```
art/source/        CC0 原始资产（git 忽略，tools/fetch_assets.py 可重下）
art/blender/       saloon_blockout.blend（由脚本生成）
tools/blender/build_saloon.py   酒馆白模：建筑 + 道具摆放 + 渲染 / 导出 GLB
tools/review.sh    一键：重建场景 → Mac 构建 → 自动截图（--test 加跑自动通关）
Game/              Unity 工程
  Assets/_MercyCreek/
    Art/Saloon/Saloon.glb       Blender 导出（glTFast 导入）
    Scripts/Runtime/            游戏逻辑
    Scripts/Editor/             SetupSaloon（生成场景）、BuildMac、AddPackages
    Shaders/LightShaft.shader   窗口光柱
    Settings/                   URP 资产、后期 Volume Profile
Reviews/           评审截图
```

## 坐标约定
GLB 导入后根节点绕 Y 转 180°，于是 **Unity (x, y, z) = Blender (x, z, y)**。前墙内侧 z = 0，房间向 +z 延伸到 10，宽 x ∈ [-7, 7]，二楼回廊高 3.2。

## 场景是生成出来的
`Saloon.unity` 由 `SetupSaloon.Build()` 整份重建，**不要在编辑器里手改场景**——改脚本，再跑 `tools/review.sh`。
在编辑器里也可以用菜单 `Mercy Creek → Rebuild Saloon Scene`。

## 运行时系统
| 脚本 | 作用 |
|---|---|
| LoopMemory | 跨循环保留的状态（轮数、碎片、累计时间）；每轮最多记住 1 个新碎片 |
| LoopDirector | 一轮 180 秒：太阳仰角 26°→8°、变红，油灯渐亮；按时间点放字幕；到点褪色、黑场、重载场景 |
| FirstPersonController | WASD / Shift / 鼠标，Esc 释放鼠标 |
| PlayerInteractor + Interactable | 准星交互，E 或左键；碎片、上锁门、结局 |
| Hud | 代码搭的 uGUI：循环数、提示、字幕、黑场、结局卡 |
| LightShaft | 沿太阳方向平移窗口矩形叠 28 张切片，additive + 深度软相交 + 窗棂遮挡 + 浮尘噪声 |
| AutoShot / AutoTest | `-autoshot <dir>` 固定机位截图；`-autotest <dir>` 自动通关并输出 PASS/FAIL |

## 已知问题 / 待办
- 中文字体用的是系统字体（`Font.CreateDynamicFontFromOSFont`），Web 版没有系统字体 → 换 TextMeshPro + 思源黑体子集
- 构建 1.7GB：贴图未压缩、GLB 里 93 张 2K 图。上线前做贴图压缩（ASTC/BC7）、降到 1K、Addressables 分包
- 没有烘焙 GI：靠 Trilight 环境光 + 无阴影补光凑。下一步用 Adaptive Probe Volumes 烘焙
- 没有 NPC、没有音频；剧情事件目前只是字幕
- 自动钢琴是方块占位（等 Tripo）
- Web（WebGPU）构建未验证
