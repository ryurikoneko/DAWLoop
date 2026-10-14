# Basic Pitch 独立组件候选

这是应用内安装的可选 ONNX 组件，使用官方 Python 3.14.8 原件及固定官方 wheel。软件及分析组件没有共享活动 Python 环境。

Basic Pitch 0.4.0 原始包的通用依赖声明包含 TensorFlow。本候选是独立验证的 ONNX 运行变体，不宣称通用 pip 依赖解析通过，也不安装 TensorFlow。

组件清单保留每个原件地址、版本、SHA-256、原始许可及逐文件摘要。Python 和已有依赖的通知及源码提供方式继承 `../desktop-runtime`。新增依赖的许可证原文与 SBOM 放在本目录。

兼容补丁仅将 resampy 的资源定位改为标准库 importlib.resources，并使 audioread 在 Python 已移除 aifc/audioop/sunau 时跳过不可用的旧解码器。滤波器、重采样算法、Basic Pitch 模型及音符推理算法没有修改。实际 WAV 通过经过审阅的 libsndfile 解码。未使用的 SoundFont 和命令行入口没有进入组件包；排除记录及原件摘要保留于 component.json。

原生文件与官方 wheel 一致，已补齐完整通知、Eigen 源码及微软运行库独立条款；详细逐文件结果见 NATIVE_INVENTORY.json。组件可用于 Alpha.2 预发行草稿，公开发布仍等待维护者最终确认，通知保持关闭。安全检查限定于固定模型和已检索的版本，未声称所有二进制没有漏洞。
