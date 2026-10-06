# 部署与操作合同

本版提供可安装的 Python 包与离线学习框架，以及有受限现场证据的 Native FAST 实现。MCP live 路径暂停，普通作品工程持续写入尚未认证。包安装成功不表示可以立即写当前作品。

## A. 离线部署：无需 FL Studio

```powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning,production]"
.\.venv\Scripts\dawloop.exe --help
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

Python 3.11+；Linux/macOS 可使用 `.venv/bin/python` 跑离线合同。Native FL 现场验收发生在 Windows，其他宿主平台兼容性未建立。重复运行例子须使用新目录，禁止覆盖已有分析/profile。

可选依赖按用途安装：`learning`（Schema）、`production`（numpy）、`flstudio`（MIDI/Community）、`native`（CDP/WebSocket）、`mcp`（stdio）。完整源码回归另需以下测试工具，部分 Win32 测试需 Windows 与 `pywin32`，桥接测试需 Node.js；跳过项不能算通过。

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[learning,native,mcp,flstudio,production]"
.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio Pillow build
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m build
```

`research/`、`scripts/`、完整教程与研究集成属于源码 checkout。wheel 包含运行时、学习 Schema 与受审固定资源，不包含私人 fixture 或浏览器观察服务；仅安装 wheel 不能启用 `research.fast_mcp_live`。

## B. Controller：一次性安装与明确配置

取得 FL 当前活动 **Settings** 目录，不假设维护者路径，不混用多个配置根。

```powershell
.\.venv\Scripts\dawloop.exe setup-fl --settings-dir "<active FL Settings directory>" --dry-run
.\.venv\Scripts\dawloop.exe setup-fl --settings-dir "<active FL Settings directory>"
.\.venv\Scripts\dawloop.exe doctor --settings-dir "<active FL Settings directory>"
```

占位符换成真实路径。安装器备份已有托管 Controller，未知文件拒绝覆盖；不改变工程。loopMIDI 创建 `DAWLoop MCP IN` / `DAWLoop MCP OUT`，先启动 loopMIDI 再打开 FL，在 MIDI 设置给输入选 **DAWLoop Controller**。[详细配置与故障码](FL_STUDIO_SETUP.md)。

`doctor --probe-fl` 只读生命周期记录，不发送身份 RPC。现场必须由运行中的 Controller 返回并核对 `controller_build_id / controller_session_id / project_generation`；磁盘 SHA 不代替加载版本。project_title 可空，仅为描述字段。

## C. Native FAST：受限研究接入

初始化 Gopher WebView 后，研究桥接从本机 CDP 发现唯一 Gopher 页面并核对 catalog/host generation；端口开放不等于可写。普通启动未必开放端点。

已获授权的 disposable 实验可使用既有临时启动模式。参数只传给该次子进程，不写永久环境或快捷方式；下例不是自动执行指令：

```python
import os
import subprocess

env = dict(os.environ,
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=9222")
subprocess.Popen([fl_executable, disposable_flp], env=env)
```

手动打开一次 Gopher，保留人工 Preview/Accept。结束时不保存退出、核验 fixture size/SHA-256、确认宿主/端口关闭并恢复 callback/观察者。不关闭未知作品会话，不绕过 fixture/build 守卫。每 run 建桥/关桥，连接复用尚未认证。

### FAST 输入

```text
target = {
  pattern_index, pattern_name,
  channel_global_index, expected_channel_name
}
musical_plan = {
  ppq_context: {ppq: 96, time_unit: "ticks", velocity_unit: "normalized_0_1"},
  notes: [{pitch, start, length, velocity}, ...]   # 当前恰好16个
}
policy = {add_only: true, max_notes: 16, retry: 0, fallback_after_dispatch: 0}
```

全计划先校验再导航，整数 tick、规范化 velocity，无源码参数。学习 MusicalPlan 使用 MIDI velocity 1–127，含解释结构，不能原样送 FAST；需要明确转换与独立验收，不能仅除以 127 就宣称新增现场认证。

高层现场范围仍是固定 Kick 句；已有 Kick/Clap 导航证据不泛化到任意目标/计划。原基线 FLP 未公开；历史脚本保留期望 build/catalog/fixture，是研究档案而非下载后裸运行 Quickstart。研究启动器必须显式设置当前进程的 `DAWLOOP_FL_EXECUTABLE` 与必要的 `DAWLOOP_CONTROLLER_SETTINGS`，没有维护者机器路径默认值；这仍不解除其他守卫。

### FAST 结果

| 状态/字段 | 意义 |
| --- | --- |
| `READY_FOR_HUMAN_ACCEPT` | 阶段事件，等待用户审阅与一次接受 |
| `STOPPED_BEFORE_DISPATCH` | 未派发；导航可能已改变界面，不能默认安全重试 |
| `STOPPED_AFTER_DISPATCH_UNKNOWN` | 派发后未知；禁止重试或 fallback |
| `COMPLETED_UNVERIFIED` | 人工回报、应用观察与完成回调满足 FAST 合同 |
| `producer_target_binding / exact_set = NOT_VERIFIED` | 验证等级保持 |

人工报告 **persisted ≠ claimed**；协调器实际领取才记 REALTIME。晚到报告不改写原终态。Agent 点击不冒充 HUMAN，报告工具不会点击 Accept。

## D. MCP stdio：接口可启动，live 仍暂停

```powershell
.\.venv\Scripts\dawloop-mcp.exe --settings-dir "<absolute active Settings directory>" --expected-build "<approved runtime build id>" --data-dir "<absolute private run directory>"
```

MCP 客户端以 stdio 子进程启动该命令并保持 stdin/stdout；不要当 HTTP 服务或把调试输出写 stdout。未提供 live factory 的此模式必须 NOT_READY，不派发音符。配置模板填完之前不能运行。

`--live-config` + `--repository` 仅用于已受审源码集成：真实 pid/hwnd、fixture hash/size、Controller session/project、endpoint、observer 目录及显式授权均必需。不能从窗口标题/猜 URL 填身份；观察入口缺失时不能 FAST_READY。

| 工具 | 合同 |
| --- | --- |
| `fast_write_music(operation_id, target, musical_plan)` | 创建后台 run 返回 run/session；相同 operation 不增加派发 |
| `status(run_id=None)` | 组合 readiness，或指定 run 的阶段、终态、证据 |
| `submit_human_report(report)` | 唯一 run/session/report 关联，持久化不等于领取 |

观察端自动采样、hash、generation、时间区间与运输；内容由既有 Agent 视觉审阅回执确认。截图存在不等于目标正确或音符已应用。浏览器真实 page identity 当前不可稳定取得，不能用焦点、坐标或标题替代。

## 故障与反馈

READY 须同时满足 Controller、Gopher、observer、预算且无未解决派发，否则给 reasons 并停。不自动放宽 55s handoff、60s callback/state-age、65s human-event 等既有期限。

反馈仅包含版本/commit、匿名环境、失败阶段、动作计数、脱敏错误码；不上传 FLP、商业 samples、个人 workspace、token、原始截图/数据库。见 [SECURITY](../SECURITY.md)。
