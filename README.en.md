<p align="center"><img src="docs/media/hero.png" alt="DAWLoop brand hero" width="100%"></p>
<p align="center"><img src="docs/media/logo.png" alt="DAWLoop logo" width="64" height="64"></p>

# DAWLoop

**Bring AI into the music-making workflow.**

DAWLoop connects music analysis, MIDI creation and real DAW actions. Explore material and edit melodies in the Desktop workspace; use the open Runtime to build agents that plan, execute, observe and check their results.

Music tools for creators. An extensible automation framework for developers.

[中文](README.md) | [English](README.en.md)

[![CI](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml)
[![MIT code](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-Alpha-orange)](docs/DESKTOP.md)

[Download Desktop Alpha](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.2) · [Explore Developer Runtime](docs/QUICKSTART.md) · [Demos](docs/DEMOS.md) · [Capabilities](docs/CAPABILITIES.md) · [Contribute](CONTRIBUTING.md)

## Explore DAWLoop

Music Intelligence brings listening, analysis, melody creation and editing into one workspace.

![Music Intelligence workspace](docs/media/music-home.png)

<details>
<summary>Music Analysis, Piano Roll Editing and Component Management</summary>

![Music Analysis](docs/media/analysis-report.png)
![Piano Roll Editing](docs/media/piano-roll.png)
![Component Management](docs/media/model-manager.png)

</details>

[Desktop workflow](docs/DESKTOP.md) · [From audio to melody](docs/DEMOS.md) · [Image sources](docs/media/README.md)

## What you can do

| Task | Workflow |
| --- | --- |
| Understand musical material | Import and audition audio; explore loudness, rhythmic changes, key candidates and analysis reports |
| Create melodies | Generate rule-assisted melodies with harmony, rhythm, density and seed constraints |
| Edit MIDI | Review notes in the Desktop Piano Roll, change pitch and velocity, undo, audition and export MIDI |
| Transcribe notes | Turn audio into editable notes after one-click Basic Pitch installation in Component Manager |
| Work inside a real DAW | Use the Runtime's FL Studio backends for operations with an explicit target |
| Build a music agent | Connect structured plans, target constraints, observation and verification to your own agent |

FL Studio MCP is one execution path, exposing transport, Channels, Piano Roll, Mixer and loaded-plugin parameter interfaces. DAWLoop's own Controller adds existing-Pattern identification and navigation, organizing actions around explicit targets and human review. [Capabilities and integration scope](docs/CAPABILITIES.md)

## Why DAWLoop?

### Bring musical intent into the production workflow

- **From plans to actions:** express musical intent with Note Plans and target constraints, then hand supported operations to a real DAW through execution adapters. Agent developers can connect their own planning to this path.
- **From actions to checked results:** identify the target, independently read its actual state, and compare the result with the plan. `PASS / STOP` helps an agent choose its next step; an execution acknowledgement alone is not proof. [Verification scope](docs/CAPABILITIES.md)
- **From analysis to editing:** listen, analyze, create and edit MIDI in the standalone Desktop workspace, while extending agent workflows through the open Runtime. They offer separate entry points; real DAW integration is configured separately.

[Explore the analysis-to-MIDI workflow](docs/DEMOS.md) · [Read the real FL Studio research record](evidence/public/fast_session_7.json)

### Brain / Hands / Ears

| Layer | What it brings to production |
| --- | --- |
| **Brain — Music Planning & Agent Rules** | Express intent through musical grids, Note Plans and constraints; organize the next action |
| **Hands — DAW Execution & Control** | Connect to real FL Studio and turn plans into supported host operations |
| **Ears — Music Analysis & Production Assistance** | Use MIDI, orchestration and audio measurements as input for the next plan |

The three layers connect creative intent, action and feedback through interfaces that tool-using agents can extend.

### Check the result after acting

**Plan → Execute → Observe → Verify → Iterate**

A tool reporting success provides execution information. DAWLoop's verification modules compare planned and actual events, returning **PASS / STOP** to guide continuation, stopping or re-planning. Human review remains part of host operations that require confirmation.

[Architecture](docs/ARCHITECTURE.md) · [Verification model](docs/VERIFICATION.md) · [Public evidence](evidence/public/README.md)

## Get started

### Download Desktop Alpha

[Windows x64 Portable ZIP](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.2/DAWLoop%2B0.5.6-alpha.2-Windows-x64-Portable.zip) · [Release notes and checksums](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.2)

1. Extract the complete program folder and run `DAWLoop.exe`.
2. In Music Intelligence's Component Manager, review the licenses and confirm installation of basic components.
3. Import a WAV to listen and analyze; install Basic Pitch to transcribe notes, edit them in the Piano Roll and export MIDI.

Codex, Node and system Python are unnecessary. The application is unsigned: verify its official source and checksums when Windows shows an unknown-publisher warning, and keep system security protections enabled. [First-run guide](docs/DESKTOP.md)

### Explore Developer Runtime

Python 3.11+. Start with synthetic material to generate analysis, profiles and a music plan:

```powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning]"
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

On Linux/macOS, use `python3 -m venv .venv` and `.venv/bin/python`. Choose a new output directory. [Quickstart](docs/QUICKSTART.md) · [FL Studio setup](docs/FL_STUDIO_SETUP.md) · [Deployment](docs/DEPLOYMENT.md)

## Built for music creators and developers

- **Music creators:** listen, analyze, create and edit in one workspace while keeping creative decisions in your hands.
- **Agent developers:** reuse musical contracts, execution adapters and verification interfaces with your own tool-using models.
- **Open-source contributors:** improve editing, compatibility, analysis or DAW integration. [Contributing](CONTRIBUTING.md)

## Product direction

Improve installation and component management, expand verifiable FL Studio workflows, refine agent planning, and research music retrieval, analysis and generation. [Roadmap](docs/ROADMAP.md)

## Current Release Notes

- Desktop **0.5.6-alpha.2** is a public Windows x64 Pre-release. It has run in the maintainer's Windows environment; independent clean-Windows compatibility still awaits validation.
- Bundled basic components support WAV analysis. Basic Pitch now offers in-app one-click installation after license review, real note transcription, Piano Roll editing and MIDI export, without system Python.
- The Desktop Piano Roll edits local MIDI. Real FL control uses a separate Runtime integration. General AutoMix, arbitrary-project autonomous control and full style learning remain research directions.
- Live FL research and offline verification have specific scopes, recorded separately from backend tool availability in [Capabilities](docs/CAPABILITIES.md). Public update notifications are disabled; updates remain user-initiated.
- [Alpha.1 remains available](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1); its original assets are unchanged.
- Screenshots show an earlier development build. Desktop source is at the [release tag](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.2); Python Runtime is on main. [Detailed release and installation scope](docs/DESKTOP.md)

## Open source & credits

Project-authored code uses the [MIT License](LICENSE). Branding and certain images have separate notices: [brand policy](TRADEMARKS.md), [license scope](LICENSE_POLICY.md), [media](docs/media/README.md).

Thanks to [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) for community FL Studio control, and Bilibili creator [坏影子不坏](https://space.bilibili.com/599132499) (UID 599132499) for the [DSH workflow demonstration](https://www.bilibili.com/video/BV1PTht6cENP/). Those production practices influenced the Production Pipeline; some generalized analysis code is adapted from their supplied MIT-licensed `whale-music-pipeline`, retaining original notices.

[Contribute](CONTRIBUTING.md) · [Issues](https://github.com/ryurikoneko/DAWLoop/issues) · [Acknowledgements](docs/ACKNOWLEDGEMENTS.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Provenance](PROVENANCE.md) · [Security](SECURITY.md)
