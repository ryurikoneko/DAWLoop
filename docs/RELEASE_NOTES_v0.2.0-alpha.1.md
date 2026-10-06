# Runtime V2 Research Preview

[KNOWN｜HIGH] 此次更新把原有离线/Community工具扩展为结构化、证据化的Native FAST runtime，并公开用户自己的音乐学习框架。首页已重新布局，部署按离线可用、FAST受限研究集成、MCP候选接口三个成熟度说明。这是alpha预览，不是stable生产版。

## 最终行为

- [KNOWN｜HIGH] FAST：完整计划先校验，Controller导航与观察性目标确认，deterministic source/AST/hash守卫，一次Native批量派发，用户Accept，实时HumanReport/application receipt领取和宿主callback，结果`COMPLETED_UNVERIFIED`。
- [KNOWN｜HIGH] 现场范围：已有disposable Pattern 1 / 808 Kick、PPQ96、第5–8小节、固定16音符、add-only、0retry、0fallback；no-save退出、基线摘要与端口关闭已记录。已有Kick↔Clap整链导航只认证观察性绑定。
- [KNOWN｜HIGH] 音乐合同：Section/Harmony/Voice/Variation与通用StyleConstraints，保留phrase/motif/constraints/provenance。学习框架提供来源、特征、统计、profile revision四份严格Schema，四套Agent prompts和完整合成例子；用户Agent学习自己的材料，Core没有内置个人艺术家逻辑。
- [KNOWN｜HIGH] MCP：三个stdio工具与后台RunManager已离线接线，operation幂等、truthful readiness、现有FAST factory与observer证据通道保留。现场MCP与zero-Agent-CU路径未认证，暂停于外部browser page identity依赖。
- [KNOWN｜HIGH] 来源：MIT根许可保持，补NOTICE/AUTHORS/CITATION/品牌范围、精确许可政策及内容provenance。第三方原版权和创作者致谢保留；CC BY-NC文本只是备选，当前单独许可资产为空。

## 边界

[KNOWN｜HIGH] producer binding / Native structured readback / Exact Set未认证，VERIFIED研究冻结；Auto Accept延期，connection reuse未测试，正常作品连续写入未认证。图像与callback不能代替Exact Set。原始私人FLP、截图、Memos、token与大型session/debug数据未发布；公开脱敏摘要和必要回归输入。

[KNOWN｜HIGH] 发布清理迁移了私有session依赖的测试输入，明确本机安装参数；关闭的文件快照入口在状态缺失时也拒绝。没有开启新现场实验或扩大16-note认证。

## 验证与部署

[COMPUTED｜HIGH] 发布目录完整回归：710 tests passed + 331 subtests passed；另对packaging/provenance资源调整运行127项相关回归。两个第三方弃用警告不作为功能失败。wheel/sdist构建、包资源/安装隔离、公开路径/凭据扫描与本地链接检查记录在`evidence/public/release_validation.json`。

[KNOWN｜HIGH] 从源码安装 `.[learning]` 即可跑合成学习教程，无需FL。Windows Controller、Native研究入口、MCP暂停状态与必要配置见`docs/DEPLOYMENT.md`。固定现场fixture未分发，不提供绕过守卫的“一键写当前作品”指令。

[KNOWN｜HIGH] 此alpha的tag/artifact没有维护者身份签名或attestation，内容hash只校验字节；未创建DOI。GitHub保留历史release。后续路线见`docs/ROADMAP.md`，外部记忆同步仍待服务恢复。
