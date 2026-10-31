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
