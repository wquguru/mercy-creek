<div align="center">

# Mercy Creek

**每天下午三点，一切重来。**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Unity](https://img.shields.io/badge/Unity-6.3_URP-000000?logo=unity&logoColor=white)](https://unity.com/)
[![Blender](https://img.shields.io/badge/Blender-5.2-F5792A?logo=blender&logoColor=white)](https://www.blender.org/)
[![Platform](https://img.shields.io/badge/platform-macOS_%7C_Web_(WebGPU)-lightgrey)](#从零构建)
[![Assets](https://img.shields.io/badge/assets-CC0_%7C_OFL_%7C_procedural-brightgreen)](docs/ASSETS.md)
[![Built with Claude Code](https://img.shields.io/badge/built_with-Claude_Code-D97757?logo=claude&logoColor=white)](https://claude.com/claude-code)
[![Last commit](https://img.shields.io/github/last-commit/wquguru/mercy-creek)](https://github.com/wquguru/mercy-creek/commits/main)

![游戏截图：第 14 稿的主街，驿站马车停在酒馆门口，街道西头是一块画布](docs/images/screenshot.jpg)

</div>

一个 25–35 分钟的写实西部循环短篇。你是 1882 年小镇酒馆的女招待内尔，同一个下午一遍遍重来，每一遍叫"一稿"，每稿只能带走一段记忆。世界也随稿数被"写"出来：先是酒馆，然后是主街、电报局、教堂墓地，以及街道尽头那块画布。三个结局：留下、出逃、觉醒。

一个人加 AI（Claude Code）开发。模型、贴图、音频、场景全部由脚本生成，没有手工摆放的东西。

**操作**：WASD 移动 · Shift 快走 · 鼠标看 · E 交互 · 1–4 选对话 · Tab 记忆本 · Esc 暂停（可"结束这个下午"）

## 从零构建

需要 macOS（Apple Silicon 上开发）、Unity 6000.3.26f1（含 Mac 和 Web 模块）、Blender 5.2（命令行能调用 `blender`）、Python 3、ffmpeg；网页测试另需 Node.js。

```sh
git clone https://github.com/wquguru/mercy-creek.git && cd mercy-creek
tools/bootstrap.sh    # 看到 AUTOTEST ALL PASS 即成功，游戏在 Game/Builds/Mac/MercyCreek.app
```

仓库只放源码和生成脚本，`bootstrap.sh` 依次还原所有产物：

1. **下载素材**：从 Poly Haven、ambientCG 下载 CC0 模型、材质、HDRI
2. **生成贴图**：墙纸、招牌、告示、画布底稿（Python + Pillow）
3. **生成模型**：`tools/blender/build_*.py` 后台建模——酒馆、钢琴、木头人偶、马、马车、街道、教堂墓地、画布
4. **合成音频**：钢琴、马蹄、钟声、环境声全部程序合成，不用采样
5. **生成场景**：Unity 批处理运行 `SetupSaloon.cs` / `SetupTown.cs`，烘焙午后、黄昏两套光照
6. **构建测试**：构建 Mac 版、固定机位截图、自动通关五条路线

| 常用命令 | |
|---|---|
| `tools/review.sh --test` | 重建场景 → 构建 → 截图 → 自动通关 |
| `tools/playbot.sh awaken escape reset` | 像真人一样玩完三个结局（静音、后台） |
| `tools/build_web.sh` | 构建网页版，`python3 -m http.server -d Game/Builds/Web 8700` 本地试玩 |
| `tools/make_trailer.sh` / `tools/make_site.sh` | 生成宣传片 / 落地页 |

更多见 [`AGENTS.md`](AGENTS.md) 和 [`docs/TECH.md`](docs/TECH.md)。

## 方法论：让 AI 自己把游戏做完

想验证的是：人只定方向、不碰编辑器，AI 能不能独立做完一个能玩、画面过得去的小游戏。从原型到现在大约一天。最管用的几条：

1. **先写文档再写代码**。剧本（`GAME_DESIGN.md`）、美术、技术、总说明（`AGENTS.md`）先写好，改动先改文档。AI 换个对话就失忆，文档就是它的记忆本。
2. **一切都能用脚本重建**。场景、模型、音频、文本全是代码，能 diff、能回滚、删了能重建。写生成脚本正好是 AI 最擅长的事。
3. **用截图代替"看一眼"**。每次构建自动在固定机位、三个时刻截图，AI 读图查漏光、穿模、比例、颜色。开发就是"改脚本 → 重建 → 截图 → 看图"的循环。
4. **两层自动测试**。AutoTest 直接调剧情接口，验证逻辑；PlayBot 用虚拟键盘从标题画面真玩一遍，寻路、瞄准、按键、选对话，记录屏幕上的每句字和每个异常。墓地门打不开、马车点不到这类问题，只有第二层抓得到。
5. **每个决定都记下来**。AI 自己拿的主意按"决定 / 理由 / 替代"记在 `docs/DECISIONS.md`，比如为什么用木头人偶而不是写实角色。
6. **定死边界**。素材只用 CC0、OFL 或自制并逐项登记；原创故事，不借用任何影视作品；公开、部署、发帖先问人。
7. **小步走，每步都能玩**。M0 原型 → M1 画面 → M2–M6 内容 → M7 网页版 → M8 宣传片和落地页 → v2 小镇 → PlayBot 试玩修复，每一步都是能跑的提交。

## 致谢

感谢[网易叭哥说](https://bug.youdao.com/#/)提供的永久免费中文翻译功能：按 Fn + Left Shift 说中文，直接转成英文文字。这个项目里跟 AI 的大部分交流都是这样说出来的，用母语讲清想法比斟酌英文快得多，对 Vibe Coding 很有帮助。

<img src="docs/images/voice-translate.png" alt="网易叭哥说的语音翻译：说中文，转成英文文字" width="480">

## 已知问题

衣服是刚体外壳，长裙不跟腿动；挽具和车辕有几厘米缝；画布上的画黄昏不变色；Mac 版未签名，首次打开需在"隐私与安全性"里允许。更多见 [`docs/TECH.md`](docs/TECH.md)。

## 授权

代码与原创内容使用 [MIT](LICENSE)。第三方素材来自 Poly Haven、ambientCG（CC0，构建时下载），字体为 Noto Serif SC、Rye、IM Fell English SC、Zeyada（SIL OFL），清单见 [`docs/ASSETS.md`](docs/ASSETS.md)。原创作品，致敬"循环 / 觉醒"类故事，与任何影视作品无关。
