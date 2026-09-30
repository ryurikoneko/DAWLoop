import unittest

from dawloop.runtime import (
    Capability,
    CapabilityRegistry,
    ExecutionMode,
    OperationPolicy,
    SafetyGuard,
    VerificationPolicy,
    decide_verification,
)


class RuntimePolicyTests(unittest.TestCase):
    def test_fast_mode_skips_routine_verification(self):
        policy = OperationPolicy(mode=ExecutionMode.FAST, operation_kind="set_mixer_volume")
        self.assertFalse(decide_verification(policy))

    def test_fast_mode_still_verifies_destructive_boundaries(self):
        policy = OperationPolicy(
            mode=ExecutionMode.FAST,
            operation_kind="delete_channel",
            safety=SafetyGuard(destructive=True, require_explicit_confirmation=True),
        )
        self.assertTrue(decide_verification(policy))

    def test_user_request_forces_verification(self):
        policy = OperationPolicy(mode=ExecutionMode.FAST, operation_kind="set_plugin_parameter")
        self.assertTrue(decide_verification(policy, user_requested=True))

    def test_verified_mode_requests_verification(self):
        policy = OperationPolicy(mode=ExecutionMode.VERIFIED, operation_kind="set_mixer_volume")
        self.assertTrue(decide_verification(policy))

    def test_explicit_skip_beats_verified_mode_unless_user_requests(self):
        policy = OperationPolicy(
            mode=ExecutionMode.VERIFIED,
            verification=VerificationPolicy.SKIP,
            operation_kind="set_mixer_volume",
        )
        self.assertFalse(decide_verification(policy))
        self.assertTrue(decide_verification(policy, user_requested=True))

    def test_capability_registry_can_route_by_operation(self):
        registry = CapabilityRegistry((
            Capability("piano_roll.script", "gopher_native", writable=True),
            Capability("piano_roll.notes", "community_mcp", readable=True, writable=True, verifiable=True),
        ))
        self.assertEqual(registry.backends_for("piano_roll.script", write=True), ("gopher_native",))
        self.assertIsNotNone(registry.get("community_mcp", "piano_roll.notes"))


if __name__ == "__main__":
    unittest.main()
