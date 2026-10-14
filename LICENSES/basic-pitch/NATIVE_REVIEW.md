# 三个原生文件逐项审核

三个文件均属于官方 ONNX Runtime 1.31.0 Windows x64 CPython 3.14 wheel，字节未修改。主许可 MIT，完整上游第三方通知随包保留；Eigen MPL-2.0 对应源码、补丁和源码获取说明随包提供。主 MIT 许可未要求提供整个 DAWLoop 源码；涉及第三方的义务分别履行，不将原生库统一重新许可为 MIT。

## onnxruntime/capi/onnxruntime.dll

- SHA-256: `90497e3d406c09f4d59d364c696a2f93dc02f6ef13741b3b89eec95bdb4a3806`
- 官方发行来源: https://files.pythonhosted.org/packages/6a/66/0bf4fdb9f58efa69cf4eddde24c72aebcc628d6ff1d67c9546145c6b9922/onnxruntime-1.31.0-cp314-cp314-win_amd64.whl
- 直接动态依赖: KERNEL32.dll, ADVAPI32.dll, MSVCP140.dll, MSVCP140_1.dll, api-ms-win-core-path-l1-1-0.dll, dbghelp.dll, SETUPAPI.dll, dxgi.dll, VCRUNTIME140_1.dll, VCRUNTIME140.dll, api-ms-win-crt-heap-l1-1-0.dll, api-ms-win-crt-runtime-l1-1-0.dll, api-ms-win-crt-math-l1-1-0.dll, api-ms-win-crt-stdio-l1-1-0.dll, api-ms-win-crt-convert-l1-1-0.dll, api-ms-win-crt-string-l1-1-0.dll, api-ms-win-crt-locale-l1-1-0.dll, api-ms-win-crt-time-l1-1-0.dll, api-ms-win-crt-filesystem-l1-1-0.dll
- 延迟动态依赖: SHELL32.dll
- 源码与修改: 二进制无修改；上游版本源码、依赖锁与 Eigen 源码/补丁可取得，见 OFFICIAL_SOURCE_OFFER.md。
- 再分发: 保留主版权与许可原文、完整第三方通知；微软 DLL 独立适用微软条款。
- 安全维护: 当前官方1.31.0版本，九个新增固定PyPI版本本轮OSV查询无匹配；并非所有原生静态依赖安全认证。仅加载固定模型摘要，导入前关闭遥测，模型初始化前再调用官方关闭API。
- 未知项: 上游每个对象文件的静态链接映射和二进制可复现构建未独立复现；未把缺失证据当作违规。
- 结论: PASS_WITH_NOTICES_AND_SOURCE。

## onnxruntime/capi/onnxruntime_providers_shared.dll

- SHA-256: `a4d7ae5309da67ae6894977e6c1a6aecc002ad63b13f1123ae582b75ba2f8b30`
- 官方发行来源: https://files.pythonhosted.org/packages/6a/66/0bf4fdb9f58efa69cf4eddde24c72aebcc628d6ff1d67c9546145c6b9922/onnxruntime-1.31.0-cp314-cp314-win_amd64.whl
- 直接动态依赖: VCRUNTIME140.dll, api-ms-win-crt-runtime-l1-1-0.dll, KERNEL32.dll
- 延迟动态依赖: 无
- 源码与修改: 二进制无修改；上游版本源码、依赖锁与 Eigen 源码/补丁可取得，见 OFFICIAL_SOURCE_OFFER.md。
- 再分发: 保留主版权与许可原文、完整第三方通知；微软 DLL 独立适用微软条款。
- 安全维护: 当前官方1.31.0版本，九个新增固定PyPI版本本轮OSV查询无匹配；并非所有原生静态依赖安全认证。仅加载固定模型摘要，导入前关闭遥测，模型初始化前再调用官方关闭API。
- 未知项: 上游每个对象文件的静态链接映射和二进制可复现构建未独立复现；未把缺失证据当作违规。
- 结论: PASS_WITH_NOTICES_AND_SOURCE。

## onnxruntime/capi/onnxruntime_pybind11_state.pyd

- SHA-256: `79e2eaa9c4a8ba3d0ad2ded05448ddb7bc1c9168c52d1991ece3a9b80894b04b`
- 官方发行来源: https://files.pythonhosted.org/packages/6a/66/0bf4fdb9f58efa69cf4eddde24c72aebcc628d6ff1d67c9546145c6b9922/onnxruntime-1.31.0-cp314-cp314-win_amd64.whl
- 直接动态依赖: python314.dll, KERNEL32.dll, ADVAPI32.dll, MSVCP140.dll, MSVCP140_1.dll, api-ms-win-core-path-l1-1-0.dll, dbghelp.dll, SETUPAPI.dll, dxgi.dll, VCRUNTIME140_1.dll, VCRUNTIME140.dll, api-ms-win-crt-runtime-l1-1-0.dll, api-ms-win-crt-string-l1-1-0.dll, api-ms-win-crt-heap-l1-1-0.dll, api-ms-win-crt-stdio-l1-1-0.dll, api-ms-win-crt-filesystem-l1-1-0.dll, api-ms-win-crt-math-l1-1-0.dll, api-ms-win-crt-convert-l1-1-0.dll, api-ms-win-crt-locale-l1-1-0.dll, api-ms-win-crt-time-l1-1-0.dll
- 延迟动态依赖: SHELL32.dll
- 源码与修改: 二进制无修改；上游版本源码、依赖锁与 Eigen 源码/补丁可取得，见 OFFICIAL_SOURCE_OFFER.md。
- 再分发: 保留主版权与许可原文、完整第三方通知；微软 DLL 独立适用微软条款。
- 安全维护: 当前官方1.31.0版本，九个新增固定PyPI版本本轮OSV查询无匹配；并非所有原生静态依赖安全认证。仅加载固定模型摘要，导入前关闭遥测，模型初始化前再调用官方关闭API。
- 未知项: 上游每个对象文件的静态链接映射和二进制可复现构建未独立复现；未把缺失证据当作违规。
- 结论: PASS_WITH_NOTICES_AND_SOURCE。

## 共享依赖与补救

首次审计发现组件没有 msvcp140_1.dll。已按维护者明确确认的 Visual Studio 许可，从正式 Redist 目录取得四个同版本、有效微软签名的运行库 DLL，供应用本地使用。版本与SHA详见 VC_RUNTIME_SOURCES.json。没有复制 System32 DLL，没有系统级安装或注册。许可证和末端用户安装确认独立于软件MIT，全文随包提供。

未采用直接删除库的方案：pybind扩展是实际Python推理入口，删除后无法转录；换用C API仍需要同一CRT。使用现有、已许可的正式运行库补齐依赖可保留既有经过验证的推理路线。

Windows自身API是操作系统前置条件。加载实证将进一步核验四个CRT实际来自组件目录。公开发行等待E2E、清单与Draft核验；当前报告不声称已发布。
