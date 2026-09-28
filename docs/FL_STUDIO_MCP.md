# Community FL Studio MCP 集成

## 当前状态

目标版本为 `v0.2.0-alpha`。固定 commit 的 Community FL Studio MCP 源码随仓库放在 `third_party/fl-studio-mcp/`；DAWLoop 的 optional Python extra 与适配器已建立。维护者报告已完成真实 FL Studio 接入流程；该路径可能仍不稳定，欢迎用户实测并反馈环境兼容性问题。仓库没有归档该次运行的目标身份与实际 note readback 证据，因此不标记为可复现的 `Live Exact-Set Verified`。

上游快照：`karl-andres/fl-studio-mcp`，commit `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`，MIT。其依赖范围取自该 commit 的 `pyproject.toml`：FastMCP `>=2.0`、Mido `>=1.3.0`、python-rtmidi `>=1.5.0`、pynput `>=1.7`。DAWLoop 将 FastMCP 限定在 `<3`，以匹配本适配器使用的 v2 Client API。

## 安装

在仓库根目录执行：

```powershell
python -m pip install -e ".[flstudio]"
python -m dawloop doctor
```

doctor 分别报告 Python、Core、上游 server、MCP/MIDI 依赖、MIDI 输出端口与 FL Studio 通信。依赖安装或 MIDI 端口存在都不代表 FL Studio 已连接。`--probe-fl` 会发起只读传输状态查询：

```powershell
python -m dawloop doctor --probe-fl
```

User Script 检查默认查看 Windows 常见 FL Studio `Settings` 位置。若用户数据目录自定义，可设置 `DAWLOOP_FL_SETTINGS_DIR` 指向实际 Settings 目录，再运行 doctor。

## 安装 FL Studio User Scripts

将 FL Studio 的 `Settings` 目录作为参数明确传入。工具只安装上游 Controller Script 与 Piano Roll Script；若目标文件已存在，会在替换前生成带时间戳的旁路备份。

```powershell
python -m dawloop install-fl-scripts --settings-dir "<FL Studio Settings directory>"
```

安装后按上游说明在 FL Studio 的 MIDI Settings 中选择并启用 `FLStudioMCP` Controller，并准备兼容的 MIDI 输出端口。该安装命令不会配置用户的 AI 客户端。

## 目标确认与写入边界

适配器使用上游 `fl_send_notes` 和 `fl_get_piano_roll_state`。计划 tick 按 PPQ 映射为四分音符单位，读回使用上游导出的 `time_ticks`、`length_ticks`、`midi` 和归一化 `velocity`；PPQ 不一致或无法无损映射时停止。

上游读回没有 Pattern 标识，写入脚本操作当前打开的 Piano Roll。适配器因此要求外部 `identity_reader` 在执行前后核对工程、Pattern、Channel 与 FL Studio 版本，并同时核对上游读回的选中 Channel。缺少该读取器、目标不一致、请求队列已有内容、Pattern 非空、脚本未刷新读回或 Exact-Set 不匹配时，返回结构化 `STOP`。不得把 MCP 排队响应当成 PASS。

Live Execution Report 包含状态、目标、planned / actual events、planned / actual count、missing、extra、mismatches、错误、时间戳、DAWLoop 版本与上游 commit，可用 `to_json()` 输出供 agent 消费。只有空白专用测试 Pattern 中完成真实写入、新鲜读回、目标复核和 Exact-Set 匹配，才允许返回 `PASS`。

## 能力状态

- **Bundled / Implemented:** 固定上游源码、可选依赖、MCP backend 发现与调用骨架、音符字段映射、备份式 User Script 安装、目标身份门控。
- **Live Read / Write:** 维护者报告已完成现场接入；该次运行证据未归档，仓库不能据此宣称可复现的 Live Exact-Set 验证。稳定性仍待更多用户环境反馈。
- **Mixer / Plugin:** adapter 有只读 Mixer track discovery 和已加载插件参数查询入口；尚未在真实 FL Studio 中验证这些读取。任何写入能力均未标为 Verified。
- **AI agents:** Designed for AI agents and tool-using models；并不表示已适配所有 agent。
