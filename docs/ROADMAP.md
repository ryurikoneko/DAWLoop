# 路线图

以下是计划阶段，不代表已实现或已验证。只有真实适配器在 FL Studio 中写入、读回并完成 Exact-Set 验证后，相关能力才可标为现场 Verified。

| 版本阶段 | 目标范围 | 状态 |
|---|---|---|
| `v0.1` Core | Musical Grid、Absolute Tick Resolution、Note Plan、Writer / Reader Protocol、Exact-Set Verification | 核心实现完成；仅离线算法验证 |
| `v0.2` FL Studio Adapter | 最小 FL adapter、目标 Pattern 确认、真实音符写入、实际事件读回、现场验证证据 | 计划中 |
| `v0.3` 多轨扩展 | multi-channel / multi-pattern 目标模型和联合事件验证 | 计划中 |
| `v0.4` SysEx RPC | 根据明确的 FLSkill 协议规格独立实现和测试 SysEx RPC adapter | 计划中；不迁移来源未知的旧实现 |
| `v0.5` Mixer 与插件 | Mixer track、volume、pan、mute/solo、routing、insert slots、plugin discovery 与参数读写/读回验证 | 计划中；没有真实读回证据前不标 Verified |
| 后续 | Computer Use adapters、社区 FL Studio MCP 可选集成、音频分析、section-level composition | 待规格和来源审查 |

版本号是阶段规划，并非已发布 tag。首版目前也没有 FL Studio 集成。
