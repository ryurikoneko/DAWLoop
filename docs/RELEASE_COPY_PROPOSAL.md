# v0.5.6-alpha.1 Release 文案修订稿 / Release copy proposal

仅供维护者审阅。此PR不修改已发布Release正文、名称、tag、状态、二进制资产或压缩包指南。

For review only. Published release metadata, assets and packaged guides remain unchanged.

## 建议标题 / Proposed title

DAWLoop v0.5.6-alpha.1 — Music Intelligence Desktop Alpha

## 中文修订稿

把音乐试听、分析、旋律创作和MIDI编辑放在一个Windows工作区中。

### 版本亮点

- 导入与流式试听，查看WAV音乐分析报告并保存结果。
- 按和声、节奏和密度创建规则辅助旋律。
- 在Piano Roll编辑音符与力度、试听并导出MIDI。
- 中英文界面、基础组件管理及独立用户数据。

### 下载与安装

[Windows x64 Portable ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip)。解压完整目录，运行DAWLoop.exe；在Music Intelligence → Component Manager阅读许可并确认安装基础组件，再导入WAV。无需Codex、Node或系统Python。

软件未签名：先核对官方来源和SHA256SUMS.txt，保留系统安全保护。源音频与保存结果独立于程序目录；升级前备份用户数据。

### 当前版本说明

这是Pre-release，已在维护者Windows环境运行；独立干净Windows兼容性待验证。基础分析支持WAV；Basic Pitch需要已有核验环境，首次安装在此版禁用，模型权重未打包。Desktop编辑与Runtime真实FL研究分别配置；通用AutoMix、自主工程控制和完整风格学习为后续研究。公开更新通知关闭，更新由用户主动下载。

### 源码与许可

[Desktop源代码](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1)。BUILD_SOURCE.json记录构建输入；SHA256SUMS.txt记录摘要；对应源码及第三方通知见同一Release资产。项目代码MIT，品牌图片按独立声明。历史Runtime版本保持原样。

## English draft

Bring listening, analysis, melody creation and MIDI editing into one Windows workspace.

### Highlights

- Import and stream audio, explore WAV analysis reports, and save useful results.
- Create rule-assisted melodies with harmony, rhythm and density constraints.
- Edit notes and velocity in the Piano Roll, audition and export MIDI.
- Chinese/English UI, basic-component management and separate user data.

### Download and start

[Windows x64 Portable ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip). Extract the complete folder and run DAWLoop.exe. Review licenses and install basic components in Music Intelligence → Component Manager, then import a WAV. Codex, Node and system Python are unnecessary.

The binary is unsigned: verify the official source and SHA256SUMS.txt and keep system security enabled. Back up user data before updating.

### Current Release Notes

This Pre-release has run in the maintainer's Windows environment; independent clean-Windows compatibility awaits validation. Basic analysis supports WAV. Basic Pitch needs an existing verified environment; first installation is disabled in this release and model weights are not bundled. Desktop editing and Runtime FL research are separate workflows. General AutoMix, autonomous project control and full style learning remain research directions. Public update notifications are disabled; users initiate downloads.

### Source and terms

[Desktop source](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1), BUILD_SOURCE.json, SHA256SUMS.txt, corresponding source and third-party notices are supplied through the release. Project code remains MIT; branding has separate notices. Historical Runtime releases are preserved.

## 包内指南：后续正常版本 / Packaged guides for a future release

现有USER_GUIDE.zh.md与USER_GUIDE.en.md内容均为双语综合说明，首句先讲兼容性验收，来源/构建篇幅较长。后续版本可拆成真正独立语言指南：先启动与许可确认→素材试听/分析→旋律编辑/导出→保存与更新→一个版本说明；构建配方保留在FIRST_RUN_AND_SOURCE和独立源码说明。当前ZIP与其摘要不变，不重新打包修文案。

The current zh/en guides both contain the same bilingual first-run/build text. A future normal release can separate language-specific user journeys from source/build recipes; this release is not repackaged.
