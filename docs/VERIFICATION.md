# 验证规则

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
- `FL Studio Verified` 需要真实 FL 目标身份确认、写入后从 FL 重新读回实际事件、Exact-Set 匹配和可审阅证据。当前仓库尚无此能力。
