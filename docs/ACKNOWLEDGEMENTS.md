# 致谢与上游项目

## FL Studio MCP

- 项目：[`karl-andres/fl-studio-mcp`](https://github.com/karl-andres/fl-studio-mcp)
- 仓库：<https://github.com/karl-andres/fl-studio-mcp>
- FLSkill 开发期间参考的 commit：[`f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`](https://github.com/karl-andres/fl-studio-mcp/commit/f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0)
- 该 commit 中的许可证：MIT，见[上游 LICENSE](https://github.com/karl-andres/fl-studio-mcp/blob/f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0/LICENSE)。
- 与 FLSkill 的关系：早期实际实验中使用并参考过的 FL Studio 控制路径，也是我们理解 MCP 驱动 DAW 自动化的重要实践来源。

该版本上游 README 描述了传输控制、Mixer 音量和声像及静音/独奏、Channel 控制与 Mixer 路由、Piano Roll 音符写入和读回，以及已加载插件参数的查询与设置。上游同时说明不能加载新插件或程序化创建 Pattern。这些能力描述来自上游文档，不是 FLSkill 的实现或验证声明。

FLSkill 不打算取代 FL Studio MCP。上游项目提供 FL Studio 控制路径；FLSkill 致力于在控制执行之外提供确定性音乐时值、Note Plan、写入/读回分离、Exact-Set Verification、状态验证与可恢复编排。FL Studio MCP 是未来的可选 adapter，不是 Core 的强制依赖。

当前公开 FLSkill Core 未 vendoring 或捆绑 FL Studio MCP 源码。未来如直接改编上游代码，将单独标记来源并保留适用的上游 attribution 与 MIT 许可声明。

> FL Studio MCP helped prove that FL Studio could be controlled programmatically; FLSkill is trying to make those operations verifiable.
