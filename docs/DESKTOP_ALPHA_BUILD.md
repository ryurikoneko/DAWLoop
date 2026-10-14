# DAWLoop Desktop 0.5.6-alpha.2 - Internal candidate


这是尚未公开发布的补丁候选；现有公开 v0.5.6-alpha.1 ZIP、标签及摘要不变。

This is an unpublished patch candidate. The existing public v0.5.6-alpha.1 ZIP, tag and checksums are unchanged.

## 本候选的 Basic Pitch 首次安装 / First Basic Pitch installation

1. 打开音乐智能 → 组件管理，先确认许可并安装基础组件。
2. 找到 Basic Pitch，展开安装选项，查看 132.6 MiB 组件及至少 1 GiB 可用空间要求，确认许可后点击安装／重试。
3. 安装器离线核验固定包、解压独立 Python 3.14.8／ONNX 环境、执行真实模型健康检查。取消只清理本次暂存目录；已有环境不被覆盖。
4. 导入 WAV，进入音频转 MIDI 与音符编辑，加载转录模型，点击开始音频转 MIDI。审阅和修改音符，再导出 MIDI。

1. In Music Intelligence → Component Manager, review licenses and install basic components first.
2. Expand Basic Pitch installation options, review the 132.6 MiB pack and minimum 1 GiB free-space requirement, confirm the license and choose Install / retry.
3. The offline installer verifies the fixed archive, installs isolated Python 3.14.8 / ONNX and runs real model inference as its health check. Cancellation removes only owned staging files; existing environments are preserved.
4. Import a WAV, open Audio to MIDI & note editor, load the transcription model and start audio-to-MIDI. Review/edit notes, then export MIDI.

仅承诺本轮自有 WAV 的本机隔离用户目录验收；复杂混音不等于完整多轨分离。新增原生依赖公开分发审核仍待完成。许可原文、来源、SBOM 和兼容补丁说明见 licenses/basic-pitch 与组件的 component.json。不得把本候选当作获准公开发行的新版本。

Validation covers an owned WAV in isolated application/component directories on the maintainer's machine, not independent clean Windows. Complex mixes are not complete multitrack separation. Public redistribution review of new native dependencies is pending. Licenses, sources, SBOM and compatibility-patch details are in licenses/basic-pitch and component.json. This candidate is not approved for public release.

本候选通知渠道为 internal，公共通知关闭，不继承维护者对 Alpha.1 Preview 的单版本批准。新的发行与通知需要分别批准。

This candidate uses the internal channel with public notifications disabled. It does not inherit the one-version Alpha.1 Preview approval. A new release and its notifications require separate approval.

以下保留 Alpha.1 使用与构建来源说明作为历史参照，转录首装限制不适用于本次已包含可选转录组件的内部候选。

The Alpha.1 usage/build notes below are retained as historical reference. Their first-transcription-install limitation does not apply to this internal candidate with the optional transcription component.

Experimental Alpha — Tested on maintainer's Windows environment. Clean Windows compatibility has not been independently verified.

## 使用 / Use

解压 Windows x64 Portable ZIP，双击 `DAWLoop.exe`。无需 Node、Codex 或系统 Python。进入音乐智能后，在组件管理中查看随包许可，确认“安装基础组件”。组件仅安装到用户数据目录，不修改 PATH、系统 Python、FL Studio 或原始音乐。

Extract the Windows x64 Portable ZIP and run `DAWLoop.exe`. Node, Codex and system Python are not required. In Music Intelligence, open Component Manager, review the bundled licenses and confirm installation of basic components. Components are installed in the user's data directory without modifying PATH, system Python, FL Studio or source music.

本包基础分析支持 WAV。导入后可播放、分析、查看报告并主动保存；规则式旋律创作、Piano Roll 编辑和 MIDI 导出不需要新增模型。临时导入不会自动成为永久音乐库记录。保存的分析及编辑保留在独立用户数据目录，移除软件目录不会删除源音频。

Basic analysis in this package supports WAV. Import, play, analyze, inspect the report and explicitly save the result. Rule-based composition, Piano Roll editing and MIDI export require no additional models. Temporary imports do not automatically become persistent library entries. Saved analyses and edits are separate from the application folder; removing that folder does not delete source music.

Basic Pitch 音频转 MIDI 已在维护者现有的受管理模型环境验收，本 Alpha 不包含模型权重或旧 Python。已验证的现有环境可继续使用；旧 Python 3.11.9 安装链的首次安装暂时禁用。全新用户不能把“转录能力已实现”理解为本包已经提供可用模型。OMAR、SheetSage2、YuE2 为可选／实验性功能，受实际组件、许可证与硬件状态限制。FL 自动控制及 AutoMix 不属于此次认证范围。

Basic Pitch audio-to-MIDI was tested with the maintainer's existing managed model environment. Model weights and legacy Python are not included. Existing verified environments remain usable; first installation through the legacy Python 3.11.9 installer is disabled in this Alpha. Implementation of transcription does not mean a new user already has an installed model. OMAR, SheetSage2 and YuE2 remain optional/experimental, subject to actual component, license and hardware availability. FL automation and AutoMix are outside this release's certification.

更新中心可以检查发行信息、由用户打开下载页面。公开 Windows 通知始终关闭；本次发行不批准任何用户推送、不自动下载安装、不增加后台服务。

The update center can check releases and let users open the download page. Public Windows notifications remain disabled. Publication does not approve user notifications, automatic downloads/installations or background services.

## 来源与构建 / Source and build

发行标签 `v0.5.6-alpha.1` 指向包含 `apps/desktop` 的公开 Desktop 源码，不是历史 Runtime 标签。`resources/app/build-record.json` 记录实际提交、版本、工具、依赖与逐文件配方；`portable-manifest.json` 和 `SHA256SUMS.txt` 提供校验。软件二进制未签名。

The `v0.5.6-alpha.1` tag contains the Desktop sources in `apps/desktop`, separately from historical Runtime tags. `resources/app/build-record.json` records the source commit, version, tools, dependencies and file recipe. `portable-manifest.json` and `SHA256SUMS.txt` provide integrity checks. The application binary is unsigned.

1. Checkout the release tag; use the locked dependencies in `apps/desktop/package-lock.json` (`npm ci` in that directory).
2. Fetch the official artifacts listed in `packages/music-intelligence/basic-component-sources.lock`, verify their SHA-256 and prepare an isolated embedded Python environment. Preserve every license file. No system Python fallback is used by the application.
3. Build libsndfile using the source archive and commands in the Corresponding Source release asset. Replace only the explicitly authorized DLL; retain all other official wheel bytes. The supplied recipe has its SHA-256. Modified LGPL libraries may be rebuilt with a newly reviewed recipe/hash, rather than disabling guards.
4. Run `tools/build-wheel-audio-pack.py --help`, passing the recipe SHA, artifact cache, isolated environment, native DLL directory and a new output ZIP. Update the component lock only for a newly built and reviewed version.
5. Set `DAWLOOP_BUILD_PYTHON` to a trusted build interpreter (icon resource editing only); run `node tools/build-portable.mjs <new-absolute-output> <verified-component-zip>`. The public build requires a clean source tree and disabled notification gate.
6. Run `node tools/verify-portable.mjs <output>` and the Desktop regression suite. Never package user data, model caches or acceptance directories.

Third-party terms, notices, SBOM and LGPL source routes: [REDISTRIBUTION.md](../LICENSES/desktop-runtime/REDISTRIBUTION.md). DAWLoop software remains MIT; brand assets retain their separate policy and unresolved provenance status. Independent clean Windows testing remains NOT_TESTED, with the release uncertainty accepted by the maintainer.
