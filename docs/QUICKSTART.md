# Quickstart — Runtime 开发入口 / Developer Runtime

从合成素材开始，体验音乐特征、profile与计划的连接。音乐创作者可先 [下载Desktop Alpha](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1)；本页用于Python开发者，不启动FL Studio。

Start with synthetic material to explore features, profiles and musical plans. For the creator workspace, use the Desktop Alpha; this page is the Python developer route.

## 1. 安装并运行一个例子 / Install and run

Python3.11+，Windows PowerShell：

```powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning]"
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

Linux/macOS在clone并进入目录后：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[learning]"
.venv/bin/python learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

例子生成分析、报告、profile和16-note音乐计划JSON。输出目录必须尚不存在；重复运行用新的目录，避免覆盖已有资料。 / The example produces analysis, reports, profiles and a 16-note plan. Use a fresh output directory on each run.

[学习流程](../learning/WORKFLOW.md) · [部署与依赖](DEPLOYMENT.md) · [FL设置](FL_STUDIO_SETUP.md)

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

## 开发回归 / Developer regression

测试依赖与源码完整检查见 [部署指南](DEPLOYMENT.md) 和 [贡献指南](../CONTRIBUTING.md)。历史v0.1.0-alpha使用当时名称FLSkill，标签与发行保持原样。
