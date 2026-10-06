<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2026 ryurikoneko -->
# 多参考比较

输入：ReferenceRecord 列表、ExtractedFeatureSet 列表、明确的 group_id、预先选好的 holdout_source_ids。

核对 source/hash；相同 independent_work_id 不算两个作品。不同 role/section/meter 不混合，不同方法不混桶。不能把 unknown 当零或把空桶补成平均值。单位或定义不兼容时停止，不改写标签假装兼容。

使用 aggregate_features 与 validate_bundle 生成和核对 LearningReport。报告保留样本、覆盖、离散度、排除原因，generalization=NOT_CERTIFIED。不要自行改写程序计算字段。

另外提交自写审阅记录：稳定共性的暂定假设、偶发特征、单曲特例、冲突、适用范围；每条引用 source_id 和具体特征。没有足够证据就说不足。留出材料不参与 profile 推导；实际评估前 holdout_result 保持 NOT_EVALUATED，不把样本数阈值当流派定律。
