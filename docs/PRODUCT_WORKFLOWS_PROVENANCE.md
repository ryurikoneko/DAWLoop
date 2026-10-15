# 产品工作流文档来源 / Product workflow documentation sources

本页记录产品介绍采用的实现来源，不改变既有 [PROVENANCE](../PROVENANCE.md)、版权通知或历史验证记录。文档重写和新术语表、Release文案提案属于 `CONFIRMED_PROJECT_GENERATED`；引用第三方行为时仍保留原始来源。

This source map supplements the existing provenance without changing copyright notices or historical verification. Rewritten product documentation, the new glossary and the release-copy proposal are project-generated documentation; third-party behavior retains its original attribution.

## 交付来源 / Delivery sources

| 内容 / Content | 版本与依据 / Version and reference |
| --- | --- |
| Desktop公开功能与首次组件安装 / Desktop and component setup | [Alpha.2发行标签](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.2)，对应源码commit `0e27d40b530d526c5bfac2630915ec53bc4855a6`；Release ID `412979500` |
| Runtime、Controller与Production / Runtime, Controller and Production | 本文档分支基于main `961f79d359d7b14de6754bf3bfe3a2441ba75b18`；下表链接为当前分支源码 / Documentation base and branch source below |
| 图片 / Images | [原媒体清单](media/provenance.json)，原图与许可保持不变 / Original images and terms retained |
| 真实宿主故事 / Actual host story | [fast_session_7.json](../evidence/public/fast_session_7.json)，原终态与观察字段保持 / Original terminal state and observations retained |

## 宣称与实现 / Claims and implementation

| 介绍中的行为 / Described behavior | 实现依据 / Source |
| --- | --- |
| Desktop导入、试听、保存分析与乐谱 / Import, playback and saved results | [MusicIntelligence.tsx](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/apps/desktop/src/MusicIntelligence.tsx) |
| 和声、密度、节奏、Seed的规则创作 / Constrained rule-based composition | [ComposerControls.tsx](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/apps/desktop/src/ComposerControls.tsx)、[composer.mjs](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/packages/music-intelligence/composer.mjs) |
| 音符选择、移动、时值、力度与撤销 / Note editing and undo | [PianoRoll.tsx](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/apps/desktop/src/PianoRoll.tsx) |
| Basic Pitch首次安装 / First-time Basic Pitch setup | [pitch-component.mjs](https://github.com/ryurikoneko/DAWLoop/blob/v0.5.6-alpha.2/packages/music-intelligence/pitch-component.mjs)、Release附件 `BASIC_PITCH_NATIVE_REVIEW.md` |
| 音乐网格、NotePlan与多重集合比较 / Grid, plan and multiset comparison | [time](../src/dawloop/time/)、[note_plan](../src/dawloop/note_plan/)、[verification](../src/dawloop/verification/) |
| 当前身份、已有目标导航与观察 / Identity, navigation and observation | [Controller](../src/dawloop/fl_scripts/device_DAWLoopController.py)、[身份客户端](../src/dawloop/adapters/fl_controller_identity.py)、[目标准备](../src/dawloop/adapters/fl_target_preparation.py) |
| Community音符写入与独立刷新读回 / Community note requests and separate refresh | [Adapter](../src/dawloop/adapters/fl_studio_mcp/adapter.py)、[mapping](../src/dawloop/adapters/fl_studio_mcp/mapping.py)、[固定上游](../third_party/fl-studio-mcp/README.md) |
| Native独立桥接与固定16-note任务 / Native bridge and fixed task | [transport](../src/dawloop/adapters/gopher_native/transport.py)、[fast_music](../src/dawloop/runtime/fast_music.py) |
| DAWLoop自有MCP入口 / DAWLoop MCP entry | [fast_mcp_server](../src/dawloop/fast_mcp_server.py) |
| MIDI、配器、RMS、推子规划 / Production analysis and planning | [production](../src/dawloop/production/)、[原来源记录](PRODUCTION_PIPELINE_PROVENANCE.md) |

## 图示与情境 / Diagrams and scenarios

Desktop情境演示是基于实现的使用示例，现有截图来自不同开发界面，不声称同一音频的一次连续录屏。架构图按不同后端分支；时序图解释已记录Native流程。历史16-note操作保持 `COMPLETED_UNVERIFIED`，Exact Set保持 `NOT_VERIFIED`。规划中的Mixer控制与音频结果分别表示。

Desktop scenarios are implementation-based usage examples; existing images are not presented as a continuous recording of one audio input. Architecture diagrams branch by backend; the sequence diagram explains the recorded Native workflow. The historical 16-note operation remains `COMPLETED_UNVERIFIED`, with Exact Set `NOT_VERIFIED`. Planned Mixer control and audio outcomes are represented separately.

## 发布与设置 / Publication and settings

[GitHub展示建议](GITHUB_SHOWCASE.md) 和 [Release文案提案](RELEASE_COPY_v0.5.6-alpha.2_PROPOSAL.md) 只提供维护者审阅材料。当前Release正文仍含早先通知关闭描述，而main已有特定Alpha.2 Preview限时批准；两者的历史不同，不通过文档修改扩大批准范围。正式Release、资产、标签、通知文件与设置不在本次文档改动内。

The presentation and release-copy proposals are review material. The current release still contains an earlier notification-disabled statement, while main has a time-limited approval for the specific Alpha.2 Preview release. Those histories differ; documentation does not expand approval. Published releases, assets, tags, notification files and settings are outside this documentation change.
