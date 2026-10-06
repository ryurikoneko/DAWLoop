from __future__ import annotations

import asyncio
from pathlib import Path

from .fl_controller_identity import ControllerIdentityBackend, controller_snapshot
from dawloop.runtime.identity import IdentityFieldStatus


class ControllerChannelSelector(ControllerIdentityBackend):
    """受限导航入口；动作回执与独立身份读回分开。"""

    name = 'fl_controller_channel_selector'
    _allowed_actions = ('dawloop.getIdentitySnapshot', 'dawloop.selectOneChannelOnce')
    _action = 'dawloop.selectOneChannelOnce'
    _confirmation = 'CHANNEL_SELECTION_CONFIRMED'

    def __init__(self, port_name, *, settings_dir, timeout=3):
        if not isinstance(settings_dir, Path) or not settings_dir.is_absolute():
            raise ValueError('EXPLICIT_CONTROLLER_SETTINGS_REQUIRED')
        super().__init__(port_name, settings_dir=settings_dir, timeout=timeout)
        self.used_operations = set()

    def _select_and_read(self, operation_id, global_index, channel_name):
        before = self._read()
        _, status = controller_snapshot(before)
        required = ('pattern_index', 'pattern_name', 'channel_index', 'channel_name', 'ppq')
        if any(status[key] != IdentityFieldStatus.AVAILABLE for key in required):
            raise ValueError('CHANNEL_INITIAL_IDENTITY_UNCONFIRMED')
        visible = before.get('visible_channels', [])
        if sum(row.get('global_index') == global_index and row.get('name') == channel_name
               for row in visible) != 1:
            raise ValueError('CHANNEL_TARGET_UNCONFIRMED')
        ack = self._read(self._action, dict(operation_id=operation_id,
            global_index=global_index, channel_name=channel_name,
            expected_controller_build_id=before['controller_build_id'],
            controller_session_id=before['controller_session_id'],
            project_generation=before['project_generation']))
        try:
            after = self._read()
            _, status = controller_snapshot(after)
            stable = ('controller_build_id', 'controller_session_id', 'project_generation',
                      'pattern_number', 'pattern_name', 'ppq')
            if (any(status[key] != IdentityFieldStatus.AVAILABLE for key in required) or
                    any(before.get(key) != after.get(key) for key in stable) or
                    after.get('channel_index_type') != 'global' or
                    type(after.get('channel_index')) is not int or
                    after['channel_index'] != global_index or after.get('channel_name') != channel_name or
                    after.get('selected_channels') != [global_index] or
                    any(type(index) is not int for index in after['selected_channels'])):
                raise RuntimeError('CHANNEL_SELECTION_CONFIRMATION_FAILED')
        except BaseException:
            self.poisoned = True
            raise
        return dict(status=self._confirmation, execution=ack,
                    identity_before=before, identity_after=after,
                    producer_target_verified=False, exact_target_binding=False)

    async def select_once(self, operation_id, global_index, channel_name):
        if (not isinstance(operation_id, str) or not operation_id.strip() or
                type(global_index) is not int or global_index < 0 or
                not isinstance(channel_name, str) or not channel_name.strip()):
            raise ValueError('CHANNEL_SELECTION_REQUEST_INVALID')
        async with self.lock:
            if operation_id in self.used_operations:
                raise RuntimeError('CHANNEL_SELECTION_BUDGET_EXHAUSTED')
            # 即使结果未知，调用者也不能再次使用本操作编号。
            self.used_operations.add(operation_id)
            task = asyncio.create_task(asyncio.to_thread(self._select_and_read,
                operation_id, global_index, channel_name))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                self.poisoned = True
                try:
                    await task
                except Exception:
                    pass
                raise


class ControllerPianoRollOpener(ControllerChannelSelector):
    """只显示已独占选中通道的卷帘；身份不等于可见目标绑定。"""

    name = 'fl_controller_piano_roll_opener'
    _allowed_actions = ('dawloop.getIdentitySnapshot', 'dawloop.openPianoRollOnce')
    _action = 'dawloop.openPianoRollOnce'
    _confirmation = 'PIANO_ROLL_OPEN_ACK_WITH_STABLE_IDENTITY'
