import asyncio
from dataclasses import replace
import unittest

from research.practical_music_slice import (OPERATION_ID, TARGET, HumanSliceInteraction,
    guard_preparation, musical_plan, operation_plan, validate_slice)


class SliceTests(unittest.TestCase):
    def test_music_bounds_and_reproducibility(self):
        plan = musical_plan()
        self.assertEqual(len(plan.events),16)
        self.assertEqual(len({e.start_tick for e in plan.events}),16)
        self.assertTrue(all(1536<=e.start_tick<e.start_tick+e.duration<=3072 for e in plan.events))
        self.assertEqual(validate_slice(operation_plan()),validate_slice(operation_plan()))
        self.assertEqual(operation_plan().parameters['notes'][0]['velocity'],0.850394)

    def test_changed_source_plan_scope_rejected(self):
        plan = operation_plan()
        for altered in (replace(plan,target=dict(plan.target,expected_channel_index=1)),
                replace(plan,parameters={'notes':plan.parameters['notes']*2}),
                replace(plan,metadata=dict(plan.metadata,operation_id='another'))):
            with self.assertRaisesRegex(ValueError,'SCOPE'):
                validate_slice(altered)

    def test_empty_region_fresh_session_required(self):
        receipt = dict(operation_id=OPERATION_ID, session={'host_generation':'a'}, target=TARGET,
            region=[1536,3072],active_region_empty=True,human_available=True,preview_absent=True,
            observer='agent_visual_review',evidence_ref='full.png',observed_unix=100)
        guard_preparation(receipt,receipt['session'],now=101)
        for mutation in ({'active_region_empty':False},{'observed_unix':0},
                         {'session':{}},{'human_available':False},{'preview_absent':False}):
            with self.assertRaises(ValueError):
                guard_preparation(dict(receipt,**mutation),receipt['session'],now=101)

    def test_second_session_keeps_source_but_rejects_old_operation(self):
        second='practical-kick-16-session-2'
        self.assertEqual(validate_slice(operation_plan(second),second),validate_slice(operation_plan()))
        with self.assertRaisesRegex(ValueError,'SCOPE'):
            validate_slice(operation_plan(),second)
        with self.assertRaisesRegex(ValueError,'NOT_APPROVED'):
            operation_plan('practical-kick-16-session-3')


class HumanTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_flow_does_not_certify_pixels_or_click_timing(self):
        base = dict(operation_id=OPERATION_ID,evidence_ref='full.png',observer='agent_visual_review')
        events = dict(preview=dict(base,observed=True,host_preview_present=True),
            accept=dict(base,observer='human',accepted=True,accepted_within_window=True),
            application=dict(base,observed=True,preview_closed=True,phrase_visible=True))
        async def check():
            return True
        task = asyncio.create_task(asyncio.sleep(10))
        interaction = HumanSliceInteraction(events.get,check)
        interaction.bind_dispatch_task(task)
        try:
            await interaction.wait_preview(OPERATION_ID)
            await interaction.wait_accept(OPERATION_ID)
            await interaction.wait_application(OPERATION_ID)
            self.assertFalse(interaction.local_preview)
            self.assertIsNone(interaction.timing()['accept_to_callback_ms'])
            with self.assertRaisesRegex(ValueError,'DEFERRED'):
                await interaction.guarded_auto_accept()
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    async def test_timeout_cannot_be_relabelled_by_late_human_accept(self):
        async def check():
            return True
        async def failed():
            return None, ValueError('timeout'),0,0
        task = asyncio.create_task(failed())
        await task
        event = dict(operation_id=OPERATION_ID,evidence_ref='human',observer='human',
            accepted=True,accepted_within_window=True)
        interaction = HumanSliceInteraction(lambda _:event,check)
        interaction.bind_dispatch_task(task)
        interaction.preview = {}
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):
            await interaction.wait_accept(OPERATION_ID)

    async def test_expired_preview_window_stops(self):
        async def check():
            return True
        task = asyncio.create_task(asyncio.sleep(10))
        interaction = HumanSliceInteraction(lambda _:None,check,clock=lambda:31)
        interaction.bind_dispatch_task(task)
        interaction.started=0
        try:
            with self.assertRaisesRegex(ValueError,'WINDOW_CLOSED'):
                await interaction.wait_preview(OPERATION_ID)
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    async def test_success_callback_allows_later_human_receipt(self):
        async def check():
            return True
        async def completed():
            return {'result':{'isError':False}},None,1,1
        task = asyncio.create_task(completed())
        await task
        receipt = dict(operation_id=OPERATION_ID,evidence_ref='human',observer='human',
            accepted=True,accepted_within_window=True)
        interaction = HumanSliceInteraction(lambda _:receipt,check,clock=lambda:31)
        interaction.bind_dispatch_task(task)
        interaction.started = 0
        interaction.preview = {}
        await interaction.wait_accept(OPERATION_ID)
        self.assertTrue(interaction.timing()['human_accept_reported'])
        self.assertEqual(interaction.timing()['human_content_review'],'NOT_CERTIFIED')
        self.assertIsNone(interaction.timing()['human_accept_timestamp'])

    async def test_failed_callback_stops_without_waiting_for_receipt(self):
        async def check():
            return True
        async def failed():
            return None,ValueError('timeout'),0,0
        async def no_wait(_):
            self.fail('失败回调后不应继续等待人工消息')
        task = asyncio.create_task(failed())
        await task
        interaction = HumanSliceInteraction(lambda _:None,check,sleep=no_wait)
        interaction.bind_dispatch_task(task)
        interaction.preview = {}
        with self.assertRaisesRegex(ValueError,'CALL_COMPLETION_UNKNOWN'):
            await interaction.wait_accept(OPERATION_ID)

    async def test_cancelled_dispatch_does_not_prove_host_cancelled(self):
        async def check():
            return True
        task = asyncio.create_task(asyncio.sleep(10))
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        interaction = HumanSliceInteraction(lambda _:None,check)
        interaction.bind_dispatch_task(task)
        interaction.preview = {}
        with self.assertRaisesRegex(ValueError,'CALL_COMPLETION_UNKNOWN'):
            await interaction.wait_accept(OPERATION_ID)

    async def test_human_refusal_stops_without_acceptance(self):
        async def check():
            return True
        receipt = dict(operation_id=OPERATION_ID,evidence_ref='human',observer='human',accepted=False)
        task = asyncio.create_task(asyncio.sleep(10))
        interaction = HumanSliceInteraction(lambda _:receipt,check)
        interaction.bind_dispatch_task(task)
        interaction.preview = {}
        try:
            with self.assertRaisesRegex(ValueError,'HUMAN_ACCEPT_REQUIRED'):
                await interaction.wait_accept(OPERATION_ID)
            self.assertFalse(interaction.timing()['human_accept_reported'])
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    async def test_window_observation_is_not_human_review(self):
        async def check():
            return True
        receipt = dict(operation_id=OPERATION_ID,evidence_ref='window',observer='agent_visual_review',
            observed=True,host_preview_present=True)
        task = asyncio.create_task(asyncio.sleep(10))
        interaction = HumanSliceInteraction(lambda _:receipt,check)
        interaction.bind_dispatch_task(task)
        try:
            await interaction.wait_preview(OPERATION_ID)
            self.assertEqual(interaction.timing()['preview_certification'],'HOST_PREVIEW_PRESENT')
            self.assertEqual(interaction.timing()['human_content_review'],'NOT_CERTIFIED')
            self.assertFalse(interaction.timing()['human_accept_reported'])
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
