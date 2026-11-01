# DAWLoop Desktop 0.5.8-alpha.1 — Audio Transcription Studio

音频导入、后台转写、多轨时间轴、Piano Roll 编辑、试听和原生 MIDI 文件拖出现在整合在「音乐智能 → Audio Transcription Studio」。当前保存的编辑用于另存和拖出；原始推理结果独立保留，可恢复，不需要重新分析整曲。

Audio import, background transcription, a multitrack timeline, Piano Roll editing, preview and native MIDI file drag-out now live in Music Intelligence → Audio Transcription Studio. Exports use saved edits while original predictions remain recoverable.

## 首次使用 / First use

解压 Windows x64 Portable ZIP 后运行 DAWLoop.exe。在组件管理中分别确认许可并安装随包提供的 Basic Audio 和 Basic Pitch 组件，再进入工作台导入 WAV。组件安装与推理在本地执行，不需要付费API或系统Python。

Extract the Windows x64 Portable ZIP and run DAWLoop.exe. In Component Manager, review the terms and install the included Basic Audio and Basic Pitch packs, then import a WAV into the Studio. Installation and inference are local; no paid API or system Python is required.

Basic Pitch 单独可用时，显示混音中高音候选与低音区候选；它们按音区拆分，不能冒充人声/器乐分离或精确主旋律。缺少的声部显示未提供，不生成伪造和弦。支持读取已有整曲转写目录。已有受审本地 SheetSage2 环境时可进一步分析人声、器乐与参考和弦；本发行不包含 SheetSage2 权重或其首次安装器。

With Basic Pitch alone, mid/high and low-register mixed-audio candidates are shown. Register splitting is not source separation or exact lead extraction. Missing parts remain unavailable; chords are not fabricated. Existing transcription folders can be restored. A separately reviewed local SheetSage2 environment enables additional vocal, instrumental and reference-chord analysis; its weights and first-install setup are not included.

## 交互与兼容性 / Interaction and compatibility

- 五类同步视图、缩放/滚动、原曲与MIDI试听、静音/独奏、音符移动/尾音编辑/删除、撤销重做及恢复原始结果。综合项不额外叠加播放。
- 导出前保存编辑。`↗ MIDI` 发起操作系统文件拖放；点击或键盘访问另存按钮可保存真实 MIDI 文件。导出文件不会因失焦或拖放结束立即删除。
- 原生拖放已在维护者环境由资源管理器和宿主 Piano Roll 接收。Playlist 直接接收未确认；Piano Roll 接收不代表全局tempo map自动同步。
- 与原Composer兼容，新增参考和弦JSON导出；本轮没有一键写入Composer画布。

Five synchronized views support zoom/scroll, original/MIDI preview, mute/solo and note editing with undo/redo. Combined is a view/export, not another playback layer. Save edits before dragging `↗ MIDI`; keyboard-accessible save-as is also available. Export files persist after focus changes and drag completion. Explorer and host Piano Roll receipt were observed; direct Playlist receipt and automatic conductor-tempo import remain unconfirmed. Reference-chord JSON export is available without changing Composer.

## 范围 / Scope

公开组件的验收格式为WAV；MP3/FLAC处理取决于另行可用的解码能力。预测、参考Voicing及低音候选均需听审，技术回读不证明音乐准确。独立干净Windows机器兼容性仍待确认，程序二进制未签名。本机隔离组件安装测试不等于独立机器验收。

WAV is the validated public-component format; MP3/FLAC analysis depends on separately available decoding support. Predictions and candidate parts need musical review. Independent clean-Windows compatibility remains unverified; the application binary is unsigned. Isolated installation on the maintainer's machine is not an independent-machine test.

所有既有通知批准仅限对应旧版本；本发行不启用新版本通知，不自动下载安装。MIT原文与其他既有许可不改。Basic Audio、Basic Pitch 原生通知、SBOM、Microsoft条款及对应源码随发行提供；SheetSage2的非商业限制不因本次界面发布而改变。

Old notification approvals remain scoped to their original releases; this release enables no new public notification or automatic installation. Existing licenses, including MIT, are unchanged. Native notices, SBOMs, Microsoft terms and corresponding source are provided. The Studio release does not change SheetSage2's noncommercial restrictions.
