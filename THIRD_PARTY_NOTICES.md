# 第三方声明

## FL Studio MCP

- Project: `karl-andres/fl-studio-mcp`
- Repository: <https://github.com/karl-andres/fl-studio-mcp>
- Bundled commit: `f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0`
- License: MIT
- Copyright:
  - Copyright (c) 2025 calvinw
  - Copyright (c) 2025 Karl Andres
- Bundling purpose: Used as an optional FL Studio execution backend for DAWLoop.

DAWLoop does not claim authorship of the bundled FL Studio MCP implementation. The upstream source snapshot is stored under [`third_party/fl-studio-mcp/`](third_party/fl-studio-mcp/); its original MIT license is preserved at [`third_party/fl-studio-mcp/LICENSE`](third_party/fl-studio-mcp/LICENSE). The root [`LICENSE`](LICENSE) applies to DAWLoop-authored files and does not replace the bundled project's license.

The vendored snapshot contains only the upstream files needed to run its MCP server and install its FL Studio scripts. The demo video and upstream installer scripts are not bundled.

## whale-music-pipeline

- Original project: `whale-music-pipeline`
- Developer attribution: [坏影子不坏](https://space.bilibili.com/599132499), Bilibili UID `599132499`
- Code license: MIT
- Original copyright notice: `Copyright (c) 2026 whale-music-pipeline contributors`
- Additional permission: the DAWLoop maintainer reports receiving direct permission from the developer to reuse the code.
- Bundling purpose: reusable MIDI inspection, orchestration checks, SoundFont auditioning, audio-level analysis, mixer calibration/planning, and optional Windows loopback capture for DAWLoop's agent-oriented production pipeline.

The complete original code-license notice is preserved at [`third_party/whale-music-pipeline/LICENSE`](third_party/whale-music-pipeline/LICENSE). DAWLoop does not claim original authorship of adapted algorithms.

The following DAWLoop files are adapted from, or directly generalized from, the MIT-licensed source scripts:

- `src/dawloop/production/smf.py` — adapted from `scripts/mix/midi-windows.py`.
- `src/dawloop/production/mix.py` — adapted from `scripts/mix/active-rms.py`, `scripts/mix/fader-plan.py`, and `scripts/mix/level-balance.py`.
- `src/dawloop/production/loopback.py` — adapted from the WASAPI loopback scripts under `scripts/mix/`.
- `src/dawloop/production/sf2.py` — adapted from `scripts/score/sf2.py`.
- `src/dawloop/production/orchestration.py` — generalized from reusable orchestration checks in `scripts/orch/orch-fugue-v2.py`, including register-aware melody handoff, midrange gap detection, and source-note coverage checks. It does not copy the source score's instrument plan or commission-specific material.

The supplied archive applies separate terms to non-code material: its documentation is identified as CC BY 4.0 and its example scores retain attribution/non-commercial terms. Those documentation and example-score assets are therefore not bundled into DAWLoop's MIT code package. Project-specific composition scripts were reviewed as design material but are not represented as generic DAWLoop Core behavior without adaptation and verification.

## Desktop preview references — not bundled dependencies

[KNOWN | HIGH] This showcase includes screenshots from an independent internal Desktop, not its model code, packages or weights. Basic Pitch, OMAR-RQ, SheetSage2 and YuE2 references describe provider scope, not licenses granted by this repository. Any future source or model distribution needs its own pinned provenance and dependency/weight license review. The screenshots do not alter the notices above.

[KNOWN｜HIGH] 本轮不把模型缓存、权重、FFmpeg 或 Python 环境作为公开附件；名称出现不代表第三方背书，也不改变原许可。[Desktop范围](docs/DESKTOP.md) · [品牌图像声明](docs/media/LICENSE.txt)

## Brand and character provenance review

[KNOWN | HIGH] No completed character art, layered file or new third-party artwork is included by this supplement. The selected logo's original artist, reference permissions and AI-assisted creation details remain PENDING_OWNER_REVIEW. Existing component notices above are unchanged; this supplement does not replace a missing artist license with software MIT or the maintainer's signature.

[KNOWN｜HIGH] 商标、人物及展示文件的来源/作者/拟定个人主体分别登记；发现第三方素材时按实际原许可记录，不把本项目声明当作第三方授权。[清单](docs/brand/README.md)
