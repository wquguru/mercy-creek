# 技术

## 版本
- Unity **6000.3.26f1**（6.3 LTS），装在 `/Applications/Unity/Hub/Editor/6000.3.26f1/`，含 Mac (IL2CPP)、Web、Windows (Mono) 模块
  - Hub 在国内会自动走 `download.unitychina.cn` 镜像，该镜像缺文件会 404。要装别的版本 / 模块：从 `download.unity3d.com` 手动下 pkg（aria2 多线程）后解包到上述目录
- URP 17.3（Forward+、SSAO、HDR、MSAA 4x），Input System 1.20（仅新输入系统），Timeline、glTFast 6.20、AI Navigation
- Blender 5.2

## 目录
```
art/source/        CC0 原始资产（git 忽略，tools/fetch_assets.py 可重下）
art/blender/       saloon_blockout.blend（由脚本生成）
tools/blender/build_saloon.py   酒馆白模：建筑 + 道具摆放 + 渲染 / 导出 GLB
tools/review.sh    一键：重建场景 → Mac 构建 → 自动截图（--test 加跑自动通关）
tools/playbot.sh   像真人一样试玩（虚拟键盘、寻路、静音、后台窗口），四个结局各走一遍
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
| Story | 剧本唯一实现：每轮时间表（按 LoopDirector.Elapsed 触发，快进时以 instant 补上）、12 个碎片、对话选项、四个结局、按稿数解锁地点（StreetWritten / GraveyardWritten）、记忆本"下一步"提示 |
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
- 长裙 / 围裙 / 风衣后摆在场景生成时转成蒙皮网格（`ClothSkin.cs`，权重按顶点位置程序生成，跟腿走）；其余衣服仍是刚体壳。裙子只有约 7 圈竖向分段，大步时弯折处略显棱角
- 手持道具（`HandProps.cs`）是基本体拼的：格斯擦杯（杯 + 布）/ 倒酒（瓶 + 杯）、克兰写字（笔），按姿势开关；倒酒时瓶里没有液体流出
- 镜子是平面反射（`MirrorReflection.cs` + `Mirror.shader`）：HDR RT（桌面全分辨率 + 2×MSAA，网页版半分辨率），只在玩家 7 米内、镜面朝向且在画面里时渲染；镜中站着内尔的人偶（只给反射相机看），第 4 稿起慢 0.45 秒。反射相机不做后期、不抗锯齿
- 前墙内侧、天花板在午后仍略偏冷灰
- 界面字体是静态图集：**不能用富文本 `<size>`**（那一段会整段不显示），大小不同的字要分开放 Text；**`<i>` / `FontStyle.Bold|Italic` 会报错且不生效**——Loc.T 把 `<i>` 换成旁白色 `<color=#d4c2a2>`
- Bundle ID 是 `dev.mercycreek.game`（PlayerPrefs 域同名）；自动测试 / 截图（`Automated`）不写存档，`review.sh` / `playbot.sh` 跑完恢复窗口设置
- 导入的 glTF 是 Prefab 实例：**不能给里面的节点改父级**（会报 "is not possible" 并静默失败）。要转的门直接把 SwingDoor 挂在节点上（SwingDoor 以载入时的朝向为静止朝向）
- 街上：马的挽具是刚体，走起来与车辕的接缝会差几厘米；缰绳只在 Blender 评审图里有；画布上的画随循环进度乘上黄昏色（`LoopDirector.paintedCanvas`，MaterialPropertyBlock）
- 电报线改成 1.4 cm 十字截面（原来 8 mm 单条竖带，远处断成虚线）；极远处仍可能细到断续
- 烘 APV 时日志里会出现一次 `ArgumentNullException ... WriteBakingCells`（新建场景后第一次烘焙时情景名为空），两个情景的数据仍会正确写入，暂不处理

## Windows 版
- `tools/build_win.sh` → `Game/Builds/Win/MercyCreek.exe` + `Game/Builds/MercyCreek-win64.zip`（约 0.9GB / 压缩 0.6GB）。Mono 后端（Mac 上交叉编译不了 IL2CPP），D3D12 / D3D11
- 模块装法：从 `download.unity3d.com/download_unity/de8167e7440c/MacEditorTargetInstaller/UnitySetup-Windows-Mono-Support-for-Editor-6000.3.26f1.pkg` 下载，`pkgutil --check-signature` 核验，`pkgutil --expand-full` 后把 `TargetSupport.pkg.tmp/Payload/` 拷到 `PlaybackEngines/WindowsStandaloneSupport/`
- **只构建过、没在 Windows 上运行过**（本机没有 Windows）。发布前要在真机上跑一遍 `MercyCreek.exe -autotest <目录> -ending awaken`
- 构建会把工程的当前平台切到 Win64；`review.sh` 已固定 `-buildTarget OSXUniversal`

## 网页版
- 只用 WebGPU（`BuildWeb.cs`），Brotli + 解压回退，模板 `Assets/WebGLTemplates/MercyCreek`：不支持 WebGPU 时显示中英说明；网址参数转成命令行参数（`?lang=zh&autotest=x&ending=awaken`）
- 贴图 Web 端 1K DXT Crunch（`TextureImportRules.cs`）；字体是静态图集（`FontImportRules.cs`，动态字体在 WebGPU 上会丢字）
- 首包约 92MB（v2 加了小镇）；Chrome 本机加载约 3 秒
