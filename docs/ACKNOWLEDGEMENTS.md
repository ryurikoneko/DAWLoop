# 致谢与上游项目

## FL Studio MCP

- 项目：[`karl-andres/fl-studio-mcp`](https://github.com/karl-andres/fl-studio-mcp)
- 仓库：<https://github.com/karl-andres/fl-studio-mcp>
- FLSkill 开发期间参考的 commit：[`f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`](https://github.com/karl-andres/fl-studio-mcp/commit/f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0)
- 该 commit 中的许可证：MIT，见[上游 LICENSE](https://github.com/karl-andres/fl-studio-mcp/blob/f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0/LICENSE)。
- 与 FLSkill 的关系：早期实际实验中使用并参考过的 FL Studio 控制路径，也是我们理解 MCP 驱动 DAW 自动化的重要实践来源。

该版本上游 README 描述了传输控制、Mixer 音量和声像及静音/独奏、Channel 控制与 Mixer 路由、Piano Roll 音符写入和读回，以及已加载插件参数的查询与设置。上游同时说明不能加载新插件或程序化创建 Pattern。这些能力描述来自上游文档，不是 FLSkill 的实现或验证声明。

FLSkill 不打算取代 FL Studio MCP。上游项目提供 FL Studio 控制路径；FLSkill 致力于在控制执行之外提供确定性音乐时值、Note Plan、写入/读回分离、Exact-Set Verification、状态验证与可恢复编排。当前集成分支将固定上游快照作为可选执行后端随仓库打包；它不是 FLSkill Core 的强制依赖。

FLSkill Core 不依赖 FL Studio MCP。当前集成分支把固定上游快照随仓库打包在 Core 之外，作为 optional backend；未改编或修改其源码。若未来直接改编上游代码，将单独标记来源并保留适用的上游 attribution 与 MIT 许可声明。

> FL Studio MCP helped prove that FL Studio could be controlled programmatically; FLSkill is trying to make those operations verifiable.

## DSH / whale-music-pipeline

感谢 DSH「编曲混音自动化」流程及其 `whale-music-pipeline` 开源代码的开发者。FLSkill 维护者提供了开发者直接授权复用代码的说明；同时，所提供压缩包本身也将 `scripts/` 代码声明为 MIT License。

这套流水线给 FLSkill 带来了非常直接的实践参考：从原始 SMF/MIDI 数据处理，到管弦编排思路，再到 Windows WASAPI 环回测量、活跃帧 RMS、FL Studio 推子实测标定，以及“写完后相信读回而不是相信自己已经写成功”的工作原则。

当前 FLSkill 已将其中适合通用化的部分整理为 `src/flskill/dsh/`：MIDI 结构检查与密集窗口选择、活跃帧 RMS、可配置推子标定与推子计划，以及可选的 Windows loopback capture。它们继续受 FLSkill `Plan → Execute → Read Back → Verify → PASS / STOP` 约束：例如，DSH 标定表可以帮助计算下一次 Mixer 操作，但计算结果本身不等于 FL Studio 中的已验证状态。

DSH 压缩包内还有大量针对具体作品的写谱、管弦改编、SoundFont 渲染和谱面生成脚本。我们已经阅读并用于架构学习，但不会把针对单个委托/作品的决策直接包装成通用 FLSkill Core 规则；通用化前仍需要拆除作品专属数据、补测试并明确验证边界。

许可边界和具体适配文件见 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) 与 [`docs/DSH_PIPELINE.md`](DSH_PIPELINE.md)。
