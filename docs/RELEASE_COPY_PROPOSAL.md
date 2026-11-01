# v0.5.6-alpha.1 Release 文案 / Release copy

维护者已批准采用下列标题与正文。已发布 Release 的 tag、状态、二进制资产和校验和保持不变；文末包内指南调整用于后续正常版本。

The maintainer approved the title and body below. Published tags, release status, binaries and checksums remain unchanged. Packaged-guide improvements at the end apply to a future normal release.

## 当前标题 / Title

DAWLoop v0.5.6-alpha.1 — Music Intelligence Desktop Alpha

## 中文文案

把音乐试听、分析、旋律创作和MIDI编辑放在一个Windows工作区中。

### 版本亮点

- 导入与流式试听，查看WAV音乐分析报告并保存结果。
- 按和声、节奏和密度创建规则辅助旋律。
- 在Piano Roll编辑音符与力度、试听并导出MIDI。
- 中英文界面、基础组件管理及独立用户数据。

### 产品预览

![Music Intelligence 工作区](https://raw.githubusercontent.com/ryurikoneko/DAWLoop/f07642af73355576f15cd62fba20344e7f9a8dff/docs/media/music-home.png)

在一个工作区中探索素材、查看分析并进入旋律编辑。[分析到 MIDI 的操作流程](https://github.com/ryurikoneko/DAWLoop/blob/f07642af73355576f15cd62fba20344e7f9a8dff/docs/DEMOS.md)。图片来自此前开发版本。

### 下载

[Windows x64 Portable ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip) · [SHA256SUMS.txt](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/SHA256SUMS.txt)

### 三步开始

1. 解压完整目录，运行 `DAWLoop.exe`。
2. 在 Music Intelligence → Component Manager 阅读许可，确认安装基础组件。
3. 导入 WAV 试听与分析，或创建规则辅助旋律，进入 Piano Roll 编辑并导出 MIDI。

无需 Codex、Node 或系统 Python。

软件未签名：先核对官方来源和SHA256SUMS.txt，保留系统安全保护。源音频与保存结果独立于程序目录；升级前备份用户数据。

### 当前版本说明

这是Pre-release，已在维护者Windows环境运行；独立干净Windows兼容性待验证。基础分析支持WAV；Basic Pitch需要已有核验环境，首次安装在此版禁用，模型权重未打包。Desktop编辑与Runtime真实FL研究分别配置；通用AutoMix、自主工程控制和完整风格学习为后续研究。公开更新通知关闭，更新由用户主动下载。

### 源码与许可

[Desktop源代码](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1) 对应提交 `b5967ef50fca9d54590559559441ad7f964ec12e`，main 上的 Runtime 不是此 Desktop 二进制的源码。`BUILD_SOURCE.json` 记录构建输入，`SHA256SUMS.txt` 记录摘要；原始通知、逐文件 SBOM 和组件许可随包提供，LGPL 对应源码与构建资料作为同一 Release 的独立资产提供。

DAWLoop 自有代码采用 MIT，第三方组件保留各自许可；品牌和部分图片按独立声明，既有来源审阅状态不因文案修改而改变。历史 Runtime 版本保持原样。此发布不授权用户通知、自动下载/安装或后台服务。

## English copy

Bring listening, analysis, melody creation and MIDI editing into one Windows workspace.

### Highlights

- Import and stream audio, explore WAV analysis reports, and save useful results.
- Create rule-assisted melodies with harmony, rhythm and density constraints.
- Edit notes and velocity in the Piano Roll, audition and export MIDI.
- Chinese/English UI, basic-component management and separate user data.

### Product preview

![Music Intelligence workspace](https://raw.githubusercontent.com/ryurikoneko/DAWLoop/f07642af73355576f15cd62fba20344e7f9a8dff/docs/media/music-home.png)

Explore material, review analysis and move into melody editing in one workspace. [Analysis-to-MIDI workflow](https://github.com/ryurikoneko/DAWLoop/blob/f07642af73355576f15cd62fba20344e7f9a8dff/docs/DEMOS.md). The screenshot is from an earlier development build.

### Download

[Windows x64 Portable ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip) · [SHA256SUMS.txt](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/SHA256SUMS.txt)

### Start in three steps

1. Extract the complete folder and run `DAWLoop.exe`.
2. In Music Intelligence → Component Manager, review the licenses and confirm installation of basic components.
3. Import a WAV to listen and analyze, or create a rule-assisted melody, edit it in the Piano Roll and export MIDI.

Codex, Node and system Python are unnecessary.

The binary is unsigned: verify the official source and SHA256SUMS.txt and keep system security enabled. Back up user data before updating.

### Current Release Notes

This Pre-release has run in the maintainer's Windows environment; independent clean-Windows compatibility awaits validation. Basic analysis supports WAV. Basic Pitch needs an existing verified environment; first installation is disabled in this release and model weights are not bundled. Desktop editing and Runtime FL research are separate workflows. General AutoMix, autonomous project control and full style learning remain research directions. Public update notifications are disabled; users initiate downloads.

### Source and terms

[Desktop source](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1) corresponds to commit `b5967ef50fca9d54590559559441ad7f964ec12e`; the Runtime on main is not the source for this Desktop binary. `BUILD_SOURCE.json` records build inputs and `SHA256SUMS.txt` provides integrity checks. Original notices, a per-file SBOM and component terms are included; LGPL corresponding source and build materials are separate assets in this release.

DAWLoop-authored code remains MIT; third-party components retain their own terms. Branding and certain images have separate notices, and existing provenance-review status is unchanged by this copy revision. Historical Runtime releases are preserved. This release authorizes no user notifications, automatic downloads/installations or background services.

## 包内指南：后续正常版本 / Packaged guides for a future release

现有USER_GUIDE.zh.md与USER_GUIDE.en.md内容均为双语综合说明，首句先讲兼容性验收，来源/构建篇幅较长。后续版本可拆成真正独立语言指南：先启动与许可确认→素材试听/分析→旋律编辑/导出→保存与更新→一个版本说明；构建配方保留在FIRST_RUN_AND_SOURCE和独立源码说明。当前ZIP与其摘要不变，不重新打包修文案。

The current zh/en guides both contain the same bilingual first-run/build text. A future normal release can separate language-specific user journeys from source/build recipes; this release is not repackaged.
