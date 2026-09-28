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
