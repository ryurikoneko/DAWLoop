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
| `src/dawloop/setup.py` / `src/dawloop/cli.py` | `CONFIRMED_PROJECT_GENERATED` | 安装、doctor、CLI 与集成胶水；CLI 后续增加 Production Pipeline API 入口 |
| `src/dawloop/production/environment.py` | `CONFIRMED_PROJECT_GENERATED` | Production Pipeline 环境档案及可选依赖探测 |
| `tests/test_*.py`（除明确第三方 fixture 外） | `CONFIRMED_PROJECT_GENERATED` | 使用自造测试数据；当前不包含第三方音乐作品 fixture |

公开 clean-core 的历史创建提交仍保留在 Git 历史中；本文件不重写历史 commit，只维护当前来源状态。

## FL Studio MCP 固定源码快照

| 路径范围 | 分类 | 来源 | 许可 / 版权 | 状态 |
|---|---|---|---|---|
| `third_party/fl-studio-mcp/**` | `THIRD_PARTY` | `karl-andres/fl-studio-mcp` commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0` | MIT；保留 calvinw 与 Karl Andres 原版权 | 固定快照，未改写为 DAWLoop 原创 |

Bundled 运行文件包括 upstream `LICENSE`、`README.md`、`pyproject.toml`、FL controller script、ComposeWithLLM script，以及 `src/fl_studio_mcp/` 下运行所需 Python 文件。DAWLoop-specific adapter 位于 `src/dawloop/adapters/fl_studio_mcp/`，与第三方源码分离。

## Production Pipeline / whale-music-pipeline

来源：维护者提供的 whale-music-pipeline 源码包。压缩包中的代码声明为 MIT License，版权文本为 `Copyright (c) 2026 whale-music-pipeline contributors`；开发者为坏影子不坏（Bilibili UID 599132499）；维护者报告已获开发者直接授权复用代码。

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

某段代码来源合法、许可证清楚，并不等于其行为已经在 FL Studio 中现场验证。同样，某个 third-party backend 支持一项能力，也不自动等于 DAWLoop 对该能力宣称 `Verified`。

DAWLoop 对 DAW-changing operation 继续使用：

`Plan → Execute → Read Back → Verify → PASS / STOP`

基于 whale-music-pipeline 改编的 MIDI、编排、RMS 或推子标定工具可以为下一步计划提供证据，但只有真实 DAW 状态读回并满足对应验证规则时，才允许把具体操作记录为 `PASS`。

## 许可摘要

- DAWLoop 自有代码：根目录 MIT License，Copyright (c) 2026 ryurikoneko。
- Bundled FL Studio MCP：其 upstream MIT License 与原作者版权保持不变。
- whale-music-pipeline 改编代码：基于所提供源码包中的 MIT 许可代码，记录开发者坏影子不坏（Bilibili UID 599132499）及维护者报告的直接复用授权。
- Python dependencies 通过包管理器安装，不把其源码自动重新许可为 DAWLoop MIT。

更完整的第三方声明见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
