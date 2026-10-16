# AGENTS.md — Mercy Creek

给在这个仓库里工作的 AI 代理（Claude Code、Codex 等）和人看的总说明。`CLAUDE.md` 只是引用本文件。

## 1. 项目是什么
单人 + AI 开发的写实西部短篇游戏。玩家是 1880 年代小镇酒馆 Mercy Creek 的女招待，每个下午被重置一次；在 4 分钟（240 秒）一轮的循环里拾起记忆碎片，逐渐意识到自己身处一个被"写出来"的世界。
- 时长：首通 25–35 分钟（6–8 稿）。前 30 秒必须出现第一个"不对劲"。
- 平台：macOS 原生（主）、Web/WebGPU（传播用，次）。
- 原创作品，致敬"循环 / 觉醒"类型。**不使用任何《西部世界》的名字、角色、台词、配乐、标志或具体剧情**，也不模仿其片头、钢琴翻奏流行歌等标志性手法。

## 2. 授权规则（硬性，违者回滚）
允许进入工程的外部内容只有：
| 类别 | 例子 | 要求 |
|---|---|---|
| CC0 | Poly Haven、ambientCG | 在 `docs/ASSETS.md` 登记来源 URL |
| 公有领域 | 19 世纪老照片、1927 年前出版的乐谱 | 登记来源与出版年份 |
| SIL OFL 字体 | 思源黑体 / 思源宋体、Noto | 登记，随构建附带 OFL 文本 |
| 自己生成 | Blender 脚本建模、Python 合成音频、Tripo（账号条款允许商用） | 登记生成脚本或平台 |

禁止：影视 / 游戏截图、真实演员长相、来源不明的网图、CC-BY-NC、"免费下载"但授权不清的素材、需要署名而我们没署名的素材。Mixamo、Asset Store 等平台素材默认不用（条款限制再分发）。

## 3. 目录
```
AGENTS.md            本文件（规则、路线图、完成标准）
docs/GAME_DESIGN.md  玩法、循环规则、剧本、结局（剧情以它为准）
docs/ART_STYLE.md    美术基准、调色、精度预算
docs/ASSETS.md       资产清单与授权
docs/TECH.md         引擎、渲染、构建、坐标约定、已知问题
docs/DECISIONS.md    代理自主做的设计决定，等人复核
tools/               所有可复现的生成 / 构建 / 评审脚本
art/source/          下载的 CC0 原始资产（git 忽略，tools/fetch_assets.py 重下）
art/blender/         脚本生成的 .blend（git 忽略，可重建）
Game/                Unity 6.3 工程（URP）
Reviews/             评审截图（unity/ 与 autotest/ 每次重新生成，git 忽略）
```

## 4. 环境
- Unity **6000.3.26f1**：`/Applications/Unity/Hub/Editor/6000.3.26f1/Unity.app/Contents/MacOS/Unity`（含 Mac、Web 模块）
  - Hub 在国内走 `download.unitychina.cn` 镜像会 404。要别的模块：从 `download.unity3d.com` 用 aria2 下 pkg，核验签名后解包
  - **同一时间只能有一个 Unity 进程打开 `Game/`**。批处理前确认编辑器没开着这个工程（`pgrep -fl Unity`），否则 batchmode 会因为工程锁失败
- Blender 5.2：`blender --background --python <脚本> -- <参数>`
- Python：工程内 `.venv`（`tools/bootstrap.sh` 自动创建并装 pillow / numpy / fonttools，已忽略）
- 其他：ffmpeg、fluidsynth、aria2、gh（账号 wquguru）
- 网络：Poly Haven / ambientCG 偶发 SSL EOF，重试即可；脚本里要有重试

## 5. 常用命令
| 做什么 | 命令 |
|---|---|
| 从零复原工程（新机器 / 新克隆） | `tools/bootstrap.sh` |
| 重下 CC0 资产 | `python3 tools/fetch_assets.py` |
| 重建酒馆模型并导出 | `blender --background --python tools/blender/build_saloon.py -- --export Game/Assets/_MercyCreek/Art/Saloon/Saloon.gltf` |
| 重建场景 + Mac 构建 + 截图 | `tools/review.sh` |
| 同上并自动通关（三个结局 + town 路线 + walls 隐形墙各一遍，含标题 / 开场 / 记忆本 / 分享卡片截图） | `tools/review.sh --test` |
| 像真人一样试玩三个结局（静音、后台，约 12 分钟；看 `Reviews/playbot/<路线>/`） | `tools/playbot.sh` |
| 只截图（默认第 3 稿；`SHOT_ARGS="-loop 1"` 拍第 1 稿） | `tools/review.sh --no-setup --no-build` |
| Web 构建 | `tools/build_web.sh`（输出 `Game/Builds/Web/`，约 92MB） |
| Web 冒烟测试（本机 Chrome WebGPU，标题截图 + 一个结局自动通关） | `node tools/webtest/webtest.mjs 8700 awaken`（首次先 `cd tools/webtest && npm install`） |
| 本地试玩网页版 | `python3 -m http.server -d Game/Builds/Web 8700` → http://localhost:8700/?lang=zh |
| 排查画面（关掉某个光照成分） | `SHOT_ARGS="-debug noprobe -only bar -times 8" tools/review.sh --no-setup --no-build` |
| 改了 Loc 文本后重新裁字体 | `.venv/bin/python tools/fonts/make_font.py` |
| 录一段试玩视频（PlayBot 自动玩 + 30fps 逐帧 JPG + AudioRenderer 同步录游戏声；输出 frames/、audio.f32、frames.tsv） | `"Game/Builds/Mac/MercyCreek.app/Contents/MacOS/Mercy Creek" -playbot <目录>/pb -route awaken -record <目录> -lang zh -screen-width 1660 -screen-height 1080 -screen-fullscreen 0`（约为游戏时间的 2.5 倍；完整觉醒路线约 5GB 帧） |
| 发布预告片（约 85 秒；镜头 / 配乐 / 字幕都由 `tools/trailer/edl.py` 剪辑表驱动；约 20 分钟） | `tools/make_trailer.sh`（`--reuse` 复用已拍的镜头；只重拍某几个：删掉 `Reviews/trailer/shots/<名字>.txt`） |
| 组装落地页到 dist/site（不发布） | `tools/make_site.sh` |
| 截图对照表 | `python3 tools/contact_sheet.py Reviews/unity Reviews/unity/sheet.jpg` |

## 6. 工作方式
1. **改需求先改文档**：玩法 / 剧本改 `GAME_DESIGN.md`，技术约定改 `TECH.md`，再写代码。
2. **场景是生成的**：`Saloon.unity` 由 `SetupSaloon.cs` + `SetupTown.cs` 整份重建，不要手改 `.unity`，不要依赖编辑器里的手工操作。所有资产生成都要有脚本（Blender / Python / Unity Editor 脚本）。
3. **每次改动都要自己验证，看过结果才能说"完成"**：
   - 视觉改动：跑 `tools/review.sh`，先看对照表（`contact_sheet.py` 拼成一张），只对有疑点的机位再单独看原图；对照 `ART_STYLE.md`
   - 玩法 / 剧本改动：跑 `tools/review.sh --test`，必须看到 `[AutoTest] PASS`，并检查日志里没有 `Exception`；再跑 `tools/playbot.sh`，必须 `PLAYBOT ALL CLEAN`（AutoTest 直接调 Story，走不到、瞄不到的问题只有 PlayBot 能发现）
   - 音频改动：用 ffmpeg 出波形 / 频谱图看，确认没有爆音、电平合理（峰值 ≤ -1 dBFS）
   - 新增结局或分支：给 `AutoTest` 加对应路线
4. **完不成就说完不成**：测试失败、截图难看、某步跳过，都要在汇报里写清楚，并记进 `TECH.md` 的已知问题。
5. **自主决定要留痕**：人不在场时，剧情、角色、美术方向上的取舍可以自己定，但要写进 `docs/DECISIONS.md`（日期、决定、理由、可替代方案），方便事后复核推翻。
6. **精度预算**（见 `ART_STYLE.md`）超标先写进 DECISIONS 再做。
7. 代码风格：C# 命名空间 `MercyCreek`（编辑器脚本 `MercyCreek.EditorTools`），注释用中文、只写"为什么"；运行时不依赖编辑器 API；不引入新的第三方包，除非写进 DECISIONS。

## 7. Git
- 远端：GitHub **公开**仓库 `wquguru/mercy-creek`（MIT），默认分支 `main`。提交前确认没有密钥、个人信息、授权不清的素材
- 大文件走 LFS（见 `.gitattributes`）。**能由脚本重建的产物不提交**（Saloon.glb、.blend、构建、评审截图），只提交脚本和 `.meta`，以免 LFS 配额爆掉
- 一个里程碑或一个独立功能一次提交，提交前 `tools/review.sh --test` 通过；提交信息用英文，第一行说做了什么
- 不 force push，不改历史（2026-10-16 应人的要求把历史提交信息改成英文，强推过一次；以后仍需人明确同意）

## 8. 路线图与完成标准
状态：☐ 未开始 / ◐ 进行中 / ☑ 完成。完成一项就更新这里。

| # | 里程碑 | 完成标准 |
|---|---|---|
| M0 | ☑ 原型 | 可走动、3 分钟循环、4 碎片、上锁门、结局卡；AutoTest PASS |
| M1 | ◐ 画面过关 | APV 烘焙 GI，大厅不再死黑；墙纸有纹理和凹凸；吧台无白色溢光；窗外有远景；自动钢琴为真实模型；4 个评审机位截图都能当宣传图 |
| M2 | ☑ 剧本 | `GAME_DESIGN.md` 写完：角色设定、每轮事件时间表（≥6 轮变化）、8–12 个碎片、3 个结局的触发条件与文本 |
| M3 | ◐ NPC | 陌生人、酒保、钢琴师、楼上房客 4 个角色：有模型、有骨骼、能按时间表走位 / 做动作 / 看向玩家；不穿模、不滑步 |
| M4 | ☑ 对话与事件 | 走近 NPC 按 E 对话；碎片解锁对话选项；事件按时间表触发并随轮数变化；3 个结局都可达；AutoTest 覆盖 3 个结局 |
| M5 | ◐ 声音 | 室内环境音、风、脚步（木地板）、钟摆、自动钢琴曲（每轮细微变化，作为线索）、重置音效、结局音乐；音量混合合理 |
| M6 | ☑ 界面与流程 | 标题画面、设置（鼠标灵敏度、音量、语言中 / 英）、暂停菜单、存档（当前轮数与碎片）、内嵌 OFL 中文字体、分享卡片（轮数 + 用时 + 结局徽记，可保存 PNG） |
| M7 | ☑ Web 版 | WebGPU 构建可在 Chrome 打开并通关；首包 ≤ 200MB；加载进度条；不支持 WebGPU 时显示说明页 |
| M8 | ◐ 发布准备 | 宣传片（脚本化机位 + ffmpeg 合成）、落地页、README、致谢与授权清单。仓库已开源（MIT）；**部署网页版 / 落地页、发帖前必须问人** |
| M9 | ☑ 易懂性 | "第 N 稿"框架、开场打字页、重置稿数卡、Tab 记忆本（含下一步提示）、乐谱线索、"结束这个下午" |
| M10 | ☑ 主街 | 一条街可走：北侧 4 栋 + 电报局室内、南侧 5 栋、东头教堂墓地、西头画布（出逃）；酒馆外立面；按稿数解锁；隐形墙不漏 |
| M11 | ☑ 马车与镇民 | 驿站马车 + 两匹木头马从画布驶出、停在酒馆门口、克兰下车；车轮 / 马步不打滑；3 个定格镇民随稿数转头；室外音效（马蹄、车轮、电报、教堂钟、街道风、土路 / 栈道脚步） |

## 9. 省 token
上下文越长，每次调用重读的就越多（缓存读取占总量 97%）。实测：一个会话连跑两天，平均每次调用带 21 万 token 上下文，100 张截图占了其中一大块。
- **一个里程碑一个会话**：提交后开新会话，靠本文件和 `docs/` 接上，不要在一个会话里连做几个阶段
- **截图先看对照表**：`contact_sheet.py` 拼成一张再看；要看原图时先缩到 1024 宽 JPG（`sips -Z 1024`）。需要逐张细看的视觉评审交给子代理，只带回文字结论
- **日志只取需要的**：构建、测试、Blender 输出一律 `| tail` 或 `grep -E 'error|Exception|PASS|FAIL|ISSUE'`，不要整段读进来
- **改代码用 Edit**，不要整份重写大文件；`SetupSaloon.cs`、`PlayBot.cs`、`Loc.cs` 都在 25–45KB，按需 `grep -n` 定位后读局部
- **并行用子代理**：互不依赖的资产（模型、音频）交给子代理同时做，主会话只集成和验收
- 等构建 / 烘焙时用后台任务，完成会自动通知，不要轮询

## 10. 不要做的事
- 不要部署到公网、不要发帖、不要改仓库可见性：这些都要人来点头
- 不要删除 `docs/` 里的内容来"简化"；过时内容改成新的
- 不要为了让测试通过而削弱测试
