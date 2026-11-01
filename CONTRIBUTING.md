# Contributing

Help improve music workflows, editing, analysis or DAW integration. Start with the [Runtime Quickstart](docs/QUICKSTART.md), [Desktop source tag](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.2) and [public writing guide](docs/PUBLIC_CONTENT_STYLE.md). Document the behavior and verification scope of your contribution.

## Choose a contribution / 选择贡献方向

- **Creator workflows:** share a reproducible editing or analysis task and the result you need. Start with [Desktop](docs/DESKTOP.md) and [Demos](docs/DEMOS.md).
- **Runtime and analysis:** add a musical contract, analyzer or synthetic fixture. Start with [Quickstart](docs/QUICKSTART.md) and [Production Pipeline](docs/PRODUCTION_PIPELINE.md).
- **FL integration:** study targets, execution paths and applicable readback before proposing an adapter change. Start with [Architecture](docs/ARCHITECTURE.md) and [FL integration](docs/FL_STUDIO_MCP.md).
- **Documentation and translation:** improve task explanations, diagrams and bilingual terminology using the [Glossary](docs/GLOSSARY.md).

欢迎创作工作流反馈、分析与Runtime实现、宿主适配、合成测试素材及文档翻译。请说明用户想完成什么、预期与实际结果，并遵守下文的安全、来源和验证要求。

## Product scope / 产品范围

Desktop and Runtime are open source. Private Plugin implementation is developed separately and is not contributed through this public repository. Plugin documentation, translation and reproducible user feedback are welcome; do not attach private source, binaries, credentials or music without permission. See [Plugin scope](docs/PLUGINS.md).

Desktop 与 Runtime 开源；Plugin 私有实现独立维护。本公开仓库欢迎 Plugin 文档、翻译和可复现反馈，不要求提交私有实现，不接收未经授权的源码、二进制、凭据或音乐素材。

## Development setup

Use Python 3.11 or newer. From the repository root:

```powershell
python -m pip install -e ".[learning,native,mcp,flstudio,production]"
python -m pip install pytest pytest-asyncio Pillow build
```

Run the offline and adapter tests with:

```powershell
python -m pytest -q tests
```

Live FL Studio testing is not part of the ordinary test command. Use a disposable project and follow [Live test prerequisites](tests/live_fl/README.md).

## Contribution rules

- Do not label a capability `Verified` without readback evidence for that capability and target scope.
- Keep execution, readback, and verification separate. A backend success response alone is not a verification result.
- Do not modify `third_party/fl-studio-mcp/` unless an intentional upstream update is being reviewed. Preserve its attribution, license, and pinned source information.
- Record new project files and any external source influence in `PROVENANCE.md`.
- New live adapters must provide safe target checks, fresh readback, machine-readable evidence, and a defined `STOP` path.
- Use original, synthetic test data. Do not include private projects, commercial samples, plugin binaries, credentials, or personal logs in a change.

## Commit authorship

DAWLoop commits should use the repository maintainer Git identity. Automation and AI development tools must not be recorded automatically as commit authors or co-authors.

Examples:

- `feat(mixer): add fader write/readback verification`
- `fix(adapter): preserve duplicate MIDI events during readback`
- `refactor(package): migrate public namespace to dawloop`
- `build(package): rename distribution and CLI entry point`
- `docs(verification): define control and audio outcome boundaries`
- `test(mixer): cover tolerance and readback mismatch cases`

## Pull Requests

Describe the change, its scope, and the exact checks you ran. State whether evidence is offline, backend-only, or live. Do not present upstream capabilities as DAWLoop-verified capabilities.


## 来源、学习资料与许可

新增项目自有源码使用SPDX-License-Identifier: MIT及真实版权主体；第三方改编保留原通知并更新PROVENANCE。不要把设备脚本的必要头移动，或替换原作者为笼统contributors。

提交者应确认自己有权按该文件许可提供贡献，说明复制/改编来源及适用许可；这是来源审查要求，不是自动签署CLA或转移版权。将来单独许可的新研究报告先列具体资产与权属，现有MIT授权不回收。

私人参考、profile、音频、工程、网页全文与授权不明图片不进入公开贡献。学习示例只用合成或可证明获准发布的材料；用户数据许可不会因为进入Schema自动变成MIT。详见learning/WORKFLOW.md与LICENSE_POLICY.md。

## Desktop 与展示贡献 / Desktop and presentation

Desktop Alpha源代码在公开发行标签，Runtime与文档位于main。注明贡献对象及基线；Desktop功能变更单独审阅，文档PR不携带安装包或隐式业务改动。截图使用获准公开的自有或合成素材，删除私人路径、凭据及工程信息。品牌素材遵循 [媒体声明](docs/media/README.md)，原许可保持。

Desktop Alpha source is public at its release tag; Runtime and documentation are on main. State the target and baseline, keep product code changes separate from docs PRs, and sanitize screenshots. Follow existing media terms and the [content review guide](docs/PUBLIC_CONTENT_STYLE.md).
