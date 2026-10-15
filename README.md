# Mercy Creek

> 每天下午三点，一切重来。 · Every afternoon at three, it all begins again.

一个 15–20 分钟的写实西部循环短篇。你是 1882 年小镇酒馆的女招待内尔，每个下午被重置一次；每轮只能记住一件事，拼出这个世界是怎么被"写"出来的。三个结局：留下、出逃、觉醒。

单人 + AI 开发（Claude Code），Unity 6.3 URP。macOS 原生 + 网页版（WebGPU，约 65MB）。

## 试玩
- Mac：`tools/review.sh` 之后打开 `Game/Builds/Mac/MercyCreek.app`
- 网页：`tools/build_web.sh && python3 -m http.server -d Game/Builds/Web 8700`，打开 http://localhost:8700/?lang=zh
- 操作：WASD 移动 · Shift 快走 · 鼠标看 · E 交互 · 1–4 / 滚轮选择对话 · Esc 暂停

## 从零构建
```sh
tools/bootstrap.sh     # 下载 CC0 素材 → 生成贴图 / 模型 / 音频 → Unity 场景 → Mac 构建 → 自动测试
```
需要：Unity 6000.3.26f1（含 Mac、Web 模块）、Blender 5.2、Python 3、ffmpeg、Node（网页测试）。

## 仓库里有什么
| 路径 | 内容 |
|---|---|
| `AGENTS.md` | 给 AI 代理和人的总说明：规则、命令、路线图 |
| `docs/` | 设计（剧本）、美术、技术、资产授权、自主决定记录 |
| `tools/` | 所有生成脚本：Blender 建模、程序合成音频、贴图、字体子集、评审截图、宣传片、落地页 |
| `Game/` | Unity 工程；场景由 `SetupSaloon.cs` 整份生成 |
| `site/` | 落地页 |

## 授权
- 代码与原创内容：版权所有，暂未开源
- 第三方素材：Poly Haven / ambientCG（CC0）、Noto Serif SC 与 Rye（SIL OFL），清单见 `docs/ASSETS.md`
- 原创作品，致敬"循环 / 觉醒"类型，与任何影视作品无关
