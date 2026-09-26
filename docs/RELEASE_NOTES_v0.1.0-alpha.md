# FLSkill v0.1.0-alpha

The first clean public alpha of **FLSkill**.

FLSkill is an experimental framework for building **verifiable, resumable AI-assisted music-production workflows for FL Studio**.

Instead of treating a DAW operation as successful merely because an agent attempted it, FLSkill is designed around a stricter principle:

> **Plan → Write → Read Back → Verify → PASS / STOP**

This first public release intentionally contains only the clean, DAW-independent core.

## What's included

### Musical Grid
Represent musical positions using deterministic bar / beat / tick coordinates.

### Absolute Tick Resolution
Convert musical positions into absolute timeline locations that can later be mapped to a DAW.

### Note Plan
Structured note events containing pitch, start position, duration and velocity.

### Writer / Reader abstraction
A generic boundary for future DAW adapters. The core does not require FL Studio, Computer Use, MCP or SysEx.

### Exact-Set Verification
After writing events, FLSkill reads the resulting event set back and compares it with the plan. Duplicate-event counts are preserved, and mismatches are diagnosed instead of being treated as success.

### PASS / STOP semantics
Write failures, read failures, missing events, extra events or mismatched event fields result in `STOP`.

## Verification status

**Offline Algorithm Verified**

The release was published after:

- 14 passing offline tests
- Python compile checks
- JSON Schema checks
- clean public provenance tracking

Important:

> **Offline Algorithm Verified ≠ FL Studio Verified**

This release does **not** yet claim successful live FL Studio operation.

## Why FLSkill exists

Most AI + DAW experiments focus on whether an agent can perform an action. FLSkill focuses on a second question:

**Can the system prove that the musical operation it intended to perform is what actually happened in the target?**

The long-term architecture separates composition planning, musical timing, note-event planning, execution adapters, state readback, verification and recovery/resume workflows.

## Planned execution paths

Future optional adapters may include:

- Native Computer Use
- Community FL Studio MCP integration
- FLSkill SysEx RPC
- compatibility Computer Use bridges

These are intended to remain adapters around FLSkill Core rather than mandatory dependencies.

## Roadmap

Planned work includes:

- live FL Studio note write/readback verification
- multi-channel / multi-pattern workflows
- SysEx RPC
- Mixer control with readback verification
- plugin parameter read/write/readback
- Computer Use and community MCP adapters
- audio analysis and section-level composition workflows

See [`docs/ROADMAP.md`](ROADMAP.md) for the current development plan.

## Provenance

The public repository is a clean implementation of the FLSkill core. Experimental third-party integrations and unknown-provenance implementation files from the private development environment are not included.

See [`PROVENANCE.md`](../PROVENANCE.md) for file-level provenance.

## Current limitations

`v0.1.0-alpha` does not yet provide:

- live FL Studio control
- SysEx RPC
- Computer Use integration
- community FL Studio MCP adapter
- Mixer control
- plugin parameter control
- autonomous song production

Those capabilities remain on the roadmap.

## Download

The GitHub release source archives contain the exact `v0.1.0-alpha` tagged source tree.

Licensed under the **MIT License**.
