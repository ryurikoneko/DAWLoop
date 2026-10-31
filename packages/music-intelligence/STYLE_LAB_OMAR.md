# Style Lab：复用 OMAR-RQ

Phase 2 在原 `model-worker.py` 的已审核模型读取协议上增加窗口索引、检索和研究界面，不另建模型推理实现。

## 数据路径

本地 StyleLab SQLite → `VectorLab.plan` → 受管 OMAR Python / 原 model-worker → 窗口 NPY + 来源元数据 → 5秒检索描述 → 偏好反馈及片段画像。

`style-omar-host.py` 只包装原 worker 的结果发送，增加进程内资源计数；原权重核验、安全加载、重采样、L6提取、25Hz和10GiB门不变。Windows venv存在多层启动器，不能把外层PID的工作集当作推理内存。

## 研究 API

在现有基础音频环境中：

```python
from style_lab import StyleLab
from style_omar import VectorLab

lab = StyleLab(PRIVATE_RESEARCH_ROOT)
vectors = VectorLab(lab, EXISTING_MANAGED_MUSIC_RUNTIME)
vectors.plan([asset['id'] for asset in lab.search()])
vectors.run()  # 只计算未READY窗口；maximum可限制本次窗口数
segments = vectors.descriptors()
matches = vectors.search(segments[0]['id'], scope='cross')
groups = vectors.clusters(k=4)
```

中断后先调用 `vectors.recover()`，确认所属worker已不存在后回队PROCESSING窗口；READY缓存保留。运行仍持有独立锁，不能并发启动多个观察任务。此研究入口不接受Renderer任意Python代码或宿主操作。

## 时间与比较

30秒窗、25秒步长、5秒重叠；尾段不足5秒时由上一窗覆盖，否则保留尾窗。每窗完整float32帧向量、25Hz全局时间网格和原始摘要保留。检索描述为非重叠归属区间内5秒均值再L2归一化；不能以整曲平均替代原序列。

只对相同版本比较。版本包含模型revision、层、分窗策略与原worker代码摘要；记录保留原音频SHA、区间及向量SHA。当前历史缓存运行环境见对应执行记录；不把后来升级的环境版本回写为旧计算环境。相同缓存重复检索保持稳定排序；同曲排除相距小于15秒的片段。余弦值未校准为音乐相似概率。

聚类为确定性球面k-means，均匀初始化、25迭代，不生成流派、乐器、情绪等语义标签。正负反馈为公开显示的±0.05排序调整，原始余弦另存；它不是神经网络学习。喜欢的片段画像保存具体向量片段引用和版本，与原DSP画像及提示词历史并存。

## 主窗口操作

Music Intelligence → Style Lab → 打开已完成计算的研究目录 → 选择参考片段 → 同曲/跨曲搜索 → 双方试听 → 喜欢/不喜欢 → 保存片段画像。首次向量批处理仍由研究API完成，当前GUI不自动启动整库模型计算。

仅新增 `styleOpen/styleSearch/styleFeedback/styleProfile/stylePreview` 五个显式music操作，沿用主进程来源校验。用户通过系统目录选择器授权研究库，音频只由主进程发放既有流式预览许可，Renderer不能传任意读取路径。关闭后回收本功能所属进程。普通界面展示歌曲、时间和操作，不展示向量JSON或调试日志。

## 验收解释

历史24秒600×1024证据必须与当前推理分别报告。当前工程验收、媒体实际播放、人工听审和音乐检索质量是不同结果；自动播放不能替代人类判断。权重许可沿用已有记录，私人研究产物不提交，不随新内部候选分发模型环境或权重。

下一模型决策先依赖盲听与正负样本：向量替代方案必须证明额外检索收益；文字语义模型用于补文字与音频关联；结构/和弦分析器补显式时间事件。未经验证不增加模型数量。


## Phase 3 整曲研究

当前分支新增style_batch.py递归扫描MP3/WAV/FLAC，完整解码后按源SHA与解码PCM身份记录；有损重编码的同录音关系未确认，不凭文件名合并。文件名合作/Remix/Instrumental线索保留为待确认字段。各曲分别验收DSP、向量覆盖与结构，单曲失败保留原因。

style_structure.py按原始采样数合并窗口区间，检查逐帧时间格和尾端，不完整拒绝整曲报告。tailgrid2只对短尾窗填充额外上下文，再按原始时长裁回；填充不是歌曲内容。旧向量保留，完整30秒窗可复用。结构使用1秒向量、曲内中心化、8秒棋盘新颖性与12秒候选间隔，重复关系仅排名候选，不强命名Verse/Chorus/Drop。自动结构不等于人工验证真值。

主窗口WholeSong支持完整时间轴、缩放、范围试听/跨曲检索、段落扩展试听及连续边界编辑，原自动结构JSON不覆盖，用户编辑另存SQLite。边界改变后旧段落测量置空待刷新，防止给新范围展示旧测量。全曲描述与编辑版本均保存来源，不能用五秒局部结果代替完整歌曲提示词。语义乐器、情绪、编曲及和弦当前留空；局部节奏为低置信度候选。

全库入口：使用已配置音频Python导入style_batch.batch(PRIVATE_ROOT, AUDIO_FOLDER, MANAGED_RUNTIME)。OMAR阶段复用常驻模型；可通过本次报告目录CANCEL标记请求在当前窗口结束后取消，已READY窗口保留；恢复时只排未完成窗口。不承诺窗口内实时取消或断电全流程已验收。

## Phase 4 检索对照与盲听

`style_quality.run_experiment(vectors, PRIVATE_PHASE4_ROOT)`读取已有完整帧序列及EXPERIMENT_PLAN.json，只写独立研究结果。七种方法比较均值余弦、显式L2、逐帧归一化再平均、中位数、均值加标准差、当前库中心化及有顺序的1秒子序列。L2与原余弦数学等价，不能当成质量改进。中心化只拟合当前库，不能据此宣称泛化。

438个完整5秒实验窗与448个生产检索片段不同：10个不足5秒的尾片段仅不进入等长对照，原始尾部向量仍保留。不同窗宽和重叠的Top5、分数分布与整曲相对位置序列另存。跨曲查询不含本曲；同曲候选要求区间间隔至少15秒，且原始模型推理上下文没有交集。相邻或共享上下文对只作诊断，不作正样本。当前没有人工正负真值，Precision/Recall保持null。

研究目录`phase4/audition-pairs.json`固定16组，每类4组：跨曲高分、同曲不同候选段、随机跨曲、低分跨曲。主窗口Style Lab → 打开研究资料库 → 打开听审清单，可盲听A/B并保存六项评价，再按需展开歌曲、时间和原始分数。清单不足或缺失时显示错误，不生成替代样例。评分与展开事件追加到SQLite `audition_events`，绑定清单内容摘要；先展开后评分会注明非盲，不覆盖清单和原分析。自动化验证只写隔离TEST_FIXTURE库。

仅增加四个显式music操作`styleAuditionList/styleAuditionPreview/styleAuditionRate/styleAuditionReveal`，无任意路径读取、通用Python或宿主操作。试听沿用主进程受控音频许可，切组/退出释放旧许可。结果页继续保留原始自动结构及独立人工边界编辑；技术连续性通过不代表96段的音乐正确性通过。

静音、独立纯音和独立噪声使用同一固定模型真实推理。中位数变化、排名改变或测试通过不等于听感检索改善。此阶段不切换生产排名，不安装其他模型；后续先完成固定清单听审及额外真实异风格对照，再决定是否试验其他层或模型。

## Phase 5 有上下文的个人听审

`style_listening.prepare(vectors)`从既有Phase4清单和完整缓存生成独立`phase5/study.json`，已存在时拒绝覆盖。保留13对原锚点，补3对跨曲中等分数；4高/3中/3低/3随机/3同曲不同候选段。每侧默认20秒上下文，临近结尾平移区间，A/B保持等长；可延长40秒或播放整首，不改变五秒模型锚点及原始分数。此入口不运行OMAR推理。

复用听审API及组件，增加`styleAuditionSummary`和`styleAuditionLeaveBlind`两个显式本地操作。普通界面聚焦盲听，其他整曲信息仅在离开盲听后显示。后端在本组评价保存前拒绝揭示来源；保存可以包含无法判断，必须明确确认已完成本组评价。离开盲听会记录来源暴露，之后的评价不计入盲评关联。原Phase4事件/清单保留，不把旧三档评价转换为新五档。

### 评分与个人画像合同

`ListeningRating`（shared music-contracts）包含六项相似程度overall/rhythm/drumsBass/melodyHarmony/timbre/arrangement，以及独立enjoymentA/B、referenceA/B，均为1–5或null；另有preference（a/b/both/neither/unknown）、notes（用户描述，最多2000字）、reviewed（明确确认）。相似度低但两段都喜欢是合法组合，不能互相代替。

SQLite `listening_events(id,study,pair,kind,body,created)`追加保存PREVIEW_REQUEST、RATING、REVEAL及RESEARCH_EXPOSURE。study绑定清单字节摘要；评分保留模型分数、五秒作用范围、请求过的试听范围及揭示前后状态。请求过播放不证明已经听完。重启恢复最新评分，旧评分及原始分析不覆盖。

`auditionSummary`从当前清单最新评分生成独立个人画像投影，profileId绑定清单与评分事件ID。保留sourceRatingEvents、references、userDescriptions、associations、wholeSongPreferences、characteristics。喜欢程度和参考价值均≥4的项目进入个人参考清单，范围引用实际请求的试听区间，未请求时明确标记默认上下文。整曲喜好及节奏/Bass/音色等语义解释没有证据时保持null，不从歌曲名、艺术家或高模型分数补写。画像可由持久事件重建，不依赖运行内存。

六维相似评分与原始模型分数采用含并列秩的Spearman作描述性比较，仅使用揭示前的最新评价；不足3条、常量评分或缺失时结果null，逐维报告实际样本数。20/40秒或整首听感与五秒模型锚点作用范围不同，事件中的previewRequests用于后续分层分析；相关性不证明普遍音乐理解，不训练权重。

### 异风格对照导入方案（未执行）

使用单独研究根及独立SQLite、解码缓存和向量目录，清单记录`corpusRole: CONTROL_ONLY`、用户手动选择文件、sourceSha256、作品/发行版本及用户确认的类型。不得自动扫描其他目录。通过既有StyleLab/完整DSP/VectorLab批处理逐曲运行，复用同一受管模型环境和相同算法版本，验证完整音频覆盖及缓存后才能用于质量对照。失败逐曲保存；字节/PCM去重，跨编码同录音待确认。该库只进入检索评价数据集，不进入目标研究画像或个人创作引用，除非维护者另行明确选择。先等待维护者提供5–10首作品，不下载音乐，不启动这批任务。

### 后续创作接口方案（未连接Composer）

```json
{
  "schemaVersion": 1,
  "state": "DRAFT_SELECTION_ONLY",
  "preferenceProfileId": null,
  "studySha256": null,
  "references": [
    {
      "role": "drumsBass",
      "assetId": null,
      "sourceSha256": null,
      "range": null,
      "ratingEventIds": [],
      "userApprovedDescription": null
    }
  ],
  "creativeConstraints": {"tempo": null, "harmony": null, "structure": null},
  "userEdits": [],
  "generatedPrompt": null
}
```

role仅允许wholeSong/section/drumsBass/melodyHarmony/timbre/arrangement。整曲引用需要额外的明确整曲评价或选择，不能从20秒评价推出。下游只消费用户选择的来源、范围和可解释描述，不附原音频、不默认要求模仿艺术家、不生成最终提示词；后续需要单独接入Suno等工具，当前无上传或外部调用。
