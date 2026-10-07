# 来源记录 / Provenance

DAWLoop 的公开仓库从独立、干净的 Git 历史开始。项目自己的 Core、Schema、测试和文档按本仓库需求编写；第三方源码或基于第三方实现改编的文件必须单独标记来源、许可证和边界。

当前公开开发树中存在两类有意引入的第三方来源：

1. **FL Studio MCP**：以固定 upstream commit 的源码快照形式放在 `third_party/fl-studio-mcp/`，分类为 `THIRD_PARTY`。
2. **Production Pipeline / whale-music-pipeline**：由维护者提供的 whale-music-pipeline 源码包中的 MIT 代码。通用算法被整理到 `src/dawloop/production/`，分类为 `ADAPTED_FROM_THIRD_PARTY`；原始代码许可证保存在 `third_party/whale-music-pipeline/LICENSE`。

旧 Private FLSkill-lab 仍只作为行为规格、架构要求和历史验证边界的参考；本公开仓库没有直接迁移其中来源不明确的旧实现。根目录 `LICENSE` 是 DAWLoop 自有代码的 MIT License，不会覆盖第三方组件自己的版权和许可声明。

## 分类定义

- `CONFIRMED_PROJECT_GENERATED`：在 DAWLoop 公开仓库中为本项目新建/重写的文件或胶水代码。
- `THIRD_PARTY`：按原作者/上游形式收录的第三方文件或许可证文本。
- `ADAPTED_FROM_THIRD_PARTY`：明确基于第三方源码算法或实现改编、重构或通用化的文件；必须保留 attribution 和适用许可证。

这些标签用于工程来源管理，不替代完整的法律权利调查。

## 项目与路径命名历史

项目名称依次为 `FLSkill` → `DAWProof` → `DAWLoop`。Python 包路径依次为 `src/flskill/` → `src/dawproof/` → `src/dawloop/`。本次迁移只更新当前路径和公开名称，不改写历史提交、tag 或 Release 中的旧名称。

## DAWLoop 自有 Core

代码目录由历史路径 `src/flskill/` 经 `src/dawproof/` 重命名为当前路径 `src/dawloop/`；表格记录的是当前路径，不改写历史提交中使用的旧路径。历史 tag 与发布记录保持原样。

下列模块属于 `CONFIRMED_PROJECT_GENERATED`，最初在公开 clean implementation 中从空白实现：

| 路径范围 | 分类 | 说明 |
|---|---|---|
| `src/dawloop/time/**` | `CONFIRMED_PROJECT_GENERATED` | Musical Grid、确定性 absolute tick 解析 |
| `src/dawloop/note_plan/**` | `CONFIRMED_PROJECT_GENERATED` | NoteEvent / NotePlan 数据模型和验证 |
| `src/dawloop/io/**` | `CONFIRMED_PROJECT_GENERATED` | Writer / Reader Protocol 和离线内存实现 |
| `src/dawloop/verification/**` | `CONFIRMED_PROJECT_GENERATED` | Exact-Set Verification、重复事件计数、PASS / STOP 语义 |
| `schemas/note_plan.schema.json` | `CONFIRMED_PROJECT_GENERATED` | Note Plan JSON Schema |
| `src/dawloop/adapters/fl_studio_mcp/**` | `CONFIRMED_PROJECT_GENERATED` | DAWLoop 特有的 MCP 调用、目标身份门控、映射、读回与验证报告；不复制 upstream server 实现 |
| `src/dawloop/midi_setup.py`, `src/dawloop/setup.py`, `src/dawloop/fl_mcp_server.py`, `src/dawloop/fl_scripts/device_DAWLoopController.py` | `CONFIRMED_PROJECT_GENERATED` | 统一控制器封装、只读身份请求复用、MIDI 端口与 loopMIDI 诊断、模块/OnInit/READY 生命周期诊断、User Script 安装器和 bundled backend 端口选择胶水；上游实现仍单独归类 |
| `docs/FL_STUDIO_SETUP.md` | `CONFIRMED_PROJECT_GENERATED` | 一次性 MIDI / User Script 配置和诊断说明；supportedDevices 行为参考 Image-Line 官方文档 |
| `tests/test_midi_setup.py` | `CONFIRMED_PROJECT_GENERATED` | 合成设备名称与 mock 环境下的诊断测试 |
| `src/dawloop/fl_scripts/**` | `CONFIRMED_PROJECT_GENERATED` | 新写的只读 FL Studio 目标身份查询脚本；复用上游 MIDI/JSON 通道并委托非身份命令，未改动 bundled 上游源码 |
| `src/dawloop/setup.py` / `src/dawloop/cli.py` | `CONFIRMED_PROJECT_GENERATED` | 安装、doctor、CLI 与集成胶水；CLI 后续增加 Production Pipeline API 入口 |
| `src/dawloop/controller_runtime.py` | `CONFIRMED_PROJECT_GENERATED` | 以已安装 Controller 的绝对目录统一解析生命周期标记、READY 状态、build identity 和心跳新鲜度；不依赖磁盘 SHA 推断内存运行版本 |
| `src/dawloop/updates.py`, `tests/test_updates.py` | `CONFIRMED_PROJECT_GENERATED` | 新写的公开 Release 查询、24 小时成功/失败缓存、安装来源识别、只读 Controller 版本观察及合成测试；仅提醒，不升级或操作宿主 |
| `tests/test_controller_runtime.py` | `CONFIRMED_PROJECT_GENERATED` | 合成状态 JSON 与 mock FL API 下的路径一致性、模块/OnInit/READY 生命周期、错误阶段和 PING 门禁测试 |
| `src/dawloop/production/environment.py` | `CONFIRMED_PROJECT_GENERATED` | Production Pipeline 环境档案及可选依赖探测 |
| `tests/test_*.py`（除明确第三方 fixture 外） | `CONFIRMED_PROJECT_GENERATED` | 使用自造测试数据；当前不包含第三方音乐作品 fixture |
| `tests/live_fl/capture_note_roundtrip.py` / `tests/live_fl/probe_target_identity.py` / `tests/live_fl/README.md` | `CONFIRMED_PROJECT_GENERATED` | 本项目新建的开发期现场证据采集器、只读身份探测与说明；没有复制第三方实现；实际运行证据默认不纳入 Git |

公开 clean-core 的历史创建提交仍保留在 Git 历史中；本文件不重写历史 commit，只维护当前来源状态。

## FL Studio MCP 固定源码快照

| 路径范围 | 分类 | 来源 | 许可 / 版权 | 状态 |
|---|---|---|---|---|
| `third_party/fl-studio-mcp/**` | `THIRD_PARTY` | `karl-andres/fl-studio-mcp` commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0` | MIT；保留 calvinw 与 Karl Andres 原版权 | 固定快照，未改写为 DAWLoop 原创 |

Bundled 运行文件包括 upstream `LICENSE`、`README.md`、`pyproject.toml`、FL controller script、ComposeWithLLM script，以及 `src/fl_studio_mcp/` 下运行所需 Python 文件。DAWLoop-specific adapter 位于 `src/dawloop/adapters/fl_studio_mcp/`，与第三方源码分离。

## Production Pipeline：创作者致谢与代码来源

**创作者与工作流启发：** 感谢 Bilibili 创作者 [坏影子不坏](https://space.bilibili.com/599132499)（UID 599132499）。其 DSH 视频 / 工作流展示（包括[这条视频](https://www.bilibili.com/video/BV1PTht6cENP/)）及相关制作自动化实践，对 DAWLoop Production Pipeline 的编曲 / orchestration analysis、MIDI / section analysis、playback / loopback measurement、active-frame RMS、FL Studio Mixer / fader calibration 和 production workflow automation 设计有重要启发。这里的 DSH 指创作者的视频与工作流展示，不是单独打包的软件或代码来源。

**代码来源与许可：** Production Pipeline 的部分通用化代码改编自维护者提供的 `whale-music-pipeline` 源码包。压缩包中的代码声明为 MIT License，版权文本为 `Copyright (c) 2026 whale-music-pipeline contributors`；维护者报告已获开发者直接授权复用代码，原始许可证保存在 `third_party/whale-music-pipeline/LICENSE`。创作者致谢、工作流启发与实际代码来源分别记录，不改变 DAWLoop 自有代码的归属。

详细记录见 [`docs/PRODUCTION_PIPELINE_PROVENANCE.md`](docs/PRODUCTION_PIPELINE_PROVENANCE.md)。当前分类如下：

| 路径 | 分类 | 原始来源 / 改编关系 | 许可 |
|---|---|---|---|
| `third_party/whale-music-pipeline/LICENSE` | `THIRD_PARTY` | supplied archive root `LICENSE` 中代码许可部分 | MIT |
| `src/dawloop/production/smf.py` | `ADAPTED_FROM_THIRD_PARTY` | `scripts/mix/midi-windows.py` | MIT；保留 attribution |
| `src/dawloop/production/mix.py` | `ADAPTED_FROM_THIRD_PARTY` | `active-rms.py`、`fader-plan.py`、`level-balance.py` | MIT；保留 attribution |
| `src/dawloop/production/loopback.py` | `ADAPTED_FROM_THIRD_PARTY` | WASAPI loopback scripts | MIT；保留 attribution |
| `src/dawloop/production/sf2.py` | `ADAPTED_FROM_THIRD_PARTY` | `scripts/score/sf2.py` | MIT；保留 attribution |
| `src/dawloop/production/orchestration.py` | `ADAPTED_FROM_THIRD_PARTY` | `scripts/orch/orch-fugue-v2.py` 中可复用的 register / gap / source-coverage 思路，已移除具体作品数据 | MIT；保留 attribution |
| `src/dawloop/production/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | DAWLoop 新建 package glue | 根项目 MIT |
| `tests/test_production_pipeline.py` | `CONFIRMED_PROJECT_GENERATED` | DAWLoop 新建；仅使用合成 MIDI / 波形 / NoteEvent | 根项目 MIT |
| `docs/PRODUCTION_PIPELINE.md` | `CONFIRMED_PROJECT_GENERATED` | DAWLoop 新写集成说明 | 根项目 MIT |
| `docs/PRODUCTION_PIPELINE_PROVENANCE.md` | `CONFIRMED_PROJECT_GENERATED` | DAWLoop 新写来源附录 | 根项目 MIT |

压缩包中的 `docs/` 被其作者标注为 CC BY 4.0，`examples/` 乐谱/MIDI 另带署名/非商业条件，因此这些非代码资产没有直接放入 DAWLoop 的 MIT 代码包。它们可用于理解 Production Pipeline 工作流，但不会被误标为 DAWLoop 原创或 MIT 示例资产。

### 环境耦合与可移植性边界

supplied archive 未包含 `track-scan.py` 引用的 `spectrum-peak` 模块。原开发者报告该工作流可在其已配置的制作环境中运行，因此标记为 `ENVIRONMENT_COUPLED` / `PORTABILITY_NOT_ESTABLISHED`；当前尚未建立便携配置。

`fugue-v4.py` 通过 `sys.argv[1]` 接收输出路径；不带参数的裸调用会失败。原开发者报告其正常调用路径会提供所需上下文，因此标记为 `INVOCATION_ASSUMPTION` / `PORTABILITY_NOT_ESTABLISHED`。

`src/dawloop/production/environment.py` 是本项目新建的环境档案与可选依赖探测代码，分类为 `CONFIRMED_PROJECT_GENERATED`。档案把原开发者环境标为 `reported_working`，并独立记录当前便携环境的实际探测结果；前者是开发者报告，不能当作 DAWLoop 兼容性验证。

## 项目文档、展示与贡献文件

以下文件均为 DAWLoop 自己撰写/维护，分类为 `CONFIRMED_PROJECT_GENERATED`；它们可以总结第三方行为，但不复制第三方实现源码：

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/VERIFICATION.md`
- `docs/QUICKSTART.md`
- `docs/ROADMAP.md`
- `docs/FL_STUDIO_MCP.md`
- `docs/ACKNOWLEDGEMENTS.md`
- `docs/PRODUCTION_PIPELINE.md`
- `docs/PRODUCTION_PIPELINE_PROVENANCE.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/ISSUE_TEMPLATE/**`
- `.github/pull_request_template.md`
- `THIRD_PARTY_NOTICES.md`

## 验证与来源是两条独立轴

### 运行时第二版第一轮

[KNOWN｜HIGH] `src/dawloop/runtime/`、`src/dawloop/adapters/gopher_native/` 及对应测试和文档为本项目独立实现，分类为 `CONFIRMED_PROJECT_GENERATED`。原生协议研究参考 [宿主桥接协议说明](https://github.com/sadoway7/flaik/blob/main/gopher_override/FL_BRIDGE_PROTOCOL.md)和其公开工具参数定义；没有复制参考项目源码、界面、知识库或手册资源。原生依赖通过可选安装项提供。

[KNOWN｜HIGH] 新运行时将执行确认与结果验证分开，旧音符适配器保持下述闭环契约。当前Native FAST固定16-note流程已有受限现场证据；producer绑定/Exact Set未认证。模拟基准不构成真实宿主性能证据。

某段代码来源合法、许可证清楚，并不等于其行为已经在 FL Studio 中现场验证。同样，某个 third-party backend 支持一项能力，也不自动等于 DAWLoop 对该能力宣称 `Verified`。

DAWLoop 的 VERIFIED 契约使用下列闭环；Native FAST 使用观察与人工接受，结果为COMPLETED_UNVERIFIED：

`Plan → Execute → Read Back → Verify → PASS / STOP`

基于 whale-music-pipeline 改编的 MIDI、编排、RMS 或推子标定工具可以为下一步计划提供证据，但只有真实 DAW 状态读回并满足对应验证规则时，才允许把具体操作记录为 `PASS`。

## 许可摘要

- DAWLoop 自有代码：根目录 MIT License，Copyright (c) 2026 ryurikoneko。
- Bundled FL Studio MCP：其 upstream MIT License 与原作者版权保持不变。
- whale-music-pipeline 改编代码：基于所提供源码包中的 MIT 许可代码，记录开发者坏影子不坏（Bilibili UID 599132499）及维护者报告的直接复用授权。
- Python dependencies 通过包管理器安装，不把其源码自动重新许可为 DAWLoop MIT。

更完整的第三方声明见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。


## Learning Framework 与来源清单（2026-10-07）

[KNOWN｜HIGH] src/dawloop/learning、learning/prompts、合成generic_learning例子、src/dawloop/provenance.py及对应测试为本项目新增实现，继续MIT。Schema源只有随包安装的一份；没有引入艺术家样本或官方手册全文。NOTICE/AUTHORS/CITATION.cff记录来源，不增加MIT之外的引用义务。

[KNOWN｜HIGH] dawloop provenance的默认清单是开发快照，记录当前HEAD、dirty状态与实际允许列表字节hash；并不把未提交实现归为HEAD既有内容，也不证明签名、作者或研究优先权。LICENSE_POLICY.md明确未来新研究资产的逐项许可与发布准备；本轮不改变既有资料许可。

## Runtime V2 research-preview 发布范围

[KNOWN｜HIGH] 新增 runtime、Native adapter、Controller导航、FAST/MCP胶水、MusicalPlan、learning合同及对应研究/测试为本项目自有实现；继续MIT。third_party固定快照与Production改编的既有版权保持。公开catalog是现场工具参数事实记录；固定回归source是本项目生成。

[KNOWN｜HIGH] evidence/public只含脱敏摘要；完整私有会话、FLP、截图、Memos、凭据与development-manifest不发布。历史模板NPZ仅含受审窗口标题/按钮条裁剪，不含私人桌面；Auto Accept仍延期且默认关闭。合成JPEG仅作返回格式回归。

[KNOWN｜HIGH] 发布清理只参数化维护者安装路径、迁移回归输入、保留关闭标记并使缺失状态拒绝。未重新进行现场实验，已认证范围没有扩张；重整的公开源码摘要与原实验源码冻结记录属于不同版本证据。
