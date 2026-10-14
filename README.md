<p align="center"><img src="docs/media/hero.png" alt="DAWLoop 品牌头图" width="100%"></p>
<p align="center"><img src="docs/media/logo.png" alt="DAWLoop 标志" width="64" height="64"></p>

# DAWLoop

**让 AI 真正参与音乐制作。**

DAWLoop 连接音乐分析、MIDI 创作与真实 DAW 操作。在桌面工作区探索素材、编辑旋律；通过开放 Runtime 为 Agent 构建规划、执行、观察和结果核对的工作流。

为音乐创作者提供制作工具，为开发者提供可扩展的音乐自动化框架。

[中文](README.md) | [English](README.en.md)

[![CI](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml)
[![MIT code](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-Alpha-orange)](docs/DESKTOP.md)

[下载 Desktop Alpha](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) · [试用开发者 Runtime](docs/QUICKSTART.md) · [演示](docs/DEMOS.md) · [功能](docs/CAPABILITIES.md) · [参与贡献](CONTRIBUTING.md)

## 探索 DAWLoop

Music Intelligence 将试听、分析、旋律创作与编辑放在一个工作区中。

![Music Intelligence 工作区](docs/media/music-home.png)

<details>
<summary>音乐分析、Piano Roll 编辑与组件管理</summary>

![音乐分析](docs/media/analysis-report.png)
![Piano Roll 编辑](docs/media/piano-roll.png)
![组件管理](docs/media/model-manager.png)

</details>

[完整体验流程](docs/DESKTOP.md) · [素材到旋律的演示](docs/DEMOS.md) · [图片来源](docs/media/README.md)

## 你可以做什么？

| 工作 | 使用方式 |
| --- | --- |
| 理解音乐素材 | 导入与试听音频，查看响度、节奏变化、调性候选和分析报告 |
| 创作旋律 | 根据和声、节奏、密度与 Seed 约束生成规则辅助旋律 |
| 编辑 MIDI | 在 Desktop Piano Roll 审阅音符、调整音高与力度、撤销、试听并导出 MIDI |
| 转录音符 | 使用已配置的 Basic Pitch 模型环境，把音频转为可编辑音符 |
| 操作真实 DAW | 通过 Runtime 的 FL Studio 执行后端进行目标明确的宿主交互 |
| 构建音乐 Agent | 将结构化计划、目标约束、状态观察与结果验证接入自己的 Agent |

FL Studio MCP 是执行路径之一，提供 transport、Channel、Piano Roll、Mixer 与已加载插件参数等接口。DAWLoop 自有 Controller 补充现有 Pattern 的识别和导航，把操作放在明确目标与人工审阅的流程中。[功能与集成范围](docs/CAPABILITIES.md)

## 为什么选择 DAWLoop？

### Brain / Hands / Ears

| 层次 | 为制作工作带来什么 |
| --- | --- |
| **Brain — 音乐规划与 Agent 规则** | 用音乐网格、Note Plan 与约束表达意图，组织下一步动作 |
| **Hands — DAW 执行与控制** | 连接真实 FL Studio，将计划转为受支持的宿主操作 |
| **Ears — 分析与制作辅助** | 用 MIDI、编排与音频测量理解素材，为下一轮计划提供输入 |

三层将创作意图、实际操作和反馈连接起来，Agent 可以利用熟悉的工具接口扩展工作流。

### 操作之后，核对结果

**Plan → Execute → Observe → Verify → Iterate**

工具回复“成功”只是执行信息。DAWLoop 的验证模块比较计划与实际事件，以 **PASS / STOP** 帮助 Agent 决定继续、停止或重新规划。人工审阅保留在需要确认的宿主操作中。

[架构](docs/ARCHITECTURE.md) · [验证模型](docs/VERIFICATION.md) · [公开证据](evidence/public/README.md)

## 开始使用

### 下载 Desktop Alpha

[Windows x64 便携版 ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip) · [发行说明与校验和](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1)

1. 解压完整程序目录，运行 `DAWLoop.exe`。
2. 在 Music Intelligence 的组件管理中阅读许可并确认安装基础组件。
3. 导入 WAV，试听并分析，或直接创建旋律并进入 Piano Roll。

无需 Codex、Node 或系统 Python。软件未签名；遇到未知发布者提示时先核对官方来源与校验和，保留系统安全保护。[首次运行指南](docs/DESKTOP.md)

### 试用开发者 Runtime

Python 3.11+。先运行合成素材示例，生成分析、profile 和音乐计划：

```powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning]"
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

Linux/macOS 使用 `python3 -m venv .venv` 和 `.venv/bin/python`。输出目录须为新目录。[Quickstart](docs/QUICKSTART.md) · [FL Studio 设置](docs/FL_STUDIO_SETUP.md) · [部署指南](docs/DEPLOYMENT.md)

## 为创作者与开发者而设计

- **音乐创作者：**在一个工作区中试听、分析、创作和编辑，保留对音乐结果的选择。
- **Agent 开发者：**复用音乐合同、执行适配器与验证接口，接入自己的工具调用模型。
- **开源贡献者：**改进编辑体验、兼容性、分析方法或 DAW 集成。[贡献指南](CONTRIBUTING.md)

## 产品方向

持续改善首次安装与组件管理，扩展可验证的 FL Studio 工作流，完善 Agent 规划，并研究音乐检索、分析与生成。[路线图](docs/ROADMAP.md)

## 当前版本说明

- Desktop **0.5.6-alpha.1** 已公开为 Windows x64 Pre-release；维护者 Windows 环境已运行，独立干净 Windows 兼容性尚待验证。
- 随包基础组件支持 WAV 分析。Basic Pitch 转录使用已有核验模型环境；此版暂不提供新用户的首次模型安装，权重另行配置。
- Desktop 内置 Piano Roll 用于本地 MIDI 编辑；真实 FL 控制通过独立 Runtime 集成。通用自动混音、任意工程自主控制及完整风格学习属于后续研究。
- 已有 FL 现场研究和离线验证各有明确范围；后端工具能力与宿主验证记录分别列在 [能力页](docs/CAPABILITIES.md)。公开更新通知关闭，更新由用户主动完成。
- 展示截图来自此前开发版本。Desktop 源码在 [发行标签](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1)，Python Runtime 在 main。[详细版本与安装说明](docs/DESKTOP.md)

## 开源、贡献与致谢

项目自有代码采用 [MIT 许可证](LICENSE)。品牌与部分图片使用独立声明，见 [品牌政策](TRADEMARKS.md)、[许可范围](LICENSE_POLICY.md) 和 [媒体说明](docs/media/README.md)。

感谢 [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) 的 FL Studio 控制工作，以及 Bilibili 创作者 [坏影子不坏](https://space.bilibili.com/599132499)（UID 599132499）的 [DSH 工作流展示](https://www.bilibili.com/video/BV1PTht6cENP/)。其制作实践启发了 Production Pipeline；部分通用分析代码改编自其提供的 MIT 许可 `whale-music-pipeline`，保留原作者通知。

[贡献](CONTRIBUTING.md) · [Issues](https://github.com/ryurikoneko/DAWLoop/issues) · [完整致谢](docs/ACKNOWLEDGEMENTS.md) · [第三方通知](THIRD_PARTY_NOTICES.md) · [来源](PROVENANCE.md) · [安全](SECURITY.md)
