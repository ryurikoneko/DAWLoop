# Contributing

Thanks for helping improve DAWLoop. The project is experimental; clear scope and honest verification status matter more than broad claims.

## Development setup

Use Python 3.11 or newer. From the repository root:

```powershell
python -m pip install -e ".[flstudio]"
```

Run the offline and adapter tests with:

```powershell
python -m unittest discover -s tests -v
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
