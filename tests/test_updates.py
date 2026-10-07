# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""更新提醒使用合成发布、Git 输出和 Controller 状态，不连接宿主。"""

import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from dawloop import updates
from dawloop.controller_runtime import RuntimeObservation


def release(tag, **changes):
    return dict(tag_name=tag, html_url=updates.REPOSITORY + "/releases/tag/" + tag,
                draft=False, prerelease="-" in tag, **changes)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = Path(self.directory.name) / "cache.json"
        environment = patch.dict("os.environ", {"DAWLOOP_NO_UPDATE_CHECK": "0"})
        environment.start()
        self.addCleanup(environment.stop)

    def check(self, fetch, **options):
        return updates.check_updates("1.0.0a1", cache_path=self.cache, fetch=fetch, now=100000, **options)

    def test_semantic_order_and_equivalent_formats(self):
        tags = ["0.2.9", "0.2.10", "1.0.0-alpha.1", "1.0.0-alpha.2", "1.0.0-beta.1", "1.0.0-rc.1", "1.0.0"]
        self.assertEqual(tags, sorted(tags, key=updates.version_key))
        self.assertEqual(updates.version_key("1.0.0a1"), updates.version_key("v1.0.0-alpha.1"))
        self.assertIsNone(updates.version_key("arbitrary-main-commit"))

    def test_prerelease_channel(self):
        result = self.check(lambda: [release("0.2.0"), release("v1.0.0-alpha.2")])
        self.assertTrue(result["update_available"])
        self.assertEqual(result["release"]["tag"], "v1.0.0-alpha.2")

    def test_release_state_machine(self):
        for tag, expected in (("1.0.0-alpha.1", "UP_TO_DATE"), ("1.0.0-alpha.2", "UPDATE_AVAILABLE"),
                              ("0.2.0-alpha.1", "AHEAD_OF_RELEASE")):
            with self.subTest(tag=tag):
                result = self.check(lambda: [release(tag)], refresh=True)
                self.assertEqual(result["release_status"], expected)
        self.assertEqual(self.check(Mock(), disabled=True)["release_status"], "CHECK_DISABLED")
        self.assertEqual(self.check(Mock(side_effect=TimeoutError), refresh=True)["release_status"], "CHECK_UNAVAILABLE")

    def test_prerelease_channel_accepts_final_release(self):
        result = self.check(lambda: [release("1.0.0-alpha.3"), release("1.0.0")])
        self.assertEqual(result["release_status"], "UPDATE_AVAILABLE")
        self.assertEqual(result["release"]["tag"], "1.0.0")

    def test_development_version_ordering(self):
        tags = ["1.0.0.dev1", "1.0.0a1.dev1", "1.0.0a1", "1.0.0a3", "1.0.0a4.dev2", "1.0.0a4", "1.0.0"]
        self.assertEqual(tags, sorted(tags, key=updates.version_key))
        result = updates.check_updates("1.0.0a4.dev2", cache_path=self.cache, now=100000, fetch=lambda: [release("1.0.0-alpha.3")])
        self.assertEqual(result["release_status"], "AHEAD_OF_RELEASE")
        self.assertFalse(result["update_available"])

    def test_ahead_display_has_no_update_instructions(self):
        with patch.object(updates, "fetch_releases", return_value=[release("0.2.0")]), \
             patch.object(updates, "update_instructions") as instructions, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            updates.print_update_status("1.0.0a1", Path(self.directory.name), cache_path=self.cache)
        instructions.assert_not_called()
        self.assertIn("AHEAD_OF_RELEASE", output.getvalue())
        self.assertIn("No update action recommended", output.getvalue())

    def test_invalid_json_and_rate_limit_stay_unavailable(self):
        from urllib.error import HTTPError
        for error in (ValueError("invalid JSON"), HTTPError(updates.RELEASES_API, 429, "rate limit", {}, None)):
            with self.subTest(error=type(error).__name__):
                result = self.check(Mock(side_effect=error), refresh=True)
                self.assertEqual(result["release_status"], "CHECK_UNAVAILABLE")
                self.assertIsNone(result["update_available"])

    def test_stable_excludes_prereleases(self):
        result = self.check(lambda: [release("0.2.0"), release("1.0.0-alpha.2")], channel="stable")
        self.assertFalse(result["update_available"])
        self.assertEqual(result["release"]["tag"], "0.2.0")

    def test_draft_is_not_published(self):
        draft = release("2.0.0")
        draft["draft"] = True
        self.assertEqual(self.check(lambda: [draft])["status"], "NO_RELEASE")

    def test_missing_or_unrecognized_releases_are_unknown(self):
        result = self.check(lambda: [release("unknown-version")])
        self.assertIsNone(result["update_available"])
        self.assertEqual(result["status"], "NO_RELEASE")

    def test_malicious_url_is_not_displayed_or_cached(self):
        data = release("2.0.0")
        data["html_url"] = "https://evil.invalid/login?secret=token"
        self.assertIsNone(self.check(lambda: [data])["release"])
        self.assertNotIn("token", self.cache.read_text(encoding="utf-8"))

    def test_cache_prevents_repeated_fetch(self):
        fetch = Mock(return_value=[release("2.0.0")])
        self.check(fetch)
        result = self.check(fetch)
        self.assertTrue(result["from_cache"])
        self.assertEqual(fetch.call_count, 1)

    def test_stable_cache_cannot_supply_prerelease(self):
        self.cache.write_text(json.dumps(dict(schema=1, channel="stable", checked_at=100000,
            status="AVAILABLE", release={"tag":"1.0.0-alpha.2", "url":updates.REPOSITORY + "/releases/tag/1.0.0-alpha.2"})), encoding="utf-8")
        fetch = Mock(return_value=[release("1.0.0")])
        result = self.check(fetch, channel="stable")
        fetch.assert_called_once()
        self.assertEqual(result["release"]["tag"], "1.0.0")

    def test_failure_is_cached_without_credentials(self):
        fetch = Mock(side_effect=TimeoutError("proxy password secret"))
        self.assertEqual(self.check(fetch)["status"], "UNAVAILABLE")
        self.assertIsNone(self.check(fetch)["update_available"])
        self.assertEqual(fetch.call_count, 1)
        self.assertNotIn("secret", self.cache.read_text(encoding="utf-8"))

    def test_refresh_bypasses_cache(self):
        fetch = Mock(return_value=[])
        self.check(fetch)
        self.check(fetch, refresh=True)
        self.assertEqual(fetch.call_count, 2)

    def test_expiry_fetches_again(self):
        fetch = Mock(return_value=[])
        self.check(fetch)
        result = updates.check_updates("1.0.0a1", cache_path=self.cache, now=200000, fetch=fetch)
        self.assertFalse(result["from_cache"])
        self.assertEqual(fetch.call_count, 2)

    def test_disable_does_not_read_write_or_fetch(self):
        fetch = Mock()
        with patch.object(updates, "_read_cache") as read:
            self.assertEqual(self.check(fetch, disabled=True)["status"], "DISABLED")
        fetch.assert_not_called()
        read.assert_not_called()
        self.assertFalse(self.cache.exists())

    def test_environment_can_disable(self):
        with patch.dict("os.environ", {"DAWLOOP_NO_UPDATE_CHECK": "1"}):
            self.assertEqual(self.check(Mock())["status"], "DISABLED")

    def test_corrupt_or_future_cache_does_not_claim_success(self):
        for text in ("[]", "{", json.dumps(dict(schema=1, channel="prerelease", checked_at=300000, status="AVAILABLE", release=None))):
            with self.subTest(text=text):
                self.cache.write_text(text, encoding="utf-8")
                self.assertEqual(self.check(lambda: [])["status"], "NO_RELEASE")

    def test_cache_write_failure_does_not_hide_release(self):
        with patch.object(updates, "_write_cache", return_value=False):
            result = self.check(lambda: [release("2.0.0")])
        self.assertTrue(result["update_available"])
        self.assertFalse(result["cache_written"])

    def test_timeout_and_response_limit(self):
        response = Mock()
        response.read.return_value = b" " * (updates.MAX_RESPONSE_BYTES + 1)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(updates, "urlopen", return_value=response) as open_url:
            with self.assertRaises(ValueError):
                updates.fetch_releases()
        self.assertEqual(open_url.call_args.kwargs["timeout"], 3)

    def test_git_checkout_safe_pull_only_clean_main_without_ahead(self):
        for dirty, branch, counts, safe in (("", "main", "0 1", True), (" M README", "main", "0 1", False),
                                            ("", "main", "1 0", False), ("", "main", "1 2", False),
                                            ("", "feature", "0 1", False)):
            with self.subTest(dirty=dirty, branch=branch, counts=counts):
                outputs = [dirty, branch, updates.REPOSITORY + ".git", counts]
                with patch.object(updates.subprocess, "run", side_effect=[Mock(stdout=x) for x in outputs]):
                    source = updates.installation_source()
                self.assertEqual(source["safe_pull"], safe)

    def test_git_failure_is_not_safe_pull(self):
        with patch.object(updates.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 3)):
            self.assertFalse(updates.installation_source()["safe_pull"])

    def test_unknown_source_never_recommends_pypi_or_pull(self):
        instructions = updates.update_instructions(dict(kind="INDEX_OR_UNKNOWN", safe_pull=False))
        self.assertNotIn("pip install -U", "\n".join(instructions))
        self.assertNotIn("git pull --ff-only", instructions)

    def test_index_metadata_is_not_proof_of_pypi(self):
        with patch.object(Path, "exists", return_value=False), patch.object(updates.importlib.metadata, "distribution") as dist:
            dist.return_value.read_text.return_value = None
            self.assertEqual(updates.installation_source()["kind"], "INDEX_OR_UNKNOWN")
            dist.return_value.read_text.return_value = '{"url":"file:///synthetic.whl"}'
            self.assertEqual(updates.installation_source()["kind"], "DIRECT_PACKAGE")

    def test_missing_runtime_is_not_protocol_match(self):
        result = updates.controller_versions(Path(self.directory.name))
        self.assertIsNone(result["protocol_match"])
        self.assertIsNone(result["installed_matches_package"])

    def test_stale_runtime_is_not_protocol_match(self):
        observation = RuntimeObservation("CONTROLLER_RUNTIME_STALE", "STOP", {"protocol_version":"dawloop-midi-json-v1"}, 100)
        with patch("dawloop.controller_runtime.inspect_controller_lifecycle", return_value={"runtime": observation, "verification":"RELOAD_REQUIRED"}):
            self.assertIsNone(updates.controller_versions(Path(self.directory.name))["protocol_match"])

    def test_fresh_protocol_mismatch_is_visible(self):
        observation = RuntimeObservation("CONTROLLER_RUNTIME_READY", "PASS", {"protocol_version":"different"}, 1)
        with patch("dawloop.controller_runtime.inspect_controller_lifecycle", return_value={"runtime": observation, "verification":"PASS"}), \
             patch("dawloop.controller_runtime.installed_controller_identity", return_value=("installed-build", "synthetic-sha")):
            self.assertFalse(updates.controller_versions(Path(self.directory.name))["protocol_match"])

    def test_ready_payload_without_valid_lifecycle_is_unknown(self):
        observation = RuntimeObservation("CONTROLLER_RUNTIME_READY", "PASS", {"protocol_version":"dawloop-midi-json-v1"}, 1)
        with patch("dawloop.controller_runtime.inspect_controller_lifecycle", return_value={"runtime": observation, "verification":"STOP"}):
            self.assertIsNone(updates.controller_versions(Path(self.directory.name))["protocol_match"])

    def test_unavailable_display_does_not_claim_up_to_date(self):
        with patch.object(updates, "fetch_releases", side_effect=TimeoutError), patch("sys.stdout", new_callable=io.StringIO) as output:
            updates.print_update_status("1.0.0a1", Path(self.directory.name), cache_path=self.cache)
        self.assertIn("CHECK_UNAVAILABLE", output.getvalue())
        self.assertIn("UNKNOWN", output.getvalue())
        self.assertNotIn("up to date", output.getvalue())

    def test_doctor_update_failure_preserves_exit_code(self):
        from dawloop import cli
        import importlib.util
        with patch.dict("os.environ", {"DAWLOOP_NO_UPDATE_CHECK":"1"}), \
             patch.object(cli, "_print_integration_doctor", return_value=(True, True)), \
             patch("dawloop.setup.user_script_status", return_value={"controller":True,"backend":True,"license":True}), \
             patch.object(importlib.util, "find_spec", return_value=None), \
             patch("sys.stdout", new_callable=io.StringIO), \
             patch.object(updates, "print_update_status") as printer:
            baseline = cli._doctor(False, Path(self.directory.name))
            printer.side_effect = RuntimeError("synthetic")
            self.assertEqual(cli._doctor(False, Path(self.directory.name)), baseline)

    def test_doctor_pass_stays_pass_when_update_check_fails(self):
        from dawloop import cli
        import importlib.util
        with patch.object(cli, "_print_integration_doctor", return_value=(True, True)), \
             patch("dawloop.setup.user_script_status", return_value={"controller":True,"backend":True,"license":True}), \
             patch.object(importlib.util, "find_spec", return_value=Mock()), \
             patch.dict("sys.modules", {"mido":Mock(get_output_names=Mock(return_value=["synthetic"]))}), \
             patch("sys.stdout", new_callable=io.StringIO), \
             patch.object(updates, "print_update_status", side_effect=RuntimeError("synthetic")):
            self.assertEqual(cli._doctor(False, Path(self.directory.name)), 0)


if __name__ == "__main__":
    unittest.main()
