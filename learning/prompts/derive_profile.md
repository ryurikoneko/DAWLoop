<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2026 ryurikoneko -->
# 推导个人 Profile

输入：已通过 validate_bundle 的报告、用户用途与偏好、现有硬约束。生成器不接受 artist、任意 Python 或 source 字段。

只为 rhythm_syncopation、melody_leap_tendency、harmony_tension_usage、motif_variation_strength 分别提供 value(0..1)、feature_names、reason。采用 manual-review-v1：每项是显式审阅决策，不宣称观测指标已经校准为旋钮。不得直接把 offbeat_ratio 复制成 rhythm_syncopation 后称为等价量。

音域、密度、最大跳进、和弦和变奏硬约束交给 PlanningRequest，不塞进 StyleConstraints。无法合理决定时停止并请求具体偏好，不能凭来源标签补默认风格。

调用 build_profile(report, profile_id=opaque_id, decisions=decisions)，再 validate_profile(profile, report=report)。profile v1 无反馈、无用户覆盖；没有实际试听不能记录 LISTENED_OK。来源研究只决定候选偏好，不扩大 Runtime 能力。
