# 路线图

以下是计划阶段，不代表已实现或已验证。只有真实适配器在 FL Studio 中写入、读回并完成 Exact-Set 验证后，相关能力才可标为现场 Verified。

| 版本阶段 | 目标范围 | 状态 |
|---|---|---|
| `v0.1` Core | Musical Grid、Absolute Tick Resolution、Note Plan、Writer / Reader Protocol、Exact-Set Verification | 核心实现完成；仅离线算法验证 |
| `v0.2` Bundled FL Studio MCP + Adapter | 固定上游源码打包、可选依赖、安装与 doctor、MCP adapter、目标身份门控、离线集成测试 | 开发中；Live 尚未验证 |
| `v0.3` Live Note Verification | 明确 Pattern / Channel 的真实目标识别、测试音符写入、fresh readback、Exact-Set PASS / STOP 与可复现实验证据 | 计划中 |
| `v0.4` 多轨扩展 | multi-channel / multi-pattern 目标模型和联合事件验证 | 计划中 |
| `v0.5` SysEx RPC | 根据明确的 FLSkill 协议规格独立实现和测试 SysEx RPC adapter | 计划中；不迁移来源未知的旧实现 |
| `v0.6` Mixer 与插件 | Mixer track、volume、pan、mute/solo、routing、insert slots、plugin discovery 与参数读写/读回验证 | 计划中；没有真实读回证据前不标 Verified |
| 后续 | Computer Use adapters、社区 FL Studio MCP 可选集成、音频分析、section-level composition | 待规格和来源审查 |

## Community FL Studio MCP Adapter

**状态：Bundled / Integration in development。** FLSkill 早期实验工作流实际使用并参考过 [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)，参考 commit 为 [`f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`](https://github.com/karl-andres/fl-studio-mcp/commit/f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0)，上游许可证为 MIT。该快照目前已随开发分支打包，adapter foundation 正在开发；Live 写入/读回还未验证。

它作为可选后端，不并入 FLSkill Core；保留上游署名和 MIT 许可要求；把 FLSkill Note Plan / 操作请求映射为 MCP 调用；执行后读取 DAW 实际状态并交给 Exact-Set / 状态验证；区分上游 MCP 调用成功与 FLSkill 验证成功。bundled source 与基础适配已实现，Live FL Studio 写入/读回仍未通过现场验证。

## v1.0.0 稳定版里程碑

`v1.0.0` 的目标是首个可安装且能在真实 FL Studio 完成确定性 NotePlan、目标身份确认、音符写入、真实读回、Exact-Set Verification 与 `PASS` / `STOP` 的稳定版本，并具备稳定安装流程和可复现实验。是否将多轨及基础 Mixer 验证列为发布阻塞条件，待 Live MIDI 路径稳定后决定。

版本号是阶段规划，并非已发布 tag。首版目前也没有 FL Studio 集成。
