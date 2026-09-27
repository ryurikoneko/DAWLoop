# 架构

本阶段只实现与具体宿主无关的音乐时间、Note Plan、写入/读回接口和事件验证。核心没有 FL Studio、MCP、Computer Use、SysEx 或音频库依赖。

```text
Musical Grid → Absolute Tick → Note Plan
                                  ↓
                         Writer / Reader
                                  ↓
                     Exact-Set Verification
                                  ↓
                              PASS / STOP
```

## 时间模型

`MusicalGrid` 保存 PPQ、每小节拍数和拍单位。位置使用从 1 开始的小节与拍，加上从该拍起点开始的 tick 偏移。PPQ 表示四分音符的 tick 数；每拍 tick 数由拍单位确定。网格会拒绝不能被拍单位整除的 PPQ，避免产生隐式舍入。

解析公式：

```text
absolute_tick = section_start_tick
              + (bar - 1) * ticks_per_bar
              + (beat - 1) * ticks_per_beat
              + tick
```

所有位置和时长均为整数 tick，不使用浮点时间换算。当前 `NotePlan` 有明确的段落起点和小节长度；事件必须完整落在该段落范围内。

## Note Plan

计划包含版本、目标标识、网格、段落起点、小节数和事件列表。每个事件包含绝对 `start_tick`、正整数 `duration`、MIDI `pitch`（0–127）及 MIDI `velocity`（1–127）。重复事件允许存在，因为 exact-set 比较采用多重集合语义。

JSON Schema 用于结构验证；Python 模型还验证跨字段约束，例如事件是否位于段落范围内。Schema 和运行时验证各自明确，不把单纯 JSON 结构有效误认为目标现场有效。

## 写入和读回边界

`Writer` 只负责将计划事件写到指定目标；`Reader` 负责从同一目标读取实际事件。Writer 返回或不抛错都不是成功证据。执行流程必须调用 Reader，再比较实际内容。当前内存实现只服务离线测试，不能证明任何宿主软件中的写入。

## 执行适配器

`adapters/` 当前只有范围说明，没有真实适配器。之后可分别增加 FL Studio、Computer Use、MCP 或 SysEx 实现；适配器不得成为核心算法的硬依赖。每个现场适配器须独立证明目标身份、写入后的实际读回路径和可保存的证据，然后才能支持现场 Verified 声明。

## 执行适配器模型

FLSkill Core 不绑定单一控制路径。未来可选的执行适配器包括：

1. Native Computer Use
2. Community FL Studio MCP
3. FLSkill SysEx RPC
4. 兼容 Computer Use bridge
5. 未来的 DAW adapters

适配器接收已验证的 Note Plan 或操作计划，确认真实目标，执行写入或操作，从 DAW 读回实际状态，并把读回证据交给 FLSkill 验证层。适配器返回“执行成功”不能直接变成 FLSkill `PASS`：

```text
Write → Read Back → Verify → PASS / STOP
```

社区 FL Studio MCP 是 FLSkill 早期实际使用和参考过的控制路径。它负责提供 FL Studio 控制能力；FLSkill 的核心工作是把规划、执行、读回、验证和恢复续作组织起来。两者互补，MCP 是未来的可选 adapter，而非 Core 依赖。上游项目、指定 commit、许可证和能力边界见 [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md)。

当前 `v0.1.0-alpha` 只有离线 Core。Native Computer Use、Community FL Studio MCP adapter、SysEx RPC adapter、兼容 bridge 和现场 DAW 读回尚未实现；Mixer 与插件控制也仍在 Roadmap。
