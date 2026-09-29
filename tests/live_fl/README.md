# 现场音符证据采集

本目录的工具不会被普通测试命令自动运行。它只对独立、可丢弃的 FL Studio 测试工程写入四个自造音符，不会创建或清空 Pattern，也不会自动重试。运行前请准备：

- 工程标识 `DAWLoop_Live_Verification`；
- 已存在且空白的 Pattern `DAWLoop Live Test`；
- 已选中、明确命名的 Channel `DAWLoop Test`；
- 已安装 bundled FL Studio MCP 所需的 User Scripts；
- 能独立读取现场工程、Pattern、Channel 和 FL Studio 版本的 `identity_reader`。

上游 Piano Roll 状态本身没有 Pattern 身份。因此 `identity_reader` 必须从独立的现场状态来源读取真实身份，返回 `TargetIdentity(project_id, pattern_id, channel_index, channel_name, fl_studio_version)`；不得直接回传预期常量、从计划或 CLI 参数构造身份，也不得只依靠截图。若没有这样的读取器，请停止，不要运行写入步骤。

读取器需要在当前 Python 环境可导入。准备好专用测试工程后，显式运行：

```powershell
python tests/live_fl/capture_note_roundtrip.py --identity-reader your_reader_module:read_current_target --ppq 96 --confirm-disposable-project DAWLoop_Live_Verification
```

上例中的 `96` 只是命令格式示意，应换成当前测试工程的真实 PPQ。适配器会对新鲜 Piano Roll 读回中的 PPQ 做严格核对，不匹配时在写入前 STOP。测试计划使用四分音符 tick 坐标，不依赖工程拍号的自动发现。

运行器先探测连接，再确认现场身份、选中 Channel、请求队列和空白 Piano Roll；正式写入经过现有 DAWLoop adapter。写入后重新触发 User Script 并等待新状态文件，读取实际事件后才做 Exact-Set 比较。任一检查失败均为 STOP。尤其不要把上游排队响应当成读回。

运行前 Git 工作树须干净。环境记录包含当前提交和身份读取器源码的摘要，不会复制读取器文件或暴露其本机路径。若将一次 PASS 作为可复现的公开证据，仍需同时提供可审阅的身份读取器实现或明确其独立现场读取方法。

每次运行创建独立目录 `evidence/live_fl/note_roundtrip/<run-id>/`，保存 `environment.json`、`target_identity.json`、`plan.json`、`pre_state.json`、`execution.json`、`readback.json`、`verification.json` 和 `README.md`。该目录默认由 Git 忽略；失败尝试也保存。请先审查全部文件，再决定是否把某次运行有意归档到公开仓库。不要使用私人歌曲工程、商业素材或本机状态文件作为公开证据。

并发采集由目录锁阻止。若进程异常终止，需在确认没有其他采集进程后，人工移除 `.capture.lock`。前一次写入留下音符后，下一次运行会因目标非空而 STOP；应由维护者在 FL Studio 中准备新的空白测试目标，不能让工具自动清除现场内容。

参见 [`docs/VERIFICATION.md`](../../docs/VERIFICATION.md)。只有一次完整现场运行得到可审计的写入、独立新鲜读回、Exact-Set PASS，才能对该次目标和运行声明现场验证；工具存在本身不构成证据。
