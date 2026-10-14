# Basic Pitch 独立组件候选

这是应用内安装的可选 ONNX 组件，使用官方 Python 3.14.8 原件及固定官方 wheel。软件及分析组件没有共享活动 Python 环境。

Basic Pitch 0.4.0 原始包的通用依赖声明包含 TensorFlow。本候选是独立验证的 ONNX 运行变体，不宣称通用 pip 依赖解析通过，也不安装 TensorFlow。

组件清单保留每个原件地址、版本、SHA-256、原始许可及逐文件摘要。Python 和已有依赖的通知及源码提供方式继承 `../desktop-runtime`。新增依赖的许可证原文与 SBOM 放在本目录。

兼容补丁仅将 resampy 的资源定位改为标准库 importlib.resources，并使 audioread 在 Python 已移除 aifc/audioop/sunau 时跳过不可用的旧解码器。滤波器、重采样算法、Basic Pitch 模型及音符推理算法没有修改。实际 WAV 通过经过审阅的 libsndfile 解码。未使用的 SoundFont 和命令行入口没有进入组件包；排除记录及原件摘要保留于 component.json。

新增 ONNX Runtime 原生依赖和漏洞审核尚未完成，所以组件只随内部候选提供，不授权公开分发。新的公开发行与更新通知分别需要维护者批准。
