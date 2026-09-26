# FLSkill

**状态：** `v0.1.0-alpha`（本地预发布候选，尚未对外发布）<br>
**核心：** `Offline Algorithm Verified`<br>
**FL Studio 集成：** 尚未实现

FLSkill Core 是一个来源清晰、可独立测试的音乐时间解析与音符事件验证核心。当前阶段不连接 FL Studio，也不包含 Computer Use、MCP、SysEx、Mixer、插件或音频分析器。

**项目关系声明：** FLSkill 是独立开源项目，与 Image-Line 或 OpenAI 无关联，也未获其认可或赞助。

```text
Musical Grid
→ Absolute Time Resolution
→ Note Plan
→ Writer
→ Reader
→ Exact-Set Verification
→ PASS / STOP
```

核心采用 Python 标准库，无第三方运行依赖。它可把小节/拍/tick 定位解析为绝对 tick，将计划交给 Writer，再从 Reader 取得实际事件并比较。Writer 的返回值不作为成功证据；写入后必须读取并比较。

当前通过内存 Writer / Reader 验证算法。成功结果标记为 `Offline Algorithm Verified`，不代表 FL Studio 写入验证。接入真实适配器前，必须能够确认目标身份、写入后从实际目标读回事件，并保存该读回证据；缺少任一条件都不能报告 `FL Studio Verified`。

**核心原则：** `Offline Algorithm Verified ≠ FL Studio Verified`。

## 使用

需要 Python 3.11 或更新版本。运行标准库测试：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

## 当前范围

- Musical Grid：PPQ、拍号和一基小节/拍位置。
- Absolute Time Resolution：确定地解析为非负绝对 tick。
- Note Plan：验证目标、段落范围和事件字段。
- Writer / Reader Protocol：定义写入与实际读回边界。
- 内存实现：只用于自造离线测试数据。
- Exact-Set Verification：保留重复事件数量，检查 missing / extra 及音符字段差异。
- PASS / STOP：写入错误、读回错误或计划/实际不一致时 STOP。

规格、验证边界和计划见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、[`docs/VERIFICATION.md`](docs/VERIFICATION.md) 与 [`docs/ROADMAP.md`](docs/ROADMAP.md)。文件来源记录见 [`PROVENANCE.md`](PROVENANCE.md)。本项目按 [`MIT License`](LICENSE) 授权。
