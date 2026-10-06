"""真实模块跨进程交接演练；宿主、像素输入与界面动作全部模拟。"""

import asyncio
import copy
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import controlled_visual_interaction as visual
from dawloop.runtime.local_preview import FIXED_HASH
from dawloop.runtime.visual_accept import ReviewedAcceptLocator, TITLE_CROP, FOOTER_CROP


@pytest.mark.parametrize('mode', ['success', 'target_changed', 'viewport_changed',
    'callback_before_action', 'template_changed', 'unknown_action', 'callback_error',
    'preview_still_open', 'no_application', 'post_accept_target_changed'])
def test_real_accept_modules_exchange_with_simulated_external_action(tmp_path, monkeypatch, mode):
    node = shutil.which('node')
    if not node: pytest.skip('离线跨语言演练需要已有节点运行时')

    async def exercise():
        target = dict(controller_session='offline-controller', project_generation='offline-project',
            pattern_number=1, pattern_name='样式 1', channel_index=0, channel_name='808 Kick',
            selected_channels=[0], ppq=96)
        fingerprint = dict(roi=[620,300,850,450], dpi=120, viewport='offline-only')
        preview = dict(hwnd=103, parent=102, process_id=101, rectangle=[778,470,1271,635],
            native_title='DAWLoop Native Add',window_class='TScriptDialog',
            fixed_title=True, visible=True, enabled=True)
        host = asyncio.get_running_loop().create_future()
        confirmations = 0
        accepted = False
        async def confirm(expected, session):
            nonlocal confirmations
            confirmations += 1
            value = copy.deepcopy(target)
            if (mode == 'target_changed' and confirmations >= 3
                    or mode == 'post_accept_target_changed' and accepted):
                value['channel_index'] = 1
            if mode == 'callback_before_action' and confirmations >= 3 and not host.done():
                host.set_result(({'payload':{'result':{'isError':False}}},None,0,0))
            return dict(identity=value)
        def state():
            current = copy.deepcopy(fingerprint)
            if mode == 'viewport_changed' and confirmations >= 3: current['dpi'] = 144
            return dict(preview=copy.deepcopy(preview),
                preview_confirmed=not accepted or mode == 'preview_still_open', fingerprint=current)
        viewport = SimpleNamespace(pid=101, top=102, preview_snapshot=state,
            user=SimpleNamespace(GetDpiForWindow=lambda hwnd:120),
            gui=SimpleNamespace(GetForegroundWindow=lambda:103, GetWindowRect=lambda hwnd:[0,0,2048,1152]))
        backend = SimpleNamespace(transport=SimpleNamespace(poisoned_epoch=None),
            target_preparer=SimpleNamespace(confirm=confirm), check_target=lambda plan,evidence:None)
        interaction = visual.ControlledVisualInteraction(viewport,None,trace_id='offline',
            diagnostic=None,backend=backend,directory=tmp_path,sky_window_id=10)
        interaction.session = dict(session='offline-epoch', host_generation='offline-host',bridge_epoch='offline-epoch')
        interaction.plan = SimpleNamespace(target={})
        interaction.target = copy.deepcopy(target)
        interaction.baseline_fingerprint = copy.deepcopy(fingerprint)
        interaction.observation = {'confirmed':True}
        interaction.operation_id = 'offline-fixed-four'
        interaction.runtime_ready_at = time.perf_counter_ns()
        interaction.bind_dispatch_task(host)
        locator = ReviewedAcceptLocator(enabled=True)
        frame = np.zeros((165,493,4),dtype=np.uint8)
        for rect, value in ((TITLE_CROP,locator.title),(FOOTER_CROP,locator.footer)):
            left,top,right,bottom = rect
            frame[top:bottom,left:right,:3] = value
        def capture(**facts):
            value = frame.copy()
            if mode == 'template_changed' and confirmations >= 3:
                value[FOOTER_CROP[1],FOOTER_CROP[0],0] ^= 1
            return dict(control=locator.locate(value,**facts))
        monkeypatch.setattr(interaction.locator,'capture',capture)
        peer = await asyncio.create_subprocess_exec(node,
            str(Path(__file__).with_name('controlled_accept_exchange_peer.mjs')),str(tmp_path),mode,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        rejected_before_action = mode in ('target_changed','viewport_changed','callback_before_action','template_changed')
        try:
            # 先确认模拟观察端启动，避免把Node冷启动算成待验证动作的证据年龄。
            async with asyncio.timeout(3):
                while not (tmp_path / 'offline_peer_ready.json').exists():
                    await asyncio.sleep(0.01)
            if rejected_before_action or mode == 'unknown_action':
                with pytest.raises(ValueError,match='VISUAL_ACCEPT_ACTION_UNKNOWN'):
                    await interaction.guarded_auto_accept(interaction.operation_id,FIXED_HASH)
            else:
                await interaction.guarded_auto_accept(interaction.operation_id,FIXED_HASH)
            stdout,stderr = await asyncio.wait_for(peer.communicate(),6)
            assert peer.returncode == 0, stderr.decode('utf-8')
            result = json.loads((tmp_path/'offline_peer_result.json').read_text(encoding='utf-8'))
            assert result['clicks'] == (0 if rejected_before_action else 1)
            if rejected_before_action or mode == 'unknown_action':
                assert interaction.accept_receipt['action_status'] == 'UNKNOWN'
                assert interaction.accept_receipt['commit_status'] == 'UNKNOWN'
                with pytest.raises((ValueError,FileExistsError)):
                    await interaction.guarded_auto_accept(interaction.operation_id,FIXED_HASH)
                return
            accepted = True
            host.set_result(({'payload':{'result':{'isError':False}}},
                TimeoutError() if mode == 'callback_error' else None,0,0))
            class Capture:
                def grab(self): return frame.copy(),time.perf_counter_ns(),time.perf_counter_ns()
                def close(self): pass
            monkeypatch.setattr(visual,'RegionCapture',lambda roi:Capture())
            monkeypatch.setattr(visual,'note_geometry',lambda value,floor:(mode != 'no_application',[]))
            interaction.detector = SimpleNamespace(chroma_floor=1)
            if mode == 'success':
                outcome = await interaction.wait_accept(interaction.operation_id)
                assert outcome['accepted'] and outcome['exact_set_verified'] is False
                assert (await interaction.wait_application(interaction.operation_id))['exact_set_verified'] is False
            else:
                with pytest.raises(ValueError): await interaction.wait_accept(interaction.operation_id)
            with pytest.raises(ValueError,match='CONTEXT_UNPROVEN'):
                await interaction.guarded_auto_accept(interaction.operation_id,FIXED_HASH)
        finally:
            if peer.returncode is None:
                peer.kill()
                await peer.communicate()
            if not host.done(): host.cancel()
    asyncio.run(exercise())
