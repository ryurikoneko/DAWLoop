<p align="center"><img src="docs/media/hero.png" alt="DAWLoop 品牌头图" width="100%"></p>

<p align="center"><img src="docs/media/logo.png" alt="DAWLoop 标志" width="64" height="64"></p>

# DAWLoop

**连接音乐创作与真实 DAW 操作的 AI 开放框架。**

从分析音乐素材、规划与编辑 MIDI，到通过执行后端操作真实 FL Studio，DAWLoop 为音乐创作者和 AI Agent 开发者提供一条可观察的制作路线。它让 Agent 在受支持的工作流中核对操作结果，再决定继续还是重新规划。

现在可以试用**开源 Python Runtime / Agent 工具**，或下载 **Desktop 实验性 Alpha 音乐工作区**。两者独立开发，尚未形成完整的桌面 DAW 控制产品。

[中文](README.md) | [English](README.en.md)

[![CI](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml)
[![MIT code](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-Alpha-orange)](docs/CAPABILITIES.md)

[试用 Runtime](#快速开始) · [探索 Desktop](docs/DESKTOP.md) · [文档](docs/QUICKSTART.md) · [能力清单](docs/CAPABILITIES.md) · [参与贡献](CONTRIBUTING.md) · [Releases](https://github.com/ryurikoneko/DAWLoop/releases)

## 看看 DAWLoop Desktop

截图来自此前内部开发版本，展示 Music Intelligence 工作区。当前 [Desktop 0.5.6 Alpha](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) 已公开；实际发行范围与限制见下文。

![DAWLoop Music Intelligence 工作区](docs/media/music-home.png)

<details>
<summary>查看更多：音频分析、Piano Roll 与模型管理</summary>

![音乐分析](docs/media/analysis-report.png)

![Piano Roll 编辑](docs/media/piano-roll.png)

![模型管理](docs/media/model-manager.png)

</details>

[查看 Desktop 说明](docs/DESKTOP.md) · [演示场景](docs/DEMOS.md) · [截图来源](docs/media/README.md)

## 可以用 DAWLoop 做什么？

| 方向 | 主要内容 | 当前可用范围 |
| --- | --- | --- |
| 音乐分析 | 分析响度、节奏变化与调性候选，帮助理解音乐素材 | Desktop 实验性 Alpha；部分结果属于估计 |
| 音频转 MIDI | 借助 Basic Pitch 转录音符，再审阅、编辑和导出 | 现有核验环境可用；首次安装禁用，不等于完整分轨 |
| MIDI 创作 | 根据和声、节奏、密度和 Seed 约束生成旋律 | Desktop 实验性 Alpha；目前基于规则 |
| Piano Roll 编辑 | 审阅与编辑音符、调整力度、撤销、试听及导出 MIDI | Desktop 实验性 Alpha；应用内编辑器 |
| 音乐计划与验证 | 描述音符、节奏和目标，比较计划与读回的结果 | Python Runtime 已公开；核心验证有离线测试 |
| DAW 控制 | 通过 FL Studio MCP 等执行后端操作真实宿主、获取状态 | Runtime 实验性集成；现场验证范围因操作而异 |

Desktop 的 Piano Roll 是应用内编辑界面，不应与已验证的 FL Studio 宿主写入能力混为一谈。

**可以操作真实 FL Studio。** 公开 Runtime 包含固定版本的社区 FL Studio MCP 后端，为 Agent 提供进入运行中 FL Studio 的执行路径，覆盖 transport、Channel、Piano Roll、Mixer 状态及已加载插件参数等能力领域。支持访问已有 Pattern；上游不支持程序化创建 Pattern 或加载新插件。具体操作仍需按集成文档配置、确认目标并审阅结果；后端支持某项操作，并不意味着 DAWLoop 已完成该操作的现场验证。

[查看完整能力清单及证据](docs/CAPABILITIES.md)

## 为什么选择 DAWLoop？

DAWLoop 将制作工作分成三个相互配合的层次：

| 层次 | 职责 |
| --- | --- |
| Brain — DAWLoop Core | 音乐时间网格、结构化计划、目标约束与结果验证 |
| Hands — DAW 执行后端 | 在真实 DAW 中执行受支持的操作并获取状态；FL Studio 是当前主要目标 |
| Ears — Production Pipeline | MIDI 与编排分析、音频测量和制作规划辅助 |

三层为 Agent 提供理解、行动和反馈的接口，完整自主制作仍是研究方向。设计中的循环是：

~~~text
理解 → 规划 → 执行 → 观察 → 验证 → 迭代
                              PASS / STOP
                         人工审阅 / Agent 决策
~~~

普通 MIDI 工具可以把文件交给用户导入；DAWLoop 还提供真实 DAW 执行路径，以及核对结果的规则。工具回复“成功”不足以证明计划已实现：在具备可信读回的工作流中，验证器比较计划与实际事件，用 **PASS / STOP** 表达结果，帮助 Agent 判断下一步。

计划与比较模块已公开并有离线测试；有限的 FL Studio 研究工作流已有现场运行记录。实际跑过、公开归档证据与达到验证规则，是不同的证据范围，详见 [能力清单](docs/CAPABILITIES.md)。

[了解架构](docs/ARCHITECTURE.md) · [验证方法](docs/VERIFICATION.md) · [公开现场证据](evidence/public/README.md)

## 快速开始

### 想使用音乐创作界面？

下载 [DAWLoop v0.5.6-alpha.1 Windows x64 便携版](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip)（约 266 MiB），或查看 [发行说明与 SHA-256 校验](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1)。解压后运行 `DAWLoop.exe`，在组件管理中确认安装随包基础音乐分析组件，再导入 WAV。无需 Codex、Node 或系统 Python。

**实验性 Alpha：已在维护者 Windows 环境测试，未独立验证全新 Windows 兼容性。** Basic Pitch 权重不随包提供，旧运行环境的首次安装暂时禁用；已有核验环境仍可转录。规则创作、Piano Roll 与 MIDI 导出可独立使用。[首次运行与限制](docs/DESKTOP.md) · [实际 Desktop 源码](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1)。历史 Python Runtime 发行包不是 Desktop 安装程序。

### 想试用开源 Runtime？

需要 Python 3.11 或更高版本。下面的示例只使用合成数据，**不需要启动 FL Studio**。

Windows PowerShell：

~~~powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning]"
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
~~~

Linux / macOS 在 clone 并进入目录后使用：

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[learning]"
.venv/bin/python learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
~~~

示例在指定目录生成分析、profile 与音乐计划 JSON。输出目录必须尚不存在；重复运行请选择新目录。

[入门教程](docs/QUICKSTART.md) · [部署与依赖](docs/DEPLOYMENT.md) · [Runtime 开发指南](docs/RUNTIME_GUIDE.zh.md)

### 想研究 FL Studio 集成？

请从 [部署指南](docs/DEPLOYMENT.md) 和 [FL Studio 设置说明](docs/FL_STUDIO_SETUP.md) 开始，准备独立测试工程，并按文档完成目标确认与人工授权。不要把实验性操作直接用于尚未备份的正式工程。

## 版本与后续计划

**Python Runtime：**源码及 Alpha 发行物已公开，可以从 [GitHub Releases](https://github.com/ryurikoneko/DAWLoop/releases) 获取。

**DAWLoop Desktop：**[0.5.6-alpha.1](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) 已作为 Pre-release 公开。随包基础分析组件已在本机完成首次安装、真实 WAV 分析和重启恢复；Piano Roll 编辑及 MIDI 导出／读回通过。独立干净 Windows 仍为 NOT_TESTED，维护者接受此版兼容性风险；不标为 Stable 或开箱即用。公开更新通知保持关闭，不自动下载或安装。

后续方向：

- 改善 Desktop 首次安装与组件管理。
- 扩展并验证 FL Studio 集成。
- 完善 Agent 的音乐规划与结果核验。
- 研究音乐检索、分析与生成能力。

具体进度与限制以 [路线图](docs/ROADMAP.md) 和 [能力表](docs/CAPABILITIES.md) 为准。

## 开源、贡献与致谢

DAWLoop 项目自有软件代码采用 [MIT 许可证](LICENSE)。第三方代码保留原有许可与署名；项目名称、Logo 和部分展示图片另有使用说明，详见 [品牌政策](TRADEMARKS.md)、[许可范围](LICENSE_POLICY.md) 与 [媒体声明](docs/media/README.md)。

感谢 [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) 的社区 FL Studio 控制工作，以及 Bilibili 创作者 [坏影子不坏](https://space.bilibili.com/599132499)（UID 599132499）的 [DSH 工作流展示](https://www.bilibili.com/video/BV1PTht6cENP/)，对 Production Pipeline 的设计与制作实践带来启发。部分通用分析代码改编自其提供的 MIT 许可 `whale-music-pipeline`，保留原作者署名。具体代码来源、版权和许可见 [第三方声明](THIRD_PARTY_NOTICES.md) 与 [完整致谢](docs/ACKNOWLEDGEMENTS.md)。

欢迎通过 [Issues](https://github.com/ryurikoneko/DAWLoop/issues) 反馈问题，或参照 [贡献指南](CONTRIBUTING.md) 参与开发。[安全报告](SECURITY.md) · [项目来源](PROVENANCE.md) · [引用信息](CITATION.cff)
