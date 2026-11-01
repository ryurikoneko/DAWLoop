# Desktop Alpha.2 Release 文案建议 / Release copy proposal

供维护者审阅的正文候选，面向现有 `v0.5.6-alpha.2`。它不改变已发布正文、九项附件、标签或校验和。旧Alpha.1文案记录保留在 [原提案](RELEASE_COPY_PROPOSAL.md)。

Proposed copy for the existing Alpha.2 release, pending owner review. Published copy, its nine assets, tag and checksums remain unchanged. The previous proposal retains the Alpha.1 record.

建议标题 / Proposed title: **DAWLoop Desktop 0.5.6-alpha.2 — From audio ideas to editable MIDI**

---

## 一起研究素材，继续创作 / Study material and keep creating

DAWLoop Desktop把试听、音乐分析、规则辅助旋律和Piano Roll集中在一个工作区。导入自己的WAV，研究节奏、能量与调性候选，选择创作条件，再把想法变成可编辑、可试听和可导出的MIDI。

DAWLoop Desktop brings listening, music analysis, rule-assisted melody creation and Piano Roll editing into one workspace. Import your WAV, explore rhythm, energy and key candidates, choose musical constraints and turn ideas into MIDI you can edit, audition and export.

## 这个版本带来什么 / Highlights

- **素材到旋律 / Material to melody:** 音频试听与分析报告连接你的创作判断，和声、节奏、密度和Seed帮助准备候选。 / Listening and reports inform creative decisions; harmony, rhythm, density and seed controls generate candidates.
- **继续编辑 / Keep editing:** 在Piano Roll选择、移动和修改音符、时值与力度，撤销重做，保存乐谱并导出MIDI。 / Select, move and adjust notes, timing and velocity, undo/redo, save scores and export MIDI.
- **Basic Pitch安装 / Basic Pitch setup:** 组件管理器恢复首次安装入口，核验组件和模型，并准备独立运行环境。 / First-time component installation is restored, with component/model verification and a dedicated runtime.
- **保留工作 / Keep your work:** 主动保存的分析报告与命名乐谱可在下次启动后重新打开，中英文界面帮助理解操作。 / Explicitly saved reports and named scores reopen after restart, with Chinese and English UI.

## 看看工作流 / Explore the workspace

![Music Intelligence workspace](https://raw.githubusercontent.com/ryurikoneko/DAWLoop/main/docs/media/music-home.png)

试听素材，选择分析或旋律创作，再把音符交给Piano Roll。现有截图来自开发版本；[图文演示](https://github.com/ryurikoneko/DAWLoop/blob/main/docs/DEMOS.md) 说明每一步与图片来源。

Listen, choose analysis or melody creation, then work with notes in the Piano Roll. Existing screenshots come from development builds; the illustrated guide explains the workflow and image sources.

## 下载与三步开始 / Download and get started

先核对官方附件与 [SHA256SUMS.txt](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.2/SHA256SUMS.txt)。Windows可执行文件尚未签名，系统可能显示信誉提示；先确认来源与校验，不要批量关闭系统防护。使用自有或获准音频。Basic Pitch安装前审阅许可，准备网络、约136.5MiB组件下载和至少1GiB空闲空间；模型不会因打开软件而自动下载。

Verify the official assets against SHA256SUMS first. The Windows executable is unsigned and may trigger a reputation warning; establish source and checksums rather than disabling system protection. Use permitted audio. Review component terms before Basic Pitch setup and allow for network access, roughly 136.5 MiB of component download and at least 1 GiB free space. Opening the app does not automatically download models.

1. 下载并完整解压 [Windows x64 Portable ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.2/DAWLoop%2B0.5.6-alpha.2-Windows-x64-Portable.zip)。 / Download and fully extract the portable ZIP.
2. 从解压目录启动DAWLoop，进入Music Intelligence，导入WAV试听并分析。 / Launch from the extracted directory, open Music Intelligence, import a WAV and analyze it.
3. 创建旋律或配置Basic Pitch后转录，在Piano Roll审阅修改，保存乐谱或导出MIDI。 / Create a melody, or configure Basic Pitch for transcription, then review notes, save a score or export MIDI.

[完整使用指南](https://github.com/ryurikoneko/DAWLoop/blob/main/docs/DESKTOP.md) · [Runtime开发入口](https://github.com/ryurikoneko/DAWLoop/blob/main/docs/QUICKSTART.md)

## 源码与许可 / Source and licenses

Desktop对应源码在 [v0.5.6-alpha.2](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.2) 与本Release的 `Corresponding-Source.zip`；Runtime main独立演进。项目自有代码保留MIT，Electron、音频运行组件及其他依赖分别遵循各自许可，品牌与媒体按独立声明使用。查看附件 `FIRST_RUN_AND_SOURCE.md`、`BASIC_PITCH_NATIVE_REVIEW.md`、`THIRD_PARTY_NOTICES.md` 与 [许可范围](https://github.com/ryurikoneko/DAWLoop/blob/main/LICENSE_POLICY.md)。

Desktop source is at the release tag and in its Corresponding-Source ZIP; Runtime main evolves separately. Project code retains MIT, dependencies retain their own terms, and brand/media use follows separate notices. Review the source, component and third-party documents above.

社区 [FL Studio MCP](https://github.com/karl-andres/fl-studio-mcp) 提供执行工具来源；[坏影子不坏](https://space.bilibili.com/599132499) 的DSH视频与自动化实践提供工作流启发，部分Production代码改编自其MIT许可 `whale-music-pipeline`。这些来源与DAWLoop自有工作分别记录。

Community FL Studio MCP supplies execution-tool prior art. The DSH demonstrations of 坏影子不坏 (UID 599132499) informed production workflows; some Production code was adapted from the MIT-licensed whale-music-pipeline. These contributions remain distinct from DAWLoop's own work.

## 当前版本说明 / Current Version Notes

- 公开Windows x64 Alpha；独立干净Windows兼容性仍需另行确认。 / Public Windows x64 Alpha; independent clean-Windows compatibility remains to be established.
- 基础分析支持WAV；节奏与调性结果是参考估计。 / Basic analysis supports WAV; rhythm and key outputs are estimates.
- 转录需安装配置Basic Pitch并审阅输出；高级模型按具体设备和组件条件使用。 / Transcription needs configured Basic Pitch and output review; advanced models depend on their actual setup.
- 本地编辑与真实FL操作是不同路径；宿主案例按其原始观察与验证范围解释。 / Local editing and FL host operations are distinct; host cases retain their original evidence scope.
- 更新提示只在用户设置和有效维护者审批同时满足时生效，不自动下载或安装；本稿不新增通知授权。 / Update reminders require both user settings and valid owner approval, never auto-download/install, and this proposal grants no new notification authority.
