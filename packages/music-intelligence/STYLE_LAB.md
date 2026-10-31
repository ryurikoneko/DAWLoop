# Style Lab Phase 1

本地研究入口，基于公开 Alpha.2 独立分支；不替换已发布 Desktop，不改变原分析、转录、Piano Roll 或 MIDI 路径。

## 运行

使用已有受管音频解释器运行 `style_lab.py --root PRIVATE_DATA_ROOT --folder AUDIO_FOLDER --limit 3`。运行目录必须置于仓库外。当前 CLI 按文件名排序取小批量，不能视为随机或有代表性的艺术家抽样。原始文件只读；MP3/WAV 经现有 soundfile 解码为本地 FLOAT WAV，再由原 song-dsp.py 测量。未安装依赖时拒绝执行，不下载模型或调用网络。

`StyleLab` 提供 import_audio/search/enqueue/run/cancel/retry/recover/rate/create_profile/summarize/save_prompt。根目录内 SQLite 保存资产、任务、评分、多个画像及提示词版本，原分析 JSON 独立保留。内容 SHA 去重；相同内容改名不新增分析，画像追加资产只需对新增资产 enqueue。当前内容去重不是跨编码声学指纹。评分影响加权统计与提示词；词句偏好标明用户输入，不是模型发现。

单 worker，单曲默认180秒超时，解码缓存默认2GiB，沿用原7200秒、8通道预算。progress 来自真实解码帧；断点不假装 READY，recover 只在无活跃 worker 时标记 INTERRUPTED，再由 retry 排队。缓存需手动管理，目前没有自动淘汰。内存未实施操作系统硬上限，不将流式解码说成硬内存隔离。

## 分析合同

- A：复用 SONG_DSP_1、librosa、频谱、RMS、响度及低置信度速度/调性候选，保留算法版本和时间范围。
- B：仅提供 RMS 相邻变化候选；不将其宣称为已识别主歌/副歌。重复结构、和弦与节奏模式尚未实现。
- C：NOT_EVALUATED。Essentia 的库、模型及依赖分别存在许可条件，不能直接纳入当前 MIT 分发。CLAP 代码 LICENSE 标示 CC0，不代表所有权重或数据自动相同许可；具体 checkpoint、中文音乐标签效果及本机资源仍须验收。本阶段未下载或运行这两个模型。
- D：独立保存整曲/片段评分、喜欢与避免因素。只有覆盖分析区间的评分影响该条证据，片段评分不冒充整曲偏好。

统计保持来源任务与区间；缺失速度不填均值。提示词是确定性的、证据驱动的草案，不是已经通过生成工具实验的风格控制器。谱质心等测量不能自动解释为乐器或情绪；结构建议标记为可编辑建议。原音频、缓存、个人评分和样本报告禁止提交。

## Desktop 接入方案

后续在 Music Intelligence 内建立资料库 → 歌曲对比 → 画像 → 提示词四个任务区域，普通界面只显示任务和结果。现有白名单 IPC 增加显式方法，Main 持有文件访问权，Renderer 不接收任意文件路径权限。当前只交付 Python 本地研究 API/CLI，尚未接入 GUI，也没有新增通用执行 IPC。

复用：音频选择/预览、原整曲 DSP、基础环境、版本化分析思想、评分与提示词追加历史。新增 SQLite 仅承载 Style Lab 研究实体，不迁移/覆盖已有音乐库和分析历史。Basic Pitch 不用于混音的乐器/和弦识别；不调用 FL、Controller、AutoMix 或现有项目 Runtime。

官方来源：https://essentia.upf.edu/licensing_information.html 、https://github.com/LAION-AI/CLAP/blob/main/LICENSE 。本机实测素材与详细报告留在私人数据目录。
