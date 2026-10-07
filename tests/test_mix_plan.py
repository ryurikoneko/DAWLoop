# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""离线混音合同不把映射、读回或试听相互代替。"""

from dataclasses import asdict, replace
import hashlib
import json
import math
import unittest

from dawloop.mix_plan import (SCHEMA_VERSION, EQAction, FaderAction, MixExecutionResult,
    MixPlan, MixSourceSnapshot, MixTarget, ParameterCondition, ParameterMapping,
    PluginCapabilityProfile, PluginFingerprint, compile_mix_plan, decode_plugin_scan)
from dawloop.production.mix import FaderCalibration


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def target(track=1, slot=0):
    return MixTarget("synthetic-build", "synthetic-session", 1, "synthetic-host", track, slot, "chain-1")


def eq_fixture(second=False, track=1):
    names = ("Gain", "Q", "Hz", "Bell mode") if second else ("Frequency", "Gain", "Q", "Bell mode")
    fp = PluginFingerprint("Synthetic EQ B" if second else "Synthetic EQ A", 40, names)
    mappings = (
        ParameterMapping("frequency", 2 if second else 0, "Hz" if second else "Frequency",
                         "Hz", 20, 20000, 0, 1, "log" if second else "linear", 1e-6),
        ParameterMapping("gain", 0 if second else 1, "Gain", "dB", -12, 12,
                         1 if second else 0, 0 if second else 1, "linear", 1e-6),
        ParameterMapping("q", 1 if second else 2, "Q", "Q", 0.1, 10, 0, 1, "linear", 1e-6),
    )
    profile = PluginCapabilityProfile("synthetic-b" if second else "synthetic-a", "1", fp,
        "existing-band-1", mappings, (ParameterCondition(3, "Bell mode", 1.0, 1e-6),), "synthetic-test-only")
    values = [0.0] * 4
    for m in mappings:
        values[m.parameter_index] = m.encode({"frequency": 1000, "gain": 0, "q": 1}[m.semantic])
    values[3] = 1
    source = MixSourceSnapshot("request-1", target(track), "synthetic-clock", 10, 11,
                              fp, tuple(values), None, None, None)
    action = EQAction("eq-1", source.snapshot_hash, profile.profile_hash, profile.band_id, 3100, -2, 1.4, 3)
    return source, profile, action


def plan(*actions):
    return MixPlan(SCHEMA_VERSION, "operation-1", "plan-1", "有限调整频谱", 0, 8, "a" * 64,
                   actions, sum(1 if type(a) is FaderAction else 3 for a in actions), "synthetic-test-only")


def scan(count=3):
    return {"schema_version": "plugin-parameter-scan-v1", "api_version": 40,
        "plugin_name": "Synthetic", "parameter_count": count, "parameter_count_after": count,
        "params": [{"index": i, "name": f"P{i}", "value": 0.5, "value_string": None} for i in range(count)],
        "errors": [], "warnings": [], "complete": True, "truncated": False}


class MixPlanTests(unittest.TestCase):
    def test_same_semantic_plan_compiles_for_two_different_layouts_and_curves(self):
        compiled = []
        for second in (False, True):
            source, profile, action = eq_fixture(second)
            result = compile_mix_plan(plan(action), (source,), (profile,))
            self.assertEqual(result.execution_permission, "OFFLINE_ONLY")
            for mapping, change in zip(profile.mappings, result.changes):
                expected = {"frequency": 3100, "gain": -2, "q": 1.4}[mapping.semantic]
                self.assertAlmostEqual(mapping.decode(change.absolute_value), expected)
                self.assertEqual(change.expected_before, source.parameter_values[mapping.parameter_index])
            compiled.append(result.changes[0].absolute_value)
        self.assertNotEqual(*compiled)

    def test_profile_plan_source_and_result_serialization_roundtrip(self):
        source, profile, action = eq_fixture()
        self.assertEqual(PluginCapabilityProfile.from_json(profile.to_json()), profile)
        self.assertEqual(MixSourceSnapshot.from_dict(json.loads(json.dumps(asdict(source)))), source)
        self.assertEqual(MixPlan.from_json(plan(action).to_json()), plan(action))
        result = MixExecutionResult("operation-1", "a" * 64, "OFFLINE_COMPILED", 0, 0, 0, 0,
                                   "NOT_MEASURED", "NOT_REPORTED", "NOT_ATTEMPTED")
        self.assertEqual(MixExecutionResult.from_json(result.to_json()), result)

    def test_unknown_profile_and_mismatched_layout_are_rejected(self):
        source, profile, action = eq_fixture()
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED"):
            compile_mix_plan(plan(action), (source,))
        other = replace(source, fingerprint=replace(source.fingerprint, plugin_name="Unknown"))
        with self.assertRaisesRegex(ValueError, "FINGERPRINT"):
            compile_mix_plan(plan(replace(action, snapshot_hash=other.snapshot_hash)), (other,), (profile,))

    def test_plugin_version_and_format_participate_in_layout_identity(self):
        source, profile, action = eq_fixture()
        for fp in (replace(source.fingerprint, plugin_version="2"),
                   replace(source.fingerprint, plugin_format="synthetic-format")):
            with self.subTest(fp=fp):
                changed = replace(source, fingerprint=fp)
                self.assertNotEqual(changed.fingerprint.layout_hash, source.fingerprint.layout_hash)
                with self.assertRaisesRegex(ValueError, "FINGERPRINT"):
                    compile_mix_plan(plan(replace(action, snapshot_hash=changed.snapshot_hash)), (changed,), (profile,))

    def test_same_model_different_instances_have_distinct_binding(self):
        source, profile, action = eq_fixture()
        other = replace(source, target=target(2))
        self.assertEqual(other.fingerprint.layout_hash, source.fingerprint.layout_hash)
        self.assertNotEqual(other.snapshot_hash, source.snapshot_hash)
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_MISSING"):
            compile_mix_plan(plan(action), (other,), (profile,))

    def test_stale_original_values_or_generations_do_not_reuse_old_plan(self):
        source, profile, action = eq_fixture()
        variants = [replace(source, parameter_values=(0.9,) + source.parameter_values[1:]),
                    replace(source, request_id="request-2")]
        for field, value in (("controller_build_id", "new-build"), ("controller_session_id", "new-session"),
                             ("project_generation", 2), ("host_generation", "new-host"),
                             ("chain_revision", "new-chain"), ("slot_index", 1)):
            variants.append(replace(source, target=replace(source.target, **{field: value})))
        for changed in variants:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, "SNAPSHOT_MISSING"):
                    compile_mix_plan(plan(action), (changed,), (profile,))

    def test_mode_wrong_band_and_gain_limit_rejected(self):
        source, profile, action = eq_fixture()
        changed = replace(source, parameter_values=source.parameter_values[:3] + (0,))
        with self.assertRaisesRegex(ValueError, "PRECONDITION"):
            compile_mix_plan(plan(replace(action, snapshot_hash=changed.snapshot_hash)), (changed,), (profile,))
        for modified in (replace(action, band_id="other"), replace(action, gain_db=-4)):
            with self.assertRaises(ValueError):
                compile_mix_plan(plan(modified), (source,), (profile,))

    def test_duplicate_writes_and_mixed_sessions_rejected(self):
        source, profile, action = eq_fixture()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PARAMETER"):
            compile_mix_plan(plan(action, replace(action, action_id="eq-2")), (source,), (profile,))
        other = replace(source, target=replace(target(2), controller_session_id="different"))
        other_action = replace(action, action_id="eq-2", snapshot_hash=other.snapshot_hash)
        with self.assertRaisesRegex(ValueError, "CONTEXT_DISAGREEMENT"):
            compile_mix_plan(plan(action, other_action), (source, other), (profile,))

    def test_mapping_units_domains_indexes_and_unknown_curves_rejected(self):
        _, profile, _ = eq_fixture()
        mapping = profile.mappings[0]
        cases = ({"unit": "dB"}, {"curve": "guess"}, {"parameter_index": True},
                 {"normalized_min": -0.1}, {"normalized_max": 0}, {"physical_min": 0},
                 {"physical_max": math.inf}, {"tolerance": 0})
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(mapping, **changes)
        with self.assertRaisesRegex(ValueError, "LAYOUT"):
            replace(profile, mappings=(replace(mapping, expected_name="Wrong"),) + profile.mappings[1:])
        with self.assertRaises(ValueError):
            mapping.encode(30000)
        with self.assertRaises(ValueError):
            mapping.encode(True)

    def test_calibrated_fader_compiles_absolute_target_without_clamping(self):
        calibration = FaderCalibration(((0.1, -24), (0.8, 0), (1.0, 6)))
        source = MixSourceSnapshot("request-1", target(slot=None), "synthetic-clock", 1, 2,
                                  None, (), 0.8, 0, digest(asdict(calibration)))
        action = FaderAction("fader-1", source.snapshot_hash, -2, 3)
        result = compile_mix_plan(plan(action), (source,), fader_calibrations=(calibration,))
        self.assertAlmostEqual(calibration.db_for_value(result.changes[0].absolute_value), -2)
        self.assertIsNone(result.changes[0].parameter_index)
        with self.assertRaisesRegex(ValueError, "CALIBRATION"):
            compile_mix_plan(plan(action), (source,))
        at_max = replace(source, fader_value=1.0, fader_db=6)
        with self.assertRaisesRegex(ValueError, "OUT_OF_RANGE"):
            compile_mix_plan(plan(replace(action, snapshot_hash=at_max.snapshot_hash, delta_db=1)),
                             (at_max,), fader_calibrations=(calibration,))
        bad = replace(source, fader_db=2)
        with self.assertRaisesRegex(ValueError, "BASELINE"):
            compile_mix_plan(plan(replace(action, snapshot_hash=bad.snapshot_hash)), (bad,),
                             fader_calibrations=(calibration,))

    def test_strict_plan_parser_rejects_source_and_unsupported_actions(self):
        source, profile, action = eq_fixture()
        row = json.loads(plan(action).to_json())
        row["source"] = "arbitrary-code"
        with self.assertRaisesRegex(ValueError, "FIELDS"):
            MixPlan.from_json(json.dumps(row))
        del row["source"]
        row["actions"][0]["kind"] = "load_plugin"
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_ACTION"):
            MixPlan.from_json(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "BUDGET_EXCEEDED"):
            replace(plan(action), parameter_write_budget=2)

    def test_snapshot_rejects_reversed_capture_missing_binding_and_wrong_value_count(self):
        source, _, _ = eq_fixture()
        for changes in ({"capture_completed_at": 9}, {"parameter_values": ()},
                        {"parameter_values": (True,) + source.parameter_values[1:]}, {"request_id": ""}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(source, **changes)
        with self.assertRaises(ValueError):
            replace(source.target, project_generation=True)
        with self.assertRaises(ValueError):
            replace(source.target, track_index=0)

    def test_results_keep_audio_preference_and_readback_independent(self):
        result = MixExecutionResult("op", "a" * 64, "APPLIED_READBACK_MATCHED", 3, 3, 0, 0,
                                   "MEASURED_CHANGED", "NOT_PREFERRED", "NOT_ATTEMPTED")
        self.assertEqual(result.human_audition, "NOT_PREFERRED")
        for changes in ({"binding_strength": "EXACT"}, {"matched_parameters": 2},
                        {"terminal_state": "OFFLINE_COMPILED"}, {"terminal_state": "VERIFIED_WRITE"}):
            with self.assertRaises(ValueError):
                replace(result, **changes)
        partial = replace(result, terminal_state="PARTIAL_APPLY", matched_parameters=1, unknown_parameters=2)
        self.assertEqual(partial.unknown_parameters, 2)


class PluginScanDecoderTests(unittest.TestCase):
    def test_more_than_fifty_and_missing_display_are_supported(self):
        fingerprint, values = decode_plugin_scan(scan(80))
        self.assertEqual(len(fingerprint.parameter_names), 80)
        self.assertEqual(len(values), 80)

    def test_missing_old_incomplete_duplicate_or_changed_payload_rejected(self):
        original = scan()
        cases = ([], {}, {**original, "complete": False}, {**original, "truncated": True},
                 {**original, "errors": [{"index": 1}]}, {**original, "parameter_count_after": 4},
                 {**original, "params": original["params"][:2]},
                 {**original, "params": [original["params"][0]] * 3},
                 {**original, "params": [{**p, "value": "0.5"} for p in original["params"]]},
                 {**original, "api_version": 25}, {**original, "success": False},
                 {**original, "error": "host failure"})
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    decode_plugin_scan(case)


if __name__ == "__main__":
    unittest.main()
