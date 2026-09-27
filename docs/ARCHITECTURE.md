# Architecture

FLSkill separates musical planning and verification from host-specific execution. The public `v0.1.0-alpha` release contains only the offline Core; the current integration branch adds a bundled Community FL Studio MCP backend and an FLSkill adapter foundation.

```text
AI Agent
   ↓ structured plan
FLSkill Core
   ├─ Musical Grid / absolute ticks
   ├─ Note Plan / validation
   ├─ state and target checks
   └─ Exact-Set verification
          ↓
Execution adapter → bundled FL Studio MCP → FL Studio
                                             ↓
                                     actual-state readback
                                             ↓
                                    PASS / STOP evidence
```

An adapter response only reports execution-layer behavior. It cannot independently establish FLSkill `PASS`; FLSkill must read the DAW state back and verify it against the validated plan.

## Core

The Core has no FL Studio, MCP, Computer Use, SysEx, or audio-library runtime dependency. `MusicalGrid` resolves bar / beat / tick positions to integer absolute ticks. `NotePlan` validates target, section bounds, pitch, velocity, and event duration. The Exact-Set verifier compares planned and actual events while preserving duplicate counts and diagnosing missing, extra, and mismatched fields.

The in-memory event store supports offline tests only. `Offline Algorithm Verified` is not `FL Studio Verified`.

## Execution Adapter Model

The adapter boundary keeps FLSkill Core independent of a specific control route. The current integration branch contains an FLSkill-specific adapter for the pinned Community FL Studio MCP snapshot. Native Computer Use, FLSkill SysEx RPC, compatibility bridges, and other DAW adapters remain future options.

The current MCP adapter foundation:

- maps validated FLSkill Note Plans to upstream Piano Roll operations;
- requires an external identity reader to confirm project, Pattern, Channel, and FL Studio version;
- checks the selected Channel and requires a blank target before writing;
- requests fresh Piano Roll state and converts returned notes into FLSkill events;
- returns a structured report that includes planned and actual events, differences, errors, timestamp, version, and upstream commit.

The upstream Piano Roll readback does not include Pattern identity, so the adapter must not infer Pattern identity from the Piano Roll response. If the identity reader or a fresh readback is unavailable, the adapter returns `STOP` before treating an operation as verified.

## Bundled Backend

The fixed snapshot at `third_party/fl-studio-mcp/` is third-party code and remains unchanged from the pinned upstream commit. FLSkill-specific code lives in `src/flskill/adapters/fl_studio_mcp/`. Python dependencies are installed through the optional `flstudio` extra; their source is not vendored.

See [FL Studio MCP integration](FL_STUDIO_MCP.md), [Acknowledgements](ACKNOWLEDGEMENTS.md), and [Third-Party Notices](../THIRD_PARTY_NOTICES.md).

## Live Status Boundary

The maintainer reports completing an integration run against a real FL Studio environment and requests user feedback because the path may be unstable. No archived target-identity and actual-event evidence for that run is included in this repository. The project therefore distinguishes that report from reproducible live verification: connection, target selection, note write/readback, and Exact-Set results are not claimed as repository-verified capabilities.

Mixer track discovery and plugin parameter query operations are present in the adapter/backend path, but are not live-verified here. Mixer writes, routing writes, and plugin parameter writes remain unverified roadmap work.

## AI Agent Loop and Safety

FLSkill is designed for tool-using agents through structured inputs and machine-readable reports. This does not mean every agent is already integrated or that music production is autonomous.

```text
Agent Plan → FLSkill Validate → Adapter → FL Studio
→ Read Back → Verify → PASS / STOP → Agent decides next action
```

An agent must not treat its own action, an MCP success response, or an interface screenshot as proof of the resulting DAW state. After `STOP`, it should report the failure and avoid building further operations on an unverified state.
