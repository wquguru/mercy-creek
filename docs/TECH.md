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
tools/playbot.sh   像真人一样试玩（虚拟键盘、寻路、静音、后台窗口），三个结局各走一遍
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
建筑类 glTF（Saloon / StreetBackdrop / Town / TownEdges）导入后根节点绕 Y 转 180°，于是 **Unity (x, y, z) = Blender (x, z, y)**。前墙内侧 z = 0，房间向 +z 延伸到 10，宽 x ∈ [-7, 7]，二楼回廊高 3.2。
会动的东西（人偶、马、马车）在 Blender 里面朝 -Y，导入后不转，面朝 Unity +Z。
主街：土路 z ∈ [-12.2, -2.4]，沿 x 东西向；北侧门脸 z = -0.2，南侧门脸 z = -14；西头画布 x = -34，东头教堂 x ≈ 30，墓地 x ∈ [24.5, 40]、z ∈ [-1.5, 12]。

## 场景是生成出来的
`Saloon.unity` 由 `SetupSaloon.Build()`（酒馆）+ `SetupTown.cs`（主街、电报局、墓地、画布、马车、镇民、隐形墙）整份重建，**不要在编辑器里手改场景**——改脚本，再跑 `tools/review.sh`。
在编辑器里也可以用菜单 `Mercy Creek → Rebuild Saloon Scene`。

## 运行时系统
| 脚本 | 作用 |
|---|---|
| LoopMemory | 跨循环保留的状态（轮数、碎片、累计时间）；每轮最多记住 1 个新碎片 |
| LoopDirector | 一轮 240 秒；重置 / 读档后在黑场上打"第 N 稿"卡（Holding 期间时间不走）；太阳仰角 26°→8°、变红，油灯渐亮；按时间点放字幕；到点褪色、黑场、重载场景 |
| FirstPersonController | WASD / Shift / 鼠标，Esc 释放鼠标 |
| PlayerInteractor + Interactable | 准星交互，E 或左键；碎片、上锁门、结局 |
| Hud | 代码搭的 uGUI：循环数、提示、字幕、黑场、结局卡 |
| LightShaft | 沿太阳方向平移窗口矩形叠 28 张切片，additive + 深度软相交 + 窗棂遮挡 + 浮尘噪声 |
| Story | 剧本唯一实现：每轮时间表（按 LoopDirector.Elapsed 触发，快进时以 instant 补上）、12 个碎片、对话选项、三个结局、按稿数解锁地点（StreetWritten / GraveyardWritten）、记忆本"下一步"提示 |
| Coach + HorseRig | 驿站马车沿路点行驶（加减速、车轮按距离转、车厢晃）；木头马四拍慢步（相位按距离推进），见 docs/horse_rig.md |
| Townsfolk | 定格镇民：第 3 稿起转头看玩家，第 5 稿起转身 |
| Loc | 文本表（中 / 英），所有给玩家看的字都从这里取 |
| Npc + MannequinRig | 人偶角色：沿路点走（含楼梯）、到点换姿势、看人、说话；程序动画按 docs/mannequin_rig.md 的轴向写角度，步伐相位跟实际位移走 |
| SwingDoor | 4 号房门、后门 |
| Sfx | 全部声音；钢琴按轮数换错音版本 |
| Menus + Settings | 标题（独立相机缓推）、暂停、设置（灵敏度 / 反转 Y / 音量 / 语言）、结局后按钮；没有 EventSystem，自己处理鼠标键盘 |
| ShareCard | 1200×630 分享卡片：离屏相机 + Screen Space Camera 画布，Mac 存桌面，Web 用 jslib 下载 |
| LoopMemory | 另含存档（PlayerPrefs，每轮开始自动存，结局清除） |
| PlayBot | `-playbot <dir> -route awaken\|escape\|reset [-mute] [-startloop N -frags a,b]`：从标题按键开始，用虚拟键盘走路（运行时烘 NavMesh 寻路）、对准物件等提示再按 E、数字键选对话、Esc 菜单结束下午；屏幕上每句字、走不动、瞄不到、缺文本、异常都写进日志（`ISSUE`）。不锁真鼠标；`tools/playbot.sh` 跑前备份、跑后恢复玩家的 PlayerPrefs |
| AutoShot / AutoTest | `-autoshot <dir>` 固定机位截图（`-debug` / `-only` / `-times` / `-loop N`）；`-autotest <dir> -ending awaken\|escape\|reset\|town` 自动通关；`-titleshot <png>` 标题与设置画面；`-lang zh\|en` |

## 光照
- 间接光全部走 **APV**（Adaptive Probe Volumes），烘两个情景：Afternoon（循环开始）、Dusk（循环结束），运行时 `LoopDirector` 按进度混合。静态网格 `receiveGI = LightProbes`，不烘光照贴图（太阳会动）
- 太阳和油灯是 Mixed（直接光实时，间接光进 APV）；墙、梁双面投影，避免薄墙被法线偏移穿透漏光
- 探针只放在室内（`APV Hall` / `APV Room 4` / `APV Telegraph`），街上不放（会沿薄墙漏光），室外靠实时阳光 + 天空盒环境光 + 街道反射探针；阴影距离 70 m；反射探针盒必须完整包住房间（否则盒外表面反射天空盒，发灰发亮）

## 已知问题 / 待办
- Mac 构建约 0.8GB（贴图 BC7 2K）
- 角色衣服是刚体壳，长裙 / 围裙不跟腿动，步幅受限
- 人偶没有手持道具（倒酒、写字只是手势）
- 镜子不反射（"镜中人偶"只靠文字）
- 前墙内侧、天花板在午后仍略偏冷灰
- 界面字体是静态图集：**不能用富文本 `<size>`**（那一段会整段不显示），大小不同的字要分开放 Text；**`<i>` / `FontStyle.Bold|Italic` 会报错且不生效**——Loc.T 把 `<i>` 换成旁白色 `<color=#d4c2a2>`
- Bundle ID 是 `dev.mercycreek.game`（PlayerPrefs 域同名）；自动测试 / 截图（`Automated`）不写存档，`review.sh` / `playbot.sh` 跑完恢复窗口设置
- 导入的 glTF 是 Prefab 实例：**不能给里面的节点改父级**（会报 "is not possible" 并静默失败）。要转的门直接把 SwingDoor 挂在节点上（SwingDoor 以载入时的朝向为静止朝向）
- 街上：马的挽具是刚体，走起来与车辕的接缝会差几厘米；缰绳只在 Blender 评审图里有；画布上的画是午后光，黄昏时不会跟着变红
- 街东头天空偶尔能看到一条虚线（电报线太细，远处走样）
- 烘 APV 时日志里会出现一次 `ArgumentNullException ... WriteBakingCells`（新建场景后第一次烘焙时情景名为空），两个情景的数据仍会正确写入，暂不处理

## 网页版
- 只用 WebGPU（`BuildWeb.cs`），Brotli + 解压回退，模板 `Assets/WebGLTemplates/MercyCreek`：不支持 WebGPU 时显示中英说明；网址参数转成命令行参数（`?lang=zh&autotest=x&ending=awaken`）
- 贴图 Web 端 1K DXT Crunch（`TextureImportRules.cs`）；字体是静态图集（`FontImportRules.cs`，动态字体在 WebGPU 上会丢字）
- 首包约 92MB（v2 加了小镇）；Chrome 本机加载约 3 秒
