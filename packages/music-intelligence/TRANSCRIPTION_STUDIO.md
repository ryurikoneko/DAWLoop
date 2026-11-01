# Audio Transcription Studio

内部研究工作台复用现有 MusicIntelligence 模型环境、音频库、受控媒体协议、ModelProcess 和钢琴窗。原 Composer、既有转写接口及宿主桥接合同保持兼容。工作台不自动操作宿主。

## 会话与时间

`transcription-contracts.ts` 的会话版本为1。音符 `start/end`、和弦 `start/end`、tempo `time` 都以原曲秒为单位。`beats` 保留模型实际拍点、拍序及拍号；摘要使用主要拍号，弱起不冒充全曲拍号。钢琴窗边界通过完整 tempo map 转换为拍数，默认不吸附网格。模型预测、标签重建、低音区候选和人工编辑分别保留来源。

五类视图为人声、器乐、参考和弦、贝斯候选、综合。综合是四声部的组合视图与导出项，不参与额外播放。参考和弦标签及实际编辑音符分别保留，编辑音符不等于重新识别和弦标签。原有 `composer-reference.json` 只读；会话的秒轴和弦事件可供后续 Composer 适配，尚未新增自动写入 Composer 的合同。

## 推理和恢复

从受管资源发现或应用已经连接的运行环境解析本地环境；继续执行已有模型文件和环境核验，不下载模型。解码 Worker 显式使用 UTF-8。SheetSage2 原生整曲接口输出原始事件、LAB、tokens、MIDI；Basic Pitch 用90秒非重叠分段，保留网络输出及音符事件。贝斯只是混音低音区候选。工作台持有模型进程，连续会话可复用加载；取消只终止工作台持有的模型进程。

后台状态报告真实阶段，不捏造百分比。已完成会话去重恢复，不重新推理。异常中断恢复为 `INTERRUPTED`；重试可复用已经完成的原始 SheetSage2/Basic Pitch 文件。源音频通过原有音频库复制导入，不覆盖源文件。

会话目录独立保存 `original.json`、`session.json`、各版本 `edit-*.json`、原始推理目录和导出记录。编辑和重置均建立新版本，原始结果不覆盖。未保存编辑时，拖拽和另存暂停；保存后预生成当前版本的四声部及综合 MIDI，并程序回读核对数量、音高、力度和起止时间。

同音高的重复音发生尾音重叠时，导出分配独立 MIDI 通道，保留两个起止时间；一个逻辑声部可能因此包含多个 MIDI 通道。超过可用通道的同音同时发声数会明确拒绝，不裁短或丢弃音符。旧目录没有绑定模型版本元数据时显示 `UNKNOWN_LEGACY_VERSION`，不根据文件名伪造版本认证。

## 原生文件拖出

Renderer 的 `dragstart` 通过受限 preload 发送会话、轨道、版本和主进程生成的 token。主进程只解析已准备的受管 MIDI，不接受 Renderer 指定导出文件路径。调用 `webContents.startDrag` 发起操作系统文件拖放；另外提供键盘可操作的另存按钮。

依据：[Electron Native File Drag & Drop](https://www.electronjs.org/docs/latest/tutorial/native-file-drag-drop/)。接口启动返回不代表目标接收。

导出位于会话 `exports/<token>/<歌曲>_<声部>-r<版本>.mid`。文件不会在失焦、拖拽结束、切换会话或退出时删除，旧版本也不原地改写；当前策略为持久保留，磁盘占用随已保存版本增长。需要释放空间时由用户在应用关闭后明确管理该会话目录，不由拖拽回调自动清理。

## 本机兼容性边界

2026-11-01：真实人声 MIDI 拖入文件资源管理器成功，接收文件回读256音符；和弦 MIDI 拖入独立空白宿主的 Piano Roll 后出现导入对话框并显示导入事件。Playlist 直接拖入综合 MIDI 未观察到可确认的接收结果，不标记通过。Piano Roll 导入没有自动改变测试工程原有130 BPM，不能据此宣称 conductor tempo map 已进入宿主；完整节奏恢复应使用宿主完整 MIDI 导入路径并复核 tempo。

内部候选不包含模型权重，不代表 SheetSage2 获得商用发行许可。音乐准确性、尾音正确性及声部真实分离仍未通过人工听审。
