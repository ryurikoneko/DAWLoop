# Quickstart

本指南展示当前 `dawloop` 命名空间下的离线核心用法。历史版本 `v0.1.0-alpha` 以当时的项目名 FLSkill 发布，仍是离线核心版本；它的 tag 和 Release 内容保持原样，不包含本次改名后的 `dawloop` 命名空间。

## 1. 运行测试

需要 Python 3.11 或更新版本。

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

完整部署和测试依赖见 [DEPLOYMENT](DEPLOYMENT.md)；测试数量以本次发布记录为准。

## 2. 解析音乐位置

```python
from dawloop.time import MusicalGrid, MusicalPosition, resolve_absolute_tick

grid = MusicalGrid(ppq=480, beats_per_bar=4, beat_unit=4)
position = MusicalPosition(bar=2, beat=1, tick=0)

absolute_tick = resolve_absolute_tick(position, grid)
print(absolute_tick)  # 1920
```

## 3. 创建 Note Plan

```python
from dawloop.note_plan import NoteEvent, NotePlan
from dawloop.time import MusicalGrid

grid = MusicalGrid(ppq=480, beats_per_bar=4, beat_unit=4)
plan = NotePlan(
    target_id="offline-demo",
    grid=grid,
    section_start_tick=0,
    section_bars=2,
    events=(
        NoteEvent(start_tick=0, duration=480, pitch=60, velocity=96),
        NoteEvent(start_tick=480, duration=480, pitch=64, velocity=96),
        NoteEvent(start_tick=960, duration=480, pitch=67, velocity=96),
    ),
)
```

## 4. 写入、读回并验证

当前版本提供内存实现，用于证明验证流程，而不是证明 FL Studio 已被控制。

```python
from dawloop.io import InMemoryEventStore
from dawloop.verification import write_read_verify

store = InMemoryEventStore()
result = write_read_verify(plan, writer=store, reader=store)

print(result.status)  # PASS
print(result.label)   # Offline Algorithm Verified
```

本节离线 VERIFIED 算法的成功条件不是 Writer 返回成功，而是：

```text
Plan
  ↓
Write
  ↓
Read Back
  ↓
Exact-Set Verification
  ↓
PASS / STOP
```

如果实际读回事件出现缺失、多余或字段不一致，结果必须为 `STOP`。

## 5. 示例文件

- [`examples/note_plan.example.json`](../examples/note_plan.example.json)：一个完全自造的 Note Plan 示例，包含重复事件。
- [`examples/verification_result.example.json`](../examples/verification_result.example.json)：一个 `duration` 不一致导致 `STOP` 的诊断示例。

> `Offline Algorithm Verified` 不等于 `FL Studio Verified`。Native FAST 的固定16-note人工接受流程已有受限现场证据；Native producer-side读回与Exact Set未认证，MCP live仍暂停。安装步骤见 [`FL_STUDIO_MCP.md`](FL_STUDIO_MCP.md)。
