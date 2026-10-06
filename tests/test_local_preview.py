"""本地就绪独立于人工通知，并且视口失效不会派发。"""

import asyncio
import functools
from dataclasses import replace
import tempfile
import time

import pytest
np = pytest.importorskip('numpy')

from dawloop.runtime.local_preview import LocalPreviewInteraction, PreviewObservation
from dawloop.runtime import BackendRouter, NativeWriteJournal, ExecutionStatus
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from test_native_write_runtime import plan, Transport, Target, Interaction


def run_async(function):
    @functools.wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return run


class Viewport:
    value = 1
    def fingerprint(self):
        return dict(roi=[0, 0, 230, 150], dpi=self.value)


class Capture:
    notes = False
    preexisting = False
    closed = False
    def __init__(self, roi):
        self.blank = np.full((150,230,4),50,dtype=np.uint8)
    def grab(self):
        start = time.perf_counter_ns()
        frame = self.blank.copy()
        if self.notes or self.preexisting:
            for i in range(4):
                frame[100-i*17:110-i*17,40+i*38:57+i*38,:3]=(150,210,155)
        return frame, start, time.perf_counter_ns()
    def close(self):
        type(self).closed = True


def fixed_plan():
    return replace(plan(), parameters={'notes':[dict(number=84+i,time=3072+i*48,length=24,velocity=.5) for i in range(4)]})


@run_async
async def test_local_confirmation_no_external_preview_or_verification():
    Capture.notes = Capture.preexisting = Capture.closed = False
    class Manual(Interaction):
        async def wait_preview(self, operation):
            raise AssertionError('本地就绪不得等待外部观察')
    interaction = LocalPreviewInteraction(Viewport(),Manual(),trace_id='trace',capture_factory=Capture)
    session=Transport().connect()
    evidence=await Target().confirm(fixed_plan().target,session)
    await interaction.prepare_preview(fixed_plan(),session,evidence)
    interaction.reconfirm_preview(evidence)
    interaction.before_dispatch()
    Capture.notes=True
    observed=await interaction.wait_preview('smoke-1')
    assert observed['observation']['verification_status']=='NOT_VERIFIED'
    assert observed['observation']['confirmation_at']>observed['observation']['preview_detected_at']
    assert observed['observation']['preview_detected_at']>interaction.dispatch_at
    await interaction.close()
    assert Capture.closed and interaction.metrics()['observer_stopped']


@pytest.mark.parametrize('change', ['target','viewport'])
@run_async
async def test_baseline_invalidation_rejects_before_dispatch(change):
    Capture.notes = Capture.preexisting = False
    viewport=Viewport()
    interaction=LocalPreviewInteraction(viewport,Interaction(),trace_id='trace',capture_factory=Capture)
    session=Transport().connect()
    evidence=await Target().confirm(fixed_plan().target,session)
    await interaction.prepare_preview(fixed_plan(),session,evidence)
    if change=='target':
        evidence['identity']['pattern_number']=2
    else:
        viewport.value=2
    with pytest.raises(ValueError,match='VIEWPORT_INVALIDATED'):
        interaction.reconfirm_preview(evidence)
    assert interaction.dispatch_at is None
    await interaction.close()


@run_async
async def test_preexisting_content_rejects_baseline():
    Capture.notes=False; Capture.preexisting=True
    interaction=LocalPreviewInteraction(Viewport(),Interaction(),trace_id='trace',capture_factory=Capture)
    session=Transport().connect()
    with pytest.raises(ValueError,match='PREVIEW_ALREADY_EXISTS'):
        await interaction.prepare_preview(fixed_plan(),session,await Target().confirm(fixed_plan().target,session))
    Capture.preexisting=False
    assert not interaction.thread.is_alive()


@run_async
async def test_other_plan_rejected_without_capture():
    interaction=LocalPreviewInteraction(Viewport(),Interaction(),trace_id='trace',capture_factory=Capture)
    with pytest.raises(ValueError,match='LOCAL_PREVIEW_SCOPE_UNSUPPORTED'):
        await interaction.prepare_preview(plan(1),Transport().connect(),{})
    assert not hasattr(interaction,'thread')


@run_async
async def test_backend_invalidated_not_dispatched():
    class Invalid(Interaction):
        local_preview=True
        async def prepare_preview(self,*args):
            pass
        def reconfirm_preview(self,*args):
            raise ValueError('VIEWPORT_INVALIDATED')
        async def close(self):
            self.closed=True
    interaction=Invalid(); transport=Transport()
    with tempfile.TemporaryDirectory() as directory:
        backend=GopherNativeWriteBackend(enabled=True,transport=transport,target_preparer=Target(),
            interaction=interaction,journal=NativeWriteJournal(directory),disposable_guard=lambda:True)
        class Fallback:
            name='fallback'
            calls=0
            async def discover(self):
                return [replace(backend.capabilities[0],backend=self.name)]
            async def validate(self,*args):
                self.calls+=1
                raise AssertionError('视口失效必须拒绝整次操作')
        fallback=Fallback()
        router=BackendRouter([backend,fallback]); await router.discover()
        result=await router.execute(fixed_plan())
        assert result.execution_status==ExecutionStatus.NOT_DISPATCHED
        assert transport.calls==0 and interaction.closed and fallback.calls==0


@run_async
async def test_final_dispatch_guard_refuses_fallback():
    class InvalidAtDispatch(Interaction):
        local_preview=True
        async def prepare_preview(self,*args):
            pass
        def reconfirm_preview(self,*args):
            pass
        def before_dispatch(self):
            raise ValueError('VIEWPORT_INVALIDATED')
        async def wait_preview(self,*args):
            await asyncio.sleep(.01)
            raise ValueError('VIEWPORT_INVALIDATED')
        async def close(self):
            pass
    transport=Transport()
    with tempfile.TemporaryDirectory() as directory:
        backend=GopherNativeWriteBackend(enabled=True,transport=transport,target_preparer=Target(),
            interaction=InvalidAtDispatch(),journal=NativeWriteJournal(directory),disposable_guard=lambda:True)
        class Fallback:
            name='fallback'
            calls=0
            async def discover(self):
                return [replace(backend.capabilities[0],backend=self.name)]
            async def validate(self,*args):
                self.calls+=1
                raise AssertionError('不得回退')
        fallback=Fallback(); router=BackendRouter([backend,fallback]); await router.discover()
        result=await router.execute(fixed_plan())
        assert result.error_code=='VIEWPORT_INVALIDATED'
        assert result.execution_status==ExecutionStatus.NOT_DISPATCHED
        assert transport.calls==fallback.calls==0


@run_async
async def test_wrong_epoch_and_cancelled_observation_do_not_deliver():
    interaction=LocalPreviewInteraction(Viewport(),Interaction(),trace_id='trace')
    interaction.loop=asyncio.get_running_loop(); interaction.future=interaction.loop.create_future()
    interaction.operation_id='operation'; interaction.session=dict(host_generation='current',bridge_epoch='epoch')
    old=PreviewObservation('trace','operation','old','epoch',1,2,3,4,5,3,(0,0,230,150),16)
    interaction._deliver(old)
    with pytest.raises(ValueError,match='CONTEXT_MISMATCH'):
        await interaction.future
    interaction.future=interaction.loop.create_future(); interaction.stop_event.set()
    interaction._deliver(replace(old,host_generation='current'))
    assert not interaction.future.done()
    await interaction.close()


@run_async
async def test_full_runtime_uses_local_ready_state_and_preserves_verification():
    Capture.notes=Capture.preexisting=False
    class LocalTransport(Transport):
        def invoke_batch(self,*args):
            Capture.notes=True
            return super().invoke_batch(*args)
    class Manual(Interaction):
        async def wait_preview(self,*args):
            raise AssertionError('不得等待人工预览标记')
    interaction=LocalPreviewInteraction(Viewport(),Manual(),trace_id='smoke-1',capture_factory=Capture)
    transport=LocalTransport()
    with tempfile.TemporaryDirectory() as directory:
        backend=GopherNativeWriteBackend(enabled=True,transport=transport,target_preparer=Target(),
            interaction=interaction,journal=NativeWriteJournal(directory),disposable_guard=lambda:True)
        router=BackendRouter([backend]); await router.discover()
        result=await router.execute(fixed_plan())
        assert transport.calls==1 and result.execution_status==ExecutionStatus.SUCCESS
        assert result.value['preview_status']=='LOCAL_PREVIEW_READY'
        assert result.value['local_preview_observation']['verification_status']=='NOT_VERIFIED'
        states=[r['state'] for r in result.value['states']]
        assert states.index('LOCAL_PREVIEW_READY') < states.index('WAITING_FOR_ACCEPT') < states.index('ACCEPTED')
        assert 'WRITE_VERIFIED' not in states and 'EXACT_SET_VERIFIED' not in states
        assert interaction.metrics()['observer_stopped']
