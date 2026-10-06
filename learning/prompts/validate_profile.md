<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2026 ryurikoneko -->
# 验证与修订

输入：ProfileRevision、原报告、父版本（若不是v1）、固定 PlanningRequest 和用户实际反馈。

先 validate_profile(profile, report=report, parent=parent)，再运行 PlanningRequest/MusicalPlan 现有验证器。不得以合法代替好听；用固定请求比较版本变化，把留出审阅的观察和未知单独记录。

用户反馈必须绑定实际 plan_hash/profile_hash、唯一 report_id、时间、来源 HUMAN，以及 LISTENED_OK/LISTENED_BAD/VISUAL_REVIEW_ONLY。只按真实回报填写；Agent 推测不算人工反馈。合成测试必须 context=SYNTHETIC_EXAMPLE。

调用 revise_profile 生成下一版；使用 write_revision 写新文件，不覆盖旧版，不改写原分析、报告或先前反馈。核对只有明确 changes 改变了四个旋钮；硬约束变更用独立新 PlanningRequest。没有新的可执行授权就结束于离线计划，不启动 FL 或 FAST。
