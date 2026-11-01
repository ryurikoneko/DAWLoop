# 动态编曲研究合同

## 来源与复用

复用 Style Lab 原资料库、全曲结构缓存、Phase6个人画像和 Phase7 版本化实验。`style_arrangement.py` 仅准备草案并读取可选候选；不加载模型、不执行音频任务。`tools/prepare-arrangement.py` 只向新的 `phase7.1` 目录写入，不更新原实验库。原 A/B/C 比较仍保留原条件，不把新版开场草案伪装成同一实验的修订。

## 数据结构

候选 `schemaVersion: 1` 包含 `references`、`preferences`、`proposals`。

- 每首参考记录原 `asset/sourceSha256`、全长、原分析文件与候选首段范围。
- `entryTimes` 保存 vocals、melody、bass、kick、drums、mainTimbres、coreMotifEstablished；无可靠观察为 null。
- `introTypes` 是多选数组，允许空数组；Motif-led、Atmosphere-led、Groove-led、Vocal-led、Texture-led、Hybrid 只是研究分类。
- `candidateOpeningRange` 不是已确认 Intro。补充完整 Intro 边界与人耳时间标注后才能分类；本轮不拿结构首段、能量或余弦代替声部识别。
- 后续声部观察应保存 `asset/sourceSha256/range/field/value/method/modelRevision/validationStatus`；未知模型版本保持 null。分类依据必须引用观察，不根据名称或相似度自行产生。
- 个人负面偏好独立保存来源与适用范围；正向偏好保留原 `sourceRatingEvents` 和 claims。没有训练权重，不把整曲喜好归到所有声部。
- 每个草案 `parts` 分为 direction、language、arrangement、preferences，分别对应方向、声部关系、编曲行为和用户选择；`sections/structurePlan/lyrics` 同源生成，标签顺序一致。

当前三套是维护者方向驱动的创作选择，不是参考歌曲分类。旋律、氛围与律动开场都有可解释的进入与交接行为；没有强制每首使用九段。后续作品选择可以采用其他类型或混合类型，不自动择优。

## Suno 对照

风格栏使用简短音乐语言，歌词栏负责明确段落。避免重复负面口令；以“先建立音乐动机、稳定开场鼓组、连贯过渡”表达偏好。提示词长度与段落标签符合软件合同不等于平台遵循效果已验证。

原 A 组保留。新一轮记录平台实际版本、共同歌词、人声、BPM、时长、生成日期与批次；未知 seed 为空。若检验 Intro，只替换开场行为并固定下游段落；三套完整方案的比较属于多变量整体方案比较。每套少量重复，人工分别评价开场、旋律建立、Verse衔接、全曲发展与喜爱程度，不自动填分。记录实际生成中各声部进入和偏离位置，保留失败样本。未生成前效果待验证。
