# Native SysEx 连接故障：HELLO 恢复案例与排障指南

> **适用范围**：实验性 Native/SysEx 只读通路，而非默认 `DAWLoop MCP IN/OUT` JSON-RPC 路线。不要因本文修改运行正常的 FLSkill、DAWLoop MCP 或其他 MIDI 映射。
>
> 现场日期：2026-10-15—16。来自维护者提供的 Script Output、MIDI Settings 截图及本地执行回执的脱敏摘要。**本文件是故障复盘和手动修复方法，不代表自动诊断功能已实现。**

## 结果与认证边界

人工纠正 MIDI 设置后，一次真实 HELLO 获得匹配响应：约 **16ms**，Python 原始回调 **1次**，request_id、MAC、Session 和 build 全部匹配，判定 `LIVE_PASS`。但仅认证该会话的只读握手；正式 Mixer READ、Setter、跨重启稳定性均**未验证**。写入隔离保持不变。

## 故障时间线

| 阶段 | 真实观察 | 判定 |
| --- | --- | --- |
| 环境准备 | 缺少专用虚拟端口；冻结入口依赖 GUI 回执；另一次等待 MIDI 配置约300秒超时 | 前置条件阻断，HELLO未发送 |
| 来源检查 | 某冻结候选和现有 Driver 文件发生漂移 | 磁盘源码存在不代表已加载版本 |
| 第一轮真实 HELLO | 发送一次、10秒无匹配响应；当时未保存原始 MIDI callback snapshot | 原始丢包边界未知 |
| 人工检查 Script Output | OnInit/Session/OnInit Returned 均有标记，OnSysEx 抛出 Guard 异常 | 宿主 Controller 已运行、确有 SysEx 到达 |
| 细化 Guard 诊断 | 发现 `ONINIT_SESSION_READY` 通知自返；另一次 HELLO 的 ID 出现 `HOST_REQUEST_REPLAY`，Python 收到0个原始回调 | 自返和 Guard 拒绝有证据，但不能直接认定由何处回环 |
| 人工检查设置 | 发现 `DAWLoop HELLO IN` 额外被启用为 **Output Port 2** | 确定存在多余的输出映射 |
| 修正与复验 | 取消额外 Output 映射；其余配置不变；新 ID HELLO 约16ms 成功，回调1次 | 修正后通信恢复；**Port 2 是否唯一根因仍未证明** |

尤其注意：`request_count=1` 只能证明 ID 曾在 Guard 登记，**不是外部客户端发了两次的证明**。成功响应或其他报文回流、重复分发仍需独立报文摘要排查。

## 本案例中有效的映射

这里的 **Port 1 是 FL Studio 的逻辑关联编号，不是系统 MIDI 设备枚举序号**。下列配置只适用于本案例的独立 HELLO 测试通路：

| FL Studio MIDI Settings | 设备 | 本案例的设置 |
| --- | --- | --- |
| Output | `DAWLoop HELLO OUT` | 启用，Port 1；主同步关闭 |
| Output | `DAWLoop HELLO IN` | 禁用 / Port 未分配 |
| Input | `DAWLoop HELLO IN` | 启用，Controller Type = `DAWLoop Native Read Only`，Port 1 |
| Input | `DAWLoop HELLO OUT` | 禁用 |

```text
Python OUT → loopMIDI DAWLoop HELLO IN → FL Controller Input (Port 1)
FL Controller Output (Port 1) → loopMIDI DAWLoop HELLO OUT → Python IN
```

**不要**将上表的 Port 1 强行应用到用户的默认 MCP、FLSkill 或其他装置。若设置已一致，不要反复更改编号来试错。

## 普通用户如何检查

1. **确认使用的通路**：默认 MCP JSON-RPC 和实验 Native SysEx 并不共享相同回包机制。
2. **检查 loopMIDI**：程序正在运行、所需两个虚拟端口名称精确存在。先启动 loopMIDI，再让 FL Studio 枚举设备。端口存在不等于映射已正确。
3. **检查 FL MIDI Settings（F10）**：查看目标通路的 Input/Output 启用状态、Controller Type 与逻辑 Port。不要修改其他正常工作的端口。
4. **检查 Script Output**：选择对应 Controller 标签，寻找本次 OnInit、Session、build、OnSysEx traceback。**脚本安装成功不代表已在宿主内重新加载。**
5. **在具备权限的诊断程序中只发送一次只读 HELLO**：使用新 request_id，保存请求/响应摘要、运行身份、Guard 错误、客户端原始 callback 和匹配结果。未知结果不得盲目重发有副作用的指令。
6. **按最早失败环节处理**：

| 现象 | 当前可证明内容 | 后续措施 |
| --- | --- | --- |
| 虚拟端口不存在 | 本机环境未准备好 | 启动 loopMIDI；核对真实设备名称 |
| 磁盘 Controller 匹配但无 OnInit | 运行状态未知 | 查看 Script Output，不要直接重装 |
| `HOST_REQUEST_ID_TYPE_INVALID` | 宿主处理了无合法 ID 的消息；本案例关联到通知自返 | 先对照 action/摘要/方向；不要当成 HELLO 的必然失败原因 |
| `HOST_REQUEST_REPLAY` | 请求 ID 已登记 | 查首次登记与回流；保留防重放 Guard |
| 超时且 Python 原始回调为0 | 外部没有观察到字节 | 结合宿主接收/发送日志查输出关联和转发 |
| 原始字节存在但匹配失败 | 数据已抵达外部 | 检查解析、ID、Session、build、MAC |
| HELLO 成功、READ 未成功 | 握手成功，Mixer Getter 仍未验收 | 另行验收 READ，不能以 HELLO 冒充 Getter |

## 对维护者的后续改进

这些是**待实施的产品改动，不是已上线功能**：

1. 安装/配置与运行分开：配置检查在创建现场 Session 之前完成。
2. 保留经过真实 HELLO 验证的不可变源码、设备名称、Port 关联与脱敏证据；避免测试文件被开发工作树覆盖。
3. 成功/失败都落盘原始回调 snapshot，记录宿主 OnInit、收包、Guard、出包等阶段，**不记录明文密钥**。
4. 分别报告无效 ID、重复请求、数量上限，不放宽防重放。
5. 后续 Connection Doctor 应区分自动检测与人工确认；无法由受支持 API 读取的宿主设置应显示“未验证”，不得猜测自动修复成功。

## 安全与后续验证

本案例未授权写入、Setter 或解除 `WRITE_QUARANTINED`。正式 READ、写入和稳定性均需独立真实验收。不得上传完整本地日志、私人路径、明文通道密钥、私人工程或任何可复用的认证材料。曾在诊断中暴露的测试通道密钥应按受控流程轮换。

更多信息：[FL Studio 安装](FL_STUDIO_SETUP.md) · [执行后端](FL_STUDIO_MCP.md) · [认证边界](VERIFICATION.md)。
