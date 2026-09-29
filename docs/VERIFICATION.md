# 验证规则

## 验证级别

- **Unit Tests：** 音乐时间、Note Plan、字段映射、目标身份门控与 Exact-Set 算法。
- **Offline Integration Tests：** 使用自造测试数据和替身验证 Writer / Reader 或 MCP adapter 映射，不启动 FL Studio。
- **Live FL Studio Integration Tests：** 单独人工启动；必须使用专用测试工程和确认过的 Pattern / Channel。普通 `unittest` / `pytest` 不得自动执行 Live 测试。

维护者报告曾在真实 FL Studio 环境完成接入流程，但该次运行的目标身份和实际事件读回没有归档在仓库中。开发用采集器位于 [`tests/live_fl/capture_note_roundtrip.py`](../tests/live_fl/capture_note_roundtrip.py)，它为每次尝试保存独立的机器可读记录；上游 Piano Roll state 不返回 Pattern 身份，仍需外部现场身份读取器。运行步骤与安全门控见 [`tests/live_fl/README.md`](../tests/live_fl/README.md)。采集器的实现不等于已经归档现场 PASS。

只有真实 FL Studio 写入后获得新鲜读回，且目标身份、PPQ、planned / actual Exact-Set 全部一致，才能将现场结果标为 `Live FL Studio Verified`。依赖安装、MCP 命令排队或连接状态不能单独构成 PASS。

## 离线执行

```text
validated plan → Writer.write → Reader.read → exact-set compare → PASS / STOP
```

写入错误后仍尝试读取，以便暴露可能的部分写入；写入或读回发生异常时结果均为 STOP。Writer 的返回值不会影响判断。

## Exact-Set

验证器以 `(start_tick, duration, pitch, velocity)` 作为事件键并按出现次数比较，故重复音符不会被集合去重。精确差异给出 `missing` 和 `extra`；剩余事件另提供差异诊断字段 `start_tick`、`duration`、`pitch`、`velocity`。诊断配对不改变 exact-set 结果：只有实际读回多重集合与计划完全相同，内容比较才通过。

完整离线执行只有同时满足以下条件才返回 `PASS`：

- 写入调用未抛出异常；
- 读回调用成功；
- 实际事件和计划事件的多重集合完全一致。

否则返回 `STOP`。空事件计划也必须成功写入并从该目标读回空事件后才可通过；不存在的读回目标会报错，不会默认视为空内容。

## 状态用语

- `PASS` 的离线执行结果标记为 **Offline Algorithm Verified**。
- 该标记只验证算法、内存读写闭环和给定事件数据，不表示 FL Studio 或其他宿主已写入。
- `Live FL Studio Verified` 需要真实 FL 目标身份确认、写入后从 FL 重新读回实际事件、Exact-Set 匹配和可审阅证据。仓库未归档这组证据，因此不对该次维护者报告升级为可复核的 `Verified` 声明。
