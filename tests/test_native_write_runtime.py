import asyncio
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from dawloop.runtime import (BackendError, BackendRouter, ExecutionMode, ExecutionStatus,
    BackendExecution)
from dawloop.runtime.native_write import (AcceptPolicy, NATIVE_BATCH_ADD, NativeWriteJournal,
    PianoRollBatchAddPlan, PianoRollScriptRenderer)
from dawloop.adapters.gopher_native.catalog import known_catalog
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend, CERTIFIED_VERSION


def plan(count=4):
    return PianoRollBatchAddPlan(dict(expected_pattern_index=1, expected_pattern_name='甲',
        expected_channel_index=0, expected_channel_name='808 Kick'),
        tuple(dict(number=84+i, time=3072+i*48, length=24, velocity=0.5) for i in range(count)),
        'smoke-1').operation_plan()


class Transport:
    poisoned_epoch = None
    epoch = 'epoch'
    callbacks_restored = True

    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def connect(self):
        return dict(session='epoch', bridge_epoch='epoch', host_generation='generation', target_id='target')

    def invoke(self, kind):
        return {'payload': [dict(name=k, description=v['description'], inputSchema=v['input_schema'])
            for k, v in known_catalog()['tools'].items()]}

    def invoke_batch(self, *args):
        self.calls += 1
        if self.error:
            self.poisoned_epoch = self.epoch
            raise BackendError(self.error, dispatched=True)
        return dict(ok=True, payload={'result': {'isError': False, 'content': []}})

    def close(self):
        pass


class Target:
    changed = False

    async def prepare(self, target, session):
        return await self.confirm(target, session)

    async def confirm(self, target, session):
        return dict(session=session, identity=dict(pattern_number=1, pattern_name='甲', channel_index=0,
            channel_name='808 Kick', selected_channels=[0], ppq=96, project_loading=False,
            fl_studio_version=CERTIFIED_VERSION), ui=dict(visible=True, confirmed=True,
            channel_name='other' if self.changed else '808 Kick', pattern_number=1,
            observed_unix=time.time(), evidence_ref='before.png'))


class Interaction:
    async def wait_preview(self, operation_id):
        await asyncio.sleep(0.01)
        return dict(operation_id=operation_id, observed=True)

    async def wait_accept(self, operation_id):
        return dict(operation_id=operation_id, accepted=True)

    async def wait_application(self, operation_id):
        return dict(operation_id=operation_id, observed=True)

    async def guarded_auto_accept(self, *args):
        raise AssertionError('默认禁止自动接受')


class RuntimeWriteTests(unittest.IsolatedAsyncioTestCase):
    async def run_backend(self, directory, operation=None, error=None, target=None, **kwargs):
        transport = Transport(error)
        backend = GopherNativeWriteBackend(enabled=True, transport=transport, target_preparer=target or Target(),
            interaction=Interaction(), journal=NativeWriteJournal(directory), disposable_guard=lambda: True, **kwargs)
        router = BackendRouter([backend])
        await router.discover()
        result = await router.execute(operation or plan())
        return result, backend, transport

    async def test_default_off_does_not_connect(self):
        backend = GopherNativeWriteBackend()
        self.assertEqual(await backend.discover(), [])

    async def test_runtime_success_and_preview_states(self):
        with tempfile.TemporaryDirectory() as temp:
            result, _, transport = await self.run_backend(temp)
            self.assertEqual(result.execution_status, ExecutionStatus.SUCCESS)
            self.assertEqual(transport.calls, 1)
            value = result.value
            self.assertEqual(value['preview_status'], 'PREVIEW_EFFECT_OBSERVED')
            self.assertEqual(value['application_status'], 'APPLICATION_OBSERVED')
            self.assertIsNone(value['timings']['actual_apply_latency'])
            self.assertEqual(value['user_message'], '已执行')

    async def test_rejected_modes_and_missing_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            for mode in (ExecutionMode.AUTO, ExecutionMode.VERIFIED):
                result, _, transport = await self.run_backend(temp, replace(plan(), mode=mode))
                self.assertEqual(result.execution_status, ExecutionStatus.NOT_DISPATCHED)
                self.assertEqual(transport.calls, 0)
            result, _, transport = await self.run_backend(temp, replace(plan(), metadata={'operation_id': 'smoke-1'}))
            self.assertEqual(result.error_code, 'EXPERIMENTAL_AUTHORIZATION_REQUIRED')
            self.assertEqual(transport.calls, 0)

    async def test_oversize_rejected_and_not_split(self):
        with tempfile.TemporaryDirectory() as temp:
            oversized = replace(plan(), parameters={'notes': [plan().parameters['notes'][0]]*129})
            result, _, transport = await self.run_backend(temp, oversized)
            self.assertEqual(result.execution_status, ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(result.error_code, 'CAPABILITY_LIMIT_EXCEEDED')
            self.assertEqual(transport.calls, 0)

    async def test_target_ui_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Target(); target.changed = True
            result, _, transport = await self.run_backend(temp, target=target)
            self.assertEqual(result.execution_status, ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(transport.calls, 0)

    async def test_timeout_result_no_retry_or_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            transport = Transport('EXECUTION_TIMEOUT')
            class DelayedPreview(Interaction):
                async def wait_preview(self, operation_id):
                    while not transport.poisoned_epoch:
                        await asyncio.sleep(0.01)
                    await asyncio.sleep(0.01)
                    return dict(operation_id=operation_id, observed=True)
            backend = GopherNativeWriteBackend(enabled=True, transport=transport, target_preparer=Target(),
                interaction=DelayedPreview(), journal=NativeWriteJournal(temp), disposable_guard=lambda: True)
            class Fallback:
                name = 'fallback'
                calls = 0
                preparations = 0
                async def discover(self):
                    return [replace(backend.capabilities[0], backend=self.name)]
                async def validate(self, *args):
                    self.preparations += 1
                async def resolve_target(self, operation):
                    return dict(operation.target)
                async def execute(self, *args):
                    self.calls += 1
                    return BackendExecution(ExecutionStatus.SUCCESS)
            fallback = Fallback()
            router = BackendRouter([backend, fallback]); await router.discover()
            result = await router.execute(plan())
            self.assertEqual(result.execution_status, ExecutionStatus.UNKNOWN)
            self.assertEqual(result.value['timeout_status'], 'TIMEOUT_BEFORE_ACCEPT', result.value['timings'])
            self.assertEqual(result.value['application_status'], 'APPLICATION_OBSERVED')
            self.assertEqual(transport.calls, 1)
            self.assertEqual(fallback.calls, 0)
            self.assertEqual(fallback.preparations, 0)
            router = BackendRouter([backend]); await router.discover()
            again = await router.execute(plan())
            self.assertEqual(again.execution_status, ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(transport.calls, 1)

    async def test_auto_accept_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            result, _, transport = await self.run_backend(temp, accept_policy=AcceptPolicy.GUARDED_AUTO_ACCEPT)
            self.assertEqual(result.execution_status, ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(transport.calls, 0)

    def test_renderer_mutations_ranges_and_precision(self):
        renderer = PianoRollScriptRenderer(); notes = plan().parameters['notes']
        rendered = renderer.render(notes)
        self.assertEqual(rendered, renderer.render(notes))
        with self.assertRaises(ValueError):
            renderer.validate(notes, replace(rendered, source=rendered.source+b'flp.score.clear()\n'))
        for field, value in [('number', True), ('number', 128), ('time', -1), ('length', 0),
                             ('velocity', float('nan')), ('velocity', float('inf')), ('velocity', 0.1234567)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                renderer.render([dict(notes[0], **{field: value})])

    def test_persistent_operation_and_host_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = NativeWriteJournal(temp); session = Transport().connect()
            journal.reserve('op-1', session, 'hash')
            for operation in ('op-1', 'op-2'):
                with self.assertRaises(ValueError):
                    NativeWriteJournal(temp).reserve(operation, session, 'hash')

    def test_real_bridge_constrained_renderer_and_timeout(self):
        root = Path(__file__).resolve().parents[1]
        notes = plan().parameters['notes']; rendered = PianoRollScriptRenderer().render(notes)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'fixture.json'
            from dawloop.runtime.native_write import normalized_notes
            path.write_text(json.dumps(dict(rows=normalized_notes(notes), hash=rendered.sha256,
                source=rendered.source.decode('utf-8'))), encoding='utf-8')
            subprocess.run([shutil.which('node'), str(root/'tests/runtime_write_bridge_harness.cjs'),
                str(root/'src/dawloop/adapters/gopher_native/bridge.js'), str(path)],
                check=True, capture_output=True, timeout=10)
