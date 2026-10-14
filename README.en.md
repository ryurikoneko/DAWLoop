<p align="center"><img src="docs/media/hero.png" alt="DAWLoop brand hero" width="100%"></p>

<p align="center"><img src="docs/media/logo.png" alt="DAWLoop logo" width="64" height="64"></p>

# DAWLoop

**Intelligent tools for music creation, and an open framework for more accountable AI-driven DAW automation.**

DAWLoop explores how music analysis, MIDI composition and DAW automation can work together—from preparing material and planning edits to executing supported operations and observing the outcome. Its guiding idea is simple: an AI agent should not only issue commands; where supported, it should also be able to check what happened.

The project currently has two distinct entry points: **a public Python Runtime / Agent toolkit** and **a Desktop music workspace still in internal preview**. They have different availability and verification scopes and are not yet one fully integrated product.

[中文](README.md) | [English](README.en.md)

[![CI](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml)
[![MIT code](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-Alpha-orange)](docs/CAPABILITIES.md)

[Quick start](#quick-start) · [Desktop preview](docs/DESKTOP.md) · [Capabilities & evidence](docs/CAPABILITIES.md) · [Architecture](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md)

## Meet DAWLoop Desktop

These images show a running internal Desktop candidate using original synthetic test material. **They are not mockups, and they do not imply that a public Desktop download is available.**

![DAWLoop Music Intelligence workspace](docs/media/music-home.png)

<details>
<summary>More views: audio analysis, Piano Roll and model management</summary>

![Audio analysis report with measurements and uncertain estimates](docs/media/analysis-report.png)

![In-app Piano Roll note and velocity editing](docs/media/piano-roll.png)

![Model and component management](docs/media/model-manager.png)

</details>

[Desktop details](docs/DESKTOP.md) · [Demo scenarios](docs/DEMOS.md) · [Screenshot provenance](docs/media/README.md)

## What can DAWLoop do?

| Area | What it explores | Availability today |
| --- | --- | --- |
| Music analysis | Audio loudness, changes over time, and tempo/key candidates | Internal Desktop preview; estimates are not guaranteed conclusions |
| Audio to MIDI | Basic Pitch transcription, note review, editing and export | Internal Desktop preview; not full source separation for complex mixes |
| MIDI creation & editing | Rule-assisted melody creation, Piano Roll, velocity, undo and audition | Internal Desktop preview; melody generation is rule-based |
| Music planning & verification | Describe notes, timing and targets, then compare planned and observed events | Public Python Runtime; core verification is offline-tested |
| FL Studio automation research | Connect control, human review and observation in defined test scenarios | Experimental integration; no general arbitrary-project write guarantee |

The Desktop's in-app Piano Roll editor should not be confused with verified note writing inside FL Studio.

[Full capabilities and evidence](docs/CAPABILITIES.md)

## Beyond execution: checking the result

DAWLoop is designed around a repeatable process:

~~~text
Understand music and goals → Plan → Execute supported actions
                                       ↓
                             Observe → Compare results
                                       ↓
                          Human or agent decides what follows
~~~

For example, after writing MIDI events, a successful tool response alone does not establish that the planned notes are present. DAWLoop's verification modules compare expected and observed events and report whether they match.

**Scope matters:** planning and comparison are implemented in the public Runtime and have offline test coverage. Real FL Studio writing, readback and complete closed loops require separate live verification; offline success is not a general live-control claim.

[Architecture](docs/ARCHITECTURE.md) · [Verification approach](docs/VERIFICATION.md) · [Public live-evidence records](evidence/public/README.md)

## Quick start

### Looking for the music workspace?

See the [Desktop preview and installation status](docs/DESKTOP.md). **There is no public download of the new Desktop yet.** Python packages on the [Releases page](https://github.com/ryurikoneko/DAWLoop/releases) are not Desktop installers.

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

On Linux or macOS, replace both Python executable paths with .venv/bin/python. Use a new output directory for each run.

[Quickstart guide](docs/QUICKSTART.md) · [Deployment & dependencies](docs/DEPLOYMENT.md) · [Runtime developer guide](docs/RUNTIME_GUIDE.en.md)

### Exploring FL Studio integration?

Start with the [deployment guide](docs/DEPLOYMENT.md) and [FL Studio setup instructions](docs/FL_STUDIO_SETUP.md). Prepare a disposable test project, follow target confirmation and human-authorization requirements, and do not experiment on unsaved production projects.

## Releases and what's next

**Python Runtime:** Public source and Alpha release artifacts are available from [GitHub Releases](https://github.com/ryurikoneko/DAWLoop/releases).

**DAWLoop Desktop:** Internal builds have demonstrated audio analysis, transcription and MIDI editing. Independent clean-Windows installation and distribution of required audio components are not yet accepted, so the new Desktop is not publicly downloadable.

Next priorities include the Desktop installation experience, expanding verifiable FL Studio integration, and continuing research into music analysis and generation. See the [roadmap](docs/ROADMAP.md) and [capability matrix](docs/CAPABILITIES.md) for detailed scope and progress.

## Open source, contribution and acknowledgements

DAWLoop-authored software code is available under the [MIT License](LICENSE). Third-party code retains its original licenses and attribution. The project name, logo and certain showcase images have separate use notices: see the [brand guidelines](TRADEMARKS.md), [license scope](LICENSE_POLICY.md) and [media notice](docs/media/README.md).

Thanks to the community [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) project and to Bilibili creator [坏影子不坏](https://space.bilibili.com/599132499), whose [DSH workflow demonstration](https://www.bilibili.com/video/BV1PTht6cENP/) and related whale-music-pipeline work informed parts of the production workflow. Detailed source, copyright and license attributions are in [Third-party notices](THIRD_PARTY_NOTICES.md) and [Acknowledgements](docs/ACKNOWLEDGEMENTS.md).

[Open an issue](https://github.com/ryurikoneko/DAWLoop/issues) or see the [contribution guide](CONTRIBUTING.md) to get involved. [Security reporting](SECURITY.md) · [Provenance](PROVENANCE.md) · [Citation](CITATION.cff)
