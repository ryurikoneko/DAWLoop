"""固定三基础动作事务，不提供重试或替代导航。"""

import asyncio
from pathlib import Path

from .fl_controller_identity import ControllerIdentityBackend


class ControllerTargetNavigator(ControllerIdentityBackend):
    _allowed_actions = ('dawloop.getIdentitySnapshot', 'dawloop.navigateTargetOnce')

    def __init__(self, port_name, *, settings_dir, **kwargs):
        if not isinstance(settings_dir, Path) or not settings_dir.is_absolute():
            raise ValueError('EXPLICIT_CONTROLLER_SETTINGS_REQUIRED')
        super().__init__(port_name, settings_dir=settings_dir, **kwargs)
        self.used_targets = set()

    async def navigate_once(self, target, session, operation_id):
        async with self.lock:
            key = (target['expected_pattern_index'], target['expected_channel_index'])
            if key in self.used_targets:
                raise RuntimeError('NAVIGATION_TRANSACTION_BUDGET_EXHAUSTED')
            self.used_targets.add(key)
            params = dict(operation_id=operation_id,
                pattern_index=target['expected_pattern_index'], pattern_name=target['expected_pattern_name'],
                global_index=target['expected_channel_index'], channel_name=target['expected_channel_name'],
                expected_controller_build_id=session['controller_build_id'],
                controller_session_id=session['controller_session_id'], project_generation=session['project_generation'])
            task = asyncio.create_task(asyncio.to_thread(self._read, 'dawloop.navigateTargetOnce', params))
            try:
                ack = await asyncio.shield(task)
                if (ack.get('pattern_index') != params['pattern_index'] or
                        ack.get('pattern_name') != params['pattern_name'] or
                        ack.get('navigation_transactions') != 1 or
                        [row.get('primitive') for row in ack.get('primitives', [])] !=
                        ['select_pattern', 'select_channel_global', 'targeted_open_piano_roll'] or
                        any(row.get('status') != 'EXECUTED_UNVERIFIED' for row in ack['primitives'])):
                    self.poisoned = True
                    raise RuntimeError('NAVIGATION_RESPONSE_MISMATCH')
                return ack
            except asyncio.CancelledError:
                self.poisoned = True
                try:
                    await task
                except Exception:
                    pass
                raise
