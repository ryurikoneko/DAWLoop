# Contributing

Thanks for helping improve DAWLoop. The project is experimental; clear scope and honest verification status matter more than broad claims.

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

[KNOWN｜HIGH] 新增项目自有源码使用SPDX-License-Identifier: MIT及真实版权主体；第三方改编保留原通知并更新PROVENANCE。不要把设备脚本的必要头移动，或替换原作者为笼统contributors。

[INFERRED｜HIGH] 提交者应确认自己有权按该文件许可提供贡献，说明复制/改编来源及适用许可；这是来源审查要求，不是自动签署CLA或转移版权。将来单独许可的新研究报告先列具体资产与权属，现有MIT授权不回收。

[KNOWN｜HIGH] 私人参考、profile、音频、工程、网页全文与授权不明图片不进入公开贡献。学习示例只用合成或可证明获准发布的材料；用户数据许可不会因为进入Schema自动变成MIT。详见learning/WORKFLOW.md与LICENSE_POLICY.md。
