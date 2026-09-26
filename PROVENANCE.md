# 来源记录

本仓库从空白 Git 仓库开始。首版源代码、Schema、测试及项目文档均按本仓库的功能要求重新编写，没有复制 Private FLSkill、第三方仓库、音乐作品或测试夹具中的文件/实现。`LICENSE` 使用 SPDX 发布的标准 MIT 许可文本，单独记录其规范来源。

旧 Private 原库仅作为行为规格、架构要求和已记录验证边界的参考；没有从中复制代码、JSON Schema、文档、测试或配置。实现细节、测试数据和本仓库文案均为本仓库新建。

## 文件清单

| 路径 | 分类 | 创建来源 | 创建提交 | 外部参考 | 许可考虑 | 状态 |
|---|---|---|---|---|---|---|
| `LICENSE` | `CONFIRMED_PROJECT_GENERATED` | 项目权利人选择 MIT，并按标准文本填写版权年份与权利人 | 待本次根提交后回填 | [SPDX MIT](https://spdx.org/licenses/MIT) | MIT；此文件是许可文本，不是第三方实现代码 | 已添加 |
| `.gitattributes` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建文本换行规范 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `.gitignore` | `CONFIRMED_PROJECT_GENERATED` | 本仓库初始化时新建，仅忽略 Python 生成物和本地构建输出 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `README.md` | `CONFIRMED_PROJECT_GENERATED` | 按本仓库实现和验证边界重新撰写 | 待本次根提交后回填 | Private 项目行为规格；未复制旧文档 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `docs/ROADMAP.md` | `CONFIRMED_PROJECT_GENERATED` | 按用户确认的阶段顺序新建路线图 | 待本次根提交后回填 | 本项目计划；未复制旧路线图 | MIT；无第三方实现代码 | 已添加 |
| `PROVENANCE.md` | `CONFIRMED_PROJECT_GENERATED` | 本仓库建立的逐文件来源台账 | 待本次根提交后回填 | 无 | MIT；本台账记录来源，不代替权利证明 | 已创建 |
| `docs/ARCHITECTURE.md` | `CONFIRMED_PROJECT_GENERATED` | 从已确认需求重新撰写模块边界 | 待本次根提交后回填 | Private 项目行为规格；未复制旧文档 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `docs/VERIFICATION.md` | `CONFIRMED_PROJECT_GENERATED` | 从验证需求重新撰写 PASS / STOP 规则 | 待本次根提交后回填 | Private 项目验证要求；未复制旧文档 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `adapters/README.md` | `CONFIRMED_PROJECT_GENERATED` | 记录本阶段不含真实适配器的范围边界 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `schemas/note_plan.schema.json` | `CONFIRMED_PROJECT_GENERATED` | 根据本仓库 Note Plan 模型从空白重写 | 待本次根提交后回填 | 仅字段/行为需求；未复制旧 Schema | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建 Python 包入口 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/time/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建时间模块入口 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/time/grid.py` | `CONFIRMED_PROJECT_GENERATED` | 按 Musical Grid 与绝对 tick 需求从空白实现 | 待本次根提交后回填 | 仅音乐时间行为规格；未复制旧实现 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/note_plan/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建计划模块入口 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/note_plan/model.py` | `CONFIRMED_PROJECT_GENERATED` | 按本仓库 Note Plan 字段和范围约束从空白实现 | 待本次根提交后回填 | 仅行为规格；未复制旧实现 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/io/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建输入输出模块入口 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/io/protocol.py` | `CONFIRMED_PROJECT_GENERATED` | 按写入/读回需求定义 Protocol | 待本次根提交后回填 | 仅接口需求；未复制第三方适配器 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/io/memory.py` | `CONFIRMED_PROJECT_GENERATED` | 为离线算法测试新建内存读写实现 | 待本次根提交后回填 | 自造内存行为；未复制旧夹具 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/verification/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | 本仓库新建验证模块入口 | 待本次根提交后回填 | 无 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `src/flskill/verification/exact_set.py` | `CONFIRMED_PROJECT_GENERATED` | 按事件精确比较需求从空白实现 | 待本次根提交后回填 | 仅验证规则；未复制旧实现 | 项目采用 MIT（本地预发布候选） | 已创建 |
| `tests/test_time.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造 Musical Grid 数值新建测试 | 待本次根提交后回填 | 无第三方 fixture | 项目采用 MIT（本地预发布候选） | 3 项通过 |
| `tests/test_note_plan.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造 Note Plan 输入新建测试 | 待本次根提交后回填 | 无第三方 fixture | 项目采用 MIT（本地预发布候选） | 4 项通过 |
| `tests/test_verification.py` | `CONFIRMED_PROJECT_GENERATED` | 使用自造事件组新建 exact-set 测试 | 待本次根提交后回填 | 无第三方 fixture | 项目采用 MIT（本地预发布候选） | 3 项通过 |
| `tests/test_execution.py` | `CONFIRMED_PROJECT_GENERATED` | 使用本仓库内存适配与自造事件新建闭环测试 | 待本次根提交后回填 | 无第三方 fixture | 项目采用 MIT（本地预发布候选） | 4 项通过 |



## 分类与许可

- `CONFIRMED_PROJECT_GENERATED` 表示文件在本仓库中从空白创建，且其创建来源在此登记；它不是第三方权利调查的替代品。
- 当前无 `ADAPTED_FROM_THIRD_PARTY` 或 `THIRD_PARTY` 文件；本仓库也未引入第三方运行依赖。
- 规格参考不等于源码复制。本仓库没有迁移旧 `device_FLSkillMCPPrimary.py`、旧 `sysex_rpc.py`、旧测试/fixtures、旧 README/docs、第三方 FL Studio MCP 源码或其协议实现。
- 本记录及 Git 历史不自动决定法律许可。项目已按权利人指示选用 MIT；正式公开前仍须复核版权行、发布文件清单和权利人授权范围。
