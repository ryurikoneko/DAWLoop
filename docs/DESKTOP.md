# Desktop / Music Intelligence — 内部预览 / Internal preview

## 当前可公开内容 / Current public scope

[COMPUTED｜HIGH] 公开 main `1a99482` 不包含 `apps/desktop`。独立 `feature/music-intelligence` 功能树 `66806b5` 的内部候选为 `0.5.6-internal.1`。本 docs 分支仅增加展示与文档，不合入 Desktop 业务代码，不发布 EXE。

[COMPUTED | HIGH] Public main does not include `apps/desktop`. Separate feature-tree source `66806b5` produced internal candidate `0.5.6-internal.1`. This docs branch does not merge Desktop code or distribute an EXE.

[KNOWN｜HIGH] 普通访问者目前不能从公开 Release 安装该 Desktop，也不能从 main 运行不存在的 npm 启动脚本。请等待明确的源码集成或发行许可。已经获准使用内部候选的测试者按候选说明操作；不要复制别人未校验的模型或 Python 目录。

[KNOWN | HIGH] Visitors cannot currently install this Desktop from public Releases or run a nonexistent npm entrypoint from main. Await an explicit source integration or distribution. Authorized internal testers follow their candidate instructions; do not copy unaudited model or Python directories.

## 独立音乐工作流 / Independent music workflow

[COMPUTED｜HIGH] 已有受管组件的内部环境完成过：

1. 启动单主窗口，进入 Music Intelligence。
2. 导入自有音频；临时导入不默认成为跨重启历史列表。
3. 执行基础分析，查看结果与不确定性；主动保存才作为持续可见资产。
4. 使用已就绪的 Basic Pitch 转录，或使用 RULE_BASED 作曲。
5. 在 Piano Roll 审阅、编辑、试听，导出 MIDI 并独立读回。

[COMPUTED | HIGH] The managed internal environment has exercised a single main window → owned audio import → basic analysis and explicit save → available Basic Pitch or RULE_BASED composition → Piano Roll review/edit/audition → MIDI export and independent readback. Temporary imports do not automatically become persistent visible history.

## 安装与限制 / Installation and limits

- [KNOWN｜HIGH] Python、模型依赖与权重不是全部随便携候选提供。Basic DSP 未就绪时在创建任务前拦截；普通用户不应寻找 `runtime.json`。可信离线首装资源仍是交付阻塞。
- [KNOWN｜HIGH] 基础分析与第三方模型分开；模型未安装时不应阻止进入主界面。模型操作保留许可确认、硬件限制与真实错误。
- [KNOWN｜HIGH] Basic Pitch 不等于复杂混音分轨；OMAR 单段 Embedding 不等于学习风格。SheetSage2 offset 和 YuE2 环境限制保留。
- [KNOWN｜HIGH] FL 配置不是独立音乐功能的首启门槛；Desktop 不获得额外宿主控制权限。
- [KNOWN｜HIGH] 普通/开发者模式只是展示差异，中英文与减少动态效果均已在内部候选操作；不是权限升级机制。

[KNOWN | HIGH] Runtime components and model weights are not all bundled. Missing Basic DSP is detected before job submission; trusted offline first installation remains blocked. Model absence does not block the workspace. License confirmation, hardware constraints, uncertainty and real errors remain visible. Basic Pitch is not source separation; OMAR is not style learning. FL configuration is optional for independent music tasks. User/developer modes and reduced motion do not raise permissions.

## 内部验收摘要 / Internal acceptance summary

[COMPUTED｜HIGH] 源码 `66806b5` 候选完成品牌/中英文/重启动效、24项 Piano Roll 操作、Basic DSP / Basic Pitch /规则作曲工作流、保存恢复与大文件 Streaming 操作。数值算法证据来自前一独立阶段 `3aeb675`；本轮品牌回归没有扩张算法认证。真人三分钟、用户私人音频、真正干净 Windows 及任务栏/Alt+Tab 实际显示不是本页已通过项。

[COMPUTED | HIGH] Candidate `66806b5` exercised bilingual branding/motion/restart, 24 Piano Roll interactions, DSP / Basic Pitch / rule composition, persistence and large-file streaming. Numerical algorithm evidence belongs to preceding stage `3aeb675`; branding regression does not extend it. A human three-minute flow, private user audio, clean Windows deployment and actual taskbar/Alt+Tab rendering are not passed claims here.

[Capabilities](CAPABILITIES.md) · [Two demos](DEMOS.md) · [Media provenance](media/README.md)
