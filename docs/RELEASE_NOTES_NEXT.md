# DAWLoop v1.0.0-alpha.1

**Runtime V2 Architecture Preview**

DAWLoop 的第一代产品架构预览：结构化音乐规划、用户拥有的学习框架与证据化 FL Studio FAST 执行。本版将双语项目入口、跨平台质量门和可验证构建来源接入公开发布流程，继续保留 Alpha 定位。

本文件为待审核发布文案，尚未发布该版本。

## 公开工程化与项目入口

- 跨平台离线 CI：Ubuntu Python 3.11/3.12、Windows Python 3.12、Node 合成观察测试、构建及隔离 wheel 安装。
- Learning Framework 合成教程与 provenance/hash 回归纳入 CI。
- main 候选产物的构建 attestation，以及受已登记维护者 SSH 公钥校验约束的签名 tag 发布流程。
- 中文/英文首页、分层架构图、能力状态表与集中说明的 Alpha 范围。
- 完整包元数据与发布验证教程；包版本统一为 `1.0.0a1`。
- 架构图分开展示已实现的 FAST 结构化输入与待实现的通用 MusicalPlan 转换层。

## 能力范围

Native FAST 固定 16-note disposable 工作流已有现场证据，采用人工 Accept。MCP live 路径仍暂停；producer binding、Native Exact Set、普通工程连续写入和连接复用没有新增认证。

## 发布审核必填项

正式发布前核对实际 main commit、CI URL、可信 tag 签名身份和 artifact attestation 验证结果；不要用计划中的认证代替实际结果。历史 `v0.2.0-alpha.1` 的 tag、正文与产物保持原样。

下一项产品开发为通用 Learning MusicalPlan → 显式 Plan Adapter → FAST 合同的离线转换与验证；本版不新增 FL 现场实验。
