# 公开产品内容写作规范 / Public product writing

文档应让读者理解自己怎样使用DAWLoop完成音乐任务。内容深度来自操作、信息流和结果之间的解释，而非行数限制或技术名词堆积。

Help readers understand how to complete a musical task with DAWLoop. Depth comes from explaining actions, information flow and results, rather than meeting a line limit or listing technical nouns.

## 先建立完整故事 / Tell the whole task

以用户想做的事开头，依次解释为什么需要这项能力、怎样操作、处理什么输入、得到什么成果，以及下一步怎样继续。重要页面可以长，但每一段都应帮助理解。

Start with the user's goal. Explain why a capability matters, what the user does, which inputs are processed, what comes out and how work continues. A substantial page is useful when each paragraph answers a question.

Desktop故事从素材试听、分析或旋律条件进入本地编辑与导出；宿主故事从音乐目标进入计划、目标识别、授权、执行、观察和判断。分别解释实际交付路径，再说明它们的架构联系。

The Desktop story runs from listening, analysis or melody constraints to local editing and export. The host story runs from intent through planning, targeting, authorization, execution, observation and a decision. Explain each delivered path before connecting the architecture.

## 组织文章 / Organize the page

产品介绍采用：用途与价值 → 真实界面或情境 → 功能过程 → 技术机制与图示 → 使用入口 → 唯一的末尾“当前版本说明”。通常用四至六条版本说明集中交代平台、组件条件与交付范围。

Use: purpose and value → interface or scenario → task details → mechanisms and diagrams → entry points → one final Current Version Notes section, normally four to six points covering platform, component conditions and scope.

正文用准确的动词和条件描述功能，不在每段重复同一限制。安装安全、签名、校验和、许可、备份和真实工程写入授权必须放在相关动作之前。操作指南、验证合同、故障说明和历史档案保留必要细节。

Describe features with precise verbs and conditions rather than repeating the same limitation. Keep installation safety, signatures, checksums, licenses, backups and host-write permission before the action. Operational guides, verification contracts, troubleshooting and archives retain their necessary detail.

## 图示与演示 / Diagrams and demonstrations

- 每张图回答一个问题，优先纵向主流程，避免横向长链。 / Give each diagram one question and favor vertical main flows.
- 按实际后端分支，区分身份读取、执行与读回；不把所有协议画成必经串行。 / Branch actual backends and separate identity, execution and readback.
- 流程图说明架构，截图展示实际软件，现场故事引用原证据；不互相代替。 / Diagrams explain architecture, screenshots show software, and live stories cite original evidence.
- 不用颜色暗示未经证明的成功；检查浅色、深色和窄屏。 / Do not imply unproven success through color; check light, dark and narrow layouts.
- 假设情境明确标为使用示例，不冒充同一次连续实测。 / Label illustrative scenarios instead of presenting them as one recorded run.

## 来源与用语 / Sources and language

当前能力对应实际源码、公开发行或记录；方向使用未来语气。Desktop标签源码与Runtime main分开；上游工具可用与DAWLoop验证范围分开；通知批准与版本发布分开。原始失败、终态、版权和许可保持完整。

Ground current capabilities in code, releases or records and phrase directions as future work. Separate Desktop tag source from Runtime main, backend tools from DAWLoop verification, and notification approval from publication. Preserve failures, terminal states, copyrights and licenses.

用自然语言表达事实、推断与未知，不添加内部推理前缀、置信度标记或工程流水账。中英文保持同等内容深度、功能条件、下载与署名，术语见 [Glossary](GLOSSARY.md)。

Express facts, inferences and unknowns naturally, without internal reasoning prefixes, confidence markers or progress-log prose. Keep both languages equal in depth, conditions, downloads and credits, using the glossary above.

## 三产品边界 / Three-product boundary

Desktop 与 Runtime 是开源交付；Plugin 自有实现闭源，本轮仅交付 Composer，按实际产品核对功能和发行状态。每次写下载前核对 Published Release 和实际资产；本地 ZIP 或 Draft 不代表可公开下载。不要以 Composer 的宿主记录证明 Runtime 验证已完成。

Desktop and Runtime are open-source deliveries; private Plugin implementation is proprietary. This delivery covers Composer only. Confirm the published release and actual asset before adding a download. Local ZIPs and drafts are not public delivery. Composer host records do not certify Runtime verification.

## 审阅问题 / Review questions

只读首页，读者是否能说清：项目是什么、不连FL能做什么、为何连接FL、相较MIDI文件流程增加了什么、执行反馈怎样工作、应从Desktop还是Runtime开始？

From the homepage alone, can readers explain the project, the standalone workflow, the reason for FL integration, the value beyond MIDI files, the feedback loop, and which entry point to choose?

最后检查链接、锚点、图片、命令、实际GitHub图示与跨页版本；发布正文、Settings或通知状态变更仍需对应授权。

Finally check links, anchors, images, commands, actual GitHub diagrams and cross-page versions. Release, Settings and notification changes still need their own authorization.
