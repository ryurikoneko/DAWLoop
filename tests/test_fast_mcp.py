import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
import sys

from dawloop.adapters.gopher_native.write_backend import (
    CERTIFIED_CATALOG, CERTIFIED_VERSION, GopherNativeWriteBackend)
from dawloop.fast_mcp_server import create_server
from dawloop.runtime.fast_music import FastMusicRuntime
from dawloop.runtime.human_reports import acceptance_receipt
from dawloop.runtime.native_write import NativeWriteJournal
from dawloop.runtime.run_manager import RunManager
from test_fast_music import Host, inputs
from test_native_write_runtime import Target


class ReportInteraction:
    def __init__(self, store):
        self.report_store = store

    async def wait_preview(self, operation_id):
        await asyncio.sleep(0)
        self.report_store.bind_preview({'hwnd': 20})
        return dict(operation_id=operation_id, observed=True, host_preview_present=True,
                    evidence_ref='offline-preview', window={'hwnd': 20})

    async def wait_accept(self, operation_id):
        deadline = time.monotonic() + 2
        self.report_store.begin_accept()
        try:
            while time.monotonic() < deadline:
                receipt = self.report_store.claim_accept(deadline=deadline)
                if receipt is not None:
                    return acceptance_receipt(receipt, operation_id)
                await asyncio.sleep(0.005)
            raise ValueError('HUMAN_EVENT_TIMEOUT')
        finally:
            self.report_store.end_accept()

    async def wait_application(self, operation_id):
        return dict(operation_id=operation_id, observed=True, evidence_ref='offline-application')


class RunManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = self.root / 'settings'
        self.settings.mkdir()
        self.host = Host()
        self.factory_calls = 0
        self.snapshot = dict(observed_at=time.time(), disposable_session=True,
            controller=dict(connected=True, build_id='offline-build',
                session_generation='controller-session', project_generation='project-generation'),
            gopher=dict(discovered=True, bridge_connected=True, host_generation='generation',
                bridge_epoch='epoch', target_id='target', catalog_hash=CERTIFIED_CATALOG,
                fl_version=CERTIFIED_VERSION, bootstrap_required=False, poisoned=False),
            observation=dict(ready=True, request_generation='observer-generation'))
        self.manager = self.new_manager()

    async def asyncTearDown(self):
        await self.manager.close()
        self.temp.cleanup()

    async def readiness(self):
        return copy.deepcopy(self.snapshot)

    def factory(self, context, store):
        self.factory_calls += 1
        self.assertEqual(context.settings_dir, self.settings)
        self.assertEqual(context.expected_build, 'offline-build')
        return FastMusicRuntime(GopherNativeWriteBackend(enabled=True, transport=self.host,
            target_preparer=Target(), interaction=ReportInteraction(store),
            journal=NativeWriteJournal(context.ledger_directory), disposable_guard=lambda: True))

    def new_manager(self, **kwargs):
        config = dict(settings_dir=self.settings, expected_build='offline-build',
            runtime_factory=self.factory, readiness=self.readiness,
            experimental_authorized=True, allowed_target=inputs()[0])
        config.update(kwargs)
        return RunManager(self.root / 'runs', **config)

    async def start(self, operation='mcp-music-1'):
        return await self.manager.create(operation, *inputs())

    async def wait_state(self, run_id, expected):
        async with asyncio.timeout(3):
            while True:
                state = await self.manager.status(run_id)
                if state['state'] == expected:
                    return state
                await asyncio.sleep(0.005)

    def report(self, handle, **changes):
        value = dict(run_id=handle['run_id'], session_id=handle['session_id'],
            report_id='human-accept-1', reported_at='2026-10-06T12:00:00+08:00',
            event_type='ACCEPTED', source='HUMAN', evidence_ref='offline-direct-user-reply',
            preview_window={'hwnd': 20}, preview_review_confirmed=True)
        value.update(changes)
        return value

    async def complete(self, handle):
        await self.wait_state(handle['run_id'], 'WAITING_FOR_HUMAN_ACCEPT')
        receipt = self.manager.submit_human_report(self.report(handle))
        self.assertEqual(receipt['delivery'], 'PENDING')
        return await self.wait_state(handle['run_id'], 'COMPLETED_UNVERIFIED')

    async def test_actual_fast_runs_in_background_report_claims_and_original_result_seals(self):
        handle = await asyncio.wait_for(self.start(), 1)
        self.assertEqual(handle['initial_state'], 'CREATED')
        self.assertFalse(self.manager.tasks[handle['run_id']].done())
        state = await self.complete(handle)
        self.assertEqual(self.host.calls, 1)
        self.assertEqual(state['human_reports'][0]['delivery'], 'REALTIME')
        result = state['run_result']
        self.assertEqual((result['human_accept'], result['application'], result['completion']),
                         ('REPORTED', 'OBSERVED', 'CONFIRMED'))
        self.assertEqual(result['producer_target_binding'], 'NOT_VERIFIED')
        self.assertEqual(result['exact_set'], 'NOT_VERIFIED')
        self.assertIsNone(self.manager.runtimes[handle['run_id']].backend.session)
        self.assertEqual(state['readiness']['dispatch']['budget_consumed'], 1)

    async def test_duplicate_operation_and_conflicting_content(self):
        first, duplicate = await asyncio.gather(self.start(), self.start())
        self.assertEqual(first['run_id'], duplicate['run_id'])
        self.assertEqual(first['session_id'], duplicate['session_id'])
        self.assertTrue(duplicate['reused'])
        target, plan = inputs()
        plan['notes'][0]['velocity'] = 0.2
        with self.assertRaisesRegex(ValueError, 'OPERATION_ID_CONFLICT'):
            await self.manager.create('mcp-music-1', target, plan)
        await self.complete(first)
        self.assertEqual(self.factory_calls, 1)
        self.assertEqual(self.host.calls, 1)

    async def test_plan_rejected_before_run_navigation_or_discovery(self):
        target, plan = inputs()
        for invalid in (dict(plan, source='arbitrary'), dict(plan, notes=plan['notes'][:15])):
            with self.assertRaises(ValueError):
                await self.manager.create('invalid', target, invalid)
        plan['notes'][0]['velocity'] = 0.2
        with self.assertRaisesRegex(ValueError, 'CERTIFIED_MUSIC_SLICE_REQUIRED'):
            await self.manager.create('outside-fixture', target, plan)
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(self.host.connects, 0)

    async def test_readiness_stale_missing_build_bootstrap_and_budget_are_independent(self):
        baseline = copy.deepcopy(self.snapshot)
        cases = [('observed_at', None, time.time() - 61, 'READINESS_STALE_OR_UNKNOWN'),
            ('controller', 'build_id', 'other-build', 'CONTROLLER_NOT_READY'),
            ('gopher', 'bootstrap_required', True, 'GOPHER_BOOTSTRAP_REQUIRED'),
            ('gopher', 'poisoned', True, 'GOPHER_NOT_READY'),
            ('observation', 'ready', False, 'OBSERVATION_NOT_READY')]
        for group, key, value, reason in cases:
            self.snapshot = copy.deepcopy(baseline)
            if key is None:
                self.snapshot[group] = value
            else:
                self.snapshot[group][key] = value
            state = await self.manager.status()
            self.assertNotEqual(state['runtime'], 'FAST_READY')
            self.assertIn(reason, state['blockers'])
        self.snapshot = baseline
        self.assertEqual((await self.manager.status())['runtime'], 'FAST_READY')
        self.assertEqual(self.host.connects, 0)

    async def test_context_changes_after_job_creation_stop_before_host_action(self):
        handle = await self.start()
        self.snapshot['controller']['project_generation'] = 'changed'
        result = await self.wait_state(handle['run_id'], 'STOPPED_BEFORE_DISPATCH')
        self.assertEqual(result['run_result']['error_code'], 'RUN_CONTEXT_CHANGED')
        self.assertEqual(self.host.calls, 0)
        self.assertEqual(self.factory_calls, 0)

    async def test_single_active_run_and_shared_host_budget_remain_enforced(self):
        handle = await self.start()
        with self.assertRaisesRegex(ValueError, 'RUN_ACTIVE'):
            await self.start('second')
        await self.complete(handle)
        with self.assertRaisesRegex(ValueError, 'HOST_DISPATCH_BUDGET_UNAVAILABLE'):
            await self.start('second')
        self.assertEqual(self.host.calls, 1)

    async def test_restart_preserves_idempotency_terminal_and_late_reports(self):
        handle = await self.start()
        await self.complete(handle)
        original = self.root / 'runs' / handle['run_id'] / 'fast_music_result.json'
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        await self.manager.close()
        self.manager = self.new_manager()
        reused = await self.start()
        self.assertEqual(reused['run_id'], handle['run_id'])
        late = self.report(handle, report_id='listened', event_type='LISTENED_OK',
                           preview_window=None, preview_review_confirmed=False)
        self.assertEqual(self.manager.submit_human_report(late)['delivery'], 'LATE')
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), digest)
        self.assertEqual(self.host.calls, 1)

    async def test_unstarted_job_shutdown_and_restart_quarantine_without_replay(self):
        handle = await self.start()
        await self.manager.close()
        self.manager = self.new_manager()
        state = await self.manager.status(handle['run_id'])
        self.assertEqual(state['state'], 'STOPPED_ORPHANED_UNKNOWN')
        self.assertTrue(state['terminal'])
        self.assertIsNone(state['run_result'])
        self.assertEqual((await self.start())['run_id'], handle['run_id'])
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(self.host.calls, 0)

    async def test_timeout_does_not_retry_release_budget_or_rewrite_result(self):
        self.host.error = 'EXECUTION_TIMEOUT'
        handle = await self.start()
        await self.wait_state(handle['run_id'], 'WAITING_FOR_HUMAN_ACCEPT')
        self.manager.submit_human_report(self.report(handle))
        state = await self.wait_state(handle['run_id'], 'STOPPED_AFTER_DISPATCH_UNKNOWN')
        self.assertEqual(state['run_result']['completion'], 'UNKNOWN')
        reused = await self.start()
        self.assertEqual(reused['run_id'], handle['run_id'])
        self.assertEqual(self.host.calls, 1)
        self.assertEqual(state['readiness']['dispatch']['budget_consumed'], 1)

    async def test_wrong_session_duplicate_conflict_and_nonhuman_are_not_acceptance(self):
        handle = await self.start()
        await self.wait_state(handle['run_id'], 'WAITING_FOR_HUMAN_ACCEPT')
        wrong = self.report(handle, session_id='other-session', report_id='wrong')
        self.assertEqual(self.manager.submit_human_report(wrong)['delivery'], 'UNLINKED')
        with self.assertRaisesRegex(ValueError, 'HUMAN_REPORT_SOURCE_OR_EVENT_INVALID'):
            self.manager.submit_human_report(self.report(handle, source='AGENT'))
        valid = self.report(handle)
        first = self.manager.submit_human_report(valid)
        self.assertEqual(self.manager.submit_human_report(valid), first)
        with self.assertRaisesRegex(ValueError, 'HUMAN_REPORT_ID_CONFLICT'):
            self.manager.submit_human_report(dict(valid, evidence_ref='different-content'))
        await self.wait_state(handle['run_id'], 'COMPLETED_UNVERIFIED')
        self.assertEqual(self.host.calls, 1)

    async def test_second_manager_cannot_recover_or_replay_live_manager_runs(self):
        with self.assertRaisesRegex(ValueError, 'RUN_MANAGER_ALREADY_RUNNING'):
            self.new_manager()
        self.assertEqual((await self.manager.status())['runtime'], 'FAST_READY')

    async def test_wrong_ledger_refused_before_native_call(self):
        original = self.factory

        def bad(context, store):
            runtime = original(context, store)
            runtime.backend.journal = NativeWriteJournal(context.directory / 'private-ledger')
            return runtime
        self.manager.factory = bad
        handle = await self.start()
        state = await self.wait_state(handle['run_id'], 'STOPPED_BEFORE_DISPATCH')
        self.assertEqual(state['run_result']['error_code'], 'SHARED_DISPATCH_LEDGER_REQUIRED')
        self.assertEqual(self.host.connects, 0)

    async def test_terminal_file_tampering_is_detected(self):
        handle = await self.start()
        await self.complete(handle)
        original = self.root / 'runs' / handle['run_id'] / 'fast_music_result.json'
        original.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_RUN_RESULT_CHANGED'):
            await self.manager.status(handle['run_id'])

    async def test_unconfigured_entrypoint_is_not_ready(self):
        await self.manager.close()
        self.manager = self.new_manager(runtime_factory=None, readiness=None,
                                        experimental_authorized=False, allowed_target=None)
        state = await self.manager.status()
        self.assertEqual(state['runtime'], 'NOT_READY')
        self.assertIsNone(state['dispatch']['budget_consumed'])
        self.assertIn('LIVE_RUNTIME_NOT_CONFIGURED', state['blockers'])
        self.assertEqual(self.host.calls, 0)


    @unittest.skipUnless(importlib.util.find_spec('fastmcp'), '需要mcp extra')
    async def test_three_tools_real_mcp_background_execution_and_human_report_delivery(self):
        from fastmcp import Client
        async with Client(create_server(self.manager)) as client:
            self.assertEqual({t.name for t in await client.list_tools()},
                             {'fast_write_music', 'status', 'submit_human_report'})
            status = (await client.call_tool('status', {})).data
            self.assertEqual(status['runtime'], 'FAST_READY')
            target, plan = inputs()
            handle = (await client.call_tool('fast_write_music', dict(
                operation_id='mcp-music-1', target=target, musical_plan=plan), timeout=1)).data
            await self.wait_state(handle['run_id'], 'WAITING_FOR_HUMAN_ACCEPT')
            receipt = (await client.call_tool('submit_human_report',
                                              {'report': self.report(handle)})).data
            self.assertEqual(receipt['delivery'], 'PENDING')
            await self.wait_state(handle['run_id'], 'COMPLETED_UNVERIFIED')
            result = (await client.call_tool('status', {'run_id': handle['run_id']})).data
            self.assertEqual(result['run_result']['state'], 'COMPLETED_UNVERIFIED')
            self.assertEqual(result['human_reports'][0]['delivery'], 'REALTIME')
            self.assertEqual(self.host.calls, 1)

    @unittest.skipUnless(importlib.util.find_spec('fastmcp'), '需要mcp extra')
    async def test_actual_stdio_process_exposes_only_three_tools_and_refuses_unconfigured_write(self):
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport
        source = Path(__file__).resolve().parents[1] / 'src'
        transport = StdioTransport(command=sys.executable, args=[
            '-m', 'dawloop.fast_mcp_server', '--settings-dir', str(self.settings),
            '--expected-build', 'offline-build', '--data-dir', str(self.root / 'stdio-service')],
            env={'PYTHONPATH': str(source), 'PYTHONUTF8': '1'}, cwd=str(self.root), keep_alive=False,
            log_file=self.root / 'stdio.log')
        async with Client(transport, timeout=10) as client:
            self.assertEqual({t.name for t in await client.list_tools()},
                             {'fast_write_music', 'status', 'submit_human_report'})
            state = (await client.call_tool('status', {})).data
            self.assertEqual(state['runtime'], 'NOT_READY')
            self.assertIn('LIVE_RUNTIME_NOT_CONFIGURED', state['blockers'])
            target, plan = inputs()
            failure = await client.call_tool('fast_write_music', dict(
                operation_id='stdio-refusal', target=target, musical_plan=plan), raise_on_error=False)
            self.assertTrue(failure.is_error)
        unlocked = RunManager(self.root / 'stdio-service', settings_dir=self.settings,
                             expected_build='offline-build')
        await unlocked.close()
        self.assertEqual(self.host.calls, 0)

    @unittest.skipUnless(importlib.util.find_spec('fastmcp'), '需要mcp extra')
    async def test_stdio_background_run_report_claim_and_sealed_actual_fast_result(self):
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport
        tests = Path(__file__).resolve().parent
        data = self.root / 'stdio-configured'
        transport = StdioTransport(command=sys.executable, args=[
            str(tests / 'native_fixtures' / 'fast_mcp_worker.py'),
            '--settings-dir', str(self.settings), '--data-dir', str(data)],
            env={'PYTHONPATH': str(tests.parent / 'src'), 'PYTHONUTF8': '1'},
            cwd=str(self.root), keep_alive=False, log_file=self.root / 'configured-stdio.log')
        async with Client(transport, timeout=10) as client:
            target, plan = inputs()
            handle = (await client.call_tool('fast_write_music', dict(
                operation_id='stdio-music-1', target=target, musical_plan=plan), timeout=1)).data
            async def wait(expected):
                async with asyncio.timeout(3):
                    while True:
                        state = (await client.call_tool('status', {'run_id': handle['run_id']})).data
                        if state['state'] == expected:
                            return state
                        await asyncio.sleep(0.005)
            awaiting = await wait('WAITING_FOR_HUMAN_ACCEPT')
            self.assertEqual(awaiting['preview_window'], {'hwnd': 20})
            receipt = (await client.call_tool('submit_human_report',
                {'report': self.report(handle, preview_window=awaiting['preview_window'])})).data
            self.assertEqual(receipt['delivery'], 'PENDING')
            state = await wait('COMPLETED_UNVERIFIED')
            self.assertEqual(state['human_reports'][0]['delivery'], 'REALTIME')
            self.assertNotIn('evidence', state['run_result'])
            reused = (await client.call_tool('fast_write_music', dict(
                operation_id='stdio-music-1', target=target, musical_plan=plan))).data
            self.assertEqual(reused['run_id'], handle['run_id'])
        original = (data / handle['run_id'] / 'fast_music_result.json').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), state['result_sha256'])
        result = json.loads(original)
        record = result['evidence']['backend_execution']
        self.assertEqual(sum(s['state'] == 'DISPATCHED' for s in record['states']), 1)
        self.assertEqual(result['completion'], 'CONFIRMED')
        unlocked = RunManager(data, settings_dir=self.settings, expected_build='offline-build')
        await unlocked.close()

    async def test_shutdown_after_dispatch_seals_unknown_and_late_report_cannot_resume(self):
        handle = await self.start()
        await self.wait_state(handle['run_id'], 'WAITING_FOR_HUMAN_ACCEPT')
        await self.manager.close()
        state = await self.manager.status(handle['run_id'])
        self.assertEqual(state['state'], 'STOPPED_AFTER_DISPATCH_UNKNOWN')
        self.assertEqual(state['run_result']['completion'], 'UNKNOWN')
        self.assertTrue(state['terminal'])
        self.assertEqual(self.manager.submit_human_report(self.report(handle))['delivery'], 'LATE')
        self.assertEqual((await self.manager.status(handle['run_id']))['state'], state['state'])
        self.assertEqual(self.host.calls, 1)

    async def test_bounded_shutdown_failure_retains_ownership_until_worker_exits(self):
        entered, release = asyncio.Event(), asyncio.Event()
        reads = 0

        async def slow():
            nonlocal reads
            reads += 1
            if reads == 2:
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
            return copy.deepcopy(self.snapshot)

        self.manager.readiness = slow
        await self.start()
        await asyncio.wait_for(entered.wait(), 1)
        with self.assertRaisesRegex(RuntimeError, 'RUN_TEARDOWN_FAILED'):
            await self.manager.close(timeout=0.01)
        with self.assertRaisesRegex(ValueError, 'RUN_MANAGER_ALREADY_RUNNING'):
            self.new_manager()
        release.set()
        await asyncio.wait_for(asyncio.gather(*self.manager.tasks.values()), 1)
        await self.manager.close()
        self.manager = self.new_manager()
        self.assertEqual(self.host.calls, 0)


if __name__ == '__main__':
    unittest.main()
