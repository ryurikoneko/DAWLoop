# DSH provenance addendum

This addendum records the DSH / `whale-music-pipeline` integration introduced on `integration/dsh-pipeline` and **supersedes the earlier statement in `PROVENANCE.md` that FL Studio MCP was the only intentionally included third-party source**. That statement was correct before this branch and is no longer complete after DSH-derived code was added.

## Source

- Supplied archive: `DSH编曲混音自动化（开源版）.zip`
- Project name inside archive: `whale-music-pipeline`
- Code license stated by archive: MIT
- Copyright: `Copyright (c) 2026 whale-music-pipeline contributors`
- Additional authorization: FLSkill maintainer states that the DSH developer explicitly authorized direct reuse of the code.

## Classification

| Path | Classification | Source / relationship |
|---|---|---|
| `third_party/dsh-whale-music-pipeline/LICENSE` | `THIRD_PARTY` | Original DSH code-license notice from supplied archive |
| `src/flskill/dsh/smf.py` | `ADAPTED_FROM_THIRD_PARTY` | `scripts/mix/midi-windows.py` |
| `src/flskill/dsh/mix.py` | `ADAPTED_FROM_THIRD_PARTY` | `active-rms.py`, `fader-plan.py`, `level-balance.py` |
| `src/flskill/dsh/loopback.py` | `ADAPTED_FROM_THIRD_PARTY` | DSH WASAPI loopback scripts |
| `src/flskill/dsh/sf2.py` | `ADAPTED_FROM_THIRD_PARTY` | `scripts/score/sf2.py` |
| `src/flskill/dsh/orchestration.py` | `ADAPTED_FROM_THIRD_PARTY` | Genericized orchestration checks from `scripts/orch/orch-fugue-v2.py`; score-specific data removed |
| `src/flskill/dsh/__init__.py` | `CONFIRMED_PROJECT_GENERATED` | FLSkill package glue for adapted modules |
| `tests/test_dsh_pipeline.py` | `CONFIRMED_PROJECT_GENERATED` | New tests using synthetic MIDI/audio/note data; no DSH example score copied |
| `docs/DSH_PIPELINE.md` | `CONFIRMED_PROJECT_GENERATED` | New FLSkill integration documentation summarizing behavior and boundaries |
| `src/flskill/cli.py` changes | `CONFIRMED_PROJECT_GENERATED` | New FLSkill CLI wiring around adapted APIs |
| `pyproject.toml` changes | `CONFIRMED_PROJECT_GENERATED` | New optional dependency groups and license packaging |
| `THIRD_PARTY_NOTICES.md` / `docs/ACKNOWLEDGEMENTS.md` updates | `CONFIRMED_PROJECT_GENERATED` | Attribution and licensing records |

## Excluded archive material

The archive's documentation is identified as CC BY 4.0 and its example scores/MIDI assets carry attribution/non-commercial terms. Those materials are not bundled in FLSkill's MIT code package. The code was studied, but project/commission-specific score data is not being presented as original FLSkill content.

The supplied `track-scan.py` imports a `spectrum-peak` module that is not present in the archive, and the supplied README invocation for `fugue-v4.py` omits an output argument required by the script. These snapshot issues are documented rather than silently treated as verified functionality.

## Verification boundary

Adapting an algorithm does not make its FL Studio behavior automatically `Verified`. DSH-derived analysis may generate an orchestration suggestion or mixer plan, but any DAW-changing action still follows FLSkill's rule:

`Plan → Execute → Read Back → Verify → PASS / STOP`.
