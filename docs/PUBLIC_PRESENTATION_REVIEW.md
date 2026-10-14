# 公开展示审阅 / Public presentation review

## 当前发行 / Publication

2026-10-14通过GitHub API核对：Desktop `v0.5.6-alpha.1` 是已Publish的Pre-release，Release ID 412318311，提供便携ZIP、对应源码、SHA256SUMS、构建记录、首次运行说明、发行说明及第三方通知。Desktop源码在发行标签；main为Runtime与文档。

The published Desktop Alpha and its assets are verified separately from the Runtime on main. This documentation PR publishes no new software assets.

## 内容核对 / Content checks

功能依据来自公开Release、tag源码、原能力页、Controller实现与原始验证合同。Basic Pitch已有环境与新用户首次安装分别描述；Desktop本地编辑器与真实FL研究分别描述。正文无行业第一或市场性能排名。

Claims are tied to the release, source tag, Controller code and existing verification contracts. Existing transcription environments, first-time setup, local editing and host research are separate scopes.

本地Markdown、链接、命令、YAML及保护文件检查，以及GitHub桌面/窄屏核验结果在本Draft PR的验证说明中提供；没有现场观察的结果保留为未检查。

Local checks and browser desktop/narrow-layout results are reported in the Draft PR. Unobserved outcomes are not counted as passes.

## About 与 Social Preview

当前About已描述Music Intelligence、MIDI editing、DAW automation与Windows Desktop Alpha。新的推荐文本和Topics见 [GITHUB_SHOWCASE.md](GITHUB_SHOWCASE.md)，待维护者确认后应用；此PR不改变仓库设置。

2026-10-14官方GraphQL返回 `usesCustomOpenGraphImage=false`：远端仍使用GitHub自动卡片，现有 `social-preview.png` 尚未设置为自定义图片。文件尺寸1280×640，符合既定极简视觉，本次保留原字节。维护者可在Repository Settings → General → Social preview上传。

GitHub reports no custom social image. The prepared card is unchanged and can be uploaded by the maintainer; its presence in Git is not an upload result.

## Release 与包内指南

已发布便携ZIP本地副本SHA-256与官方资产digest一致：`54129c2bcb446dd96f336837151f58977f83c5ad487fa317ead0ad38bd72683c`。读取ZIP中的三份用户/首次运行指南，没有改写或重新打包。当前两个语言指南使用相同双语综合内容，后续正常版本可分离语言并突出使用流程。[Release与指南修订稿](RELEASE_COPY_PROPOSAL.md) 仅供确认，不修改发布记录。

The existing ZIP and packaged guides remain intact. Release copy and future guide improvements are proposals, not edits to published assets.

## 保护范围 / Preserved material

MIT、第三方许可、品牌权属文档、原始PROVENANCE、媒体provenance及全部不可变证据保持原字节。产品页旧技术段落在 [历史档案](archive/public-presentation-20261014/README.md) 逐字节保存。Runtime/Desktop业务代码、运行时权限、版本/tag和公共通知开关不改。

Legal/source records and immutable evidence retain their bytes. Historical page snapshots are archived, with no code or permission changes.

[内容审计](PUBLIC_CONTENT_AUDIT.md) · [写作规范](PUBLIC_CONTENT_STYLE.md) · [定位研究](POSITIONING_RESEARCH.md)
