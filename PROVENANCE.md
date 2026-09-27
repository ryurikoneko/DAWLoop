# 来源记录

本仓库从空白 Git 仓库开始。FLSkill 自有源代码、Schema、测试及项目文档均按本仓库功能要求编写。自 v0.2 开发分支起，唯一有意包含的第三方源码例外是 `third_party/fl-studio-mcp/` 下固定版本的 FL Studio MCP snapshot；该目录文件明确归类为 `THIRD_PARTY`，逐文件与上游 commit blob 核对一致。没有迁移 Private FLSkill 未知来源实现、音乐作品或测试夹具。`LICENSE` 使用 SPDX 发布的标准 MIT 许可文本，单独记录其规范来源。

旧 Private 原库仅作为行为规格、架构要求和已记录验证边界的参考；没有从中复制代码、JSON Schema、文档、测试或配置。实现细节、测试数据和本仓库文案均为本仓库新建。

## 文件清单

| 路径 | 分类 | 创建来源 | 创建提交 | 外部参考 | 许可考虑 | 状态 |
|---|---|---|---|---|---|---|
| `LICENSE` | `CONFIRMED_PROJECT_GENERATED` | 项目权利人选择 MIT，并按标准文本填写版权年份与权利人 | b63c81c6b869f81485b408a4d6f57e7666dff109 | [SPDX MIT](https://spdx.org/licenses/MIT) | MIT；此文件是许可文本，不是第三方实现代码 | 已添加 |
| `.gitattributes` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建文本换行规范 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `.gitignore` | `CONFIRMED_PROJECT_GENERATED` | 本仓库初始化时新建，仅忽略 Python 生成物和本地构建输出 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `README.md` | `CONFIRMED_PROJECT_GENERATED` | 按本仓库实现和验证边界重新撰写；后续展示增强仍仅描述已实现能力和 Roadmap | b63c81c6b869f81485b408a4d6f57e7666dff109 | Private 项目行为规格；未复制旧文档 | MIT | 已创建并维护 |
| `docs/ROADMAP.md` | `CONFIRMED_PROJECT_GENERATED` | 按用户确认的阶段顺序新建路线图 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 本项目计划；未复制旧路线图 | MIT；无第三方实现代码 | 已添加 |
| `PROVENANCE.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库建立的逐文件来源台账 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT；本台账记录来源，不代替权利证明 | 已创建并维护 |
| `docs/ARCHITECTURE.md` | `CONFIRMED_PROJECT_GENERATED` | 从已确认需求重新撰写模块边界 | b63c81c6b869f81485b408a4d6f57e7666dff109 | Private 项目行为规格；未复制旧文档 | MIT | 已创建 |
| `docs/VERIFICATION.md` | `CONFIRMED_PROJECT_GENERATED` | 从验证需求重新撰写 PASS / STOP 规则 | b63c81c6b869f81485b408a4d6f57e7666dff109 | Private 项目验证要求；未复制旧文档 | MIT | 已创建 |
| `docs/QUICKSTART.md` | `CONFIRMED_PROJECT_GENERATED` | 根据当前公开 Core API 新建最小离线用例与验证流程说明 | af1a4afc742ca130856e5d66d40b6f11d2921dbd | 当前仓库公开 API；未复制第三方教程 | MIT | 已添加 |
| `docs/RELEASE_NOTES_v0.1.0-alpha.md` | `CONFIRMED_PROJECT_GENERATED` | 根据当前公开版本能力、验证边界和 Roadmap 新建扩展版发布说明 | 6a6dbe8ea7d10d139ecd2467272195bcfb447753 | 当前仓库 README / Roadmap；未复制第三方发布说明 | MIT | 已添加 |
| `docs/ACKNOWLEDGEMENTS.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写的上游致谢与集成关系说明；未复制第三方实现代码 | e88a1d778ddc16a922ddb32d7fdfe0d163b34529 | [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)，commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0` | MIT 上游仅作外部参考；本文件为本项目新写文档 | 已添加 |
| `pyproject.toml` | `CONFIRMED_PROJECT_GENERATED` | 本分支新增 FLSkill 包元数据、可选依赖、入口和 bundled file packaging | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 依赖范围核对上游固定 commit 的 `pyproject.toml` | 根项目 MIT；额外包含上游文件时遵循其独立 MIT | 已添加 |
| `src/flskill/cli.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写 doctor 和显式 User Script 安装入口 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游安装路径和运行依赖说明 | MIT | 已添加 |
| `src/flskill/__main__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建 `python -m flskill` 入口 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 无 | MIT | 已添加 |
| `src/flskill/setup.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写的备份式 User Script 安装流程 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游 User Script 文件路径 | MIT；仅复制已声明的第三方脚本 | 已添加 |
| `src/flskill/adapters/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建适配器包入口 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 无 | MIT | 已添加 |
| `src/flskill/adapters/fl_studio_mcp/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建 MCP adapter 包入口 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 无 | MIT | 已添加 |
| `src/flskill/adapters/fl_studio_mcp/adapter.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写的上游 MCP client 调用、目标门控、读回和机器可读验证报告 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游固定 commit 工具行为；无复制实现代码 | MIT | 已添加；Live 未验证 |
| `src/flskill/adapters/fl_studio_mcp/identity.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写工程 / Pattern / Channel / FL 版本身份模型 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | FLSkill 目标确认要求 | MIT | 已添加 |
| `src/flskill/adapters/fl_studio_mcp/mapping.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写 NotePlan / Piano Roll event 字段映射与精度检查 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游固定 commit 的 Piano Roll 字段 | MIT | 已添加 |
| `docs/FL_STUDIO_MCP.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写安装、状态与适配边界文档 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游固定 commit README、代码和 pyproject | MIT | 已添加 |
| `THIRD_PARTY_NOTICES.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写的 vendored component notices | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游仓库、commit、LICENSE | MIT；保留各自许可边界 | 已添加 |
| `tests/test_fl_studio_mcp_adapter.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造目标、音符和临时目录新写 mapping / safety / installer 测试 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 无第三方 fixture | MIT | 已添加 |
| `tests/test_bundled_mcp.py` | `CONFIRMED_PROJECT_GENERATED` | 使用 bundled server 和本机 MCP client 做无 FL Studio 的工具发现集成测试 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游固定 commit 仅为被测 backend | MIT | 已添加 |
| `tests/live_fl/README.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写的现场测试安全边界和目标身份要求 | 2852e091c0de4b7b0453bf087a1d1e7d6580d2a6 | 上游 Piano Roll 返回字段规格 | MIT | 已添加；现场 runner 尚未就绪 |
| `adapters/README.md` | `CONFIRMED_PROJECT_GENERATED` | 记录 Core 与可选执行适配器的边界及验证状态 | b63c81c6b869f81485b408a4d6f57e7666dff109；更新于 `2852e091c0de4b7b0453bf087a1d1e7d6580d2a6` | 上游固定 commit 的 backend 能力边界 | MIT | 已维护 |
| `examples/note_plan.example.json` | `CONFIRMED_PROJECT_GENERATED` | 使用完全自造音符与重复事件新建展示用 Note Plan | 3c0c6d9c76edc0fbc9462abd6f247c9a96f111b0 | 当前 Note Plan schema；无音乐作品或第三方 fixture | MIT | 已添加 |
| `examples/verification_result.example.json` | `CONFIRMED_PROJECT_GENERATED` | 使用完全自造 duration mismatch 新建 STOP 诊断示例 | 2666e9b8f338c8d3c9f8816311b6cea190db068c | 当前 VerificationResult 字段；无第三方 fixture | MIT | 已添加 |
| `schemas/note_plan.schema.json` | `CONFIRMED_PROJECT_GENERATED` | 根据本仓库 Note Plan 模型从空白重写 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 仅字段/行为需求；未复制旧 Schema | MIT | 已创建 |
| `src/flskill/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建 Python 包入口 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `src/flskill/time/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建时间模块入口 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `src/flskill/time/grid.py` | `CONFIRMED_PROJECT_GENERATED` | 按 Musical Grid 与绝对 tick 需求从空白实现 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 仅音乐时间行为规格；未复制旧实现 | MIT | 已创建 |
| `src/flskill/note_plan/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建计划模块入口 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `src/flskill/note_plan/model.py` | `CONFIRMED_PROJECT_GENERATED` | 按本仓库 Note Plan 字段和范围约束从空白实现 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 仅行为规格；未复制旧实现 | MIT | 已创建 |
| `src/flskill/io/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建输入输出模块入口 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `src/flskill/io/protocol.py` | `CONFIRMED_PROJECT_GENERATED` | 按写入/读回需求定义 Protocol | b63c81c6b869f81485b408a4d6f57e7666dff109 | 仅接口需求；未复制第三方适配器 | MIT | 已创建 |
| `src/flskill/io/memory.py` | `CONFIRMED_PROJECT_GENERATED` | 为离线算法测试新建内存读写实现 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 自造内存行为；未复制旧夹具 | MIT | 已创建 |
| `src/flskill/verification/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建验证模块入口 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
| `src/flskill/verification/exact_set.py` | `CONFIRMED_PROJECT_GENERATED` | 按事件精确比较需求从空白实现 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 仅验证规则；未复制旧实现 | MIT | 已创建 |
| `tests/test_time.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造 Musical Grid 数值新建测试 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无第三方 fixture | MIT | 3 项通过 |
| `tests/test_note_plan.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造 Note Plan 输入新建测试 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无第三方 fixture | MIT | 4 项通过 |
| `tests/test_verification.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造事件组新建 exact-set 测试 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无第三方 fixture | MIT | 3 项通过 |
| `tests/test_execution.py` | `CONFIRMED_PROJECT_GENERATED` | 使用本仓库内存适配与自造事件新建闭环测试 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无第三方 fixture | MIT | 4 项通过 |

首版发布树的 24 个跟踪文件均首次加入根提交 `b63c81c6b869f81485b408a4d6f57e7666dff109`。后续公开展示文件按各自首次创建提交单独登记。

## 分类与许可

- `CONFIRMED_PROJECT_GENERATED` 表示文件在本仓库中从空白创建，且其创建来源在此登记；它不是第三方权利调查的替代品。
- 当前无 `ADAPTED_FROM_THIRD_PARTY` 文件。`third_party/fl-studio-mcp/**` 的每个文件分类均为 `THIRD_PARTY`；Python 依赖按包管理器安装，不 vendor 其依赖源码。
- 规格参考不等于源码复制。本仓库没有迁移旧 `device_FLSkillMCPPrimary.py`、旧 `sysex_rpc.py`、旧测试/fixtures、旧 README/docs、第三方 FL Studio MCP 源码或其协议实现。
- 本记录及 Git 历史不自动决定法律许可。项目已按权利人指示选用 MIT。

## 固定上游源码快照

| 路径范围 | 分类 | 来源仓库与 commit | 许可 / 版权 | 文件来源核对 |
|---|---|---|---|---|
| `third_party/fl-studio-mcp/**`（17 个文件） | `THIRD_PARTY` | `karl-andres/fl-studio-mcp`，`f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0` | MIT；保留 calvinw 与 Karl Andres 原始版权 | 每个 vendored 文件 Git blob 均与该 commit 对应路径一致 |

Bundled 文件：`LICENSE`、`README.md`、`pyproject.toml`、`fl_controller/device_FLStudioMCP.py`、`scripts/ComposeWithLLM.pyscript`，以及 `src/fl_studio_mcp/` 下的全部 12 个 Python 文件。上游 demo video、安装脚本和 Claude 专属配置脚本未纳入。

本轮更新的 `README.md`、`docs/ARCHITECTURE.md`、`docs/ROADMAP.md`、`docs/VERIFICATION.md`、`docs/ACKNOWLEDGEMENTS.md`、`docs/QUICKSTART.md`、`adapters/README.md` 与本文件均为本仓库新写或维护的项目文档（`CONFIRMED_PROJECT_GENERATED`）；主要更新记录于提交 `2852e091c0de4b7b0453bf087a1d1e7d6580d2a6`，README 状态措辞校正记录于 `9ec9451`。外部参考为 `karl-andres/fl-studio-mcp` 的 commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`（MIT）；仅自行总结上游能力，没有复制其代码或长段原文。

本轮新增与更新的展示及贡献文件也由本项目撰写，未包含第三方实现源码：

| 路径 | 分类 | 创建来源 | 创建提交 | 外部参考 | 许可考虑 | 状态 |
|---|---|---|---|---|---|---|
| `README.md` | `CONFIRMED_PROJECT_GENERATED` | 按当前代码、维护者报告及仓库可复核证据重写项目首页；区分 offline Verified、experimental 与 roadmap | 本轮首个文档提交，见 Git 历史 | 固定版本 `karl-andres/fl-studio-mcp`；仅说明后端边界 | MIT；无第三方实现代码 | 已更新 |
| `docs/ARCHITECTURE.md` | `CONFIRMED_PROJECT_GENERATED` | 重新说明 Core、execution adapter、bundled backend、readback、verification 和 agent loop | 本轮首个文档提交，见 Git 历史 | 本仓库当前实现与验证要求 | MIT | 已更新 |
| `docs/ROADMAP.md` | `CONFIRMED_PROJECT_GENERATED` | 依 Completed / In Development / Planned 整理当前分支路线 | 本轮首个文档提交，见 Git 历史 | 本仓库当前实现与维护者报告 | MIT | 已更新 |
| `docs/FL_STUDIO_MCP.md` | `CONFIRMED_PROJECT_GENERATED` | 补充维护者报告、稳定性反馈邀请及证据边界 | 本轮首个文档提交，见 Git 历史 | 本仓库 adapter 与 live test 文档 | MIT | 已更新 |
| `docs/ACKNOWLEDGEMENTS.md` | `CONFIRMED_PROJECT_GENERATED` | 补充当前分支 bundled snapshot 与 optional backend 说明 | 本轮首个文档提交，见 Git 历史 | 固定版本 `karl-andres/fl-studio-mcp` | MIT；没有复制上游实现 | 已更新 |
| `docs/VERIFICATION.md` | `CONFIRMED_PROJECT_GENERATED` | 明确维护者报告未附仓库可复核的现场读回证据 | 本轮首个文档提交，见 Git 历史 | 本仓库 live test 前置条件 | MIT | 已更新 |
| `CONTRIBUTING.md` | `CONFIRMED_PROJECT_GENERATED` | 新写开发安装、测试、验证状态与第三方代码贡献规则 | 本轮首个文档提交，见 Git 历史 | 本仓库开发流程 | MIT | 已添加 |
| `SECURITY.md` | `CONFIRMED_PROJECT_GENERATED` | 新写凭据、私人工程、样本、插件二进制及现场测试安全说明 | 本轮首个文档提交，见 Git 历史 | 本仓库使用边界 | MIT | 已添加 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | `CONFIRMED_PROJECT_GENERATED` | 新写结构化缺陷报告表单 | 本轮首个文档提交，见 Git 历史 | 无 | MIT | 已添加 |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | `CONFIRMED_PROJECT_GENERATED` | 新写结构化功能建议表单 | 本轮首个文档提交，见 Git 历史 | 无 | MIT | 已添加 |
| `.github/ISSUE_TEMPLATE/live_verification_report.yml` | `CONFIRMED_PROJECT_GENERATED` | 新写要求脱敏且不上传私人工程的现场验证反馈表单 | 本轮首个文档提交，见 Git 历史 | 本仓库验证证据字段 | MIT | 已添加 |
| `.github/pull_request_template.md` | `CONFIRMED_PROJECT_GENERATED` | 新写变更范围、测试、证据、第三方影响和验证级别清单 | 本轮首个文档提交，见 Git 历史 | 本仓库贡献要求 | MIT | 已添加 |

以上文档与表单未引入第三方源码。维护者关于真实 FL Studio 接入的陈述按维护者报告记录；因本仓库未保存该次目标身份和实际事件读回证据，不据此将对应能力标记为可复核的 `Verified`。
