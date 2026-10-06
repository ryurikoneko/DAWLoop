# DAWLoop — 下一版发布文案草案

本文件供下一次版本审核使用；尚未发布 alpha.2。

## 公开工程化与项目入口

- 跨平台离线 CI：Ubuntu Python 3.11/3.12、Windows Python 3.12、Node 合成观察测试、构建及隔离 wheel 安装。
- Learning Framework 合成教程与 provenance/hash 回归纳入 CI。
- main 候选产物的构建 attestation，以及受可信 SSH 公钥校验约束的签名 tag 发布流程。
- 中文/英文首页、分层架构图、能力状态表与集中说明的 Alpha 范围。
- 完整包元数据与发布验证教程。

## 能力范围

Native FAST 固定 16-note disposable 工作流已有现场证据，采用人工 Accept。MCP live 路径仍暂停；producer binding、Native Exact Set、普通工程连续写入和连接复用没有新增认证。

## 发布审核必填项

正式发布前填入实际版本、main commit、CI URL、可信 tag 签名身份和 artifact attestation 验证结果；不要用计划中的认证代替实际结果。alpha.1 历史 tag、正文与产物保持原样。
