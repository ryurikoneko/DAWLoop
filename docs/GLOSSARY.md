# DAWLoop 术语表 / Glossary

这些术语连接创作者看到的工作区与开发者处理的计划、宿主状态和结果。 / These terms connect the creator workspace with developer-facing plans, host state and results.

| 术语 / Term | 含义 / Meaning |
| --- | --- |
| DAWLoop Desktop | 面向创作者的Windows工作区，提供试听、分析、旋律与本地编辑。源码在Desktop发行标签。 / The Windows creator workspace for listening, analysis, melody creation and local editing; source is at its release tag. |
| DAWLoop Runtime | 公开Python框架，处理音乐合同、计划、分析、执行适配与验证。 / The public Python framework for musical contracts, plans, analysis, adapters and verification. |
| Music Intelligence | Desktop中连接音频研究、规则旋律、转录组件与编辑的工作区。 / The Desktop workspace connecting audio study, rule-based melodies, transcription components and editing. |
| Piano Roll | 音高与时间轴上的音符编辑方式。Desktop的本地编辑器与FL Studio的宿主窗口是不同对象。 / A pitch/time note editor; Desktop's local editor and FL Studio's host window are distinct. |
| Brain / Hands / Ears | 帮助理解职责的比喻：计划与规则、宿主执行、分析与测量。 / A guide to responsibilities: planning/rules, host execution, and analysis/measurement. |
| Music Plan | 音乐意图与操作范围的通称，不代表任意自然语言都能自动执行。 / A general term for musical intent and operation bounds, rather than automatic execution of arbitrary language. |
| NotePlan | Core中明确目标、网格、范围与音符事件的合同。 / The Core contract for a target, grid, bounds and note events. |
| MusicalPlan | Learning流程与计划适配使用的结构化音乐数据合同，与具体后端命令有转换边界。 / Structured musical data used by Learning and plan adaptation, with a conversion boundary to backend commands. |
| Execution Backend | 真正向宿主派发操作的实现，例如Community FL Studio MCP或Native Gopher路径。 / The implementation that dispatches host actions, such as Community FL Studio MCP or the Native Gopher path. |
| MCP | Model Context Protocol。Community FL Studio MCP是bundled第三方后端；DAWLoop自己的MCP服务是另一工具入口。 / Model Context Protocol. The bundled Community backend and DAWLoop's own MCP tool server are distinct roles. |
| DAWLoop Controller | 安装到FL Studio的User Script，提供DAWLoop身份读取、导航及统一脚本入口。 / The FL Studio User Script providing identity, navigation and the unified script entry point. |
| Target Identity | 工程上下文、Pattern、Channel、PPQ等真实字段及其匹配关系。 / Real context fields such as project, Pattern, Channel and PPQ, and whether they match the intended target. |
| Execution | 请求被派发或宿主执行了动作；具体回执由对应合同定义。 / Dispatch or host action, with acknowledgements defined by its contract. |
| Observation | 对窗口、目标、回调等可获得状态的观察。 / Observation of available window, target, callback or other state. |
| Readback | 执行之后主动取得适用实际状态；完整事件读回应包含比较所需字段。 / A fresh acquisition of applicable actual state after execution; complete event readback includes comparison fields. |
| Verification | 按明确规则比较计划与实际证据。 / Evaluation of a plan against actual evidence under explicit rules. |
| Exact-Set | 比较音符多重集合，包含字段及完全重复事件的次数。 / Comparison of note multisets, including fields and duplicate counts. |
| PASS / STOP | PASS表示对应规则满足；STOP表示结果不符或依据不足，需要停止并检查。 / PASS means the applicable rules are satisfied; STOP means a mismatch or insufficient grounds to continue. |
| Agent Workflow | 理解、规划、执行、观察、核验与决定下一步的循环，按需包含人工审阅。 / The loop of understanding, planning, acting, observing, evaluating and deciding, including human review where required. |
| Production Pipeline | MIDI、编配、音频、电平、SoundFont及环境分析工具，为后续计划提供输入。 / MIDI, orchestration, audio, level, SoundFont and environment tools that inform later plans. |
| Basic Pitch | 可选音频转录组件；经许可确认、安装与配置后提供音符候选，交由用户审阅。 / An optional transcription component that supplies note candidates after license review, installation and configuration. |
| Active RMS | 对超过门槛的音频帧计算的能量测量，与全文件RMS一起解读。 / An energy measure over frames above a floor, interpreted alongside whole-file RMS. |

阅读 [Desktop指南](DESKTOP.md)、[实际演示](DEMOS.md) 或 [架构](ARCHITECTURE.md)，查看这些概念如何组成工作流。证据等级与完整操作规则见 [Verification](VERIFICATION.md)。

See Desktop, Demos and Architecture for these concepts in a workflow; Verification defines evidence levels and operation rules.
