# DAWLoop Desktop 开发骨架

[KNOWN｜HIGH] 第一批安全壳层，默认真实只读观察。当前不是完整第一阶段 PASS，也不是无需开发环境的普通用户安装包。真实 Runtime 生命周期、FL 版本与 RPC 连通性未取得可靠接口时显示 Unknown；真实启停按钮禁用。Mock 状态始终标记 DEVELOPMENT MOCK。

## 启动

[COMPUTED｜HIGH] 开发入口是 `npm.cmd start` 或仓库根目录的 `start-desktop.bat`。双击批处理会先检查 Node.js/npm，从脚本自身位置进入项目；缺少依赖时按锁文件安装，缺少 Electron 二进制时显式下载，再检查 TypeScript、构建 renderer 并显示原生窗口。下载失败、环境缺失或构建失败会显示原因并返回失败，不安装 Node、不改 PATH 或系统设置。

[KNOWN｜HIGH] 开发需要 Node.js >=22.12 及 npm。Python >=3.11 用于可选真实只读观察；Python 缺失时桌面仍启动，状态为 Unknown。命令行方式进入本目录：

```powershell
npm.cmd ci
npm.cmd start
```

[COMPUTED｜HIGH] `package.json → scripts/dev-launcher.mjs → Electron electron/main.mjs → sandboxed preload.cjs → dist/index.html → React` 是实际启动链。源码 `index.html` 引用 TypeScript，构建后的 HTML 依赖 Electron preload 提供的 `window.dawloop`；它们都是渲染资源，不能作为软件入口直接双击。

[COMPUTED｜HIGH] 普通用户候选入口是便携目录中的 `DAWLoop.exe`。本轮仅交付内部 Windows x64 壳层候选，自带 Electron/Node，不需要用户安装 Node/npm；没有安装器，Python 与完整宿主 Core 不包含在内，真实连接仍不可用。批处理继续是开发入口。

[KNOWN｜HIGH] 若二进制下载受网络限制，可按 Electron 官方安装说明显式使用镜像，保留包内 checksums：

```powershell
$env:ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/'
node node_modules/electron/install.js
npm.cmd start
```

[KNOWN｜HIGH] 可通过 `DAWLOOP_PYTHON` 指定可信 Python 可执行文件。观察器使用参数数组，不经过 shell。默认启动不显示开发后端选择器，主进程拒绝 Mock 控制 IPC。仅未打包应用显式使用 `npm.cmd start -- --dev`（真实后端起步）或 `npm.cmd start -- --mock` 才启用开发控件；打包应用忽略这两个开发标志。启动偏好、实验开关和验证预设仍仅持久化。

## 语言

[COMPUTED｜HIGH] 设置 → 通用 → 语言提供 `简体中文 / English`。选择成功保存后立即生效，不要求重启；保存失败保留原语言。配置为 Roaming `DAWLoop/config/desktop.json` 中的 `ui.language`，独立于 Profile。优先级是显式 `zh-CN / en-US` → Windows 系统 locale → English；系统 `zh-CN / zh-SG` 默认中文，其他 locale 默认英文。旧配置没有 `ui` 时兼容，不因为系统语言改变覆盖已保存选择。

[COMPUTED｜HIGH] `locales/{zh-CN,en-US}` 按 common/home/settings/profiles/verification/mixer/diagnostics/logs 分为八个命名空间，使用 i18next/react-i18next。主进程托盘和对话框复用资源。新增文案进入对应资源；新增 reason/error code 在 common 注册展示文本，内部机器码保持。禁止跨语言回退。显式开发模式缺键显示 `[missing:key]`；普通模式使用调用处明确的默认文本，无默认文本时显示基础英文 `Text unavailable`。空字符串同样按缺键处理；资源键对称测试防止遗漏。品牌/协议、用户内容、原始诊断 JSON 和复制出的机器日志不翻译。

## 验证

```powershell
npm.cmd run build
npm.cmd test
npm.cmd run test:smoke
npm.cmd run test:launch
```

[KNOWN｜HIGH] smoke 使用临时用户数据（含 Electron 浏览器数据）与隐藏测试窗口，运行完关闭所属进程并删除自己的临时目录。覆盖真实 Electron IPC、Mock 状态、启停、Profile 切换、设置跨重启恢复、诊断复制/脱敏和日志清空视图；缺少 Python 时不崩溃，最后运行真实只读观察。截图与结构化结果位于忽略的 `test-results/`；测试不启动 FL、不安装脚本、不发送 MIDI/RPC，不包含插件参数或音符写入接口。

[COMPUTED｜HIGH] `test:launch` 通过真实 `npm.cmd start` 和从其他目录调用绝对路径批处理启动可见窗口，依次验收中文启动、当前窗口切英文、英文重启保持、中文重启保持；两种语言各七页面在正常/最小窗口检查布局。显式测试环境开启本机临时 CDP 端口，普通启动不开调试端口。原生窗口加载成功后才显示；构建辅助进程隐藏，Electron 自身正常显示。

## 模块与存储

[KNOWN｜HIGH] Renderer 仅调用 sandboxed preload。Electron main 校验请求来源、限制大小，使用独立 Renderer 方法白名单；Core 新增方法不自动获得桌面权限。`DesktopMethodMap` 约束方法、参数与结果，运行时仍由主进程和服务校验。`packages/app-core` 分开 Config/Profile 修改队列与 Runtime/后端控制队列，只读请求独立运行；状态并发请求共享同一进行中的观察。日志追加自身串行，诊断白名单导出原子写入。设置保存完成即恢复按钮，后台状态/日志刷新不延长保存等待；旧状态请求不能覆盖更新后的请求。忙碌状态按页面计数，诊断等待不锁住其他页面设置。Python observer 只复用现有公共只读检查，不导入 CLI 或 Runtime 私有执行函数。

[KNOWN｜HIGH] Roaming 保存 `DAWLoop/config/desktop.json`、`DAWLoop/profiles/*.json`；Local 保存 `DAWLoop/logs/desktop.jsonl`、`DAWLoop/diagnostics/latest.json`。不写 repo 配置，不修改 CLI 旧 config.json。`DAWLOOP_DESKTOP_DATA_ROOT` 仅用于测试/开发重定向；无此变量时使用系统用户目录。升级前备份 v0 原字节；v1 保留未知字段，未来版本拒绝覆盖。

[KNOWN｜HIGH] 损坏配置不会重置。可在 Diagnostics 导出错误报告，退出软件后修复原文件或恢复 `.bak`；修复前的状态保持 Unknown。切换 Profile 只切换持久化偏好，不把它报告为 Core 策略已应用。日志读取最近 256 KiB、展示最近 500 条；当前记录 Desktop/Mock Runtime 事件，Core 实时日志订阅后续接入。

[KNOWN｜HIGH] 架构审计、技术取舍、迁移阶段及未完成项统一记录在 [运行时工作文档](../../docs/DAWLOOP_RUNTIME_V2.md#current)。最终安装器、捆绑 Python、更新器和真实启停需要后续独立验收。

## Adapter 迁移边界

[KNOWN｜HIGH] RealAdapter v1 是 one-shot observer：每次新的状态观察启动一次 Python，经 stdin/stdout JSON v1 返回后退出。共享进行中的状态读取不是长期服务，也不是实时 Mixer 通道。confidence 合同支持 high / medium / low / very-low / unknown；扩展可表达范围不升级当前能力证据。

[KNOWN｜HIGH] Phase 1.4A 复用常驻 AppCore 内部 Publisher 与只读 Adapter，getWorldSnapshot 不再启动 Python；独立 Python Core 的跨进程握手/RPC 尚未实现。后续跨进程接入必须先确认来源、代次、取消、断开恢复及能力授权，Desktop 不导入 Mixer 私有实现。Core reason/error 永远机器码，i18n 留在 Desktop presentation；Config/Profile 偏好不冒充 Runtime 配置已应用。Diagnostics 坚持白名单导出优先，redact 仅为第二道防线。

## 只读世界消费

[COMPUTED｜HIGH] Home 展示 Session/Target，Mixer 支持轨道、API Slot 索引与只读 Plugin Inspector，Diagnostics 展示晋级阶段及证据。Phase 1.4A 已建立离线 Core 发布接口；当前未注册真实 Mixer 来源，默认只有已有本地观察范围，高级数据不可用，真实宿主验收未执行。

[KNOWN｜HIGH] 普通/打包模式拒绝 DAWLOOP_CORE_WORLD_SNAPSHOT 文件声明进入真实链；仅显式 --dev 可读取开发样例，世界标为 Development Mock。真实链仅接受 Core 内部注册来源的验证器通过、当前绑定一致且属于同一 Publisher 代次的不可伪造进程内发布凭据；复制 JSON 不继承归属。该凭据不是宿主认证或跨进程签名。合同与来源责任见 packages/core-snapshot/README.md、packages/shared-types/contracts.ts；15秒时效、逐级晋级和只读白名单共同决定数据可见性，写入永不晋级。

## Windows 便携构建

[KNOWN｜HIGH] 当前公开 Alpha 的基础组件、许可、来源与首次运行范围见 [Desktop Alpha 指南](../../docs/DESKTOP_ALPHA_BUILD.md)。下方早期内部候选说明保留其历史上下文，不能代替当前发行清单。

[COMPUTED｜HIGH] 按锁文件准备本工作树的开发依赖后，在 Windows x64 执行以下命令。输出必须是工作树外尚不存在的绝对目录；不覆盖历史产物。打包脚本先检查 TypeScript、构建 renderer，再组装 Electron、main/preload、资源、Desktop 服务与 i18next 主进程依赖，生成逐文件 SHA-256 清单和 build-record.json。采用 [Electron 官方手工分发布局](https://www.electronjs.org/docs/latest/tutorial/application-distribution)，没有新引入打包框架。

```powershell
npm.cmd run pack:portable -- D:/DAWLoop-build/new-candidate D:/DAWLoop-build/basic-audio-1.1.0-alpha.1-win-x64.zip
node ../../tools/verify-portable.mjs D:/DAWLoop-build/new-candidate
```

[COMPUTED｜HIGH] 首次启动提供中文/英文选择、本地 FL 可执行文件存在检查及仅使用桌面功能的跳过入口。文件存在不等于版本、授权、连接或会话身份通过。Controller 仅检查配置/default Settings 中两项文件是否存在，状态为 present-unverified / not-found / unavailable，不声称 Controller 已加载。没有扫描、安装脚本、修改宿主或自动调用后续现场操作。

| 依赖 | 当前候选策略 | 分发材料 / 待完成事项 |
| --- | --- | --- |
| Electron / Chromium / Node | 随候选提供；固定 Electron 44.6.0 | 保留 LICENSE 和 LICENSES.chromium.html；未签名 |
| React / i18next 与生产传递 JS 依赖 | renderer 资产内或固定主进程目录 | MIT 原文收集到 licenses，版本与锁文件匹配 |
| Desktop AppCore | 只包含本工作树的壳层服务 | 保留项目 LICENSE/NOTICE；不包含 AutoMix 活动源码或 Session A 冻结包 |
| Python / 完整 Python Core | 不捆绑，当前普通候选不会使用 PATH/PYTHONPATH 或开发 Python 覆盖变量 | 真正接入前另交付固定 runtime、完整依赖及逐项许可清单；仅用户安装 Python 尚不足以启用本候选 |
| Controller | 用户的既有安装，候选不部署 | 存在检查不能替代版本、摘要、来源和宿主加载验证 |
| FL Studio / 第三方插件 | 用户自行安装，候选不分发 | 按对应产品授权条件使用；本候选不携带安装文件或 fixture |

[KNOWN｜HIGH] Python 未来分发需要保留其许可及捆绑组件的独立许可材料，不能只写一个 PSF 标签；参见 [Python 3.12 许可原文](https://docs.python.org/3.12/license.html)。宿主分发边界参见 [FL Studio EULA 原文](https://www.image-line.com/image-line-software-eula)。这些是后续来源审计输入，本轮没有打包这些产品。

[COMPUTED｜HIGH] build-record.json 记录软件版本、内部渠道、Git 提交/脏工作树、锁文件、构建工具版本及实际输入摘要；清单验证拒绝非法路径、缺资源、额外文件和字节变化。候选启动日志仅记录白名单依赖状态、版本与机器码，诊断继续脱敏。普通候选忽略 --dev/--mock，拒绝 --core-session-spec，不从活动开发树补充 Python 模块。真实 Session A 仍从原冻结统一入口执行，需要新的现场授权。

[KNOWN｜HIGH] 这是可解压运行的分发目录，配置和日志仍写 Windows 用户目录，不是配置随 U 盘迁移的完整便携模式。构建可比较相同输入下的逐文件字节；不承诺 ZIP 元数据或不同工具链产物一致。清空 PATH 的原生启动模拟不等于真实干净 Windows 验收；安装流程、代码签名、安全软件兼容性、升级与完整 Core 交付仍待验收。
