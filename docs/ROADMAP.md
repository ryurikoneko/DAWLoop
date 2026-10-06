# Roadmap

本版是 Runtime V2 research-preview；旧 `v0.1.0-alpha` 保留。路线图区分已实现、现场认证与未来计划，不用上游支持或离线测试替代现场证据。

## 已完成

- 离线 MusicalGrid、NotePlan、保留重复次数的 Exact-Set 比较器。
- Community 固定快照、安装/诊断与通用 Production 分析工具，保留第三方来源。
- Controller build/session/project 身份；已有 Kick ↔ Clap 自动导航与观察性确认。
- 固定16-note Native FAST 高层入口、单次派发、人工接受、应用观察和完成回调的受限现场闭环。
- HumanReport 独立持久化/领取/晚到关联，原终态不可改写。
- MusicalPlan、通用约束、动机/乐句解释、Learning Protocol/Schema/Prompt/版本化profile的离线实现。
- 三工具 stdio MCP、后台 RunManager、real factory、truthful readiness 与 observer 接线的离线实现。

## P0：音乐计划与用户自己的学习

用户 Agent 用自有素材跑分析 → 同类统计 → 显式映射 → 计划验证 → 用户反馈 → 新profile版本。公共项目提供框架，不内置艺术家偏好或宣称学习泛化已认证。下一项接线是学习MusicalPlan到FAST的单位/字段转换与独立验收，不直接开放任意源码或扩张现场note预算。

## 暂停候选路线：ZERO-AGENT-COMPUTER-USE FAST

```text
MCP_FAST_PATH = NOT_LIVE_CERTIFIED
ZERO_AGENT_COMPUTER_USE_FAST_PATH = NOT_LIVE_CERTIFIED
BROWSER_PAGE_IDENTITY_TRANSPORT = UNAVAILABLE
OBSERVER_UI_BINDING = BLOCKED
OBSERVER_REQUEST_COMPLETION = NOT_PROVEN
```

已有实验FAST路径仍有受限证据；新MCP候选路径没有完成现场run。不得重复同一个fetch失败、猜URL、用窗口标题/焦点/坐标替代页面身份或为了发布而降级READY。

### GitHub待办：复验与分支展示

1. 浏览器连接端修复后，先稳定取得真实URL/page identity。
2. 不开FL，在两个不同process/session generation下各完成一次observer UI binding + request completion，并正常shutdown无残留。
3. 两次都过才开一个独立MCP现场会话：固定16 notes、一次派发、人工Accept、REALTIME报告/应用领取、宿主回调、试听、不保存恢复。MCP调用与zero-agent-CU分别认证。
4. 若目标用户仍无法使用该依赖，建立单独候选分支与兼容性说明，展示MCP路径作为可选路线，同时指向已通过的受限FAST/既有观察工作流。不得把未通过的候选路线宣传成更可靠默认方案。

本次只是将复验条件列为公开待办，未进行新浏览器/FL实验，也未创建一个虚构“已验证替代observer”分支。候选分支只在有实际兼容方案和证据后建立。

## 之后的独立阶段

| 顺序 | 阶段 | 必须保留的边界 |
| --- | --- | --- |
| MCP现场通过后 | 只读bridge/session reuse | status/read/reconnect先行，generation与ledger不拆 |
| 然后 | normal-project / multi-operation | 工程身份、checkpoint、dirty/save策略、operation预算及失效守卫 |
| 然后 | 语音输入 | 只是输入层，不重新开启自动commit |
| 独立评估 | Human telemetry完善 / Auto Accept | Auto Accept默认关闭，无新增像素识别框架 |

## 冻结：Native VERIFIED

`NATIVE_VERIFIED_RESEARCH = FROZEN_BLOCKED`，原因是缺少可认证producer-side完整音符读回。现有normal return没有数据传播证据，error channel unresolved，file routes closed，缓存/视觉不足以Exact Set。只有新的可信完整读取接口才解冻，不再重包装旧payload/文件/日志路线。

解冻后的顺序仍是 notes[] → 请求freshness与producer实际目标证据 → baseline+additions multiset/PPQ比较。不能从截图或callback直接跳到VERIFIED。普通工程持续写入与 `v1.0 stable` 的完成条件尚未达成。

## 来源与发行待办

MIT/NOTICE/AUTHORS/CFF/品牌说明与公开内容hash已有；签名身份、公钥/可信发布流水线、artifact attestation、可选真实DOI及第三方复现尚待完成。CC BY-NC只保存许可文本，当前资产清单为空。不要追溯回收MIT许可或伪造签名/DOI。
