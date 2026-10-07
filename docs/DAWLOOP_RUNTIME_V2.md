# Runtime V2：公开进度与认证边界

<a id="current"></a>

## 当前状态：2026-10-07 research-preview

[KNOWN｜HIGH] Phase 1 的受限 FAST 主线已完成。Phase 2 的音乐计划/学习合同已有离线实现；MCP 现场候选路线暂停于外部浏览器 page identity 传输。当前状态以实际结果为依据，历史失败不回填成功。完整本地会话不公开，本文件与 [evidence/public](../evidence/public/README.md) 提供脱敏摘要。

```text
FAST_MUSIC_ENTRYPOINT = LIVE_PROVEN_IN_TEST_SCOPE
FULL_TARGET_NAVIGATION = LIVE_PROVEN_OBSERVATIONAL_IN_TEST_SCOPE
HUMAN_REPORT_REALTIME_DELIVERY = LIVE_PROVEN_IN_TEST_SCOPE
APPLICATION_OBSERVATION_DELIVERY = LIVE_PROVEN_IN_TEST_SCOPE
HOST_COMPLETION_CALLBACK = LIVE_OBSERVED_SUCCESS_IN_THIS_RUN

MCP_FAST_PATH = NOT_LIVE_CERTIFIED
ZERO_AGENT_COMPUTER_USE_FAST_PATH = NOT_LIVE_CERTIFIED
PHASE_2A_MCP_LIVE = PAUSED_ON_EXTERNAL_BROWSER_IDENTITY_DEPENDENCY

PRODUCER_TARGET_BINDING = NOT_VERIFIED
EXACT_SET_VERIFICATION = NO
VERIFIED_WRITE_READY = NO
NATIVE_VERIFIED_RESEARCH = FROZEN_BLOCKED
AUTO_ACCEPT = OFF_DEFERRED
CONNECTION_REUSE = NOT_TESTED
NORMAL_PROJECT_CONTINUOUS_WRITE = NOT_CERTIFIED
```

## 维护者签名准备

[KNOWN｜HIGH] 维护者已在本机生成专用带口令 Ed25519 密钥；只登记公钥，指纹 `SHA256:pjgoJ3EUboMqiQ+n45ORU3rh+VqB18616hnIThH//O0`。仓库信任表与本机持钥签名、GitHub Signing Key 登记、正式发布认证分别判断，不以公钥入库冒充已发布。

[KNOWN｜HIGH] PR #13 通过后，main 的 [Windows 离线回归](https://github.com/ryurikoneko/DAWLoop/actions/runs/37573805736) 在本地线程交接测试的身份 freshness 检查失败；两个 Linux job 通过。此次只将该合成测试的身份/采样/年龄检查统一到可控墙钟，线程与交付计时保留真实单调时钟。Runtime freshness、期限和导航守卫未修改；原失败 run 保留。

## 发布准备：1.0.0-alpha.1

[KNOWN｜HIGH] 下一版目标调整为 `v1.0.0-alpha.1` / 包版本 `1.0.0a1`，副标题 Runtime V2 Architecture Preview。版本元数据与发布触发器同步调整；历史 `v0.2.0-alpha.1` 不变，当前尚无新版正式发布或维护者签名认证。版本定位不增加任何现场能力范围。

[KNOWN｜HIGH] 中英架构图区分已有 FAST 结构化输入和计划中的通用 MusicalPlan → Plan Adapter 转换；后者仍待实现与独立验收。发布指南将首次 CI 链接标为 initial validation run，保留原始验收证据。MCP 与 VERIFIED 冻结继续保持。

## 已完成的主线

### 公开工程化：2026-10-07

[KNOWN｜HIGH] Ubuntu Python 3.11/3.12 与 Windows Python 3.12 的完整离线 CI 已在 [main Actions](https://github.com/ryurikoneko/DAWLoop/actions/runs/37514929489) 通过，包括 Node 合成观察测试、构建、隔离 wheel 安装、学习教程与 provenance 校验。Windows 为 715 tests + 331 subtests；Linux 为 710 tests + 331 subtests，另有 3 个 Win32 项目跳过及 2 个 Win32 启动器用例不收集。跨平台测试只修正模拟环境与时间边界，不放宽 Runtime deadline、target guard 或 dispatch budget，不启动 FL。

[KNOWN｜HIGH] 中英首页先介绍能力，再集中列出 alpha 范围；公开部署和未来 Release 文案使用项目语言，内部研究记录保留证据标签。包元数据补齐 Alpha classifiers 与项目链接；仓库开启合并后删除分支、关闭 Wiki。

[KNOWN｜HIGH] 新发布流程区分 main 候选构建和可信 SSH signed tag 构建。[候选验收](https://github.com/ryurikoneko/DAWLoop/actions/runs/37514976009) 已通过，构建 commit 为 `3e0688e2603e166cdeb4dfe123bcf0a08505fd63`；五份产物的 GitHub artifact attestation 按仓库/workflow/ref/commit 验证，下载包摘要与四项校验和均匹配。此为 main 候选，不是新版 Release，也不是维护者个人签名。当前可信签名公钥未登记，正式签名 tag 发布仍拒绝。历史 `v0.2.0-alpha.1` 的 tag、Release 和五份资产摘要保持原样。维护顺序见 [发布指南](RELEASING.md)。

[KNOWN｜HIGH] [main-quality-gate](https://github.com/ryurikoneko/DAWLoop/rules/24603386) 已启用：PR、严格 `CI gate`、禁止 force-push/删除；管理员例外仅限 PR，不要求单人项目自审批准。发布沿用先合并 main、CI、可信 signed tag、重新构建与验证的顺序。

[KNOWN｜HIGH] 此更新不增加任何 FL 现场认证；MCP 外部页面身份阻塞和 Native VERIFIED 冻结继续保持。

[KNOWN｜HIGH] Controller 身份区分 build（代码）、session（加载会话）、project generation（工程上下文）。身份由运行 Controller 回报，不以磁盘脚本摘要冒充。空标题只作为 EMPTY_ACCEPTED 描述，不参与 generation equality。

[KNOWN｜HIGH] 导航使用三个固定 primitive：选已有 Pattern → `selectOneChannel(global_index, True)` 独占选通道 → `openEventEditor(getRecEventId(global_index, True) + REC_Chan_PianoRoll, EE_PR)` 定向打开卷帘。曾经点击 Channel Button 打开 Sampler、`showWindow` 只显示旧 Kick 卷帘的失败已定位并更换动作语义；不是通过反复点击凑成功。

[KNOWN｜HIGH] 完整 A→B→A 在既有 Pattern 1/Kick 与 Pattern 2/Clap 间通过：每方向一事务、三固定 primitive，identity/UI/identity 新鲜夹读，无重试、fallback 或音符派发。仅认证可见目标准备，不认证 producer 内部绑定。

[KNOWN｜HIGH] FAST 高层入口已完成结构化计划校验、导航准备、观察确认、确定性 source/AST/hash 校验、一次派发预算、人工接受和证据化终态。session 7 为完整通过记录：固定 16-note Kick 句、dispatch=1、retry=0、fallback=0、人工回执 REALTIME、应用观察 REALTIME、host completion CONFIRMED、试听 USER_OK、原终态 COMPLETED_UNVERIFIED、不保存退出和基线核验通过。

[KNOWN｜HIGH] 同一派发产生的两份 journal 凭据不是两次派发；计数按唯一 operation/实际调用。人工报告先持久化，协调器领取后才算 REALTIME；晚到试听证据独立保存，不能改写不可变运行终态。应用观察也区分 capture/review/submit/persist/claim/confirm。

## 现场范围与性能含义

| 项目 | 认证范围 |
| --- | --- |
| 宿主 | 维护者 Windows / FL Studio 26.1.6 build 5639 环境 |
| 高层写入 | disposable fixture，Pattern 1 / 808 Kick，PPQ 96 |
| 计划 | 既有固定 16 音符、第 5–8 小节、add-only、单次派发 |
| 接受 | 用户审阅后人工一次 Accept |
| 确认 | 观察性目标 + 可见应用 + completion callback + 用户试听 |
| 恢复 | 不保存退出，size/SHA-256 不变，临时端口关闭 |

[KNOWN｜HIGH] 这些限定不等于任意目标、任意音乐计划或生产工程认证。早期吞吐与固定四音符 pixel 实验保留代码，但不能把四音符 detector 当作 16-note 或任意音符 Exact Set。原生/Community 公平 A/B 尚未建立，不宣传 Nx faster。

[KNOWN｜HIGH] session 7 同域测得 capture约176 ms、capture→review acknowledgement约8.65 s、submit→persist约1.25 ms、claim→confirm约16 ms。跨进程 persist→claim 只有 wall-clock correlation，精确消费延迟未知；这些单样本不代表 API 通用性能，也不把人工等待算 Native backend 延迟。

## 冻结与阻塞

[KNOWN｜HIGH] 正常脚本返回没有数据传播证据，异常传播仍 unresolved；外层“Script executed without errors”不证明 `apply()` 实际返回/异常进入调用者。读取探针两次出现 dirty flag 0→1，可见音符不变不能升级为无副作用。

```text
VERIFIED_WRITE
  └─ BLOCKED: 可认证 producer-side structured note readback 缺失
       ├─ normal return: NOT_PROVEN
       ├─ error channel: UNRESOLVED
       ├─ file snapshots / output-only: CLOSED
       ├─ Community cache: freshness/target binding 不足
       └─ visual observation: 不能作为 Exact Set 数据源
```

[KNOWN｜HIGH] 不再设计 return/exception/stdout 变体、notes[] over error、新临时 IPC 或重开文件路线。只有新的可信完整 note-read 接口才解冻；离线 multiset 比较器仍可用。add-only 的未来比较应为 baseline + additions，保留重复次数并锁 PPQ。

[KNOWN｜HIGH] Auto Accept 默认关闭、现场未认证，保留实现与失败证据，不继续像素修补。Undo 延期；当前 disposable 实验以 no-save process rollback 收尾。连续写入/修改既有音符/无人值守需求须另开安全合同。

## Phase 2 实际实现

[KNOWN｜HIGH] MusicalPlan 与参考生成器是风格无关、受限单声部离线实现。Section Brief / Harmony / Voice / Variation / StyleConstraints 分离，输出包含音符与动机/乐句解释结构。五份数值 profile 只是 schema/validator 示例，不是官方推荐流派或用户艺术家知识。

[KNOWN｜HIGH] Learning Framework 实现四份严格 Schema、四份 Agent prompts、聚合与 profile revision。素材权限声明不证明真实授权，hash 不证明分析正确；observed/inferred/unknown 分开，缺失不填零。同类统计 DESCRIPTIVE_ONLY，映射 manual-review-v1，留出 NOT_EVALUATED。用户自己学习自有材料，私人数据忽略，公共例子全部合成。

[KNOWN｜HIGH] MCP 的三个工具、后台 RunManager、truthful readiness、real FAST factory 与独立 observer 接线离线完成。现场还未进入有效 run；当前 browser page identity transport unavailable，UI binding blocked、request completion not proven。未降低 URL/page safety gate，也不反复重试外部 fetch。

## 下一步及公开约定

[INFERRED｜HIGH] 发布之后优先让用户 Agent 跑离线学习例子、核对分析/映射/反馈。MCP 路线复验、候选分支展示与当前可用路径的选择条件见 [ROADMAP](ROADMAP.md)。不自动推进连接复用、普通工程连续写入、语音或 VERIFIED。

[KNOWN｜HIGH] 自有代码与本次公开摘要保持 MIT；CC BY-NC 资产清单为空。原始实验材料与私人 Memos 不发布。此版本没有已验证签名/DOI，不将 hash 作为作者认证。Memos 当前不可调用，公开发布状态与本地检查点可保存，外置同步未完成。
