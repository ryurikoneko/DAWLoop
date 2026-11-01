# 公开内容改造清单 / Public content audit

基线main `345e6d43d39031a53541b73b5bed728f8be966dd`，2026-10-14。扫描 55 份公开Markdown/YAML及声明文件，内部证据前缀共 192 处，其中重点产品/技术介绍页面 57 处。标签计数仅用于内容审计；证据、法律和来源记录保持原样。

Reviewed 55 public documents against the main baseline. The inventory separates product copy from user instructions, immutable evidence and source/legal records.

## 主要问题与处理 / Findings and treatment

| 问题 / Finding | 处理 / Treatment |
| --- | --- |
| 产品功能旁反复放置验收标签、SHA与失败状态 | 产品页改写，技术摘要归档并清理内部标记 |
| 新公开Desktop与旧内部候选叙述混在一起 | 以v0.5.6-alpha.1真实发行与tag源码为当前范围 |
| Quickstart以测试套件开场 | 改为安装和合成示例，回归入口保留 |
| About/模板仍包含内部预览或偏工程口吻 | 准备About建议，模板明确Desktop Alpha来源 |
| Release与包内指南先讲验收和构建 | 准备修订稿；不改发布记录或重新打包 |
| 后端接口、自有Controller、现场验证混用 | 能力页按三层说明，原证据入口保持 |

## 信息架构 / Information architecture

之前：功能介绍夹杂逐项限制 → 技术范围 → 重复安装/版本风险 → 贡献。

现在：用户价值 → 产品预览 → 可完成的任务 → Brain/Hands/Ears与反馈循环 → 下载/Runtime → 用户与开发者 → 产品方向 → 一个版本说明 → 署名。

Technical source: [Capabilities](CAPABILITIES.md), [Desktop](DESKTOP.md), [Architecture](ARCHITECTURE.md), [FL Studio backend](FL_STUDIO_MCP.md), [Production Pipeline](PRODUCTION_PIPELINE.md), and [original records](archive/public-presentation-20261014/README.md).

## 来源与保护 / Provenance and preservation

产品页、写作规范、研究摘要和审阅文档属于CONFIRMED_PROJECT_GENERATED；竞争资料使用自行总结及原项目链接，不复制实现。历史文本归档已清理内部判断标签，原始文档与清理后文本的摘要分别记录在archive manifest。第三方源码仍THIRD_PARTY，Production改编仍ADAPTED_FROM_THIRD_PARTY；许可证正文、媒体来源与法律授权范围不变。来源与品牌文档只清理表述，不改变署名、权属状态或验证结果。

Existing source classifications and licenses remain unchanged. Historical text archives have separate source and cleaned-text hashes. Removing internal annotations does not change attribution, ownership status or verification results.

## 完整目录 / Inventory

| 文件 / File | 读者 / Audience | 操作 / Action | 原标签数 |
| --- | --- | --- | --- |
| [.github/ISSUE_TEMPLATE/bug_report.yml](../.github/ISSUE_TEMPLATE/bug_report.yml) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 0 |
| [.github/ISSUE_TEMPLATE/feature_request.yml](../.github/ISSUE_TEMPLATE/feature_request.yml) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 0 |
| [.github/ISSUE_TEMPLATE/live_verification_report.yml](../.github/ISSUE_TEMPLATE/live_verification_report.yml) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 0 |
| [.github/dependabot.yml](../.github/dependabot.yml) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [.github/pull_request_template.md](../.github/pull_request_template.md) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 0 |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [.github/workflows/release.yml](../.github/workflows/release.yml) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [AGENTS.md](../AGENTS.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 8 |
| [AUTHORS](../AUTHORS) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 0 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 2 |
| [LICENSE](../LICENSE) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 0 |
| [LICENSE_POLICY.md](../LICENSE_POLICY.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 15 |
| [NOTICE](../NOTICE) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 0 |
| [PROVENANCE.md](../PROVENANCE.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 8 |
| [README.en.md](../README.en.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 0 |
| [README.md](../README.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 0 |
| [SECURITY.md](../SECURITY.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 2 |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 4 |
| [TRADEMARKS.md](../TRADEMARKS.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 10 |
| [adapters/README.md](../adapters/README.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [docs/ACKNOWLEDGEMENTS.md](../docs/ACKNOWLEDGEMENTS.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 2 |
| [docs/CAPABILITIES.md](../docs/CAPABILITIES.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 6 |
| [docs/DAWLOOP_RUNTIME_V2.md](../docs/DAWLOOP_RUNTIME_V2.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 37 |
| [docs/DEMOS.md](../docs/DEMOS.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 8 |
| [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 2 |
| [docs/DESKTOP.md](../docs/DESKTOP.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 20 |
| [docs/FL_STUDIO_MCP.md](../docs/FL_STUDIO_MCP.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 0 |
| [docs/FL_STUDIO_SETUP.md](../docs/FL_STUDIO_SETUP.md) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 0 |
| [docs/GITHUB_SHOWCASE.md](../docs/GITHUB_SHOWCASE.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 7 |
| [docs/PRODUCTION_PIPELINE.md](../docs/PRODUCTION_PIPELINE.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 0 |
| [docs/PRODUCTION_PIPELINE_PROVENANCE.md](../docs/PRODUCTION_PIPELINE_PROVENANCE.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 0 |
| [docs/QUICKSTART.md](../docs/QUICKSTART.md) | 用户与贡献入口 / User and contributor | 优化导言和范围 / Refine introduction and scope | 2 |
| [docs/RELEASE_NOTES_NEXT.md](../docs/RELEASE_NOTES_NEXT.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [docs/RELEASE_NOTES_v0.1.0-alpha.md](../docs/RELEASE_NOTES_v0.1.0-alpha.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [docs/RELEASE_NOTES_v0.2.0-alpha.1.md](../docs/RELEASE_NOTES_v0.2.0-alpha.1.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 11 |
| [docs/RELEASING.md](../docs/RELEASING.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 1 |
| [docs/ROADMAP.md](../docs/ROADMAP.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 2 |
| [docs/RUNTIME_GUIDE.en.md](../docs/RUNTIME_GUIDE.en.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 2 |
| [docs/RUNTIME_GUIDE.zh.md](../docs/RUNTIME_GUIDE.zh.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 2 |
| [docs/VERIFICATION.md](../docs/VERIFICATION.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 2 |
| [docs/brand/CHARACTER_POLICY.md](../docs/brand/CHARACTER_POLICY.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 7 |
| [docs/brand/HISTORICAL_LICENSE_REVIEW.md](../docs/brand/HISTORICAL_LICENSE_REVIEW.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 4 |
| [docs/brand/README.md](../docs/brand/README.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 6 |
| [docs/brand/REGISTRATION_READINESS.md](../docs/brand/REGISTRATION_READINESS.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 4 |
| [docs/media/README.md](../docs/media/README.md) | 产品与技术介绍 / Product and architecture | 重写或精简 / Rewrite or refine | 12 |
| [evidence/public/README.md](../evidence/public/README.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 3 |
| [learning/WORKFLOW.md](../learning/WORKFLOW.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [learning/prompts/analyze_reference.md](../learning/prompts/analyze_reference.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [learning/prompts/compare_references.md](../learning/prompts/compare_references.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [learning/prompts/derive_profile.md](../learning/prompts/derive_profile.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [learning/prompts/validate_profile.md](../learning/prompts/validate_profile.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [research/README.md](../research/README.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 3 |
| [tests/live_fl/README.md](../tests/live_fl/README.md) | 开发、技术或历史 / Engineering and history | 保持，产品页链接 / Preserve and link | 0 |
| [third_party/fl-studio-mcp/README.md](../third_party/fl-studio-mcp/README.md) | 原始证据、法律或来源 / Evidence, legal, provenance | 保持原样 / Preserve | 0 |
