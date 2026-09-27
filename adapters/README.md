# 适配器范围

核心 `Writer` / `Reader` 最小接口位于 `src/flskill/io/protocol.py`；离线内存实现用于算法测试。当前开发分支另含 `src/flskill/adapters/fl_studio_mcp/`，通过可选 backend 接入随仓库打包的上游 FL Studio MCP。

适配器放在独立模块中，不能把第三方控制实现并入 FLSkill Core。当前 FL Studio 适配器要求外部 Pattern / Channel identity reader，并在 Live 写入、读回和 Exact-Set 通过前返回 `STOP` 或开发状态；不能因 MCP 排队成功报告 `PASS`。新增或更新适配器前须定义目标发现/身份确认方式、真实读回路径、失败语义和可保留的验证证据，并在 `PROVENANCE.md` 登记来源。
