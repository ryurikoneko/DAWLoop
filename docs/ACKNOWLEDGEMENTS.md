# Acknowledgements & Prior Art

## FL Studio MCP

- Project: karl-andres/fl-studio-mcp — https://github.com/karl-andres/fl-studio-mcp
- Reference commit: f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0
- License at that commit: MIT, with the upstream notice retained in the bundled snapshot.
- Relationship to DAWLoop: used and tested as an early FL Studio control path and practical reference for MCP-driven DAW automation.

The upstream README describes transport controls, Mixer volume / pan / mute / solo, Channel control and Mixer routing, Piano Roll note writing and readback, and access to parameters on loaded plugins. It also documents that the project cannot load new plugins or create Patterns programmatically. These upstream capabilities are not claims that DAWLoop has independently implemented or verified each operation.

DAWLoop does not aim to replace FL Studio MCP. The upstream project provides an FL Studio control path; DAWLoop combines musical timing and structured Note Plans with write/readback separation, Exact-Set Verification, state checks, and iterative agent orchestration.

> FL Studio MCP helped prove that FL Studio could be controlled programmatically; DAWLoop builds a planning, observation, verification, and iteration loop around those operations.

## Creator acknowledgement: 坏影子不坏

We thank Bilibili creator [坏影子不坏](https://space.bilibili.com/599132499) (UID 599132499) for their work. Their DSH videos and production-workflow demonstrations, including [this video](https://www.bilibili.com/video/BV1PTht6cENP/), were an important influence on the DAWLoop Production Pipeline design. Relevant areas include arranging and orchestration analysis, MIDI and section analysis, playback / loopback measurement, active-frame RMS, FL Studio Mixer / fader calibration, and production-workflow automation. DSH here means the creator's video / workflow demonstrations, not a separately bundled software package.

## Code source and license: whale-music-pipeline

Portions of DAWLoop's generalized Production Pipeline code are adapted from the supplied `whale-music-pipeline` source archive. The DAWLoop maintainer reports receiving the developer's direct permission to reuse the code. The source code is MIT-licensed, and its original notice is preserved at `third_party/whale-music-pipeline/LICENSE`. This code provenance is separate from the creator acknowledgement above.

This work informed MIDI inspection, orchestration checks, Windows WASAPI loopback measurement, active-frame RMS, measured FL Studio fader calibration, and SoundFont utilities. Generalized modules live under src/dawloop/production/ and remain subject to DAWLoop's Plan → Execute → Read Back → Verify → PASS / STOP rule. An analysis result or fader plan is not proof of a verified DAW state.

Work-specific scores, arrangements, examples, and non-code assets are not included as generic DAWLoop Core behavior. See PRODUCTION_PIPELINE.md, PRODUCTION_PIPELINE_PROVENANCE.md, and THIRD_PARTY_NOTICES.md for source and license boundaries.
