<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2026 ryurikoneko -->
# 许可范围与来源发布

[KNOWN｜HIGH] 根 `LICENSE` 保持原 MIT 和 `ryurikoneko` 版权行。MIT 允许商业使用、出售和闭源派生，要求保留版权与许可通知；本项目没有添加禁止转售、强制联网、不可删除水印、强制 UI 署名等额外条件。[MIT 正文](https://opensource.org/license/mit)。

## 当前范围

| 内容 | 当前许可/处理 |
| --- | --- |
| 项目自有 src、可执行 research/scripts、测试与示例 | MIT；已有来源声明保留 |
| Learning 协议、Schema、Prompt、教程、合成资料 | MIT；可以被其他用户 Agent 复用 |
| 现有项目自有研究文档与证据 | 保留原已授予许可，本轮不批量重许可 |
| third_party 与改编代码 | 各自已有许可，见 THIRD_PARTY_NOTICES 与 PROVENANCE |
| 用户私人素材/profile | 不进入发布包；本项目不代替用户决定素材权利 |
| FLaiK 中的官方 HTML/图片 | 不打包、不代授许可，见 learning/WORKFLOW |

[KNOWN｜HIGH] 新增 NOTICE 和 CITATION 不引入超出 MIT 的强制引用义务。SPDX 头使用实际已记录的版权主体；不覆盖第三方作者，也不往 FL 控制器要求的设备头之前插入文本。

## 新研究资料的非商业许可：逐项启用

[INFERRED｜HIGH] CC BY-NC 4.0 可以用于未来新创作、权属已确认的报告文字或图表，允许署名的非商业分享与改编；不用于软件代码。它不禁止别人独立实现思想，也不追溯撤销既有 MIT 授权。NC 不是禁止所有收费活动的简单价格规则，具体用途按许可定义判断。[许可正文](https://creativecommons.org/licenses/by-nc/4.0/legalcode)、[官方 FAQ](https://creativecommons.org/faq/)。

[KNOWN｜HIGH] 本轮没有明确资产被重新许可为 CC BY-NC，`LICENSES/CC-BY-NC-4.0.txt` 只保存待选许可原文，不自动覆盖任何路径。正式启用前必须逐文件完成：

1. 确认新报告/图表作者及权利，区分引述、数据事实、第三方图片和代码片段。
2. 核查先前公开版本许可；旧许可仍能被依原条件使用，不能靠移动目录撤销。
3. 在该资产明确标注作者、许可、原文链接和适用部分；代码片段保留适合的软件许可。
4. 更新此处的精确资产清单、发行元数据和 README，不能笼统宣称整仓库只有 MIT。
5. 分别提供完整许可和商业授权入口；不发明未签署的协议或已存在的商标注册。

当前单独许可资产清单：**空**。这一步待具体的新资产和权属清单确定后启用。

## 版本来源和签名

[KNOWN｜HIGH] `dawloop provenance` 对显式指定的源码仓库根目录生成公开允许列表的字节摘要；默认是开发快照。工作树有修改时明确记录 `worktree_dirty=true`，Git commit 不能代表这些未提交字节。清单不包含私人素材、文件正文、机器用户名或个人绝对路径。它只验证所列内容，不能证明作者身份，也不能阻止别人修改代码后重新生成自己的清单。当前还不是脱离源码仓库后自动证明安装包来源的入口；release清单嵌入与实际artifact绑定由后续发布流水线补齐。

```powershell
dawloop provenance --root . --write-manifest ../dawloop-development-provenance.json
dawloop provenance --root . --manifest ../dawloop-development-provenance.json
```

[KNOWN｜HIGH] 写清单采用排他创建，不覆盖旧文件。`research_manifest_hash` 目前覆盖清单中的公开docs与evidence/public摘要及关闭路线记录；它不是全部历史研究资产存档。完整发布时另登记要发布的脱敏证据与 artifact SHA-256。

[INFERRED｜HIGH] 正式发布顺序：确认贡献来源与许可 → 清理私人信息 → 测试/构建 → 提交 → 签名 tag → 在固定 CI 工作流构建 → 签名/attest 实际 wheel、源码包和清单 → 发布 → 校验 → 可选存档 DOI。可信签名要求读者独立核对维护者公钥/身份；“摘要一致”不能升级成“官方版本”。

```powershell
git tag -s vX.Y.Z -m "DAWLoop vX.Y.Z"
git verify-tag vX.Y.Z
dawloop provenance --root . --release-tag vX.Y.Z --write-manifest ../dawloop-release-provenance.json
```

[KNOWN｜HIGH] 以上是发布操作范式，`vX.Y.Z` 是占位符；本alpha预览不具备维护者身份签名；没有创建签名密钥或DOI。CLI 对 release 要求工作树干净、tag 指向 HEAD 且本地 `git verify-tag` 成功。它仍不认证最终安装包或公钥信任。GitHub 的签名提交验证与 artifact attestations 是不同层；正式 CI 策略、公钥和实际 artifact attestation 尚未建立。[签名验证](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)、[构建证明](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)。

[KNOWN｜HIGH] CITATION.cff 当前只记录已确认的项目与维护者，没有虚构 DOI 或发布日期。未来通过维护者授权接入 Zenodo 并存档真实 release 后再填对应 DOI。[引用文件](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)、[Zenodo 发布存档](https://help.zenodo.org/docs/github/)。

## 面对来源争议

[INFERRED｜HIGH] 保留原始 Git 历史、签名/发布记录、内容清单、明确许可及涉嫌违规副本的证据；分别核对通知被移除、报告复制、虚假背书与合法商业 fork。不要把功能相似自动当侵权，也不要期待加密公开 MIT 源码能阻止重构建。投诉只引用真实、可核对的事实，不能仅凭内部水印推断权属。
