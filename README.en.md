<p align="center"><img src="docs/media/hero.png" alt="DAWLoop brand hero" width="100%"></p>

<p align="center"><img src="docs/media/logo.png" alt="DAWLoop logo" width="64" height="64"></p>

# DAWLoop

**An open framework connecting music creation with real DAW actions.**

From analyzing musical material and planning MIDI edits to operating real FL Studio through execution backends, DAWLoop gives music creators and AI-agent developers a way to connect creative decisions with observable actions. In supported workflows, an agent can check the result before deciding to continue or re-plan.

You can try the **open-source Python Runtime / Agent toolkit** today or download the **Desktop music workspace as an Experimental Alpha**. These are separate development lines, not yet a complete desktop DAW-control product.

[中文](README.md) | [English](README.en.md)

[![CI](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml)
[![MIT code](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-Alpha-orange)](docs/CAPABILITIES.md)

[Try the Runtime](#quick-start) · [Explore Desktop](docs/DESKTOP.md) · [Documentation](docs/QUICKSTART.md) · [Capabilities](docs/CAPABILITIES.md) · [Contribute](CONTRIBUTING.md) · [Releases](https://github.com/ryurikoneko/DAWLoop/releases)

## Meet DAWLoop Desktop

Screenshots are from the preceding internal development build and show the Music Intelligence workspace. [Desktop 0.5.6 Alpha](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) is now public; its actual distribution scope and limitations are described below.

![DAWLoop Music Intelligence workspace](docs/media/music-home.png)

<details>
<summary>More views: audio analysis, Piano Roll and model management</summary>

![Music Analysis](docs/media/analysis-report.png)

![Piano Roll Editing](docs/media/piano-roll.png)

![Model Management](docs/media/model-manager.png)

</details>

[Desktop details](docs/DESKTOP.md) · [Demo scenarios](docs/DEMOS.md) · [Screenshot provenance](docs/media/README.md)

## What can DAWLoop do?

| Area | What you can do | Availability today |
| --- | --- | --- |
| Music analysis | Explore loudness, rhythmic changes and key candidates to understand musical material | Desktop Experimental Alpha; some results are estimates |
| Audio to MIDI | Basic Pitch transcription, note review, editing and export | Existing verified environment; new installation disabled, not full source separation |
| MIDI composition | Generate melodies with harmony, rhythm, density and seed constraints | Desktop Experimental Alpha; currently rule-based |
| Piano Roll editing | Review notes, edit velocity, undo, audition and export MIDI | Desktop Experimental Alpha; in-app editor |
| Music planning & verification | Describe notes, timing and targets, then compare planned and observed events | Public Python Runtime; core verification is offline-tested |
| DAW control | Operate a running DAW and retrieve state through backends such as FL Studio MCP | Experimental Runtime integration; live evidence varies by operation |

The Desktop's in-app Piano Roll editor should not be confused with verified note writing inside FL Studio.

**DAWLoop has a real execution path into FL Studio.** The public Runtime bundles a pinned community FL Studio MCP backend, covering transport, Channels, Piano Roll operations, Mixer state and parameters on loaded plugins. It can access existing Patterns; the upstream backend cannot create Patterns programmatically or load new plugins. Individual operations still require integration setup, target confirmation and result review. A backend capability does not mean DAWLoop has independently live-verified that operation.

[Full capabilities and evidence](docs/CAPABILITIES.md)

## Why DAWLoop?

DAWLoop organizes the workflow into three complementary layers:

| Layer | Responsibility |
| --- | --- |
| Brain — DAWLoop Core | Musical timing, structured plans, target constraints and result verification |
| Hands — DAW execution backends | Supported actions and state retrieval inside a real DAW; FL Studio is the primary integration target |
| Ears — Production Pipeline | MIDI and orchestration analysis, audio measurement and production-planning assistance |

These layers provide interfaces for an agent to understand, act and use feedback. Fully autonomous production remains a research direction. The intended loop is:

~~~text
Understand → Plan → Execute → Observe → Verify → Iterate
                                     PASS / STOP
                              Human review / Agent decision
~~~

A MIDI tool can produce a file for manual import. DAWLoop also provides a real DAW execution path and rules for checking the result. A tool reporting success is not proof that the plan was realized: where trustworthy readback is available, the verifier compares planned and actual events and returns **PASS / STOP** to inform the agent's next action.

Planning and comparison modules are public and offline-tested; limited FL Studio research workflows also have live execution records. Having run in a real DAW, archiving evidence and meeting verification rules are distinct evidence scopes. See the [capability matrix](docs/CAPABILITIES.md).

[Architecture](docs/ARCHITECTURE.md) · [Verification approach](docs/VERIFICATION.md) · [Public live-evidence records](evidence/public/README.md)

## Quick start

### Looking for the music workspace?

Download [DAWLoop v0.5.6-alpha.1 Windows x64 Portable](https://github.com/ryurikoneko/DAWLoop/releases/download/v0.5.6-alpha.1/DAWLoop%2B0.5.6-alpha.1-Windows-x64-Portable.zip) (about 266 MiB), or see [release notes and SHA-256 checksums](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1). Extract, run `DAWLoop.exe`, confirm installation of the bundled basic music analysis components in Component Manager, then import WAV. Codex, Node and system Python are not required.

**Experimental Alpha — Tested on maintainer's Windows environment. Clean Windows compatibility has not been independently verified.** Basic Pitch weights are not bundled; first installation of its legacy runtime is disabled, while existing verified environments remain usable. Rule composition, Piano Roll and MIDI export work independently. [First run and limits](docs/DESKTOP.md) · [Actual Desktop source](https://github.com/ryurikoneko/DAWLoop/tree/v0.5.6-alpha.1). Historical Python Runtime assets are not Desktop installers.

### Trying the open-source Runtime?

Requires Python 3.11 or later. This example uses synthetic data and **does not start FL Studio**.

Windows PowerShell:

~~~powershell
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[learning]"
.\.venv\Scripts\python.exe learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
~~~

On Linux or macOS, after cloning and entering the repository:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[learning]"
.venv/bin/python learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
~~~

The example writes analysis, profile and music-plan JSON into the chosen directory. That directory must not already exist; choose a fresh path when running it again.

[Quickstart guide](docs/QUICKSTART.md) · [Deployment & dependencies](docs/DEPLOYMENT.md) · [Runtime developer guide](docs/RUNTIME_GUIDE.en.md)

### Exploring FL Studio integration?

Start with the [deployment guide](docs/DEPLOYMENT.md) and [FL Studio setup instructions](docs/FL_STUDIO_SETUP.md). Prepare a disposable test project, follow target confirmation and human-authorization requirements, and do not experiment on unsaved production projects.

## Releases and what's next

**Python Runtime:** Public source and Alpha release artifacts are available from [GitHub Releases](https://github.com/ryurikoneko/DAWLoop/releases).

**DAWLoop Desktop:** [0.5.6-alpha.1](https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.1) is publicly available as a Pre-release. Local first installation of bundled basic components, real WAV analysis, restart recovery, Piano Roll editing and MIDI export/readback passed. Independent clean Windows remains NOT_TESTED, with uncertainty accepted by the maintainer; this is not Stable or independently ready out of the box. Public update notifications remain disabled; no automatic downloading or installation occurs.

Future directions:

- Improve Desktop first installation and component management.
- Expand and verify FL Studio integration.
- Refine agent music planning and result verification.
- Research music retrieval, analysis and generation.

See the [roadmap](docs/ROADMAP.md) and [capability matrix](docs/CAPABILITIES.md) for detailed scope and progress.

## Open source, contribution and acknowledgements

DAWLoop-authored software code is available under the [MIT License](LICENSE). Third-party code retains its original licenses and attribution. The project name, logo and certain showcase images have separate use notices: see the [brand guidelines](TRADEMARKS.md), [license scope](LICENSE_POLICY.md) and [media notice](docs/media/README.md).

Thanks to the community [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) project and Bilibili creator [坏影子不坏](https://space.bilibili.com/599132499) (UID 599132499), whose [DSH workflow demonstration](https://www.bilibili.com/video/BV1PTht6cENP/) influenced the Production Pipeline design and production practices. Some generalized analysis code is adapted from their supplied MIT-licensed `whale-music-pipeline`, with original attribution retained. Detailed source, copyright and license attributions are in [Third-party notices](THIRD_PARTY_NOTICES.md) and [Acknowledgements](docs/ACKNOWLEDGEMENTS.md).

[Open an issue](https://github.com/ryurikoneko/DAWLoop/issues) or see the [contribution guide](CONTRIBUTING.md) to get involved. [Security reporting](SECURITY.md) · [Provenance](PROVENANCE.md) · [Citation](CITATION.cff)
