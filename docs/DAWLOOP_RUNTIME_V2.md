# Runtime V2：公开进度与认证边界

<a id="current"></a>

## Alpha.2 Preview 通知独立批准：2026-10-15

维护者明确确认Windows人工通知测试完成，并授权仅v0.5.6-alpha.2、preview、Release 412979500的Windows Toast与应用内更新提示。批准ID dawloop-alpha2-preview-20261015，有效期七日，UTC起止时间见release_notifications/approvals/alpha2-preview-20261015.json；Stable、未来版本、自动下载安装均未批准。系统人工测试来源登记为MAINTAINER_CONFIRMED，不冒充代理直接观察或填造逐项结果。

沿用schema v2及现有客户端权限、版本比较、去重、稍后提醒、五分钟批准时效与撤销机制，不新增常驻进程。公开Alpha.1/Alpha.2的内置简短文案不能由远端替换，指定文案独立登记。没有更新模块、未选择Preview、关闭更新检查或未主动开启系统通知的客户端不保证收到Toast；配置上线不等于全用户送达。旧Release、标签、九项发行附件不修改。最终PR及读回证据见本轮通知验收记录，详细撤销流程见release_notifications/README.md。

## 公开展示与Desktop分发独立门：2026-10-14

用户本轮已授权推送文档分支、PR、保护规则合并及通过独立门的预览发布；此前禁止Push不沿用为本轮阻塞。公开Runtime业务基线1a99482保持，品牌/README候选从最新origin/main独立集成。Hero左下灰色版权署名，选定Logo和实际产品截图保留，个人权属PENDING_OWNER_REVIEW、不声称登记。

Desktop功能源66806b5与独立打包提交8123ae3，统一分发名DAWLoop+0.5.6-internal.1。完整Windows目录内置Electron/Node和中英文指南；不携带模型权重，不借开发机Python冒充首装。未取得干净Windows VM/可信离线音频组件，公开Desktop发行BLOCKED；首页与Desktop发行各自验收，不用其中一项代替另一项。


## 项目头图版权署名：2026-10-14

用户要求GitHub品牌头图不得显示软件版本。Hero与Social候选改为纯黑底白字SVG排版，左下灰字Copyright (c) 2026 ryurikoneko，明确为品牌图而非软件截图；应用内动态版本、正式圆环Logo及功能截图不改。权属待审核与既有许可边界不变，本地候选提交，不Push或改远端设置。


## 品牌与角色资产补充候选：2026-10-14

用户确定拟定个人主体INDIVIDUAL、公开署名ryurikoneko，不填写法定姓名。新增[品牌清单](brand/README.md)、角色占位、历史许可审查与登记准备建议；作者/完整权属/既有授权未清统一PENDING_OWNER_REVIEW，未登记状态不附伪造编号或证书。

根MIT、第三方正文、旧候选与历史资产不改。记录同源Logo曾置于根MIT功能树这一许可不确定性，后续声明不撤回旧权利。未来公司不默认受让，角色私有分层与未发表设定不公开；本轮只独立docs候选本地提交，不申请、Push、Merge或发布。


## GitHub Showcase 2.0 文档候选：2026-10-13

本 docs 分支基于公开 main `1a99482`，与内部 Desktop `66806b5` 分开。双语首页使用实际候选截图和选定 Logo，保留历史 Runtime 工程说明与 FAST 脱敏证据；能力、发行、实验和计划按 [CAPABILITIES](CAPABILITIES.md)分别标记。不存在公开 Desktop 安装包的事实明确保留。

本轮仅文档、媒体和模板，不修改算法、Host、Controller或写权限，不运行FL，不发布安装包，不Push/Merge。品牌PNG按精确清单声明，既有MIT与第三方许可保留。详细本地验收记录独立存放；公开来源与隐私说明见 [媒体索引](media/README.md)，后续等待用户审阅。


## 更新提醒工程：2026-10-07

`doctor` 增加公开 GitHub Release 查询和 24 小时成功/失败缓存，支持禁用、手动刷新和 stable/prerelease 通道。发布状态、安装来源、Controller 磁盘 build 与新鲜运行时协议分别报告；网络不可用不改变本地诊断退出码。只输出明确更新建议，不自动升级、不安装脚本、不 Reload、不发送 MIDI/RPC；MCP 和 Native VERIFIED 冻结范围不变。使用说明见 [FL Studio setup](FL_STUDIO_SETUP.md#release-and-controller-update-awareness)。

本轮新增 26 tests / 8 subtests；完整离线回归 767 tests / 375 subtests 通过，0 fail / 0 skip。编译、5 个 Schema JSON、3 个 Issue YAML、`git diff --check`、sdist/wheel 和隔离 wheel 导入/doctor 检查通过。真实只读发布查询返回 `v0.2.0-alpha.1`，低于本地 `1.0.0a1`；未将 `v1.0.0-alpha.1` 草稿当作已发布版本。隔离环境缺少 FL 可选依赖时保持原有 STOP，不以更新检查替代环境诊断；未现场认证 Controller 或执行宿主操作。

## 公开主页更新：2026-10-07

中英文 README 恢复项目动机、Brain/Hands/Ears、Agent 工作循环、音乐合同、学习路径、真实 FL 控制、Production 分析、Agent 接口、三项完整致谢与 FLSkill → DAWProof → DAWLoop 历史。架构图改为纵向循环与辅助入口，Plan Adapter 保持 Planned 虚线；MCP Preview 与 Python FAST 现场路径分开说明，Alpha 范围集中呈现。

致谢文档同步区分离线 Exact-Set 算法和 Native FAST `COMPLETED_UNVERIFIED`，不扩大 producer readback 或 MCP 现场认证。本次只修改公开文档，不改 Runtime、协议、预算、期限或版本。

`v1.0.0-alpha.1` 已由维护者密钥签名并通过本机与 GitHub 验签；[tag 发布构建](https://github.com/ryurikoneko/DAWLoop/actions/runs/37576241940)成功，六份资产摘要及 252 个来源文件已核验。历史新版发布草稿尚未 Publish（该草稿地址不公开；实际发行物请查看 [Releases](https://github.com/ryurikoneko/DAWLoop/releases)），来源提交固定为 `732c3357e4475bd34e0a3a74904e2a5bd8f0a088`。本次主页更新独立于该历史快照，不移动标签、不替换资产；下方发布准备章节保留当时状态。

## 当前状态：2026-10-07 research-preview

Phase 1 的受限 FAST 主线已完成。Phase 2 的音乐计划/学习合同已有离线实现；MCP 现场候选路线暂停于外部浏览器 page identity 传输。当前状态以实际结果为依据，历史失败不回填成功。完整本地会话不公开，本文件与 [evidence/public](../evidence/public/README.md) 提供脱敏摘要。

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

维护者已在本机生成专用带口令 Ed25519 密钥；只登记公钥，指纹 `SHA256:pjgoJ3EUboMqiQ+n45ORU3rh+VqB18616hnIThH//O0`。仓库信任表与本机持钥签名、GitHub Signing Key 登记、正式发布认证分别判断，不以公钥入库冒充已发布。

PR #13 通过后，main 的 [Windows 离线回归](https://github.com/ryurikoneko/DAWLoop/actions/runs/37573805736) 在本地线程交接测试的身份 freshness 检查失败；两个 Linux job 通过。此次只将该合成测试的身份/采样/年龄检查统一到可控墙钟，线程与交付计时保留真实单调时钟。Runtime freshness、期限和导航守卫未修改；原失败 run 保留。

## 发布准备：1.0.0-alpha.1

下一版目标调整为 `v1.0.0-alpha.1` / 包版本 `1.0.0a1`，副标题 Runtime V2 Architecture Preview。版本元数据与发布触发器同步调整；历史 `v0.2.0-alpha.1` 不变，当前尚无新版正式发布或维护者签名认证。版本定位不增加任何现场能力范围。

中英架构图区分已有 FAST 结构化输入和计划中的通用 MusicalPlan → Plan Adapter 转换；后者仍待实现与独立验收。发布指南将首次 CI 链接标为 initial validation run，保留原始验收证据。MCP 与 VERIFIED 冻结继续保持。

## 已完成的主线

### 公开工程化：2026-10-07

Ubuntu Python 3.11/3.12 与 Windows Python 3.12 的完整离线 CI 已在 [main Actions](https://github.com/ryurikoneko/DAWLoop/actions/runs/37514929489) 通过，包括 Node 合成观察测试、构建、隔离 wheel 安装、学习教程与 provenance 校验。Windows 为 715 tests + 331 subtests；Linux 为 710 tests + 331 subtests，另有 3 个 Win32 项目跳过及 2 个 Win32 启动器用例不收集。跨平台测试只修正模拟环境与时间边界，不放宽 Runtime deadline、target guard 或 dispatch budget，不启动 FL。

中英首页先介绍能力，再集中列出 alpha 范围；公开部署和未来 Release 文案使用项目语言，内部研究记录保留测试结果与验证范围。包元数据补齐 Alpha classifiers 与项目链接；仓库开启合并后删除分支、关闭 Wiki。

新发布流程区分 main 候选构建和可信 SSH signed tag 构建。[候选验收](https://github.com/ryurikoneko/DAWLoop/actions/runs/37514976009) 已通过，构建 commit 为 `3e0688e2603e166cdeb4dfe123bcf0a08505fd63`；五份产物的 GitHub artifact attestation 按仓库/workflow/ref/commit 验证，下载包摘要与四项校验和均匹配。此为 main 候选，不是新版 Release，也不是维护者个人签名。当前可信签名公钥未登记，正式签名 tag 发布仍拒绝。历史 `v0.2.0-alpha.1` 的 tag、Release 和五份资产摘要保持原样。维护顺序见 [发布指南](RELEASING.md)。

[main-quality-gate](https://github.com/ryurikoneko/DAWLoop/rules/24603386) 已启用：PR、严格 `CI gate`、禁止 force-push/删除；管理员例外仅限 PR，不要求单人项目自审批准。发布沿用先合并 main、CI、可信 signed tag、重新构建与验证的顺序。

此更新不增加任何 FL 现场认证；MCP 外部页面身份阻塞和 Native VERIFIED 冻结继续保持。

Controller 身份区分 build（代码）、session（加载会话）、project generation（工程上下文）。身份由运行 Controller 回报，不以磁盘脚本摘要冒充。空标题只作为 EMPTY_ACCEPTED 描述，不参与 generation equality。

导航使用三个固定 primitive：选已有 Pattern → `selectOneChannel(global_index, True)` 独占选通道 → `openEventEditor(getRecEventId(global_index, True) + REC_Chan_PianoRoll, EE_PR)` 定向打开卷帘。曾经点击 Channel Button 打开 Sampler、`showWindow` 只显示旧 Kick 卷帘的失败已定位并更换动作语义；不是通过反复点击凑成功。

完整 A→B→A 在既有 Pattern 1/Kick 与 Pattern 2/Clap 间通过：每方向一事务、三固定 primitive，identity/UI/identity 新鲜夹读，无重试、fallback 或音符派发。仅认证可见目标准备，不认证 producer 内部绑定。

FAST 高层入口已完成结构化计划校验、导航准备、观察确认、确定性 source/AST/hash 校验、一次派发预算、人工接受和证据化终态。session 7 为完整通过记录：固定 16-note Kick 句、dispatch=1、retry=0、fallback=0、人工回执 REALTIME、应用观察 REALTIME、host completion CONFIRMED、试听 USER_OK、原终态 COMPLETED_UNVERIFIED、不保存退出和基线核验通过。

同一派发产生的两份 journal 凭据不是两次派发；计数按唯一 operation/实际调用。人工报告先持久化，协调器领取后才算 REALTIME；晚到试听证据独立保存，不能改写不可变运行终态。应用观察也区分 capture/review/submit/persist/claim/confirm。

## 现场范围与性能含义

| 项目 | 认证范围 |
| --- | --- |
| 宿主 | 维护者 Windows / FL Studio 26.1.6 build 5639 环境 |
| 高层写入 | disposable fixture，Pattern 1 / 808 Kick，PPQ 96 |
| 计划 | 既有固定 16 音符、第 5–8 小节、add-only、单次派发 |
| 接受 | 用户审阅后人工一次 Accept |
| 确认 | 观察性目标 + 可见应用 + completion callback + 用户试听 |
| 恢复 | 不保存退出，size/SHA-256 不变，临时端口关闭 |

这些限定不等于任意目标、任意音乐计划或生产工程认证。早期吞吐与固定四音符 pixel 实验保留代码，但不能把四音符 detector 当作 16-note 或任意音符 Exact Set。原生/Community 公平 A/B 尚未建立，不宣传 Nx faster。

session 7 同域测得 capture约176 ms、capture→review acknowledgement约8.65 s、submit→persist约1.25 ms、claim→confirm约16 ms。跨进程 persist→claim 只有 wall-clock correlation，精确消费延迟未知；这些单样本不代表 API 通用性能，也不把人工等待算 Native backend 延迟。

## 冻结与阻塞

正常脚本返回没有数据传播证据，异常传播仍 unresolved；外层“Script executed without errors”不证明 `apply()` 实际返回/异常进入调用者。读取探针两次出现 dirty flag 0→1，可见音符不变不能升级为无副作用。

```text
VERIFIED_WRITE
  └─ BLOCKED: 可认证 producer-side structured note readback 缺失
       ├─ normal return: NOT_PROVEN
       ├─ error channel: UNRESOLVED
       ├─ file snapshots / output-only: CLOSED
       ├─ Community cache: freshness/target binding 不足
       └─ visual observation: 不能作为 Exact Set 数据源
```

不再设计 return/exception/stdout 变体、notes[] over error、新临时 IPC 或重开文件路线。只有新的可信完整 note-read 接口才解冻；离线 multiset 比较器仍可用。add-only 的未来比较应为 baseline + additions，保留重复次数并锁 PPQ。

Auto Accept 默认关闭、现场未认证，保留实现与失败证据，不继续像素修补。Undo 延期；当前 disposable 实验以 no-save process rollback 收尾。连续写入/修改既有音符/无人值守需求须另开安全合同。

## Phase 2 实际实现

MusicalPlan 与参考生成器是风格无关、受限单声部离线实现。Section Brief / Harmony / Voice / Variation / StyleConstraints 分离，输出包含音符与动机/乐句解释结构。五份数值 profile 只是 schema/validator 示例，不是官方推荐流派或用户艺术家知识。

Learning Framework 实现四份严格 Schema、四份 Agent prompts、聚合与 profile revision。素材权限声明不证明真实授权，hash 不证明分析正确；observed/inferred/unknown 分开，缺失不填零。同类统计 DESCRIPTIVE_ONLY，映射 manual-review-v1，留出 NOT_EVALUATED。用户自己学习自有材料，私人数据忽略，公共例子全部合成。

MCP 的三个工具、后台 RunManager、truthful readiness、real FAST factory 与独立 observer 接线离线完成。现场还未进入有效 run；当前 browser page identity transport unavailable，UI binding blocked、request completion not proven。未降低 URL/page safety gate，也不反复重试外部 fetch。

## 下一步及公开约定

建议发布之后优先让用户 Agent 跑离线学习例子、核对分析/映射/反馈。MCP 路线复验、候选分支展示与当前可用路径的选择条件见 [ROADMAP](ROADMAP.md)。不自动推进连接复用、普通工程连续写入、语音或 VERIFIED。

自有代码与本次公开摘要保持 MIT；CC BY-NC 资产清单为空。原始实验材料与私人 Memos 不发布。此版本没有已验证签名/DOI，不将 hash 作为作者认证。Memos 当前不可调用，公开发布状态与本地检查点可保存，外置同步未完成。
