# Acknowledgements & Prior Art

## FL Studio MCP

- Project: karl-andres/fl-studio-mcp — https://github.com/karl-andres/fl-studio-mcp
- Reference commit: f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0
- License at that commit: MIT, with the upstream notice retained in the bundled snapshot.
- Relationship to FLSkill: used and tested as an early FL Studio control path and practical reference for MCP-driven DAW automation.

The upstream README describes transport controls, Mixer volume / pan / mute / solo, Channel control and Mixer routing, Piano Roll note writing and readback, and access to parameters on loaded plugins. It also documents that the project cannot load new plugins or create Patterns programmatically. These upstream capabilities are not claims that FLSkill has independently implemented or verified each operation.

FLSkill does not aim to replace FL Studio MCP. The upstream project provides an FL Studio control path; FLSkill focuses on musical timing, structured Note Plans, write/readback separation, Exact-Set Verification, state checks, and resumable orchestration.

> FL Studio MCP helped prove that FL Studio could be controlled programmatically; FLSkill is trying to make those operations verifiable.

## Production Pipeline / whale-music-pipeline

We thank the developer of whale-music-pipeline, 坏影子不坏 (Bilibili UID 599132499; https://space.bilibili.com/599132499), for the original workflow and reusable code. The FLSkill maintainer reports receiving the developer's direct permission to reuse the code. The supplied source code is MIT-licensed, and its original notice is preserved at third_party/whale-music-pipeline/LICENSE.

This work informed MIDI inspection, orchestration checks, Windows WASAPI loopback measurement, active-frame RMS, measured FL Studio fader calibration, and SoundFont utilities. Generalized modules live under src/flskill/production/ and remain subject to FLSkill's Plan → Execute → Read Back → Verify → PASS / STOP rule. An analysis result or fader plan is not proof of a verified DAW state.

Work-specific scores, arrangements, examples, and non-code assets are not included as generic FLSkill Core behavior. See PRODUCTION_PIPELINE.md, PRODUCTION_PIPELINE_PROVENANCE.md, and THIRD_PARTY_NOTICES.md for source and license boundaries.
