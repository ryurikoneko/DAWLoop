# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""合成 EQ 的离线语义映射示例，不对应实际插件或宿主。"""

from dataclasses import asdict
import json

from dawloop.mix_plan import (SCHEMA_VERSION, EQAction, MixPlan, MixSourceSnapshot, MixTarget,
    ParameterMapping, PluginCapabilityProfile, PluginFingerprint, compile_mix_plan)


def main():
    fingerprint = PluginFingerprint("Synthetic EQ", 40, ("Frequency", "Gain", "Q"))
    mappings = (
        ParameterMapping("frequency", 0, "Frequency", "Hz", 20, 20000, 0, 1, "log", 1e-6),
        ParameterMapping("gain", 1, "Gain", "dB", -12, 12, 0, 1, "linear", 1e-6),
        ParameterMapping("q", 2, "Q", "Q", 0.1, 10, 0, 1, "linear", 1e-6),
    )
    profile = PluginCapabilityProfile("synthetic-eq-v1", "1", fingerprint, "fixed-bell",
                                      mappings, (), "synthetic-example-only")
    target = MixTarget("synthetic-build", "synthetic-session", 1, "synthetic-host", 1, 0, "synthetic-chain")
    source = MixSourceSnapshot("synthetic-request", target, "synthetic-clock", 10, 11, fingerprint,
        tuple(m.encode(v) for m, v in zip(mappings, (1000, 0, 1))), None, None, None)
    action = EQAction("eq-1", source.snapshot_hash, profile.profile_hash, "fixed-bell", 3100, -2, 1.4, 3)
    plan = MixPlan(SCHEMA_VERSION, "synthetic-operation", "synthetic-plan", "有限调整频谱",
                   0, 8, "a" * 64, (action,), 3, "synthetic-example-only")
    compiled = compile_mix_plan(plan, (source,), (profile,))
    print(json.dumps(asdict(compiled), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
