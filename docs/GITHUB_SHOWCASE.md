# GitHub 展示建议 / Repository presentation proposals

本页把实际仓库元数据与建议分开。About、Topics与Social Preview设置由维护者审阅后操作；文档中的候选不代表已上传或已生效。

This page separates observed metadata from proposals. The owner reviews About, Topics and Social Preview changes; a candidate documented here is not a deployed setting.

## 三产品展示方案 / Three-product presentation

首页以 Desktop — Open Source、Plugin — Proprietary、Runtime — Open Source 三个入口呈现。Plugin 展示 Composer 的真实开发界面；只有 Desktop 现有公开发行提供下载。Composer 本地 r2 候选不作为公开资产，本轮仅交付 Composer。

The homepage separates the three products and shows the real Composer preview. Only the existing published Desktop release has a download. The local Composer r2 candidate is not a public asset, and this delivery includes Composer only.

建议 About： / Proposed About:

> AI music creation and verifiable DAW automation. Open-source Desktop and Runtime, with proprietary a proprietary Composer plugin.

这是一份元数据候选，不代表已修改 GitHub Settings。现有 Topics 与社交卡片保持，待维护者审阅后另行更新。

This is a metadata proposal, not a deployed GitHub setting. Existing topics and social-card settings remain for owner review.

## About：实际描述与候选 / Current description and candidates

2026-10-15读取到的描述为： / Description observed on 15 October 2026:

> AI-assisted music creation and verifiable DAW automation. Windows Desktop Alpha and an open Python Runtime.

建议候选： / Candidates:

1. **推荐 / Recommended:** “Music creation, MIDI editing and real DAW automation for AI agents, with structured plans, observation and verification.”
2. “An open framework connecting music analysis, editable melodies and verifiable AI-agent workflows in real DAWs.”
3. “Create and edit music in Desktop. Build AI agents that plan, act and verify inside real DAWs.”

第一句同时介绍创作、编辑、宿主执行和Agent方法，长度适合GitHub描述。Website目前为空，可继续保留，主要下载入口使用官方Releases。

The recommended sentence covers creation, editing, host execution and the agent method within GitHub's description limit. Website is currently empty and can remain so; use official Releases for downloads.

## Topics

当前：`ai-agent`, `ai-agents`, `ai-music`, `audio-to-midi`, `automation`, `daw`, `experimental`, `mcp`, `midi`, `music-analysis`, `music-production`, `python`。

建议保留已有主题，增加 `fl-studio`、`music-creation`、`electron`。依据分别为当前FL适配、Desktop创作工作流与公开Desktop标签中的Electron源码。避免把产品愿景作为已实现主题。

Keep existing topics and consider `fl-studio`, `music-creation` and `electron`, reflecting the adapter, creator workflow and public Desktop source. Do not use aspirations as implemented-feature topics.

## Social Preview：现状与排版 / State and layout

2026-10-15 GitHub返回 `usesCustomOpenGraphImage=false`，使用生成式仓库卡片。[已有PNG](media/social-preview.png)在仓库中，尚不能据此声称设置已上传。

GitHub reported `usesCustomOpenGraphImage=false` on that date, using a generated repository card. The existing PNG is a repository asset rather than evidence of an uploaded custom setting.

建议保留黑白背景与青色圆环Logo，制作或选用1280×640卡片：DAWLoop作主标题；下方以“Music Intelligence · AI Music Creation”为第一行，“Verifiable DAW Automation”为第二行；保持大字号与留白，版权署名置于角落。缩小后应先读到名称和三个方向，不放版本、内部状态或无依据排名。

Keep the monochrome background and cyan ring logo in a 1280×640 card: DAWLoop as the title, followed by “Music Intelligence · AI Music Creation” and “Verifiable DAW Automation.” Use large text and space, with a small copyright credit. Avoid version numbers, internal states and unsupported rankings.

## 维护者操作清单 / Owner checklist

- 审阅About候选和新增Topics，再修改Settings。 / Review description and topic candidates before applying settings.
- 按 [媒体许可](media/README.md) 审阅卡片，上传后重新核对实际社交预览。 / Review media terms and verify the actual card after upload.
- 审阅 [Alpha.2 Release文案建议](RELEASE_COPY_v0.5.6-alpha.2_PROPOSAL.md)，另行批准后才修改已发布正文。 / Review the separate release proposal before approving a published-copy change.
- 保持资产、标签、哈希、原始证据与通知审批独立。 / Keep assets, tags, hashes, evidence and notification approvals independent.

[公开写作规范](PUBLIC_CONTENT_STYLE.md) · [媒体与来源](media/README.md)
