# Roadmap

This roadmap describes the current integration branch. It is separate from the published `v0.1.0-alpha`, which remains the original offline-core release. Status names describe FLSkill's own implementation; upstream backend features do not count as FLSkill verification.

## Completed

- Offline Musical Grid, absolute tick resolution, Note Plan, and Exact-Set Verification.
- Structured `PASS` / `STOP` semantics for offline execution and comparison.
- Pinned Community FL Studio MCP source snapshot under `third_party/`, with upstream license and copyright notices retained.
- FLSkill MCP adapter foundation, Note Plan mapping, target-identity gate, and structured execution report.
- Optional FL Studio dependencies, `flskill doctor`, and explicit User Script installer.
- Agent-oriented architecture and offline adapter tests.

## In Development

- Reproducible live Pattern / Channel identity checks.
- Repeatable live note write, fresh readback, and Exact-Set evidence.
- Stability and compatibility feedback across FL Studio installations.
- User-facing setup and test workflow for the experimental integration path.

The maintainer reports completing an FL Studio integration run. The repository does not include archived target-identity and actual-event evidence for that run, so the live path is not marked `Verified` here.

## Planned

- Multi-channel and multi-pattern planning and execution.
- Mixer operations with per-operation write, readback, and verification.
- Plugin parameter operations with readback verification.
- FLSkill SysEx RPC adapter, implemented from the documented protocol specification.
- Native Computer Use adapter and compatibility bridge support.
- Audio analysis and section-level composition workflows.
- Broader agent orchestration and resumable production workflows.

## Verification Milestone

The `v1.0.0` milestone is intended to require an installable workflow that can identify a real target, write a deterministic Note Plan to FL Studio, read the actual events back, and produce a reproducible Exact-Set `PASS` / `STOP` report. It is not a released version.
