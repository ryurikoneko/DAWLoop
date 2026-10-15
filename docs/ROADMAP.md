# DAWLoop 产品方向 / Product roadmap

DAWLoop 的方向是让音乐素材、可编辑的想法和真实宿主操作连成一个可理解的工作流。我们从创作者能亲自选择和修改的成果开始，逐步扩展Agent可以执行、观察和核对的任务。

DAWLoop aims to connect musical material, editable ideas and real host actions in an understandable workflow. We start with results creators can choose and revise, then expand the tasks agents can execute, observe and evaluate.

## 现在可以从哪里开始 / Where to start today

Desktop Alpha提供试听、WAV分析、规则辅助旋律、Piano Roll、保存与MIDI导出，以及Basic Pitch组件安装入口。Python Runtime提供音乐时间、计划、Production分析、Agent合同与执行适配。已有受限的FL Studio目标识别、导航和Native操作记录，展示这些部分如何相遇。

Desktop Alpha provides listening, WAV analysis, rule-assisted melodies, Piano Roll editing, saved work, MIDI export and Basic Pitch component setup. Python Runtime provides musical timing, plans, production analysis, agent contracts and adapters. Scoped FL Studio identity, navigation and Native operation records show how these parts can meet.

[Desktop体验](DESKTOP.md) · [Runtime Quickstart](QUICKSTART.md) · [真实宿主案例](DEMOS.md) · [能力目录](CAPABILITIES.md)

## 更连贯的Desktop工作流 / A smoother Desktop workflow

让第一次导入音频、理解报告、创建候选旋律、保存和继续编辑更容易衔接。组件管理应更清楚地解释下载、许可、磁盘与运行条件；中英文使用指南应各自围绕实际操作组织。对创作者而言，这意味着减少环境摸索，把更多时间留给音乐选择。

Connect first import, report interpretation, melody candidates, saving and further editing more smoothly. Component management should explain download, license, disk and runtime requirements clearly, with separate task-oriented Chinese and English guides. Creators should spend less time on setup and more on musical decisions.

## 更丰富的FL Studio目标与操作 / Richer FL Studio targets and actions

在已有Pattern、Channel身份读取与导航的基础上，研究更完整的目标组织、Pattern管理与多对象操作。每类操作都需要明确其对象、范围、授权和反馈方式，让“改哪段、哪个乐器、哪些事件”成为可检查的计划。

Build on existing Pattern/Channel identity and navigation toward richer target organization, Pattern management and multi-object operations. Each operation needs explicit objects, bounds, authorization and feedback so the intended passage, instrument and events form an inspectable plan.

## 更完整的写入与读回 / Stronger write and readback workflows

把实际宿主中的音符与计划联系起来，保存独立读回和比较结果。统一的记录结构有助于复现问题、定位偏差，并为后续Agent动作提供依据。重复事件、时间单位和目标身份都应在对应操作合同中说明。

Connect actual host notes to their plans and preserve independent readback and comparison. Consistent records help reproduce problems, locate differences and inform later agent actions. Multiplicity, time units and target identity belong in each operation's contract.

## Mixer与混音辅助 / Mixer and production assistance

先验证推子是否写到请求值，再测量声音是否进入目标区间。Phase A比较控制值并记录容差来源；Phase B使用新音频评估结果；Phase C根据结果重新规划，并保留每次尝试的历史。这使Agent可以区分控制问题与混音策略问题。

First establish whether a fader reached its requested value, then measure whether audio entered the target range. Phase A compares control values with a traceable tolerance; Phase B evaluates newly measured audio; Phase C replans while retaining each attempt. This distinguishes control failures from production-strategy failures.

## 能持续协作的Agent / Agents that can keep collaborating

连接音乐约束、计划适配、宿主操作和反馈，使下一轮制作依赖前一轮实际取得的结果。人工预览、接受与停止应成为自然的协作环节；用户保留创作方向和危险操作的决定权。

Connect musical constraints, plan adaptation, host actions and feedback so each next step uses the results actually obtained. Preview, human acceptance and stopping should feel like natural collaboration, with the user retaining creative and safety decisions.

## 音乐检索、分析与生成 / Retrieval, analysis and generation

研究怎样从获准素材中取得有用特征、比较候选、组织参考并辅助创作。模型接入分别评估素材权利、设备要求、实际推理和输出质量，让分析与生成成为可审阅、可编辑的音乐成果。

Explore useful features from permitted material, candidate comparison, references and creation assistance. Model integrations are evaluated for material rights, device requirements, actual inference and output quality, leading to results people can review and edit.

## 参与方向 / Ways to contribute

可以从使用反馈、指南与翻译、音乐分析器、合成测试素材、目标检查或adapter合同入手。[贡献指南](../CONTRIBUTING.md) 说明各入口；[验证文档](VERIFICATION.md) 保存操作规则，[历史路线档案](archive/public-presentation-20261014/docs__ROADMAP.md.txt) 保留此前工程记录。

Contribute workflow feedback, guides and translations, analyzers, synthetic fixtures, target checks or adapter contracts. The contribution guide provides entry points; verification rules and the linked archive preserve the engineering record.

## 当前版本说明 / Current Version Notes

- 当前公开Desktop为 `0.5.6-alpha.2`；实际交付以 [Releases](https://github.com/ryurikoneko/DAWLoop/releases) 为准。 / The public Desktop is Alpha.2; Releases define actual delivery.
- 本页是产品方向，不承诺发布日期或所有方向都进入下一版本。 / These are directions, without promised dates or a guarantee for the next release.
- 本地编辑、Community工具与Native宿主操作按不同路径交付和验证。 / Local editing, Community tools and Native host operations have distinct delivery and verification paths.
- 控制层与音频结果层保持独立，归档记录保留原终态。 / Control and audio outcomes remain separate; archived records retain their original terminal states.
