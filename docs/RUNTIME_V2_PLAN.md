# DAWLoop Runtime V2 Plan

This document defines the next DAWLoop architecture after comparing the current project with FLaiK's public design and FL Studio's current Gopher control surface.

The goal is not to copy FLaiK. DAWLoop keeps its own planning, safety, production-analysis, and optional verification architecture while learning from the much faster native FL control path and from the idea of a local FL knowledge layer.

## 1. Core product decision

DAWLoop separates **Safety Guard** from **Result Verification**.

- Safety Guard stays on. It protects target identity, destructive actions, ambiguous targets, and overwrite/delete boundaries.
- Result Verification becomes optional. Routine edits should not pay readback cost unless the user requests it or the operation crosses a high-risk identity/destructive boundary.
- User-facing results distinguish `Executed` from `Verified` instead of treating all successful writes as PASS.

Planned execution modes:

| Mode | Behaviour |
|---|---|
| Fast | Default. Execute routine operations immediately after required safety guards. |
| Auto | Verify identity/destructive boundaries and operations where readback is especially valuable. |
| Verified | Request readback verification for supported write operations. |

Default mandatory verification boundaries include creating/deleting/replacing a Pattern, deleting a channel/track, clearing a Pattern, and destructive routing changes. The set will evolve from live evidence.

## 2. Current DAWLoop strengths

DAWLoop already has architectural pieces that should be preserved:

- deterministic MusicalGrid and NotePlan representations;
- exact-set comparison and structured evidence;
- explicit target-identity checks;
- Community FL Studio MCP integration;
- production-analysis pipeline for MIDI, orchestration, RMS, fader planning and loopback;
- provenance / third-party separation;
- a backend boundary rather than hard-coding all musical logic into one transport.

These make DAWLoop suitable as an agent runtime rather than only an FL chat panel.

## 3. Current DAWLoop bottlenecks

### P0 — the execution hot path is too slow

The current live Piano Roll path is optimized for proving correctness, not production speed. It can require repeated identity checks, User Script triggering, file-state refresh, readback, comparison, and in some real workflows Computer Use to bring material into the Piano Roll.

Observed user impact: a single small instrument part can take many minutes. This prevents practical section-level or song-level autonomous production.

**Runtime V2 rule:** Computer Use must not be the normal note-entry path. It is a compatibility/fallback backend only.

### P0 — one primary execution backend

The current project effectively treats Community FL Studio MCP as the main FL execution route. Runtime V2 needs multiple backends with capability-based routing.

### P1 — Piano Roll execution is note-centric

Exact note lists are useful, but many musical edits are transformations: strum, humanize, quantize, transpose, voice-leading adjustments, velocity shaping, articulation passes, etc. A scriptable native Piano Roll path can express these operations much more efficiently.

### P1 — broad FL control is incomplete

DAWLoop lacks a unified direct path for Channel creation, effect insertion/removal, Playlist organization, UI guidance, and several Mixer operations exposed by the current Gopher MCP catalog.

### P1 — no persistent FL knowledge layer

Production analysis exists, but DAWLoop does not yet maintain a fast local knowledge index covering the FL manual, native tool schemas, plugin/workflow notes, and project/session decisions.

### P2 — installation and discovery are developer-oriented

`dawloop doctor` is useful, but the runtime still requires substantial environment knowledge. Backend discovery, FL-version compatibility, capability probing, and setup need to become first-class concepts.

## 4. What we learn from FLaiK

We learn the following ideas, not its implementation code:

1. FL Studio's Gopher panel can expose a host bridge that accepts MCP-style `tools/call` requests.
2. The controllable surface can be dynamically discovered as a tool catalog rather than frozen in DAWLoop code.
3. The current catalog covers transport, Channels, Mixer, Piano Roll scripting, Playlist, plugin parameters, and system/UI helpers.
4. Piano Roll Python scripting is a high-throughput path for complex note operations.
5. A persistent local FL knowledge layer reduces repeated documentation lookup and helps an agent reason about FL-specific workflows.
6. A launcher/setup layer can make a technically complex bridge usable.

Runtime V2 should implement these ideas independently behind DAWLoop interfaces.

## 5. Target architecture

```text
AI / Codex / Agent
        |
        v
Intent + Production Analysis + FL Knowledge
        |
        v
Operation Planner
        |
        +---------------- Safety Guard ----------------+
        |                                              |
        v                                              |
Capability Router                                      |
  |          |              |             |            |
  v          v              v             v            |
Gopher     Community       SysEx       Computer Use    |
Native MCP FL MCP          RPC         fallback        |
  |          |              |             |            |
  +----------+--------------+-------------+------------+
                         |
                         v
                    FL Studio
                         |
             optional / required readback
                         |
                         v
                  Verification Engine
                         |
                 Executed / Verified
```

DAWLoop Core must not depend on one FL transport.

## 6. Backend capability registry

Every backend advertises capabilities such as:

```text
transport.play
transport.tempo
channel.list
channel.create
channel.delete
channel.rename
channel.route
step_sequencer.write
piano_roll.notes
piano_roll.script
mixer.volume
mixer.pan
mixer.routing
mixer.effect.add
mixer.effect.remove
plugin.parameter.read
plugin.parameter.write
playlist.track.rename
system.session_context
system.window
```

Each capability records:

- backend;
- readable / writable;
- verifiable;
- destructive;
- latency / quality metadata later;
- schema / version compatibility later.

The router chooses the fastest suitable backend subject to safety and user preferences.

## 7. Native Gopher MCP backend

Create an independent `gopher_native` adapter rather than importing FLaiK code.

### Phase A — read-only probe

- locate the FL Gopher WebView / supported host surface;
- discover the live tool catalog;
- normalize names, descriptions and input schemas into `CapabilityRegistry`;
- call only read-only operations such as tempo, channel list, session context and plugin-parameter reads;
- record FL version and compatibility diagnostics.

### Phase B — low-risk writes

Enable direct writes for:

- play / stop / tempo;
- selection / mute / solo / colour / rename;
- mixer volume / pan;
- plugin parameter writes;
- Playlist names/colours;
- routing where target identity is unambiguous.

Fast mode does not automatically read these values back.

### Phase C — high-throughput Piano Roll scripting

Introduce `PianoRollScriptPlan` / transformation plans.

The plan contains musical intent and constraints; generated Python is only an executor. Examples:

- exact note construction;
- chord voicing;
- strum;
- humanize;
- quantize;
- transpose;
- velocity shaping;
- arpeggiation;
- legato / duration transformations.

Fast mode executes once. Verified mode reads back and checks exact events or musical invariants depending on plan type.

### Pattern creation caveat

The currently inspected public Gopher tool catalog does not expose an explicit `create_pattern` tool. DAWLoop must not claim this capability until live discovery or another documented FL control route proves it. Pattern creation therefore remains a special P0 investigation and may temporarily use SysEx, another FL API, or a narrowly scoped GUI fallback.

## 8. Verification redesign

Verification is a capability, not a mandatory tax on every operation.

### Routine operations

By default:

```text
resolve target -> safety guard -> execute -> Executed
```

### User-requested / high-risk operations

```text
resolve target -> safety guard -> execute -> readback -> compare -> Verified / Failed
```

Verifier types:

- exact-set comparator for deterministic note replacement;
- scalar tolerance comparator for Mixer / parameters;
- state-diff comparator for batch edits;
- invariant comparator for transformations;
- identity/existence comparator for create/delete operations.

## 9. FL knowledge layer

The runtime needs a pre-indexed local knowledge base so the agent does not repeatedly crawl/search the manual during production.

Planned sources:

- FL Studio official HTML manual / locally available documentation;
- live-discovered native tool schemas;
- DAWLoop's own tested workflow notes;
- plugin parameter/workflow notes;
- project/session decisions and approved production patterns.

Recommended layout:

```text
knowledge/
  fl_manual_index/
  tool_schemas/
  workflows/
  plugins/
workspace/
  project_state/
  decisions/
  approved_patterns/
scratch/
```

**Distribution note:** public documentation is useful as a knowledge source, but public availability is not by itself a redistribution licence. DAWLoop should keep the ingestion/indexing pipeline separate from the MIT core. If redistribution rights are not explicitly established, the installer should index an official/local copy rather than commit the complete manual corpus into the MIT repository.

The important performance requirement is that indexing happens once; normal agent queries hit the local index, not hundreds of HTML files or the web repeatedly.

## 10. Execution performance targets

Runtime V2 should measure end-to-end operation latency.

Initial goals:

- simple scalar/control action: seconds, not minutes;
- direct Piano Roll script submission: one native execution transaction for a part, not one GUI action per note;
- a complete 8–16 bar single-instrument note pass should not depend on Computer Use;
- batch Channel / Mixer operations should use one or a small number of native calls where schemas support batch input;
- verification overhead is only paid when enabled/required.

Benchmarks should record plan time separately from execution time.

## 11. Implementation route

### Milestone 0 — Runtime foundation (now)

- separate safety from verification;
- introduce Fast / Auto / Verified policy;
- split `execution_status` from `verification_status`;
- add CapabilityRegistry;
- document backend-routing architecture.

### Milestone 1 — Native read-only bridge

- implement native Gopher bridge independently;
- dynamic tool discovery;
- `dawloop doctor` native-backend probe;
- capture normalized capability snapshot for the user's FL version;
- no destructive writes.

### Milestone 2 — Fast direct control

- channel/mixer/plugin/transport direct writes;
- Fast mode default;
- safety target checks only;
- benchmark against Community MCP and Computer Use.

### Milestone 3 — Piano Roll fast path

- script-plan model;
- deterministic script generator for exact note plans;
- transformation scripts;
- eliminate Computer Use from normal Piano Roll note entry;
- optional exact/invariant verification.

### Milestone 4 — Pattern and multi-part composition

- solve/prove Pattern creation and identity;
- multi-pattern / multi-channel section plans;
- Playlist arrangement;
- batch operations and section checkpoints.

### Milestone 5 — Knowledge runtime

- one-time manual ingestion/indexing;
- FL/tool schema retrieval;
- project/workspace memory;
- source/provenance metadata.

### Milestone 6 — Production loop

- production analysis -> operation plans -> direct execution;
- Mixer/plugin automation passes;
- optional audio outcome measurement separate from state verification;
- resumable section-level production.

### Milestone 7 — product UX

- setup/launcher;
- backend and capability status;
- execution mode control;
- `Executed` vs `Verified` indicators;
- diagnostics and compatibility reports.

## 12. What not to do

- Do not copy FLaiK source into DAWLoop without a clear licence.
- Do not claim native capabilities that have not been live discovered/tested.
- Do not keep Computer Use as the normal note-writing path.
- Do not require exact readback for every routine edit.
- Do not remove target/destructive safety guards in Fast mode.
- Do not conflate execution success, verification success, and audio/musical quality.
- Do not let generated Python become the plan-of-record: the musical plan/constraints remain DAWLoop data.

## 13. Near-term definition of success

The first major Runtime V2 success is not a prettier UI. It is this scenario:

1. Agent receives an 8–16 bar part.
2. DAWLoop resolves the intended Channel/Pattern safely.
3. It generates a single direct Piano Roll script/transaction.
4. FL receives the part without manual import or per-note Computer Use.
5. Fast mode returns `Executed` immediately.
6. If the user enables verification, DAWLoop reads back once and returns `Verified` or a useful failure report.

That directly attacks the project's current largest bottleneck while preserving the stronger architecture that makes DAWLoop distinct.
