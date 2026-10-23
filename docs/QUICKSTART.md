# Quickstart — Runtime 开发入口 / Developer Runtime

从合成素材开始，体验音乐特征、profile与计划的连接。音乐创作者可先 [下载Desktop Alpha](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.2)；本页用于Python开发者，不启动FL Studio。

Start with synthetic material to explore features, profiles and musical plans. For the creator workspace, use the Desktop Alpha; this page is the Python developer route.

需要宿主内的参考、生成与试听工作区，请看独立闭源 [Plugin 预览](PLUGINS.md)；它不随 `pip install dawloop` 安装，当前也没有公开 Plugin 下载。

For reference-based creation inside the host, see the separate proprietary Plugin preview. It is not installed by `pip install dawloop` and currently has no public download.

## 1. 安装并运行一个例子 / Install and run

虚拟环境将开发依赖与系统Python分开；learning extra提供例子需要的Schema校验。使用虚拟环境解释器的完整相对路径，可以避免终端尚未激活环境时调用到另一份安装。

The virtual environment separates dependencies from system Python. The learning extra supplies schema validation; invoking the environment's interpreter directly avoids accidentally using another installation.

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

音乐计划需要让“小节、拍、tick”与明确的工程网格对应。本例的PPQ只用于合成演示；真实宿主必须读取自己的时间基准。第二小节起点应输出1920。

A plan maps bars, beats and ticks to an explicit grid. This PPQ belongs to the synthetic example; a real host must supply its own timebase. The start of bar two prints 1920.

```python
from dawloop.time import MusicalGrid, MusicalPosition, resolve_absolute_tick

grid = MusicalGrid(ppq=480, beats_per_bar=4, beat_unit=4)
position = MusicalPosition(bar=2, beat=1, tick=0)

absolute_tick = resolve_absolute_tick(position, grid)
print(absolute_tick)  # 1920
```

## 3. 创建 Note Plan

计划把目标、允许范围与预期音符放在一起，方便执行前校验。这段两小节范围中的三个音符分别从第0、480和960 tick开始；它还没有向任何DAW发送请求。

The plan combines a target, allowed bounds and expected notes for validation. These three notes start at ticks 0, 480 and 960 within a two-bar section; constructing it sends no DAW request.

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

下面将同一个计划写入内存存储，再通过Reader取得实际事件，与计划比较。你可以先理解PASS/STOP，再为自己的后端实现相同的读写接口。

Write the plan to an in-memory store, obtain actual events through the reader and compare them. This introduces PASS/STOP before implementing the same writer/reader boundary for a host backend.

```python
from dawloop.io import InMemoryEventStore
from dawloop.verification import write_read_verify

store = InMemoryEventStore()
result = write_read_verify(plan, writer=store, reader=store)

print(result.status)  # PASS
print(result.label)   # Offline Algorithm Verified
```

本例的PASS由读回比较产生，预期输出为上述PASS与标签。完整过程为： / PASS comes from comparing the readback, with the expected output shown above:

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

接下来可以 [分析MIDI或音频](PRODUCTION_PIPELINE.md)、[理解真实FL执行路径](FL_STUDIO_MCP.md)，或 [配置Controller](FL_STUDIO_SETUP.md)。本页的PASS只对应内存例子；真实宿主的目标检查、授权和读回按对应合同执行。

Next, analyze MIDI/audio, study the FL execution paths or configure the Controller through those guides. This page's PASS covers the in-memory example; host target checks, authorization and readback follow their own contracts.

## 开发回归 / Developer regression

测试依赖与源码完整检查见 [部署指南](DEPLOYMENT.md) 和 [贡献指南](../CONTRIBUTING.md)。历史v0.1.0-alpha使用当时名称FLSkill，标签与发行保持原样。
