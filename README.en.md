<p align="center"><img src="docs/media/hero.png" alt="DAWLoop black-and-white brand hero with a copyright signature" width="100%"></p>

<p align="center"><img src="docs/media/logo.png" alt="Official DAWLoop circular waveform logo" width="64" height="64"></p>

# DAWLoop

**Music intelligence, MIDI editing and evidence-aware DAW automation.**

[中文](README.md) | [English](README.en.md)

[![CI](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ryurikoneko/DAWLoop/actions/workflows/ci.yml)
[![MIT code](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-Alpha-orange)](docs/CAPABILITIES.md)

[Get started](#get-started) · [Desktop preview](docs/DESKTOP.md) · [Capabilities & evidence](docs/CAPABILITIES.md) · [Architecture](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) · [Contribute](CONTRIBUTING.md)

[KNOWN | HIGH] DAWLoop connects music assets, structured plans, editing and controlled host operations. The public repository currently delivers Runtime / Agent engineering; the single-window Desktop / Music Intelligence product is developed in a separate feature tree.

> **Alpha / Internal Preview, not a stable release.**
> [COMPUTED | HIGH] Audited 2026-10-14: public Runtime code baseline `1a99482` is unchanged by this showcase. Desktop feature baseline is `66806b5`; latest separate packaging source is `8123ae3`, version `0.5.6-internal.1`. **Desktop is not publicly downloadable yet**: clean-Windows first installation and distributable audio components remain blocked. [Release gates and components](docs/DESKTOP.md)

## See the product in development

[COMPUTED | HIGH] These are actual running internal-candidate screenshots with original synthetic test material, not mockups or a promise of public installation availability.

![Actual Music Intelligence workspace](docs/media/music-home.png)

<details>
<summary>See the real analysis report and Piano Roll</summary>

![Actual audio analysis; uncertain tempo and key remain uncertain](docs/media/analysis-report.png)

![Actual Piano Roll with notes, velocity and linked selection](docs/media/piano-roll.png)

![Model Manager honestly explains missing components](docs/media/model-manager.png)

</details>

[Screenshot provenance & privacy](docs/media/README.md) · [Two separate demo scenarios](docs/DEMOS.md)

## DAWLoop Desktop

| Area | What to explore | Current delivery scope |
| --- | --- | --- |
| Music analysis | Audio import, basic measurements, loudness, key candidates and time curves | Internal Desktop scenario tests; estimates are not certain conclusions |
| Audio to MIDI | Basic Pitch transcription, note review, editing and export | Internal candidate tests; complex mixes are not complete multitrack separation |
| Melody creation | Harmony, rhythm, density and Seed constraints | `RULE_BASED`, not large-model inference |
| MIDI editing | Piano Roll, velocity, undo, audition and MIDI readback | Internal candidate tests |
| Runtime / Agent | Music plans, offline verification, target guards, human acceptance and observation | Public main; historical constrained FAST live evidence |
| Model management | Isolated Workers, installation state, versions and failure reasons | Internal candidate; clean-Windows first installation is not proven |

## DAWLoop Runtime / FL Studio Integration

[KNOWN | HIGH] Public Runtime provides structured plans, offline verification and constrained FAST research. Live work retains target checks, one-shot dispatch, human Preview/Accept and observation. New Desktop Host/Mixer wiring is uncertified; the two demos are not presented as seamless autonomous control.

## Capabilities and verification scope

[KNOWN | HIGH] **Public code, internal candidate, offline-tested, scenario-live-tested, experimental, unverified, planned and blocked are distinct states.** See the [shared capability matrix](docs/CAPABILITIES.md).

- [KNOWN | HIGH] Historical Native FAST live loop: fixed 16 notes, one dispatch, human Accept, application observation and completion callback; terminal state remains `COMPLETED_UNVERIFIED`. [Sanitized evidence](evidence/public/fast_session_7.json)
- [KNOWN | HIGH] The new Desktop Host / Session integration, real Mixer and arbitrary-project writes are not certified here. A visible UI does not grant permission.
- [KNOWN | HIGH] OMAR-RQ Embedding extraction is not artist-style learning. Similarity search and style recognition require separate implementation, evaluation and authorization.
- [KNOWN | HIGH] Auto Accept, complete AutoMix, autonomous Agent operation and full YuE2 generation are not certified product capabilities.

## Get started

### Music creators

[KNOWN | HIGH] For the desktop experience, read the [Desktop preview guide](docs/DESKTOP.md). Public Releases do not currently offer the new Desktop. A Runtime wheel is not a desktop installer; avoid unaudited mirrors. A future distribution will document components, model licenses and installation requirements separately.

### Developers: start offline, without a host

[KNOWN | HIGH] Public source requires Python 3.11+. This tutorial uses synthetic material and does not launch FL Studio:

```sh
git clone https://github.com/ryurikoneko/DAWLoop.git
cd DAWLoop
python -m venv .venv
# Windows: use .venv/Scripts/python.exe
.venv/bin/python -m pip install -e ".[learning]"
.venv/bin/python learning/examples/generic_learning/run.py --output workspace/personal/demo-v1
```

[KNOWN | HIGH] Choose a fresh output directory on each run. [Quick Start](docs/QUICKSTART.md) · [Deployment & dependencies](docs/DEPLOYMENT.md) · [Runtime engineering guide](docs/RUNTIME_GUIDE.en.md)

### FL Studio research integration

[KNOWN | HIGH] Follow the [deployment contract](docs/DEPLOYMENT.md) for a dedicated test project, Controller and real observation entrypoint. Package installation does not authorize writes to a current work. Preserve target, generation, source, budget and human-acceptance gates. Community adapters and Native FAST are verified separately.

## Downloads and system requirements

| Entry | Current state | System and components |
| --- | --- | --- |
| Windows Desktop | **No public download yet**; internal candidate 0.5.6-internal.1 | Windows x64; complete program folder; managed components required for analysis/transcription |
| [Public Runtime Alpha](https://github.com/ryurikoneko/DAWLoop/releases) | Actual Python releases, not Desktop installers | Python3.11+ and selected extras; live FL research has a stated Windows scope |
| [Source and offline tutorial](docs/QUICKSTART.md) | Public-main engineering entrypoint | FL not required; Desktop source is not in main and no fictitious npm command is offered |

[KNOWN | HIGH] The portable interface includes Electron/Node and requires no Codex. Basic DSP, Basic Pitch and OMAR weights are not bundled. The UI remains accessible when components are missing and explains configuration. A development-machine environment is not a first-user installation. Historical analyses and models are not automatically deleted. [Desktop scope](docs/DESKTOP.md)

## Architecture and components

```text
Public Runtime / Agent    Music contracts → validation → controlled FAST → observation & human review
Internal Desktop          Renderer → Preload → controlled IPC → Adapter / Worker
Future host integration   Trusted source → session & target binding → Publisher → Desktop
```

[KNOWN | HIGH] Publication and certification are managed separately for these routes. Desktop does not call private FL implementations; models do not run in the Renderer. Generic MusicalPlan → FAST field/unit conversion still needs independent integration. [Full architecture](docs/ARCHITECTURE.md)

## Next

- [INFERRED | HIGH] Separately deliver a Desktop candidate, trusted offline components and clean-Windows acceptance.
- [INFERRED | HIGH] Verify Host / Session, Mixer structure and plugin read capabilities under an exclusive host lease.
- [INFERRED | HIGH] Research reference retrieval, music learning and generative models under separate evidence and permission gates; do not invent Embedding semantics.
- [INFERRED | HIGH] Connect generic music plans to the constrained FAST workflow while retaining human confirmation and verification boundaries.

[Roadmap](docs/ROADMAP.md) · [Verification rules](docs/VERIFICATION.md) · [Historical Runtime status](docs/DAWLOOP_RUNTIME_V2.md#current)

## Contribution, licensing and acknowledgements

[KNOWN | HIGH] **DAWLoop software code is released under the MIT License. Brand marks and character artwork are subject to separate asset policies where applicable.** Prior grants are preserved. Individual ownership is the confirmed plan; authorship and legal title remain pending review, and future characters are not yet created. [Brand policy](TRADEMARKS.md) · [License scope](LICENSE_POLICY.md) · [Asset registry](docs/brand/README.md) · [Media notice](docs/media/README.md)

[KNOWN | HIGH] The pinned MIT snapshot of [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) retains its original notices. Bilibili creator [坏影子不坏](https://space.bilibili.com/599132499), the [DSH workflow demonstration](https://www.bilibili.com/video/BV1PTht6cENP/) and `whale-music-pipeline` provide practical inspiration and code provenance for the Production Pipeline. Inspiration, code licensing and private-material rights are recorded separately.

[Contribute](CONTRIBUTING.md) · [Security reporting](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Full acknowledgements](docs/ACKNOWLEDGEMENTS.md) · [Provenance](PROVENANCE.md) · [NOTICE](NOTICE) · [AUTHORS](AUTHORS) · [Citation](CITATION.cff)

[KNOWN | HIGH] Historical FLSkill → DAWProof → DAWLoop commits, tags and Releases remain intact. Detailed engineering content lives in the [Runtime guide](docs/RUNTIME_GUIDE.en.md), preserving evidence behind the shorter homepage.
