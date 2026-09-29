# Community FL Studio MCP 集成

## 当前状态

目标版本为 `v0.2.0-alpha`。固定 commit 的 Community FL Studio MCP 源码随仓库放在 `third_party/fl-studio-mcp/`；DAWLoop 的 optional Python extra 与适配器已建立。维护者报告已完成真实 FL Studio 接入流程；该路径可能仍不稳定，欢迎用户实测并反馈环境兼容性问题。仓库没有归档该次运行的目标身份与实际 note readback 证据，因此不标记为可复现的 `Live Exact-Set Verified`。

上游快照：`karl-andres/fl-studio-mcp`，commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`，MIT。其依赖范围取自该 commit 的 `pyproject.toml`：FastMCP `>=2.0`、Mido `>=1.3.0`、python-rtmidi `>=1.5.0`、pynput `>=1.7`。DAWLoop 将 FastMCP 限定在 `<3`，以匹配本适配器使用的 v2 Client API。

## 安装

在仓库根目录执行：

```powershell
python -m pip install -e ".[flstudio]"
python -m dawloop setup-fl --dry-run
python -m dawloop setup-fl --settings-dir "<FL Studio Settings directory>"
python -m dawloop doctor --settings-dir "<FL Studio Settings directory>"
```

doctor 分别报告 Python、Core、上游 server、MCP/MIDI 依赖、MIDI 输出端口与 FL Studio 通信。依赖安装或 MIDI 端口存在都不代表 FL Studio 已连接。`--probe-fl` 会发起只读传输状态查询：

```powershell
python -m dawloop doctor --probe-fl
```

`setup-fl` 安装统一的 `DAWLoop Controller` 与随包 backend；活动 Settings 目录会保存在用户级 DAWLoop 配置中。安装器不需要用户单独下载或配置第二个身份 Controller。

## 安装 FL Studio User Scripts

`install-fl-scripts` 兼容入口仍可用；新安装建议使用 `setup-fl`。它安装一个由 DAWLoop 包装的主 Controller、独立放置的上游 backend 文件、上游许可证和 Piano Roll Script。既有过渡身份脚本仅在其名称明确匹配 DAWLoop 管理脚本时才会先备份再替换；不相关同名文件会使安装停止。Piano Roll 文件若只是换行符不同，会保留原文件。

```powershell
python -m dawloop install-fl-scripts --settings-dir "<FL Studio Settings directory>"
```

Controller 声明 `# name=DAWLoop Controller` 与 `# supportedDevices=DAWLoop MCP IN,FLSkill MCP IN`。Image-Line 的 supportedDevices 机制可按设备名自动关联；FL 现场加载与重启持久性仍待测试。开发期间旧 `FLSkill MCP IN/OUT` 端口可用，新安装默认建议 `DAWLoop MCP IN/OUT`。当前 backend 用 MIDI IN 发送触发、JSON 文件返回请求结果，不依赖 Port 42；端口方向、loopMIDI 顺序与一次性配置见 [FL Studio MIDI setup](FL_STUDIO_SETUP.md)。

## 当前实际通信路径

- **常规 FL API / 状态 RPC：** Python MCP server 写入 `Hardware/DAWLoopMCP/mcp_command.json`，向精确选中的 MIDI 输出端口（FL 侧的 `DAWLoop MCP IN`）发送 note 127 触发；主 Controller 读取命令并调用 FL API，再写入 `mcp_response.json`。响应通过共享文件返回，不走 MIDI OUT。
- **Pattern / Channel 身份查询：** 使用同一 command JSON、MIDI 触发和 response JSON；主 Controller 只读读取身份字段并在响应中关联 `request_id`。它不需要第二个 Controller，也不另建 SysEx / socket transport。
- **Piano Roll 持久音符：** upstream Piano Roll 工具写入 `Piano roll scripts/mcp_request.json`，再通过 `pynput` 发送 `Ctrl+Alt+Y`；`ComposeWithLLM.pyscript` 调用 FL Piano Roll API 并更新状态文件。这个上游路径与 note 127 控制器 RPC 是两条不同触发路径。当前上游 Piano Roll helper 按 Windows 默认 Documents Settings 路径定位文件。
- **loopMIDI：** 虚拟端口只在 loopMIDI 运行时存在；应先启动 loopMIDI，再启动或刷新 FL Studio 的 MIDI 设备列表。当前机器的已检测端口名仍是旧 `FLSkill MCP IN/OUT`，由迁移别名兼容；新安装建议使用 `DAWLoop MCP IN/OUT`。

当前公共代码没有 Port 42 协议常量；bundled MCP 按端口名称选择 Python 到 FL 的 MIDI 设备。不要仅因旧开发环境出现过 Port 42 约定就更改宿主端口设置。

## 目标确认与写入边界

适配器使用上游 `fl_send_notes` 和 `fl_get_piano_roll_state`。计划 tick 按 PPQ 映射为四分音符单位，读回使用上游导出的 `time_ticks`、`length_ticks`、`midi` 和归一化 `velocity`；PPQ 不一致或无法无损映射时停止。

上游 Piano Roll 读回没有 Pattern 标识，写入脚本操作当前打开的 Piano Roll。DAWLoop 主 Controller 在控制器 RPC 通道中提供只读身份 action，执行前后核对工程标题、Pattern 编号与名称、Channel 索引与名称、PPQ、safeToEdit 和 FL Studio 版本；同时校验上游读回的选中 Channel。身份读回不可用、目标不一致、请求队列已有内容、Pattern 非空、脚本未刷新读回或 Exact-Set 不匹配时，返回结构化 `STOP`。身份查询不另建 transport；它也不意味着现场加载已经验证。不得把 MCP 排队响应当成 PASS。

Live Execution Report 包含状态、目标、planned / actual events、planned / actual count、missing、extra、mismatches、错误、时间戳、DAWLoop 版本与上游 commit，可用 `to_json()` 输出供 agent 消费。只有空白专用测试 Pattern 中完成真实写入、新鲜读回、目标复核和 Exact-Set 匹配，才允许返回 `PASS`。

## 能力状态

- **Bundled / Implemented:** 固定上游源码、可选依赖、MCP backend 发现与调用骨架、音符字段映射、备份式 User Script 安装、目标身份门控。
- **Live Read / Write:** 维护者报告已完成现场接入；该次运行证据未归档，仓库不能据此宣称可复现的 Live Exact-Set 验证。稳定性仍待更多用户环境反馈。
- **Mixer / Plugin:** adapter 有只读 Mixer track discovery 和已加载插件参数查询入口；尚未在真实 FL Studio 中验证这些读取。任何写入能力均未标为 Verified。
- **AI agents:** Designed for AI agents and tool-using models；并不表示已适配所有 agent。
