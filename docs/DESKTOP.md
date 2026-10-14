# Desktop / Music Intelligence — Experimental Alpha

## 当前可公开内容 / Current public scope

[COMPUTED｜HIGH] [DAWLoop v0.5.6-alpha.1](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) 已公开 Windows x64 Portable ZIP、校验和、构建记录、第三方通知和对应源码。Desktop 源码提交为 `b5967ef50fca9d54590559559441ad7f964ec12e`，位于 [公开发行标签](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1)；Runtime main 与旧 Python Release 仍独立，不能将其当成 Desktop 构建来源。

[COMPUTED | HIGH] The Desktop Pre-release provides a Windows portable ZIP, checksums, build provenance, notices and corresponding source. Desktop source is published at the release tag above, separately from Runtime main and historical Python Releases.

[KNOWN｜HIGH] 解压运行 `DAWLoop.exe`，在音乐智能 → 组件管理中确认许可并安装随包基础组件，再导入 WAV 分析。无需系统 Python、Node、Codex 或寻找 runtime.json。模型权重不随包提供；Basic Pitch 的旧 Python 首次安装链暂时禁用，现有核验环境仍可用。规则创作、Piano Roll 与 MIDI 导出不受其影响。

[KNOWN | HIGH] Extract and run DAWLoop.exe; review licenses and install bundled basic components in Music Intelligence → Component Manager, then analyze WAV. System Python, Node and Codex are unnecessary. Model weights are not bundled. First installation of the legacy Basic Pitch runtime is disabled; existing verified environments remain usable. Rule composition, Piano Roll and MIDI export remain available.

**Experimental Alpha — Tested on maintainer's Windows environment. Clean Windows compatibility has not been independently verified.**

[KNOWN｜HIGH] `CLEAN_WINDOWS_E2E = NOT_TESTED / RISK_ACCEPTED_BY_MAINTAINER`。此次维护者明确取消其强制发行门，未把未测试状态改为 PASS。不声称开箱即用。`PUBLIC_NOTIFICATION_GATE = DISABLED`：公开发行不批准 Windows 用户通知或自动下载安装。

[KNOWN | HIGH] Clean Windows remains untested; the maintainer accepted this Alpha's uncertainty. Public notifications remain disabled; publication does not grant notification or automatic installation consent.

[首次运行、源码构建与许可 / First run, source build and licensing](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.1/docs/DESKTOP_ALPHA_BUILD.md)

## 独立音乐工作流 / Independent music workflow

[COMPUTED｜HIGH] 已有受管组件的内部环境完成过：

1. 启动单主窗口，进入 Music Intelligence。
2. 导入自有音频；临时导入不默认成为跨重启历史列表。
3. 执行基础分析，查看结果与不确定性；主动保存才作为持续可见资产。
4. 使用已就绪的 Basic Pitch 转录，或使用 RULE_BASED 作曲。
5. 在 Piano Roll 审阅、编辑、试听，导出 MIDI 并独立读回。

[COMPUTED | HIGH] The managed internal environment has exercised a single main window → owned audio import → basic analysis and explicit save → available Basic Pitch or RULE_BASED composition → Piano Roll review/edit/audition → MIDI export and independent readback. Temporary imports do not automatically become persistent visible history.

## 安装与限制 / Installation and limits

- [KNOWN｜HIGH] Python、模型依赖与权重不是全部随便携候选提供。Basic DSP 未就绪时在创建任务前拦截；普通用户不应寻找 `runtime.json`。可信离线基础组件现已随 Alpha 提供；安装须确认许可，分析编解码范围以发行说明为准。
- [KNOWN｜HIGH] 基础分析与第三方模型分开；模型未安装时不应阻止进入主界面。模型操作保留许可确认、硬件限制与真实错误。
- [KNOWN｜HIGH] Basic Pitch 不等于复杂混音分轨；OMAR 单段 Embedding 不等于学习风格。SheetSage2 offset 和 YuE2 环境限制保留。
- [KNOWN｜HIGH] FL 配置不是独立音乐功能的首启门槛；Desktop 不获得额外宿主控制权限。
- [KNOWN｜HIGH] 普通/开发者模式只是展示差异，中英文与减少动态效果均已在内部候选操作；不是权限升级机制。

[KNOWN | HIGH] Runtime components and model weights are not all bundled. Missing Basic DSP is detected before job submission; the trusted basic component is now bundled with the Alpha and requires license confirmation. Model absence does not block the workspace. License confirmation, hardware constraints, uncertainty and real errors remain visible. Basic Pitch is not source separation; OMAR is not style learning. FL configuration is optional for independent music tasks. User/developer modes and reduced motion do not raise permissions.

## 内部验收摘要 / Internal acceptance summary

[COMPUTED｜HIGH] 源码 `66806b5` 候选完成品牌/中英文/重启动效、24项 Piano Roll 操作、Basic DSP / Basic Pitch /规则作曲工作流、保存恢复与大文件 Streaming 操作。数值算法证据来自前一独立阶段 `3aeb675`；本轮品牌回归没有扩张算法认证。真人三分钟、用户私人音频、真正干净 Windows 及任务栏/Alt+Tab 实际显示不是本页已通过项。

[COMPUTED | HIGH] Candidate `66806b5` exercised bilingual branding/motion/restart, 24 Piano Roll interactions, DSP / Basic Pitch / rule composition, persistence and large-file streaming. Numerical algorithm evidence belongs to preceding stage `3aeb675`; branding regression does not extend it. A human three-minute flow, private user audio, clean Windows deployment and actual taskbar/Alt+Tab rendering are not passed claims here.

[Capabilities](CAPABILITIES.md) · [Two demos](DEMOS.md) · [Media provenance](media/README.md)

## 历史内部候选记录 / Historical internal candidate (superseded by the Alpha scope above)

[COMPUTED｜HIGH] 软件功能基线66806b5，新打包来源8123ae3，版本0.5.6-internal.1，分发名DAWLoop+0.5.6-internal.1。新增随包中英文使用指南、MIT及组件通知，不改算法或宿主。代码仍在独立本地release功能树，公开main不包含该构建源码；本轮未公开安装包。

[KNOWN｜HIGH] 本机没有取得可用干净Windows VM验收；现有基础Python venv依赖开发机绝对路径，不能复制冒充可分发组件。干净Windows与完整可信离线音频组件门均BLOCKED，禁止标为开箱即用。Node/npm/Codex不是界面运行要求，独立Python及权重不随包提供。

[COMPUTED | HIGH] Feature baseline66806b5, packaging source8123ae3, version0.5.6-internal.1, distribution nameDAWLoop+0.5.6-internal.1. Packaging adds bilingual guides and notices without algorithm/host changes. Source remains in a separate local release tree, not public main; no Desktop installer is published.

[KNOWN | HIGH] No usable clean-Windows VM was available for acceptance. The existing Python venv relies on the development machine's absolute base path and is not a distributable runtime. Clean-system and trusted offline-component gates remain BLOCKED; no ready-out-of-the-box claim is made.
