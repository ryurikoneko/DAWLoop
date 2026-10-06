# 发布、签名与来源验证

## 当前状态

`v0.2.0-alpha.1` 是保留的历史快照，未签名、没有构建 attestation。本轮不移动 tag、不覆盖 Release 或资产。新流程把内容摘要、tag 签名和 CI 构建来源分别验证。

CI 在 Ubuntu Python 3.11/3.12 和 Windows Python 3.12 执行离线回归；Node 观察测试使用合成图像。构建、隔离 wheel 安装、学习教程与来源摘要检查均不启动 FL。Linux 不收集依赖 Win32 启动器的 `test_target_prepare_live_catalog.py`，并明确跳过需要 Win32 API 的三项测试；这些检查由 Windows job 执行。测试 JUnit 报告保留 14 天。

2026-10-07 的 [main CI](https://github.com/ryurikoneko/DAWLoop/actions/runs/37514929489) 与 [候选发布验收](https://github.com/ryurikoneko/DAWLoop/actions/runs/37514976009) 均通过。候选来源 commit 为 `3e0688e2603e166cdeb4dfe123bcf0a08505fd63`，五份产物的 attestation 已按仓库、workflow、ref 和 source digest 验证；下载包与校验和另行核对。这没有创建新版 Release，不等于维护者个人 tag 签名认证。

main 已启用 [质量规则](https://github.com/ryurikoneko/DAWLoop/rules/24603386)：PR、严格 `CI gate`、禁止 force-push 与删除。管理员 bypass 仅限 PR；单人项目不要求自审批准。

## 两个发布入口

- **main 候选构建**：在 Actions 手动运行 `Release provenance`，只允许当前 main。通过同一套 CI 后生成 wheel、sdist、来源清单、SHA256SUMS 与构建 attestation，保存在 Actions artifacts，不发布新 Release。
- **签名 tag 构建**：只接受 `vX.Y.Z-alpha.N`，对应包版本 `X.Y.ZaN`，必须指向当时的 main HEAD。SSH tag 签名必须匹配 main 中明确登记的可信公钥；通过后创建新的 prerelease **draft**，维护者审核后发布。

当前 `.github/release-signers.allowed` 仅含说明，没有可信公钥。正式 tag 构建会拒绝。尚未进行新的签名 tag 发布；不要把流程代码已存在写成发布认证已完成。

## 维护者准备与顺序

1. 使用由维护者控制的 SSH 签名密钥；在安全位置保存私钥，不上传到仓库、聊天或 artifact。
2. 通过 PR 将可信**公钥**登记到 `.github/release-signers.allowed`，格式例如 `maintainer@example.invalid namespaces="git" ssh-ed25519 <public-key>`，实际 principal 与公钥由维护者确认。只需要支持本流程的 SSH 签名；GPG 发布可单独接入，不能混称已支持。
3. 配置本地 Git：`git config gpg.format ssh`、`git config user.signingkey <path-to-signing-key>`。确认 GitHub 账户的 signing key 登记与公开指纹一致。
4. 更新包版本、`src/dawloop/__init__.py`、CITATION 与最终 release notes，经 PR 合并 main，等待 `CI gate` 成功。
5. 在最新 main 上执行 `git tag -s v0.2.0-alpha.2 -m "DAWLoop v0.2.0-alpha.2"`；先用可信公钥表运行 `git verify-tag`，再 push 这个新 tag。
6. Actions 重跑离线检查、验证 main/tag/version/signer，构建并 attest 产物。审核 draft 内容、下载产物并独立验证，再公开发布。

本轮不会代维护者生成签名身份，也不自动升版或创建 alpha.2。独立签名 `SHA256SUMS.txt` 的 maintainer detached signature 尚未接入；当前新流程将其作为 attestation subject，证明的是受信 GitHub 构建身份，不是维护者个人签名。独立签名以后应在安全签名环境完成，另附 `.sig` 与验证说明。

## 使用者验证

下载 wheel 与 `SHA256SUMS.txt` 后，在对应目录运行 `sha256sum -c SHA256SUMS.txt`。Windows 可用 `Get-FileHash -Algorithm SHA256 <file>` 对照。摘要验证下载字节，不证明作者。

新流程产物使用 GitHub CLI 验证构建来源：

```bash
gh attestation verify <wheel-or-SHA256SUMS.txt> \
  --repo ryurikoneko/DAWLoop \
  --signer-workflow ryurikoneko/DAWLoop/.github/workflows/release.yml \
  --source-ref refs/tags/v0.2.0-alpha.2
```

验证候选产物时改为 `--source-ref refs/heads/main`，并核对输出的 source commit 与目标提交。检查 tag 签名时使用维护者公开的可信 SSH 公钥表，不能只相信文件里的作者字符串或未知公钥。

来源清单的 `authenticity = NOT_VERIFIED_BY_THIS_MANIFEST` 是刻意保留的边界；它核对列出的源码内容，与 attestation、签名校验分工不同。构建 attestation 不增加 FL 现场能力认证。

官方资料：[GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)、[CLI 验证选项](https://cli.github.com/manual/gh_attestation_verify)、[SSH 签名设置](https://docs.github.com/en/authentication/managing-commit-signature-verification/telling-git-about-your-signing-key)。
