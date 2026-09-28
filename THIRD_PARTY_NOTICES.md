# 第三方声明

## FL Studio MCP

- Project: `karl-andres/fl-studio-mcp`
- Repository: <https://github.com/karl-andres/fl-studio-mcp>
- Bundled commit: `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`
- License: MIT
- Copyright:
  - Copyright (c) 2025 calvinw
  - Copyright (c) 2025 Karl Andres
- Bundling purpose: Used as an optional FL Studio execution backend for DAWProof.

DAWProof does not claim authorship of the bundled FL Studio MCP implementation. The upstream source snapshot is stored under [`third_party/fl-studio-mcp/`](third_party/fl-studio-mcp/); its original MIT license is preserved at [`third_party/fl-studio-mcp/LICENSE`](third_party/fl-studio-mcp/LICENSE). The root [`LICENSE`](LICENSE) applies to DAWProof-authored files and does not replace the bundled project's license.

The vendored snapshot contains only the upstream files needed to run its MCP server and install its FL Studio scripts. The demo video and upstream installer scripts are not bundled.

## whale-music-pipeline

- Original project: `whale-music-pipeline`
- Developer attribution: [坏影子不坏](https://space.bilibili.com/599132499), Bilibili UID `599132499`
- Code license: MIT
- Original copyright notice: `Copyright (c) 2026 whale-music-pipeline contributors`
- Additional permission: the DAWProof maintainer reports receiving direct permission from the developer to reuse the code.
- Bundling purpose: reusable MIDI inspection, orchestration checks, SoundFont auditioning, audio-level analysis, mixer calibration/planning, and optional Windows loopback capture for DAWProof's agent-oriented production pipeline.

The complete original code-license notice is preserved at [`third_party/whale-music-pipeline/LICENSE`](third_party/whale-music-pipeline/LICENSE). DAWProof does not claim original authorship of adapted algorithms.

The following DAWProof files are adapted from, or directly generalized from, the MIT-licensed source scripts:

- `src/dawproof/production/smf.py` — adapted from `scripts/mix/midi-windows.py`.
- `src/dawproof/production/mix.py` — adapted from `scripts/mix/active-rms.py`, `scripts/mix/fader-plan.py`, and `scripts/mix/level-balance.py`.
- `src/dawproof/production/loopback.py` — adapted from the WASAPI loopback scripts under `scripts/mix/`.
- `src/dawproof/production/sf2.py` — adapted from `scripts/score/sf2.py`.
- `src/dawproof/production/orchestration.py` — generalized from reusable orchestration checks in `scripts/orch/orch-fugue-v2.py`, including register-aware melody handoff, midrange gap detection, and source-note coverage checks. It does not copy the source score's instrument plan or commission-specific material.

The supplied archive applies separate terms to non-code material: its documentation is identified as CC BY 4.0 and its example scores retain attribution/non-commercial terms. Those documentation and example-score assets are therefore not bundled into DAWProof's MIT code package. Project-specific composition scripts were reviewed as design material but are not represented as generic DAWProof Core behavior without adaptation and verification.
