# 品牌资产管理 / Brand asset governance

用户确认拟定持有主体为**个人**：`ownerType: INDIVIDUAL`。公开署名仍为 `ryurikoneko`，不填写、推断或公开法定姓名。拟定主体与已证明法定权属是不同字段；后者统一 `PENDING_OWNER_REVIEW`。未来成立公司或工作室不会自动转移资产，许可/转让由用户另行决定。

The user selected an individual as the proposed holder. The public signature remains `ryurikoneko`; no legal name is inferred or disclosed. The ownership plan is confirmed, but legal identity and title remain `PENDING_OWNER_REVIEW`. Formation of a company or studio creates no automatic asset transfer.

## 清单与版本

- [品牌资产清单](ASSET_REGISTRY.json)：名称、Logo、Splash/Hero、展示截图和未来美术条目。
- [清单结构](asset-registry.schema.json)：明确的个人主体、未知值、摘要及未登记状态。
- [角色清单](CHARACTER_ASSET_REGISTRY.json)：当前仅占位，无正式角色名、作品或公开版本。
- [历史许可审查](HISTORICAL_LICENSE_REVIEW.md)：保留根MIT背景与后续图像声明，不借新路径撤回旧权利。
- [角色政策](CHARACTER_POLICY.md)：发布图、再利用素材和私人源文件分别管理。
- [登记准备清单](REGISTRATION_READINESS.md)：只准备材料，不代办申请。

清单版本是管理版本，SHA-256仅绑定具体字节或名称文本，不证明创作时间、原创性、作者、权利人或登记成功。`firstPublicAt: null` 表示首次公开时间未建立；本地Git提交时间不自动变成首次公开时间。私人来源只记录逻辑引用与摘要，实际位置保存在非公开验收目录，不复制原图/PSD/未发表设定。

Registry versions and hashes identify records or bytes, not authorship, originality, ownership or registration. Local Git dates are not automatically first-publication dates. Private source references do not disclose their filesystem location or publish source art.

## 更新流程

新作品先登记实际文件与来源 → 区分人工/AI过程和第三方成分 → 核查既有分发许可 → 用户确认作者/权属及拟定许可 → 批准具体公开版本和范围 → 才考虑发布或申请。未知不填NONE/已确认；未创作条目不产生作品权利声明。现有用户许可不因新政策或重新编码失效。

Record actual files and provenance, distinguish human/AI/third-party contributions, check prior grants, obtain owner review and approve an exact public version before considering distribution or registration. Unknown is not none; placeholders do not assert rights in nonexistent works.

[软件许可](../../LICENSE_POLICY.md) · [品牌使用规范](../../TRADEMARKS.md) · [Logo与截图来源](../media/provenance.json)
