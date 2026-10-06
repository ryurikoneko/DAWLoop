# DAWLoop

**把音乐意图变成结构化计划，再把计划送到正确的 FL Studio 目标。**

*An experimental agent runtime for structured, evidence-aware FL Studio automation.*

[![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Research preview](https://img.shields.io/badge/status-research--preview-orange)](docs/ROADMAP.md)

[开始部署](docs/DEPLOYMENT.md) · [能力与证据](docs/DAWLOOP_RUNTIME_V2.md#current) · [让自己的 Agent 学习](learning/WORKFLOW.md) · [架构](docs/ARCHITECTURE.md) · [路线图](docs/ROADMAP.md)

## 现在能做什么

[KNOWN｜HIGH] Runtime V2 已在受限测试工程跑通：**自动导航 → 观察性确认目标 → 确定性批量写入 → 人工 Accept → 应用观察与宿主回调 → 试听确认**。现场认证范围是已有 Pattern 1 / 808 Kick、PPQ 96、第 5–8 小节、16 个音符、add-only、单次派发；结束后不保存退出并核验基线。它是实验性 FAST 工作流，尚不是普通作品工程的连续写入产品。

```mermaid
flowchart LR
    A[Agent / 用户意图] --> B[结构化计划与完整校验]
    B --> C[Controller 自动目标准备]
    C --> D[身份 → 新鲜界面 → 身份]
    D --> E[确定性 renderer]
    E --> F[Gopher 单次批量派发]
    F --> G[人工 Preview / Accept]
    G --> H[应用观察 + 完成回调]
    H --> I[COMPLETED_UNVERIFIED]
```

[KNOWN｜HIGH] **FAST success ≠ VERIFIED write。** 观察性目标确认不能证明执行器内部对象绑定；可见、听感与成功回调不能代替精确音符读回。当前 Native VERIFIED 分支冻结于缺少可认证的 producer-side structured note readback。

| 能力 | 当前状态 | 范围 |
| --- | --- | --- |
| Controller 运行时 build/session/project 身份 | 现场通过 | 运行中的 Controller 自己报告版本 |
| 自动 Pattern / Channel / Piano Roll 导航 | 现场通过 | 已有 Kick ↔ Clap，观察性绑定 |
| FAST 高层音乐入口 | 现场通过 | 固定 16-note disposable 测试范围 |
| 人工回执、应用观察实时领取 | 现场通过 | 持久化与实际领取分别记录 |
| MusicalPlan / Learning Framework | 离线实现与测试通过 | 风格无关合同、验证器、合成示例 |
| 异步 stdio MCP / RunManager | 离线接线完成；现场未认证 | 外部浏览器 page identity 依赖阻塞 |
| Native producer binding / Exact Set | 未认证；研究冻结 | 不以视觉、缓存或成功回调替代 |
| 普通工程连续写入、连接复用、Auto Accept | 未认证 / 未测试 / 延期 | 不作为本版承诺 |

[KNOWN｜HIGH] 表中“现场通过”是维护者限定实验结论，不表示所有用户环境已兼容。公开的是[脱敏证据摘要](evidence/public/README.md)与回归输入；私人 FLP、原始截图、会话日志不随仓库分发。

## 三个入口，三个成熟度

### 1. 离线音乐计划与学习框架：可以直接开始

[KNOWN｜HIGH] Core 接收 Section Brief、Harmony Context、音域/跳进/密度约束与 Motif/Variation，输出含 `notes[]`、`phrase_map`、`motif_map`、约束快照与来源的 MusicalPlan。参考生成器目前是受限、确定性的单声部实现，不是完整自动作曲模型。

```powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning]"
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

[KNOWN｜HIGH] 例子不启动 FL、不写音符、不访问外部素材，生成参考登记、特征、报告、两版 profile 和离线计划。用户自己的 Agent 分析自己的素材；公共仓库提供 **Learning Protocol + Schemas + Prompts + Validators**，不替用户学完某个艺术家或流派。详见[八步学习路径](learning/WORKFLOW.md#八步学习路径)。

### 2. Native FAST：已有现场证据的研究集成

[KNOWN｜HIGH] `FastMusicRuntime.execute_fast_music_plan(...)` 拥有校验、目标准备、观察确认、规范渲染、一次派发与人工接受生命周期。输入是结构化字段，不能提交 arbitrary Python。未知派发结果不允许自动重试或 fallback。

```python
# backend 必须由显式配置的受审集成提供。
from dawloop.runtime.fast_music import FastMusicRuntime

result = await FastMusicRuntime(backend).execute_fast_music_plan(
    target, musical_plan, operation_id=operation_id,
    acceptance_mode="human", experimental_authorized=True,
)
```

[KNOWN｜HIGH] 须准备已有目标、自己的 disposable 工程、Controller、Gopher 和真实观察回执入口。维护者固定测试 FLP 不随包提供；历史 harness 的 fixture/build/hash 守卫不能为了运行示例而绕过。学习层的 MIDI velocity 与 FAST 的 normalized velocity 合同不同，自动转换接线尚未认证。[部署与输入合同](docs/DEPLOYMENT.md)。

### 3. DAWLoop MCP：异步接口预览，现场路径暂停

[KNOWN｜HIGH] 三个工具：`fast_write_music(...)` 创建后台 run，`status(run_id)` 查询真实就绪与进度，`submit_human_report(...)` 转交用户报告。MCP handler 不阻塞到 Accept；RunManager 保持 operation 幂等身份与一次派发预算。

```text
MCP → RunManager → 既有 FAST Runtime
                     ├─ Controller / Gopher
                     ├─ 独立采样 + 真实视觉审阅
                     └─ HumanReport / evidence channels
```

[KNOWN｜HIGH] **MCP_FAST_PATH / ZERO_AGENT_COMPUTER_USE_FAST_PATH 未现场认证**。Controller、Gopher、observer、预算任一缺失，`status()` 必须 NOT_READY。stdio 服务运行不等于 FL 可写；截图成功不等于目标确认。第一版允许用户每个 FL 会话人工 bootstrap 一次 Gopher；连接复用未测试。

## 保留的分析与验证工具

[KNOWN｜HIGH] 原离线 MusicalGrid、NotePlan 和 multiset Exact-Set 比较器继续可用；算法通过不代表 Native live verification。可选 Production Pipeline 提供 SMF/MIDI 检查、声部/音域辅助、active-frame RMS、推子标定计划、WASAPI loopback 与 SoundFont 工具。[分析文档](docs/PRODUCTION_PIPELINE.md)。Community FL Studio MCP 固定快照仍保留，上游能力与本项目认证分别记录。

## 下一步与贡献

[KNOWN｜HIGH] 主线是通用学习合同与实际音乐计划；MCP 候选路线等待可信 page identity 恢复，复验与止损条件见[路线图](docs/ROADMAP.md)。连接复用、正常工程、多 operation、语音均在后续阶段；本版不增加隐蔽返回通道或自动 Accept 研究。

[KNOWN｜HIGH] 贡献前阅读 [CONTRIBUTING](CONTRIBUTING.md) 与 [SECURITY](SECURITY.md)。个人 profiles、workspace、Memos 内容、凭据、原始实验会话不发布。官方手册 HTML/图片未收录，[本地知识规则](learning/WORKFLOW.md#官方操作知识与-flaik-html)不代授第三方许可。

## 来源与许可

[KNOWN｜HIGH] 自有代码、学习协议、示例和本次公开文档保持 [MIT](LICENSE)，允许商业使用并要求保留许可通知。`NOTICE`、`AUTHORS`、`CITATION.cff` 与 provenance 记录来源，不添加隐藏禁止转售条件。当前没有单独启用 CC BY-NC 资产；许可文本存在不等于目录已改许可。[精确许可范围](LICENSE_POLICY.md) · [品牌说明](TRADEMARKS.md) · [来源记录](PROVENANCE.md)。

[KNOWN｜HIGH] Bundled backend 来自 [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) 固定 MIT 快照，保留原作者版权。Production Pipeline 部分代码改编自维护者提供的 MIT `whale-music-pipeline`，另见[第三方声明](THIRD_PARTY_NOTICES.md)。

[KNOWN｜HIGH] 感谢 Bilibili 创作者[坏影子不坏](https://space.bilibili.com/599132499)的 DSH 视频与工作流展示（[示例视频](https://www.bilibili.com/video/BV1PTht6cENP/)）对编排、MIDI 分析、RMS、loopback、Mixer 标定与生产流程的启发。DSH 指视频/工作流，不是独立软件；创作者致谢与实际代码来源分别记录。

[KNOWN｜HIGH] 历史名称 FLSkill → DAWProof → DAWLoop，旧 tag 与发布保留。这是 research-preview，不是 stable；签名、DOI 与第三方复现实验尚未完成，不以内容 hash 冒充作者证明。
