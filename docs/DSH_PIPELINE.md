# DSH / whale-music-pipeline integration

FLSkill incorporates reusable ideas and code from the developer-provided **whale-music-pipeline** archive (also described as the DSH arranging/mixing automation pipeline). The developer authorized reuse of the code, and the archive itself licenses `scripts/` under MIT.

## What was learned and integrated

The archive contributes four especially useful ideas to FLSkill:

1. **Dependency-free SMF inspection.** A small MIDI parser can inspect track names, note density and time windows without pulling in a large music-analysis dependency. FLSkill exposes this as structured Python data for agents.
2. **Active-frame RMS.** Sparse instruments should not be boosted merely because they are silent for most of a song. The DSH workflow measures short frames and evaluates only active material. FLSkill keeps that method but exposes the frame size and floor threshold as policy inputs.
3. **Measured fader calibration.** FL Studio mixer faders are not treated as a linear dB mapping. A calibration table maps normalized fader values to values actually read back from the DAW. FLSkill can plan against a calibration table, but a plan is never considered `PASS` until the real mixer value is read back.
4. **Windows loopback measurement.** WASAPI loopback can measure the audible result when DAW meter data is unavailable. FLSkill provides an optional Windows helper around `pyaudiowpatch`.

The archive also contains orchestration, raw MIDI generation, SoundFont rendering and score-rendering scripts. Those scripts were reviewed as design material, but project-specific composition decisions are not automatically promoted into FLSkill Core policy.

## How this fits FLSkill

```text
AI Agent / Section Plan
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

DSH-derived analysis can suggest the **next** mixer operation. It does not bypass FLSkill's verification rule: `planned fader value != verified fader value` until FL Studio is read back.

## License boundary

- Adapted FLSkill integration code under `src/flskill/dsh/` is derived from MIT-licensed DSH scripts and retains attribution in `THIRD_PARTY_NOTICES.md`.
- The original MIT notice is preserved under `third_party/dsh-whale-music-pipeline/LICENSE`.
- The archive's `docs/` (CC BY 4.0) and `examples/` (attribution / non-commercial terms) are intentionally **not bundled** into FLSkill. This avoids unnecessary license mixing in the redistributable code package.
- The supplied archive contains a `track-scan.py` that imports `spectrum-peak`, but that module was not included in the archive. FLSkill therefore does not advertise that script as independently runnable.

## Current integrated API

- `flskill.dsh.smf.parse_smf()` — structured SMF track/note inspection.
- `flskill.dsh.smf.recommend_dense_window()` — finds a note-dense bar window for measurement.
- `flskill.dsh.mix.active_rms()` — all-frame and active-frame RMS / peak measurement.
- `flskill.dsh.mix.FaderCalibration` — measured fader-value ↔ dB mapping.
- `flskill.dsh.mix.plan_fader_db()` — calibration-aware next-step plan; still requires live readback for `PASS`.
- `flskill.dsh.loopback` — optional Windows WASAPI device listing and capture.
