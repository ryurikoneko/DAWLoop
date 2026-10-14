# DAWLoop 使用场景 / DAWLoop in practice

## 从音乐素材到可编辑旋律 / From musical material to editable notes

**目标：**理解一段素材，创作或整理旋律，并带回自己的制作工程。

**Goal:** understand material, create or refine a melody, and take it into your production project.

1. 在 Desktop 导入 WAV，试听并定位想研究的片段。 / Import a WAV, listen and locate a section.
2. 查看音乐分析报告，主动保存有用的结果。 / Review the analysis report and save useful results.
3. 使用规则约束生成旋律，或在已配置 Basic Pitch 环境中转录。 / Generate a constrained melody, or transcribe with a configured Basic Pitch environment.
4. 进入 Piano Roll，编辑音符、力度和时值，试听并导出 MIDI。 / Edit notes, velocity and timing, audition and export MIDI.

**得到：**分析报告、可编辑的旋律与 MIDI 文件。 / **Result:** an analysis report, editable notes and a MIDI file.

### 看见制作流程 / See the workflow

**选择入口：**在 Music Intelligence 工作区选择音频分析、旋律创作或音符编辑。 / **Choose a starting point:** open analysis, melody creation or note editing from Music Intelligence.

![Music Intelligence workspace](media/music-home.png)

**理解素材：**查看音频测量与分析结果，为下一步创作提供参考。 / **Understand the material:** review measurements and analysis before choosing the next creative action.

![Music Analysis](media/analysis-report.png)

**编辑与带走：**在本地 Piano Roll 调整音符、试听并导出 MIDI。 / **Edit and take it with you:** adjust notes in the local Piano Roll, audition and export MIDI.

![Piano Roll Editing](media/piano-roll.png)

这些图片展示已有开发版本的操作界面，分别说明三个步骤，并非同一素材的一次连续录屏。 / These existing development-build screenshots illustrate the three steps separately; they are not a continuous recording of one source file.

[Desktop 操作指南](DESKTOP.md)

## 让 Agent 在 FL Studio 中执行受控操作 / An agent working inside FL Studio

**目标：**把明确的音乐计划交给真实 DAW 执行，并观察操作结果。

**Goal:** execute a specific musical plan inside the running DAW and inspect what happened.

研究流程使用独立测试工程：确认已有 Pattern 与 Channel → 审阅计划 → 一次受控执行 → 用户确认 → 观察结果并记录。开发者可复用目标约束、人工接受及结果报告接口。

The research workflow uses a disposable project: identify an existing Pattern and Channel → review the plan → dispatch once → human confirmation → observe and record. Developers can reuse target constraints, human acceptance and result-reporting interfaces.

**得到：**受限测试目标中的真实宿主操作记录。查看 [公开现场摘要](../evidence/public/fast_session_7.json) 与 [验证规则](VERIFICATION.md)，了解实际记录的范围。

**Result:** a record of real host actions within a constrained test scope. See the [public record](../evidence/public/fast_session_7.json) and [verification model](VERIFICATION.md).

宿主测试前备份工程，使用专用测试目标；人工接受及目标检查按 [部署指南](DEPLOYMENT.md) 保留。

Back up projects and use a dedicated test target; follow the [deployment guide](DEPLOYMENT.md) for target checks and human confirmation.

## 当前版本说明 / Current Release Notes

Desktop Alpha 已公开；第一场景为独立音乐工作区，第二场景为 Runtime 宿主研究，分别展示。Basic Pitch 需要已有核验环境，首次模型安装在此版暂不可用。历史宿主记录包含固定16-note操作及人工接受，终态为 `COMPLETED_UNVERIFIED`；完整宿主 Exact-Set 认证另有前置条件。截图来自此前开发版本，公开短视频尚未提供。

The Desktop Alpha is public. The music workspace and Runtime host-research scenarios are separate demonstrations. Basic Pitch needs an existing verified environment. The historical host record covers 16 notes and human acceptance, ending in `COMPLETED_UNVERIFIED`; full host Exact-Set verification has separate prerequisites. Screenshots are from an earlier build; no public video is linked yet.

[能力页](CAPABILITIES.md) · [图片来源](media/README.md) · [历史场景记录](archive/public-presentation-20261014/README.md)
