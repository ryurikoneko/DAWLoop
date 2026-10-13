# 能力与公开范围 / Capabilities and publication scope

[COMPUTED｜HIGH] 核验日期：2026-10-13。公开 `main`：`1a99482aa9b47a61fdf37275583a7b432775ab8d`；独立 Desktop：`66806b510556ec2c11c2eedfe8b1f8a6bf302c6a`。本页是文档候选，不改变远端代码或发行物。

[COMPUTED | HIGH] Audited 2026-10-13 against the public main and separate Desktop commits above. This documentation candidate does not publish the Desktop feature tree or installers.

## 状态词 / State vocabulary

| 状态 | English | 含义 / Meaning |
| --- | --- | --- |
| 已实现并离线测试 | OFFLINE_TESTED | 没有真实宿主认证 / No live host certification |
| 特定场景真实验收 | SCENARIO_LIVE_TESTED | 只在明确素材、目标和环境范围 / Limited to stated data, target and environment |
| 内部候选 | INTERNAL_PREVIEW | 本地候选，不表示公开 Release / Local candidate, not a public Release |
| 实验性 | EXPERIMENTAL | 限制和误差必须保留 / Retain limitations and uncertainty |
| 尚未验证 | NOT_PROVEN | 代码存在或缓存存在不能升级 / Code or cache existence is insufficient |
| 计划中 | PLANNED | 不当作现有功能 / Not an available capability |
| 阻塞 | BLOCKED | 明确的未解决前置条件 / Unresolved prerequisite |

## 两条独立产品线 / Two independent delivery lines

| 能力 / Capability | 所在范围 / Location | 状态 / State | 证据与限制 / Evidence and limits |
| --- | --- | --- | --- |
| MusicalGrid / NotePlan / Exact-Set algorithm | Public main | OFFLINE_TESTED | 内存读回算法；不等于 FL 实际读回 / In-memory comparison is not FL readback |
| MusicalPlan / Learning schemas / reference generator | Public main | OFFLINE_TESTED | 合成教程、受限计划；没有艺术家风格泛化证据 / Synthetic tutorial and constrained plans; no artist-style generalization evidence |
| Controller target navigation | Public main | SCENARIO_LIVE_TESTED | 历史 Kick ↔ Clap 观察性确认 / Historical observational confirmation; [record](../evidence/public/README.md) |
| Native FAST + human Accept | Public main | SCENARIO_LIVE_TESTED | 固定16-note，一次派发；COMPLETED_UNVERIFIED / Fixed 16 notes, one dispatch; [record](../evidence/public/fast_session_7.json) |
| MCP / RunManager offline wiring | Public main | OFFLINE_TESTED | 新 MCP 现场路径 BLOCKED 于 observer 身份 / New MCP live path blocked on observer identity |
| Native producer Exact Set | Public research | BLOCKED | 没有认证的完整 producer notes[] / No certified complete producer note readback |
| Production MIDI / RMS / planning utilities | Public main | OFFLINE_TESTED | 算法与计划不授予宿主写权限 / Analysis and plans do not grant host writes |
| Single-window Desktop / audio streaming | Independent feature tree | INTERNAL_PREVIEW + SCENARIO_LIVE_TESTED | 实际内部程序操作；不在公开 main / Actual internal application tests; not in public main |
| Full-song DSP / LUFS / key candidates | Independent feature tree | INTERNAL_PREVIEW + SCENARIO_LIVE_TESTED | 自有素材、数值对照；调性估计非确定结论 / Owned fixtures and numerical references; key is an estimate |
| Basic Pitch audio-to-MIDI | Independent feature tree | INTERNAL_PREVIEW + SCENARIO_LIVE_TESTED | 单乐器自有素材；混音误差不能外推 / Owned instrument fixtures; not universal mixed-audio accuracy |
| Rule-based melody composer | Independent feature tree | INTERNAL_PREVIEW + SCENARIO_LIVE_TESTED | RULE_BASED；不声称大模型语义 / RULE_BASED, no large-model semantics claim |
| Piano Roll / MIDI roundtrip / persistence | Independent feature tree | INTERNAL_PREVIEW + SCENARIO_LIVE_TESTED | 实际编辑、导出、独立事件读回与重启 / Actual editing, export, independent event readback and restart |
| OMAR-RQ 25Hz Embedding | Independent feature tree | INTERNAL_PREVIEW + SCENARIO_LIVE_TESTED | 既有单段推理记录；30秒窗口，不等于风格学习 / Recorded single-window inference; 30-second scope, not style learning |
| SheetSage2 transcription | Independent feature tree | EXPERIMENTAL | 已有特定素材推理，offset限制保留；品牌阶段未重跑 / Prior fixture inference; offset limitations retained, not rerun in branding phase |
| YuE2 symbolic / full audio | Future isolated Provider | BLOCKED / NOT_PROVEN | 两种能力分别评估；不把预置ABC当推理 / Evaluate separately; fixture ABC is not inference |
| Desktop trusted Snapshot / binding / invalidation | Independent feature tree | OFFLINE_TESTED | 离线规则不等于当前 FL 通信 / Offline rules are not current FL communication |
| Desktop Host Session / real Mixer / plugin reads | Independent feature tree | NOT_PROVEN | 不从进程检测、UI或旧缓存推导 / Not inferred from process presence, UI or old cache |
| Clean Windows first install | Desktop distribution | BLOCKED / NOT_PROVEN | 完整可信离线运行组件与独立系统验收未完成 / Trusted offline runtime distribution and independent clean-system acceptance incomplete |
| OMAR similarity search / artist-style learning | Future research | PLANNED | Embedding不证明搜索、学习或风格标签 / Embeddings do not prove search, learning or style labels |
| Generic MusicalPlan → FAST Adapter | Public roadmap | PLANNED | 单位、目标和字段转换须独立验证 / Unit, target and field conversion needs independent verification |
| Auto Accept / arbitrary writes / full AutoMix | Future research | NOT_PROVEN | 不提供通用认证或默认写权限 / No general certification or default write permission |

[KNOWN｜HIGH] 公开 Release `v0.2.0-alpha.1` 包含 Python wheel、sdist 和来源/摘要文件；不是 Desktop。源码中的 `1.0.0a1` 是候选版本准备，不代表同名版本已公开发行。历史 `v0.1.0-alpha` 保留。[实际 Releases](https://github.com/ryurikoneko/DAWLoop/releases)

[KNOWN | HIGH] Public `v0.2.0-alpha.1` assets are Python packages and provenance/checksum files, not Desktop. Source version `1.0.0a1` is a candidate preparation, not proof of publication. Historical Releases remain intact.

[KNOWN｜HIGH] Desktop 汇总来自内部运行记录，公开的是脱敏截图、源码提交号和限定测试说明；完整本机运行日志、安装包及私人环境不随文档分发。内部测试不等于第三方独立复现。

[KNOWN | HIGH] Desktop summaries come from internal execution records. This candidate includes sanitized screenshots, commit identities and scoped descriptions, not raw local logs, installers or private environments. Internal acceptance is not independent third-party reproduction.

[Desktop guide](DESKTOP.md) · [Verification](VERIFICATION.md) · [Roadmap](ROADMAP.md) · [Home 中文](../README.md) · [Home English](../README.en.md)
