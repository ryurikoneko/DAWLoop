# 功能与集成范围 / Capabilities and integration scope

按你的任务选择 Desktop、Python Runtime 或 FL Studio 集成。本页将产品可用性、后端接口和验证依据分别说明。

Choose Desktop, Python Runtime or FL Studio integration for your task. Availability, backend interfaces and verification evidence are recorded separately.

## Desktop Alpha

| 任务 / Task | 功能 / Capability |
| --- | --- |
| 音频工作 / Audio workflow | 导入、流式试听、暂停、定位 / Import, streaming playback, pause, seek |
| 音乐分析 / Music analysis | WAV基础测量、响度、能量和节奏变化、调性候选与报告 / WAV measurement, loudness, energy/rhythm changes, key candidates and reports |
| 旋律创作 / Melody creation | 和声、节奏、密度、Seed约束的规则生成 / Rule generation with harmony, rhythm, density and seed constraints |
| 编辑与导出 / Editing and export | 本地Piano Roll、音符/力度、撤销、试听、MIDI导出及事件读回 / In-app Piano Roll, notes/velocity, undo, audition, MIDI export and event readback |
| 工作区管理 / Workspace | 明确保存、重启恢复、基础组件管理、中英文 / Explicit save, restart recovery, components, Chinese/English |
| 转录集成 / Transcription integration | 已配置Basic Pitch环境中的音频转音符 / Audio-to-note transcription with a configured Basic Pitch environment |

[使用 Desktop](DESKTOP.md) · [公开 Desktop 源码](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1)

## Python Runtime

| 领域 / Area | 公开实现 / Public implementation |
| --- | --- |
| 音乐合同 / Musical contracts | MusicalGrid、absolute ticks、NotePlan、MusicalPlan、Learning schemas |
| 分析与规划 / Analysis and planning | SMF、dense window、音域/覆盖检查、active RMS、推子校准与计划、SoundFont辅助 |
| Agent扩展 / Agent extension | 结构化输入/报告、可选MCP与执行adapter、目标检查和执行预算 |
| 验证 / Verification | Writer/Reader分离、多重集合Exact-Set比较、PASS/STOP与不可变终态规则 |

[Quickstart](QUICKSTART.md) · [Production Pipeline](PRODUCTION_PIPELINE.md)

## FL Studio：三个不同层次 / Three layers of FL Studio capability

| 层次 / Layer | 实际内容 / Scope | 依据 / Reference |
| --- | --- | --- |
| Community backend | transport、Channel、routing、Mixer与已加载插件参数、Piano Roll写入及状态读取 / Execution and state interfaces | [固定上游快照](../third_party/fl-studio-mcp/README.md) |
| DAWLoop Controller | 工程/Pattern/Channel/PPQ身份，已有Pattern和Channel的目标导航 / Identity and navigation of existing targets | [Controller source](../src/dawloop/fl_scripts/device_DAWLoopController.py)、[MCP wrapper](../src/dawloop/fl_scripts/device_DAWLoopMCP.py) |
| Runtime研究路径 / Research workflow | 目标约束、一次派发、人工接受、观察与完成记录 / Constrained dispatch, human acceptance and observation | [现场记录](../evidence/public/fast_session_7.json)、[部署合同](DEPLOYMENT.md) |

DAWLoop 自有导航扩展与 Community backend 的 Pattern 工具范围分别管理。上游快照不能创建、切换、重命名或克隆 Pattern；DAWLoop 可识别并导航已有目标。新 Pattern 创建和自动加载新插件属于后续实现范围，不能从上游限制推导本项目未来上限。

DAWLoop navigation and upstream Pattern tools are separate. The pinned upstream does not manage Patterns; DAWLoop identifies and navigates existing targets. Creating new Patterns and loading new plugins are separate future capabilities.

## 验证依据 / Verification evidence

| 证据 / Evidence | 当前范围 / Current scope |
| --- | --- |
| Offline tested | Core计划、Exact-Set多重集合算法、Production工具及接口回归 / Planning, comparison algorithms, production utilities and interface regression |
| Maintainer live tested | 维护者真实FL接入报告；明确测试目标中的Controller导航与受限Native FAST操作 / Maintainer FL integration, scoped navigation and Native FAST |
| Archived evidence | [公开记录索引](../evidence/public/README.md)，包含指定测试的脱敏观察与结果 / Scoped sanitized observations and results |
| Live verification | 按每个操作的实际读回与比较合同判定。历史Native FAST终态保持COMPLETED_UNVERIFIED；完整producer notes读回尚不满足Exact-Set认证 / Operation-specific contracts; historical Native FAST remains COMPLETED_UNVERIFIED |

归档不是自动PASS；工具返回成功、观察性确认和完整事件集合核对分别记录。[验证规则](VERIFICATION.md) 保留全部安全要求。

Archived evidence is assessed against its operation contract; tool success, observation and complete event comparison remain separate.

## 当前版本说明 / Current Release Notes

Desktop 0.5.6-alpha.1 是公开Windows x64 Pre-release，源码在发行标签。随包分析支持WAV；Basic Pitch首次安装暂不可用，现有核验环境可用。高级模型依实际配置；完整风格学习、YuE2完整生成、通用AutoMix、任意工程持续写入及Desktop实时Host/Mixer接线尚属独立研究。干净Windows兼容性未独立验证；公开更新通知关闭。

Desktop is a public Windows Alpha with source at its release tag. WAV analysis is bundled; first-time Basic Pitch installation is unavailable while existing verified environments work. Advanced models, full style learning, full YuE2 generation, general AutoMix and seamless Desktop host integration remain separate research tracks. Independent clean-Windows compatibility awaits validation; public notifications are disabled.

[历史能力快照](archive/public-presentation-20261014/docs__CAPABILITIES.md.txt) · [Release](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) · [Roadmap](ROADMAP.md)
