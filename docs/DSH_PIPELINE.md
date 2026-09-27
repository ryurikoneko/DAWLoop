# DSH / whale-music-pipeline integration

FLSkill incorporates reusable ideas and code from the developer-provided **whale-music-pipeline** archive (also described as the DSH arranging/mixing automation pipeline). The developer authorized reuse of the code, and the archive itself licenses `scripts/` under MIT.

## What was learned and integrated

The archive contributes several especially useful ideas to FLSkill:

1. **Dependency-free SMF inspection.** A small MIDI parser can inspect track names, note density and time windows without pulling in a large music-analysis dependency. FLSkill exposes this as structured Python data for agents.
2. **Register-aware orchestration checks.** DSH chooses melody instruments by register, checks whether the midrange has collapsed, and verifies source-note coverage. FLSkill generalizes those ideas into deterministic helpers without hard-coding a particular orchestra or score.
3. **Active-frame RMS.** Sparse instruments should not be boosted merely because they are silent for most of a song. The DSH workflow measures short frames and evaluates only active material. FLSkill keeps that method but exposes the frame size and floor threshold as policy inputs.
4. **Measured fader calibration.** FL Studio mixer faders are not treated as a linear dB mapping. A calibration table maps normalized fader values to values actually read back from the DAW. FLSkill can plan against a calibration table, but a plan is never considered `PASS` until the real mixer value is read back.
5. **Windows loopback measurement.** WASAPI loopback can measure the audible result when DAW meter data is unavailable. FLSkill provides an optional Windows helper around `pyaudiowpatch`.
6. **SoundFont rendering.** DSH includes a compact SF2 parser/sample renderer. FLSkill carries an adapted version as `flskill.dsh.sf2` for offline audition workflows; this remains an optional utility, not part of the verification core.

The archive also contains raw MIDI generation, score rendering, full composition examples and a concrete 16-part orchestration script. Those files were reviewed closely as design material. Their reusable algorithms are being extracted into generic FLSkill APIs rather than making one score's instrumentation, harmony or commission-specific decisions global policy.

## How this fits FLSkill

```text
AI Agent / Section Plan
        ↓
SMF + orchestration inspection
        ↓
FLSkill Note / Operation Plan
        ↓
FL Studio execution backend
        ↓
DAW readback ───────────────┐
        ↓                   │
Mixer / note verification   │
        ↓                   │
PASS / STOP                 │
                            │
WASAPI loopback → active RMS┘
        ↓
calibration-aware next plan
```

DSH-derived analysis can suggest the **next** orchestration or mixer operation. It does not bypass FLSkill's verification rule: `planned fader value != verified fader value` until FL Studio is read back.

## License boundary

- Adapted FLSkill integration code under `src/flskill/dsh/` is derived in part from MIT-licensed DSH scripts and retains attribution in `THIRD_PARTY_NOTICES.md`.
- The original MIT notice is preserved under `third_party/dsh-whale-music-pipeline/LICENSE`.
- The archive's `docs/` (CC BY 4.0) and `examples/` (attribution / non-commercial terms) are intentionally **not bundled** into FLSkill. This avoids unnecessary license mixing in the redistributable code package.
- `track-scan.py` references `spectrum-peak`, which is not included in the supplied archive. The original developer reports that the workflow runs in their configured production environment. FLSkill classifies this as `ENVIRONMENT_COUPLED` / `PORTABILITY_NOT_ESTABLISHED`; the archive alone does not establish a portable setup or a source defect.
- `fugue-v4.py` expects an output path through `sys.argv[1]`. A bare invocation without this argument fails, while the original developer reports that their normal execution path supplies the required context. FLSkill classifies this as `INVOCATION_ASSUMPTION` / `PORTABILITY_NOT_ESTABLISHED`, not as a bug.

## Environment compatibility

`flskill.dsh.environment` provides a lightweight `EnvironmentProfile` with the detected OS and Python version, optional modules and tools, configured environment-variable names, and the DSH invocation assumptions above. It records only whether relevant variables are configured, not their values or local paths.

The profile separates the original developer environment (`reported_working`) from the portable FLSkill environment, which is assessed from actual local probes. A profile is descriptive; it does not certify that a workflow is compatible. `flskill doctor` reports capabilities independently: the SMF parser is available without NumPy, while audio analysis and WASAPI loopback are optional. WASAPI endpoint enumeration is not performed by the doctor.

Missing optional components are reported as `OPTIONAL_MISSING`; environment-specific dependencies are not called broken. DSH analysis can inform a plan, but cannot establish that a DAW operation succeeded.

## Current integrated API

- `flskill.dsh.smf.parse_smf()` — structured SMF track/note inspection.
- `flskill.dsh.smf.recommend_dense_window()` — finds a note-dense bar window for measurement.
- `flskill.dsh.orchestration.choose_instrument_for_phrase()` — register/comfort-range based phrase assignment.
- `flskill.dsh.orchestration.find_register_gaps()` — samples a score for empty pitch-band windows.
- `flskill.dsh.orchestration.source_note_coverage()` — reports source events that disappeared during an arrangement pass.
- `flskill.dsh.mix.active_rms()` — all-frame and active-frame RMS / peak measurement.
- `flskill.dsh.mix.FaderCalibration` — measured fader-value ↔ dB mapping.
- `flskill.dsh.mix.plan_fader_db()` — calibration-aware next-step plan; still requires live readback for `PASS`.
- `flskill.dsh.loopback` — optional Windows WASAPI device listing and capture.
- `flskill.dsh.sf2.Sf2` — optional SoundFont parsing and sample rendering.
- `flskill.dsh.environment.inspect_environment()` — optional dependency and environment profile checks.

## CLI entry points

SMF inspection works without NumPy. Install `flskill[dsh]` for audio analysis and SoundFont utilities; install `flskill[dsh-loopback]` for Windows loopback capture:

```powershell
flskill midi-inspect song.mid --beats-per-bar 4 --window-bars 3
flskill measure-wav track.wav --frame-ms 100 --floor-dbfs -65
```

Both commands return structured data suitable for an AI agent. The analysis output is evidence for planning; it is not a substitute for FL Studio state readback when the operation changes the DAW.
