# DAWLoop Desktop

## 音乐创作工作区 / A workspace for making music

从素材试听到旋律编辑，把下一步制作操作放在眼前。Music Intelligence 集中音频、分析报告、旋律创作和 Piano Roll；界面支持中文与英文。

Listen to material, explore its structure, create a melody and edit the result in one Music Intelligence workspace. Chinese and English interfaces are available.

![Music Intelligence](media/music-home.png)

## 开始使用 / Start here

[下载 Windows x64 Desktop Alpha / Download](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.2/DAWLoop%2B0.5.6-alpha.2-Windows-x64-Portable.zip) · [Release / SHA-256](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.2)

1. 解压完整程序目录，启动 `DAWLoop.exe`。 / Extract the complete folder and launch `DAWLoop.exe`.
2. 打开 Music Intelligence → Component Manager，阅读许可并确认安装基础组件。 / Review licenses and confirm the bundled basic-component installation.
3. 导入 WAV，播放并分析；在组件管理中安装 Basic Pitch 后转录音符，进入 Piano Roll 编辑并导出 MIDI。 / Import a WAV to play and analyze; install Basic Pitch in Component Manager to transcribe, edit in the Piano Roll and export MIDI.

软件未签名。核对官方下载及 SHA-256；保留系统安全机制。首次运行的基础音乐工作流无需 FL Studio、Codex、Node 或系统 Python。

The binary is unsigned. Verify its official download and SHA-256; keep system security enabled. Basic music workflows need no FL Studio, Codex, Node or system Python.

## 从素材到作品片段 / From material to a musical idea

### 试听与分析 / Listen and analyze

导入、流式播放、暂停和定位音频。查看响度、能量变化、节奏和调性候选；保存想保留的分析到音乐库。

Import audio, stream playback, pause and seek. Explore loudness, energy changes, rhythm and key candidates; explicitly save analyses you want to keep.

![音乐分析 / Music Analysis](media/analysis-report.png)

### 创建或转录旋律 / Create or transcribe

按和声、节奏、密度和 Seed 约束生成规则辅助旋律。Basic Pitch 支持阅读许可后应用内一键安装，把音频转录为可编辑音符。

Generate rule-assisted melodies from harmony, rhythm, density and seed constraints. Basic Pitch supports in-app one-click installation after license review and real audio-to-note transcription.

### 在 Piano Roll 中编辑 / Edit in the Piano Roll

审阅音符与力度，修改音高和时值、撤销、试听。导出 MIDI 后，继续在自己的 DAW 中制作。

Review notes and velocity, edit pitch and timing, undo and audition. Export MIDI to continue production in your own DAW.

![Piano Roll](media/piano-roll.png)

### 管理组件与结果 / Manage components and results

组件管理显示安装、版本和任务状态。主动保存结果可在下次启动恢复；临时导入保持临时，原始音频和应用数据分别保存。

Component Manager shows installation, version and job status. Explicitly saved results persist across restarts; temporary imports stay temporary, with source audio separate from application data.

## 当前版本说明 / Current Release Notes

- **0.5.6-alpha.2，Windows x64 Pre-release。** 已在维护者 Windows 环境运行；独立干净 Windows 兼容性尚待验证。 / Tested in the maintainer's Windows environment; independent clean-system compatibility awaits validation.
- 随包基础分析支持 WAV。音频预览与分析的格式支持分别管理；此版不承诺 MP3/FLAC 分析。 / Bundled analysis supports WAV; playback and analysis codec support are separate.
- Basic Pitch 独立组件随包提供，安装前确认许可并校验文件；维护者本机全新隔离目录已完成真实转录、编辑、MIDI 导出读回与重启恢复。 / The isolated Basic Pitch component is included, installed after license consent and integrity checks; real transcription, editing, MIDI roundtrip and restart recovery passed in fresh directories on the maintainer’s Windows system.
- Desktop Piano Roll 是本地编辑器；FL 操作按 [Runtime 部署](DEPLOYMENT.md) 独立配置与验证。通用自动混音和自主工程制作仍是研究方向。 / Local editing and live host integration are separate workflows.
- 分析包含估计值，按报告来源与不确定性解读。公开 Windows 更新通知关闭，没有自动下载安装。 / Interpret estimates using their source and uncertainty; public notifications and automatic updates are disabled.
- 截图来自此前开发版本。源码在 [公开发行标签](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.2)，main 为 Python Runtime 与项目文档。 / Screenshots are from an earlier build; Desktop source is at the release tag.

Basic Pitch 适合乐器素材；复杂混音不等于多轨分离。 / Basic Pitch is intended for instrument material, not complete multi-track separation of complex mixes.

[Alpha.1 历史发行 / Previous release](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) 保留原有文件。 / Original assets remain unchanged.

[首次运行与构建说明 / First run and build](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/docs/DESKTOP_ALPHA_BUILD.md) · [能力依据](CAPABILITIES.md) · [演示](DEMOS.md) · [历史技术记录](archive/public-presentation-20261014/README.md)
