# Production Pipeline

DAWLoop's optional Production Pipeline contains reusable tools for inspecting MIDI, analyzing rendered audio, planning orchestration and mixer changes, capturing Windows loopback audio, and reading SoundFont data. The package is separate from DAWLoop Core and does not itself modify FL Studio or verify a DAW operation.

## Capabilities

- Dependency-free Standard MIDI File parsing and dense-window selection.
- Register-aware phrase assignment, pitch-band gap detection, and source-note coverage checks.
- Active-frame RMS and peak measurement for PCM WAV files.
- Calibration-aware fader planning based on measured FL Studio fader values.
- Optional Windows WASAPI loopback device discovery and capture.
- Optional SoundFont parsing and offline sample rendering.
- Environment profile checks for Python modules, external tools, environment variables, and platform-specific capabilities.

## Place in the DAWLoop workflow

~~~text
AI Agent
    ↓
Production Analysis / Planning
    ↓
DAWLoop Core
    ↓
Execution Adapter
    ↓
FL Studio
    ↓
Readback
    ↓
Verification
    ↓
PASS / STOP
~~~

Audio and MIDI analysis can provide evidence for the next Production Plan:

~~~text
Audio / MIDI Analysis → next Production Plan
~~~

A calculated fader target or analysis suggestion is not a successful DAW operation. DAWLoop still requires the actual target state to be read back and checked before returning PASS.

## Multi-plugin mixing contracts (offline)

`dawloop.mix_plan` adds a plugin-independent `MixPlan`, a parameter-layout
`PluginFingerprint`, explicit `MixTarget` / `MixSourceSnapshot` context,
`PluginCapabilityProfile` mappings, and an evidence-separated `MixExecutionResult`.
The compiler has no host connection and returns `execution_permission = OFFLINE_ONLY`.
It does not apply changes or certify an installed plugin.

The first contract supports calibrated fader adjustments and an existing static
bell EQ band. Plans contain physical Hz / dB / Q values; adapters declare the exact
parameter layout and linear or logarithmic normalized conversion. Reversed
normalized controls are supported. Discrete, dynamic, compressor, routing, preset,
plugin insertion, and arbitrary-source actions are rejected. Fingerprints identify
observable layout, not a unique plugin instance. Unknown plugin version/format stays
unknown; matching a layout does not prove vendor identity or exact instance binding.

Compilation requires the referenced source snapshot and profile hashes. It checks
session/project/host consistency, parameter names, mode conditions, gain-change
bounds, duplicate parameter writes, and the primitive budget. Outputs are absolute
targets with original-value preconditions. Fader calibration is supplied explicitly;
out-of-range targets are rejected rather than clamped. Fader compilation uses the
existing optional `production` dependency. EQ compilation uses the standard library.

Run a synthetic example without FL Studio:

~~~powershell
python examples/mixing/offline_eq.py
~~~

The example describes a fictional fixed-bell EQ, not any commercial plugin. Two
different synthetic EQ layouts and transfer functions are covered by offline tests;
there are no live-certified vendor maps. Profile JSON can be exchanged through
`PluginCapabilityProfile.to_json()` / `from_json()`, and plan JSON through
`MixPlan.to_json()` / `from_json()`. Parsers reject extra fields and unsupported action
kinds. Personal installation maps and calibration data should remain in gitignored
`workspace/personal/`.

The existing bundled `fl_get_plugin_params` tool now defaults to a full scan and
retains its list return format. DAWLoop requests `include_metadata=True` to obtain
counts, `complete`, `truncated`, per-parameter errors and optional display warnings.
List compatibility refers to raw JSON/structured MCP content; an SDK may convert
list entries into model objects in its `.data` accessor. DAWLoop consumes the
metadata response, whose SDK decoding is exercised through an in-process MCP test.
An explicit limit or the 4096-parameter scan ceiling marks the result incomplete;
incomplete and legacy responses cannot create a trusted layout fingerprint. The
scanner rereads counts, original name and parameter names to detect observable
layout changes. Optional display-text failure does not discard a valid normalized
value. This is not a fresh producer-instance binding certification or an atomic
plugin-state snapshot.

Local controller corrections target the documented API version 26+ signatures:
original plugin name is separate from its user label, and `pickupMode` and global
index arguments occupy their own positions. Unsupported versions stop before the
parameter setter. No new MCP tool, IPC channel or automatic plugin loading is added.
See the [official plugin API](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm#plugins)
and [third-party patch attribution](../THIRD_PARTY_NOTICES.md).

Next gates are a separate read-only live compatibility check, then one fader in a
disposable project, followed by two explicitly mapped existing EQs. Normal projects,
automatic multi-round optimization and complete DSP-state rollback remain outside
this contract. Mixer changes may apply immediately; a future executor needs human
approval of the change list rather than the Piano Roll Preview/Accept lifecycle.
Parameter readback, audio measurement and human preference remain separate evidence.
Piano Roll Exact Set research stays frozen.

## Environment compatibility

The `dawloop.production.environment.EnvironmentProfile` records the detected operating system and Python version, optional modules and tools, configured environment-variable names, and source-workflow invocation assumptions. It records whether relevant variables are configured, not their values or local paths.

The profile keeps the original developer environment report (reported_working) separate from probes of the current portable environment. It is descriptive and does not certify compatibility. Missing optional components are reported individually as OPTIONAL_MISSING; WASAPI endpoint enumeration is not performed by dawloop doctor.

The supplied source archive does not include the spectrum-peak module referenced by one script. The developer reports that their configured production environment provides the required dependency. Another source script expects an output path in sys.argv[1]; the developer reports that the normal invocation supplies it. These are recorded as environment and invocation assumptions, not confirmed source defects.

## API

- `dawloop.production.smf.parse_smf()` — structured SMF track and note inspection.
- `dawloop.production.smf.recommend_dense_window()` — selects a note-dense bar window.
- `dawloop.production.orchestration.choose_instrument_for_phrase()` — register-aware phrase assignment.
- `dawloop.production.orchestration.find_register_gaps()` — finds empty pitch-band windows.
- `dawloop.production.orchestration.source_note_coverage()` — reports source events missing after an arrangement pass.
- `dawloop.production.mix.active_rms()` — whole-file and active-frame RMS / peak measurement.
- `dawloop.production.mix.FaderCalibration` — mapping between normalized fader values and measured dB.
- `dawloop.production.mix.plan_fader_db()` — calibration-aware fader plan; live readback is still required for `PASS`.
- `dawloop.production.loopback` — optional Windows WASAPI device listing and capture.
- `dawloop.production.sf2.Sf2` — optional SoundFont parsing and sample rendering.
- `dawloop.production.environment.inspect_environment()` — optional dependency and environment profile checks.

## Installation and CLI

SMF inspection uses the Python standard library. Install the `production` extra for audio analysis and SoundFont utilities; install `production-loopback` for Windows loopback capture.

~~~powershell
python -m pip install -e ".[production]"
python -m pip install -e ".[production-loopback]"
dawloop midi-inspect song.mid --beats-per-bar 4 --window-bars 3
dawloop measure-wav track.wav --frame-ms 100 --floor-dbfs -65
~~~

These commands return structured data for agents. They do not by themselves mark any FL Studio operation as verified.

## Attribution and license

The Production Pipeline includes code adapted from the MIT-licensed whale-music-pipeline project. See [Production Pipeline provenance](PRODUCTION_PIPELINE_PROVENANCE.md), [Acknowledgements](ACKNOWLEDGEMENTS.md), and [Third-Party Notices](../THIRD_PARTY_NOTICES.md). The source license is preserved at `third_party/whale-music-pipeline/LICENSE`.
