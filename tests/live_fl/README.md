# 现场音符证据采集

本目录的工具不会被普通测试命令自动运行。它只对独立、可丢弃的 FL Studio 测试工程写入四个自造音符，不会创建或清空 Pattern，也不会自动重试。运行前请准备：

- 工程标识 `DAWLoop_Live_Verification`；
- 已存在且空白的 Pattern `DAWLoop Live Test`；
- 已选中、明确命名的 Channel `DAWLoop Test`；
- 已安装 bundled FL Studio MCP 所需的 User Scripts；
- 在 FL Studio MIDI 设置中选择 `DAWLoop MCP Controller`，使用 DAWLoop 自有的只读身份查询；
- 事先从测试工程界面确认 Pattern 编号、全局 Channel 索引和 PPQ，作为显式预期值传入。

上游 Piano Roll 状态本身没有 Pattern 身份。DAWLoop 的 `device_DAWLoopMCP.py` 安装在独立的 `Hardware/DAWLoopMCP/` 目录，通过原有 MCP MIDI/JSON 通道只读获取工程标题、Pattern 编号与名称、全局 Channel 索引与名称、PPQ、`safeToEdit`、脚本 API 版本和 FL Studio 版本。该脚本把其他命令交给未修改的上游控制器。必须在 FL Studio MIDI 设置中将该脚本选为当前控制器；如果仍选择上游控制器，身份查询会失败并阻止写入。工程标题只是辅助安全字段，不是持久工程 ID。

读取器实现已纳入源码，但尚未通过真实 FL Studio 身份探测。对应函数来自 Image-Line 的 [MIDI Scripting API](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm)。未得到现场响应、字段不可用或索引语义不一致时必须 STOP，不可根据界面猜测。

第一次现场操作只运行 `python tests/live_fl/probe_target_identity.py --midi-port "FL Studio MCP 4"`，核对只读输出与 FL Studio 当前界面。端口名必须换成当前 `mido` 列表中的精确名称；不得依赖上游自动选择第一个端口。该探测不写音符。即使探测成功，也需维护者确认后才运行下方采集器。采集器还会在写入前确认上游执行后端自动选择的端口与身份查询端口完全一致；不一致时 STOP。

读取器需要在当前 Python 环境可导入。准备好专用测试工程后，显式运行：

```powershell
python tests/live_fl/capture_note_roundtrip.py --midi-port "FL Studio MCP 4" --ppq 96 --expected-pattern-number 1 --expected-channel-index 0 --confirm-disposable-project DAWLoop_Live_Verification
```

上例中的 `96`、Pattern 编号 `1` 和 Channel 索引 `0` 都只是命令格式示意，必须换成独立测试工程的实际值。采集器会先用 FL Studio User Script 独立读回并比较这些预期值，随后对新鲜 Piano Roll 读回中的 PPQ 再次核对；任何不符均在写入前 STOP。测试计划使用四分音符 tick 坐标，不依赖工程拍号的自动发现。

运行器先探测连接，再确认现场身份、选中 Channel、请求队列和空白 Piano Roll；正式写入经过现有 DAWLoop adapter。写入后重新触发 User Script 并等待新状态文件，读取实际事件后才做 Exact-Set 比较。任一检查失败均为 STOP。尤其不要把上游排队响应当成读回。

运行前 Git 工作树须干净。环境记录包含仓库、分支、提交、工作树状态和身份读取器源码摘要，不会复制读取器文件或暴露其本机路径。若将一次 PASS 作为可复现的公开证据，仍需同时提供可审阅的身份读取器实现或明确其独立现场读取方法。`readback.json` 的观察时间是采集器本机收到读回时的时间；状态文件修改时间也是本机文件系统时间，均不冒充 DAW revision 或时间戳。

每次运行创建独立目录 `evidence/live_fl/note_roundtrip/<run-id>/`，保存 `environment.json`、`target_identity.json`、`plan.json`、`pre_state.json`、`execution.json`、`readback.json`、`verification.json` 和 `README.md`。该目录默认由 Git 忽略；失败尝试也保存。请先审查全部文件，再决定是否把某次运行有意归档到公开仓库。不要使用私人歌曲工程、商业素材或本机状态文件作为公开证据。

并发采集由目录锁阻止。若进程异常终止，需在确认没有其他采集进程后，人工移除 `.capture.lock`。前一次写入留下音符后，下一次运行会因目标非空而 STOP；应由维护者在 FL Studio 中准备新的空白测试目标，不能让工具自动清除现场内容。

参见 [`docs/VERIFICATION.md`](../../docs/VERIFICATION.md)。只有一次完整现场运行得到可审计的写入、独立新鲜读回、Exact-Set PASS，才能对该次目标和运行声明现场验证；工具存在本身不构成证据。
