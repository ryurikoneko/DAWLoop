# Roadmap

This roadmap describes the current development state. It is separate from the published `v0.1.0-alpha`, which remains the original offline-core release. Status names describe DAWLoop's own implementation; upstream/backend features do not count as DAWLoop verification.

## Completed

- Offline Musical Grid, absolute tick resolution, Note Plan, and Exact-Set Verification.
- Structured `PASS` / `STOP` semantics for offline execution and comparison.
- Pinned Community FL Studio MCP source snapshot under `third_party/`, with upstream license and copyright notices retained.
- DAWLoop MCP adapter foundation, Note Plan mapping, target-identity gate, and structured execution report.
- Optional FL Studio dependencies, `dawloop doctor`, and explicit User Script installer.
- Agent-oriented architecture and offline adapter tests.
- Production Pipeline dependency-free SMF inspection and dense-section selection.
- Production Pipeline orchestration helpers for register-aware phrase assignment, midrange-gap detection, and source-note coverage checks.
- Production Pipeline active-frame RMS measurement and calibration-aware fader planning.
- Optional Windows WASAPI loopback capture and SF2 / SoundFont audition utility.
- Explicit Production Pipeline attribution, license boundary, and provenance classification.

## In Development

- Reproducible live Pattern / Channel identity checks.
- Repeatable live note write, fresh readback, and Exact-Set evidence.
- Integration of Production Pipeline fader planning with verified Mixer `write → readback → compare` operations.
- Section-level agent workflows that turn MIDI inspection/orchestration analysis into structured DAWLoop plans rather than direct unverified DAW edits.
- Stability and compatibility feedback across FL Studio installations.
- User-facing setup and test workflow for the experimental integration path.

The maintainer reports completing an FL Studio integration run. The repository does not include archived target-identity and actual-event evidence for that run, so the live path is not marked `Verified` here.

## Planned

- Multi-channel and multi-pattern planning and execution.
- Mixer operations with per-operation write, readback, and verification.
- Plugin parameter operations with readback verification.
- Higher-level orchestration policies built on the generic Production Pipeline checks, with score-independent tests and evidence.
- Expanded audio analysis beyond RMS/peak where deterministic measurements materially help the agent.
- DAWLoop SysEx RPC adapter, implemented from the documented protocol specification.
- Native Computer Use adapter and compatibility bridge support.
- Broader agent orchestration and resumable production workflows.

## Verification Milestone

The `v1.0.0` milestone is intended to require an installable workflow that can identify a real target, write a deterministic Note Plan to FL Studio, read the actual events back, and produce a reproducible Exact-Set `PASS` / `STOP` report. Production analysis may inform the plan, but analysis alone does not satisfy this live verification milestone. `v1.0.0` is not a released version.
