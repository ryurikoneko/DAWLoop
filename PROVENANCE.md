# 来源记录

本仓库从空白 Git 仓库开始。首版源代码、Schema、测试及项目文档均按本仓库的功能要求重新编写，没有复制 Private FLSkill、第三方仓库、音乐作品或测试夹具中的文件/实现。`LICENSE` 使用 SPDX 发布的标准 MIT 许可文本，单独记录其规范来源。

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
| `docs/ACKNOWLEDGEMENTS.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新写的上游致谢与集成关系说明；未复制第三方实现代码 | 本次文档更新 | [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)，commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0` | MIT 上游仅作外部参考；本文件为本项目新写文档 | 已添加 |
| `adapters/README.md` | `CONFIRMED_PROJECT_GENERATED` | 记录本阶段不含真实适配器的范围边界 | b63c81c6b869f81485b408a4d6f57e7666dff109 | 无 | MIT | 已创建 |
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
- 当前无 `ADAPTED_FROM_THIRD_PARTY` 或 `THIRD_PARTY` 文件；本仓库也未引入第三方运行依赖。
- 规格参考不等于源码复制。本仓库没有迁移旧 `device_FLSkillMCPPrimary.py`、旧 `sysex_rpc.py`、旧测试/fixtures、旧 README/docs、第三方 FL Studio MCP 源码或其协议实现。
- 本记录及 Git 历史不自动决定法律许可。项目已按权利人指示选用 MIT。

本轮 README、`docs/ARCHITECTURE.md`、`docs/ROADMAP.md` 与本文件的更新，均为本仓库新写的项目文档说明（`CONFIRMED_PROJECT_GENERATED`）。外部参考为 `karl-andres/fl-studio-mcp` 的 commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`（MIT）；仅自行总结上游能力，没有复制其代码或长段原文。对应变更可由 Git 历史中的本次文档提交追溯。
