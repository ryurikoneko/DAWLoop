# Production Pipeline provenance

This record covers the Production Pipeline integration and its source boundaries.

## Source

- Original project: whale-music-pipeline
- Developer: 坏影子不坏, Bilibili UID 599132499: https://space.bilibili.com/599132499
- Code license: MIT
- Original copyright notice: Copyright (c) 2026 whale-music-pipeline contributors
- Additional permission: the FLSkill maintainer reports receiving direct permission from the developer to reuse the code.
- The source archive was originally used in a DSH-based production environment.

## Classification

| Path | Classification | Source / relationship |
|---|---|---|
| third_party/whale-music-pipeline/LICENSE | THIRD_PARTY | Original code-license notice from the supplied source archive |
| src/flskill/production/smf.py | ADAPTED_FROM_THIRD_PARTY | scripts/mix/midi-windows.py |
| src/flskill/production/mix.py | ADAPTED_FROM_THIRD_PARTY | active-rms.py, fader-plan.py, and level-balance.py |
| src/flskill/production/loopback.py | ADAPTED_FROM_THIRD_PARTY | WASAPI loopback scripts under scripts/mix/ |
| src/flskill/production/sf2.py | ADAPTED_FROM_THIRD_PARTY | scripts/score/sf2.py |
| src/flskill/production/orchestration.py | ADAPTED_FROM_THIRD_PARTY | Generalized checks from scripts/orch/orch-fugue-v2.py; work-specific score data removed |
| src/flskill/production/__init__.py | CONFIRMED_PROJECT_GENERATED | FLSkill package glue |
| src/flskill/production/environment.py | CONFIRMED_PROJECT_GENERATED | FLSkill environment profile and dependency probes |
| src/flskill/cli.py changes | CONFIRMED_PROJECT_GENERATED | FLSkill CLI integration |
| tests/test_production_pipeline.py | CONFIRMED_PROJECT_GENERATED | Synthetic MIDI, audio, and note fixtures |
| docs/PRODUCTION_PIPELINE.md | CONFIRMED_PROJECT_GENERATED | FLSkill integration documentation |
| docs/PRODUCTION_PIPELINE_PROVENANCE.md | CONFIRMED_PROJECT_GENERATED | FLSkill provenance record |
| README.md, docs/ARCHITECTURE.md, docs/ROADMAP.md, docs/ACKNOWLEDGEMENTS.md, THIRD_PARTY_NOTICES.md, PROVENANCE.md, pyproject.toml changes | CONFIRMED_PROJECT_GENERATED | FLSkill documentation and packaging metadata |

## Excluded source material

The supplied archive identifies its documentation as CC BY 4.0 and its example scores and MIDI assets as carrying attribution / non-commercial terms. These assets are not bundled in FLSkill's MIT code package. Work-specific composition and orchestration choices are not presented as general FLSkill rules.

## Environment assumptions

The supplied archive does not include the spectrum-peak module referenced by track-scan.py. The developer reports that the workflow runs in their configured production environment, so FLSkill records this as an environment-specific external dependency and does not classify it as a confirmed source defect.

fugue-v4.py expects an output path through sys.argv[1]. A bare invocation without that argument fails; the developer reports that the normal invocation supplies the required context. FLSkill records this as an invocation assumption rather than a confirmed defect.

flskill.production.environment.EnvironmentProfile records the current portable environment separately from the original developer environment, whose status is reported_working. That report is not a FLSkill compatibility certification.

## Verification boundary

Source attribution and runtime verification are separate. Analysis can generate a plan, but it cannot establish that an operation succeeded in FL Studio. DAW-changing operations continue to follow:

Plan → Execute → Read Back → Verify → PASS / STOP
