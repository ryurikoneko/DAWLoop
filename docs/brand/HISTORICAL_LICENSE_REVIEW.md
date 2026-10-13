# 历史许可审查 / Historical license review

## 已核对的记录

| 范围 | 事实 | 保留方式 |
| --- | --- | --- |
| 公开软件main基线1a99482 | 根LICENSE为MIT，自有代码与技术文档；第三方原通知另存 | 不修改LICENSE、作者行、代码许可或第三方正文 |
| 本地Desktop功能提交b4de6e7 | Logo PNG/ICO进入apps/desktop/public/brand；该树存在根MIT，无逐图独立声明 | 记录潜在根许可适用问题，PENDING_OWNER_REVIEW；不把目录移动当许可隔离 |
| 本地Showcase提交e5e7e9f | 新docs/media图像及版权保留声明；PNG可能是同源衍生 | 保留该候选历史与声明；不是撤销此前可能已授出的许可 |
| 本轮个人主体决定 | 拟定个人持有，署名ryurikoneko；真实作者/法定身份未核实 | ownerType与titleStatus分开，未知不升级 |
| 未来角色 | 作品未提供，只有管理占位 | 不声明已完成作品或已登记权利 |

[COMPUTED｜HIGH] 检查可用本地Git记录和已存远端引用，公开main基线没有docs/media或apps/desktop/public/brand。未发现已存远端引用包含b4de6e7；这不证明历史上从未公开或私下分发。首次公开时间继续null；根MIT是否已经覆盖某份素材、接收者实际获得哪些授权及原作者是否允许该分发，仍需用户核查分发记录和来源。

[KNOWN｜HIGH] 本地提交不是公开发行证据，缺少明确逐图许可也不是“没有授权”的证明。无损重压缩、文件重命名或衍生图不会自动摆脱已有授权。若原图或同源衍生已经在明确许可下分发，该授权继续保留；新的独立政策只在核清权属、已有许可与未来可授权范围之后启用。

[KNOWN | HIGH] Local commits do not establish publication. Absence of a per-image notice does not establish absence of permission. Re-encoding or moving an asset does not revoke prior grants. Root-MIT coverage and actual earlier distributions remain pending owner review; the later reserved notice is not a retroactive withdrawal.

## 尚待用户核对

- 原始Logo/参考图实际作者、生成或绘制工具及使用条款。
- 人工贡献、委托/授权/转让凭据和第三方参考许可。
- Logo/ICO随内部候选或源码交付时的具体文件与许可通知。
- 是否曾公开到其他分支、平台或向他人分发，及有证据的首次时间。
- 法定权利人私人身份与拟定个人主体是否一致。

[KNOWN｜HIGH] 本轮不删除历史文件、回写旧报告或改第三方许可。软件使用、修改、分发及适用MIT权利按原许可保留；品牌说明只处理来源与身份，不限制独立实现或合法来源说明。[MIT原文](https://opensource.org/license/mit)

[许可范围](../../LICENSE_POLICY.md) · [资产清单](ASSET_REGISTRY.json)
