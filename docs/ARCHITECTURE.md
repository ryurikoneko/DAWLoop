# Architecture

DAWProof separates musical analysis/planning and verification from host-specific execution. The public `v0.1.0-alpha` release contains only the offline Core; current integration work adds a bundled Community FL Studio MCP backend plus reusable Production Pipeline analysis modules.

```text
AI Agent
   ├─ structured musical intent
   ↓
Analysis / Planning Layer
   ├─ Production SMF inspection / dense-window analysis
   ├─ Production orchestration checks
   ├─ Production active-frame RMS / fader calibration
   └─ optional loopback / SF2 audition
   ↓ structured plan
DAWProof Core
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
                                             ↓
                                  next agent decision
```

Analysis and planning can suggest what to do next. They do not prove that a DAW-changing operation happened. An adapter response likewise only reports execution-layer behavior. DAWProof `PASS` requires actual state readback and verification against the validated plan.

## Core

The Core has no FL Studio, MCP, Computer Use, SysEx, Production Pipeline, or audio-library runtime dependency. `MusicalGrid` resolves bar / beat / tick positions to integer absolute ticks. `NotePlan` validates target, section bounds, pitch, velocity, and event duration. The Exact-Set verifier compares planned and actual events while preserving duplicate counts and diagnosing missing, extra, and mismatched fields.

The in-memory event store supports offline tests only. `Offline Algorithm Verified` is not `FL Studio Verified`.

## Production Analysis / Planning Layer

The Production Pipeline lives under `src/dawproof/production/` and is optional. It is deliberately placed outside the Core because its job is to inspect material and propose better musical/mixing plans, not to redefine the verification rules.

Integrated modules include:

- `smf.py`: dependency-free Standard MIDI File parsing plus note-density window selection;
- `orchestration.py`: register-aware phrase assignment, pitch-band gap detection, and source-note coverage checks generalized from the source orchestration workflow;
- `mix.py`: active-frame RMS, measured fader calibration, and calibration-aware fader planning;
- `loopback.py`: optional Windows WASAPI loopback capture;
- `sf2.py`: optional SoundFont parsing/sample rendering for offline audition.

A typical mixer loop can therefore be:

```text
loopback capture
→ active-frame RMS
→ choose target/correction
→ calibration-aware fader plan
→ FL Studio write
→ mixer readback
→ compare actual value/state
→ PASS / STOP
```

The first four steps may be fully deterministic and still do not establish `PASS`; that only happens after the DAW readback stage.

## Execution Adapter Model

The adapter boundary keeps DAWProof Core independent of a specific control route. The current development tree contains a DAWProof-specific adapter for the pinned Community FL Studio MCP snapshot. Native Computer Use, DAWProof SysEx RPC, compatibility bridges, and other DAW adapters remain future options.

The current MCP adapter foundation:

- maps validated DAWProof Note Plans to upstream Piano Roll operations;
- requires an external identity reader to confirm project, Pattern, Channel, and FL Studio version;
- checks the selected Channel and requires a blank target before writing;
- requests fresh Piano Roll state and converts returned notes into DAWProof events;
- exposes Mixer discovery and plugin-parameter read paths from the bundled backend;
- returns a structured report that includes planned and actual events, differences, errors, timestamp, version, and upstream commit.

The upstream Piano Roll readback does not include Pattern identity, so the adapter must not infer Pattern identity from the Piano Roll response. If the identity reader or a fresh readback is unavailable, the adapter returns `STOP` before treating an operation as verified.

## Bundled / Adapted Third-Party Components

`third_party/fl-studio-mcp/` is a fixed third-party source snapshot of Community FL Studio MCP. DAWProof-specific code lives separately in `src/dawproof/adapters/fl_studio_mcp/`.

Reusable third-party code is adapted into `src/dawproof/production/`; its original MIT license is preserved at `third_party/whale-music-pipeline/LICENSE`, and adapted files are classified as `ADAPTED_FROM_THIRD_PARTY` in the provenance records. Third-party documentation and example scores with separate terms are not bundled into the root MIT package.

See [FL Studio MCP integration](FL_STUDIO_MCP.md), [Production Pipeline](PRODUCTION_PIPELINE.md), [Acknowledgements](ACKNOWLEDGEMENTS.md), [Provenance](../PROVENANCE.md), and [Third-Party Notices](../THIRD_PARTY_NOTICES.md).

## Live Status Boundary

The maintainer reports completing an integration run against a real FL Studio environment and requests user feedback because the path may be unstable. No archived target-identity and actual-event evidence for that run is included in this repository. The project therefore distinguishes that report from reproducible live verification: connection, target selection, note write/readback, Mixer write/readback, and Exact-Set results are not claimed as repository-verified capabilities.

Mixer track discovery and plugin parameter query operations are present in the adapter/backend path. Production Pipeline fader calibration and active-RMS measurement make the planning side more capable, but they do not turn Mixer writes into verified operations by themselves.

## AI Agent Loop and Safety

DAWProof is designed for tool-using agents through structured inputs and machine-readable reports. This does not mean every agent is already integrated or that music production is autonomous.

```text
Agent observes/analyzes
→ creates structured plan
→ DAWProof validates
→ Adapter executes
→ FL Studio readback
→ Verify
→ PASS / STOP
→ Agent decides next action
```

An agent must not treat its own action, an MCP success response, a calculated fader target, an audio-analysis result, or an interface screenshot as proof of the resulting DAW state. After `STOP`, it should report the failure and avoid building further operations on an unverified state.
