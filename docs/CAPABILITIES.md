# 选择你的音乐工作流 / Find your music workflow

DAWLoop 通过 Desktop、Plugin 和 Runtime 三种产品提供入口：创作者可以在 Desktop 中研究素材、制作旋律和编辑音符；开发者可以用 Runtime 组织音乐计划，接入分析工具与真实 DAW 后端。本页按任务介绍实现位置，便于选择适合自己的入口。

DAWLoop provides three product routes: Desktop, Plugin and Runtime. creators can study audio, build melodies and edit notes in Desktop; developers can use Runtime to structure musical plans and connect analysis tools with real DAW backends. This catalog connects tasks to their implementations.

## Desktop：从素材到旋律 / From material to melody

导入一段 WAV，先试听，再查看能量、节奏变化与调性候选；选择和声、节奏、密度和 Seed 后创建旋律，在本地 Piano Roll 调整音高、起点、时值和力度。保存报告与乐谱后可以重新打开；导出的 MIDI 可进入后续制作。

Import a WAV, listen, and inspect energy, rhythm changes and key candidates. Create a melody with harmony, rhythm, density and seed controls, then adjust pitch, timing, duration and velocity in the local Piano Roll. Saved reports and scores can be reopened; exported MIDI carries the result into further production.

| 想做什么 / Task | 实现 / Implementation | 使用与源码 / Guide and source |
| --- | --- | --- |
| 研究音频 / Study audio | 试听、定位、WAV测量与分析报告 / Playback, seeking, WAV measurements and reports | [Desktop guide](DESKTOP.md)、[Music Intelligence UI](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/apps/desktop/src/MusicIntelligence.tsx) |
| 准备旋律候选 / Create melody candidates | 和声、节奏、密度、Seed等约束的规则生成 / Rule-based generation with musical constraints | [Composer controls](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/apps/desktop/src/ComposerControls.tsx) |
| 审阅和编辑 / Review and edit | 音符选择、移动、属性、力度、撤销重做、试听及MIDI导出 / Note selection, movement, properties, velocity, undo/redo, audition and MIDI export | [Piano Roll](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/apps/desktop/src/PianoRoll.tsx) |
| 从音频取得音符 / Transcribe audio | 经组件管理器安装并配置Basic Pitch后运行转录 / Transcription after installing and configuring Basic Pitch | [Component setup](DESKTOP.md)、[Pitch component](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/packages/music-intelligence/pitch-component.mjs) |
| 保留创作成果 / Keep results | 主动保存报告、命名乐谱、重启后重新打开，中英文界面 / Explicit report and score saving, reopening after restart, Chinese/English UI | [Worked example](DEMOS.md) |

## Plugin：宿主内的制作工作区 / Production inside the host

Plugin 自有实现闭源，与本仓库开源代码分别交付。当前 Composer r2 是已公开的 [Windows x64 VST3 预发行版](https://github.com/ryurikoneko/DAWLoop/releases/tag/plugin-v0.2.0-rc.1)，本轮仅交付 Composer。

Plugin is proprietary and delivered separately. Composer r2 is a [public Windows x64 VST3 prerelease](https://github.com/ryurikoneko/DAWLoop/releases/tag/plugin-v0.2.0-rc.1). This delivery includes Composer only.

| 用户任务 / Task | 实际范围 / Scope |
| --- | --- |
| 参考与创作 / Reference and creation | 标准 MIDI、官方 MIDI 剪贴板、提示词、和声画布、候选与历史 / Standard MIDI, official MIDI clipboard, prompts, harmonic canvas, candidates and history |
| 比较与带回宿主 / Review and host transfer | A/B、采样钢琴试听、和弦/音区设置、MIDI 导出与拖出 / A/B, sampled-piano audition, chord/register controls, MIDI export and drag |
| 个性化 AI / Personal AI | 配置自己的 API，或让 Agent 连接插件 / Configure your API or connect an agent |
| 当前钢琴窗 / Current Piano Roll | 可选辅助脚本快照，无需保存工程；名称桥接与音符读取分开 / Optional unsaved snapshot helper; name browsing separate from note reading |

具体交付、测试范围及旧保存工程读取的外部依赖见 [Plugin 指南](PLUGINS.md)。 / See the Plugin guide for delivery, test scope and the external dependency of saved-project reading.

## Agent / Runtime：把意图变成可处理的计划 / Turn intent into a plan

例如“准备两小节短句”需要明确拍号、PPQ、时间范围、音高与力度。Runtime 用音乐网格解析位置，以 NotePlan 表达精确事件，以 MusicalPlan 和 Learning 合同承接更高层输入。Writer、Reader 与比较器分离，使后端执行和结果核对可以独立测试。

A request such as “prepare a two-bar phrase” needs a meter, PPQ, bounded time range, pitches and velocities. Runtime resolves musical positions, represents exact events with NotePlan, and uses MusicalPlan and Learning contracts for higher-level input. Writers, readers and comparators remain separate so execution and evaluation can be tested independently.

| 任务 / Task | 实现位置 / Implementation | 起点 / Start here |
| --- | --- | --- |
| 解析音乐时间 / Resolve timing | [time.py](../src/dawloop/time/grid.py) | [Quickstart](QUICKSTART.md) |
| 组织事件 / Structure events | [note_plan.py](../src/dawloop/note_plan/model.py) | [Example plan](../examples/note_plan.example.json) |
| 输入、特征与音乐计划 / Inputs, features and plans | [Learning contracts](../learning/WORKFLOW.md) | [Runnable synthetic example](../learning/examples/generic_learning/run.py) |
| 比较计划与实际事件 / Compare plan and actual events | [verification.py](../src/dawloop/verification/exact_set.py) | [Verification model](VERIFICATION.md) |
| 约束研究性宿主任务 / Bound host operations | [FAST runtime](../src/dawloop/runtime/fast_music.py) | [Deployment](DEPLOYMENT.md) |

## FL Studio：明确目标，再执行和观察 / Target, execute and observe

执行工具负责把操作送进真实 FL Studio。DAWLoop 在其外组织目标身份、音乐计划、操作边界和反馈。例如修改已有目标中的旋律时，先读取 Pattern、Channel 与 PPQ，导航到指定对象，再派发所选后端支持的操作；完成回执与适用的读回分别保存。

Execution tools reach the running FL Studio application. DAWLoop surrounds them with target identity, musical plans, bounded actions and feedback. For an existing melody target, it reads Pattern, Channel and PPQ, navigates to the intended object, dispatches an operation supported by the chosen backend, and records completion separately from applicable readback.

| 路径 / Path | 提供什么 / Provides | 实现依据 / Source |
| --- | --- | --- |
| Bundled Community FL Studio MCP | Transport、Channel、routing、Mixer、已加载插件参数及Piano Roll工具 / Execution and state tools | [Pinned upstream README](../third_party/fl-studio-mcp/README.md) |
| DAWLoop Controller | 工程、Pattern、Channel、PPQ身份，以及已有目标导航 / Context identity and existing-target navigation | [Controller](../src/dawloop/fl_scripts/device_DAWLoopController.py)、[Target preparation](../src/dawloop/adapters/fl_target_preparation.py) |
| Community note adapter | NotePlan转换、目标检查、独立状态刷新与比较 / Plan conversion, target checks, separate state refresh and comparison | [Adapter](../src/dawloop/adapters/fl_studio_mcp/adapter.py) |
| Native Gopher research path | 受控派发、宿主预览、人工接受与现场观察 / Bounded dispatch, host preview, human acceptance and observation | [Native backend](../src/dawloop/adapters/gopher_native/transport.py)、[Archived scenario](../evidence/public/fast_session_7.json) |

这些是不同执行路径；[连接原理](FL_STUDIO_MCP.md) 展开它们的调用、目标与反馈关系。上游不提供 Pattern 管理；DAWLoop 的已有目标导航是自有扩展。

These are different execution paths. [FL Studio integration](FL_STUDIO_MCP.md) explains their targets and feedback. Existing-target navigation is a DAWLoop extension, separate from the upstream's Pattern tool limitations.

## Production Pipeline：为下一步制作提供依据 / Inform the next production step

| 任务 / Task | 输出 / Output | 实现 / Source |
| --- | --- | --- |
| 了解MIDI与密集片段 / Inspect MIDI and dense sections | 轨道名、note-on事件与建议小节窗口 / Track names, note-on events and suggested bar window | [smf.py](../src/dawloop/production/smf.py) |
| 检查配器与音域 / Inspect orchestration | 乐句音域适配、空缺音区、源音符覆盖 / Phrase fit, register gaps and source coverage | [orchestration.py](../src/dawloop/production/orchestration.py) |
| 研究响度与推子 / Study levels and faders | Active RMS、峰值、校准映射与目标计划 / Active RMS, peaks, calibration and target plans | [mix.py](../src/dawloop/production/mix.py) |
| 测量与试听 / Measure and audition | 可选WASAPI捕获、SoundFont样本渲染 / Optional WASAPI capture and SoundFont rendering | [loopback.py](../src/dawloop/production/loopback.py)、[sf2.py](../src/dawloop/production/sf2.py) |
| 检查运行条件 / Inspect prerequisites | 当前环境的模块、工具与配置状况 / Modules, tools and configuration availability | [environment.py](../src/dawloop/production/environment.py) |

这些输出帮助选择片段、配器或下一次电平计划。[Production Pipeline](PRODUCTION_PIPELINE.md) 提供情境示例与API。

These outputs help choose a section, instrumentation or the next level plan. See [Production Pipeline](PRODUCTION_PIPELINE.md) for scenarios and APIs.

## 扩展与验证依据 / Extension and evidence

开发者可以添加分析器、音乐合同或执行 adapter；贡献应说明输入、输出、目标检查、错误路径和适用的读回规则。通过 [贡献指南](../CONTRIBUTING.md) 选择方向，通过 [术语表](GLOSSARY.md) 对齐概念。

Developers can contribute analyzers, musical contracts or execution adapters. Specify inputs, outputs, target checks, failure paths and applicable readback rules. Start with [Contributing](../CONTRIBUTING.md) and the [Glossary](GLOSSARY.md).

| 依据 / Evidence | 含义 / Meaning |
| --- | --- |
| Offline Tested | 对计划、算法、转换或接口运行可重复的离线检查 / Repeatable checks of plans, algorithms, conversions or interfaces |
| Maintainer Live Tested | 维护者在真实宿主中运行过指定流程 / A specific workflow run by the maintainer in the real host |
| Archived Live Evidence | 对应计划、环境、观察或结果已有公开记录 / Public records for the relevant plan, environment, observation or result |
| Live Verified | 对指定操作，归档证据满足其验证合同并取得PASS / Archived evidence satisfies the specified operation's verification contract |

归档记录按其实际字段解读。[Native现场案例](../evidence/public/fast_session_7.json) 保留 `COMPLETED_UNVERIFIED`，Exact Set 为 `NOT_VERIFIED`；[验证文档](VERIFICATION.md) 解释完整事件比较、独立控制层与音频结果层的区别。

Read an archive according to its actual fields. The Native case retains `COMPLETED_UNVERIFIED` and Exact Set `NOT_VERIFIED`. [Verification](VERIFICATION.md) explains complete event comparison and the separation of control and audio outcomes.

[工作流文档来源 / Documentation sources](PRODUCT_WORKFLOWS_PROVENANCE.md)

## 当前版本说明 / Current Version Notes

- Desktop公开版本为Windows x64 `0.5.6-alpha.2`，源码位于发行标签；Python Runtime main独立演进。 / Desktop is the public Windows x64 Alpha.2, with source at its tag; Runtime main evolves separately.
- Basic Pitch首次安装由组件管理器提供，需要下载组件、确认许可与准备磁盘空间。 / First-time Basic Pitch setup requires component download, license review and disk space.
- Desktop本地Piano Roll与FL Studio宿主操作是不同工作流。 / Local Piano Roll editing and FL Studio host operations are distinct workflows.
- 完整宿主Exact-Set读回、通用Mixer自动化与多目标持续制作按各自合同推进。 / Complete host Exact-Set readback, general Mixer automation and sustained multi-target production follow separate contracts.
- 兼容性、下载和方向见 [Desktop](DESKTOP.md)、[Releases](https://github.com/ryurikoneko/DAWLoop/releases)、[Roadmap](ROADMAP.md)。 / See those pages for compatibility, downloads and directions.
