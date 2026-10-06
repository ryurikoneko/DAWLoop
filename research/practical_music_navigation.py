"""复用既有目标准备器，将控制器身份与原生写入会话同时约束。"""

import copy
from uuid import uuid4

from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
from research.practical_music_slice import TARGET


CONTROLLER_FIELDS = ('controller_build_id', 'controller_session_id', 'project_generation')


class NavigatedMusicPreparation:
    def __init__(self, navigator, observe_ui, *, controller_context, native_guard,
                 window_identity):
        self.navigator = navigator
        self.controller_context = copy.deepcopy(controller_context)
        if any(not isinstance(controller_context.get(k), str) or not controller_context[k]
               for k in CONTROLLER_FIELDS):
            raise ValueError('CONTROLLER_CONTEXT_REQUIRED')
        self.native_guard = native_guard
        self.session = None
        owner = self

        class CheckedIdentity:
            async def read_identity(self):
                owner.check_native()
                value = await navigator.read_identity()
                if any(value.get(k) != owner.controller_context[k] for k in CONTROLLER_FIELDS):
                    raise ValueError('CONTROLLER_CONTEXT_CHANGED')
                owner.check_native()
                return value

        async def navigate(target, binding):
            owner.check_native()
            controller = dict(binding_kind='CONTROLLER_ONLY', **owner.controller_context)
            await navigator.navigate_once(target, controller, uuid4().hex)
            owner.check_native()

        self.preparer = ControllerTargetPreparer(CheckedIdentity(), navigate, observe_ui,
            window_identity=window_identity)

    def check_native(self):
        if self.session is None or self.native_guard(copy.deepcopy(self.session)) is not True:
            raise ValueError('NATIVE_CONTEXT_CHANGED')

    def binding(self, target, session):
        if target != TARGET:
            raise ValueError('MUSIC_SLICE_SCOPE_MISMATCH')
        if any(k in session and session[k] != self.controller_context[k] for k in CONTROLLER_FIELDS):
            raise ValueError('CONTROLLER_CONTEXT_CHANGED')
        if self.session is None:
            self.session = copy.deepcopy(session)
        if session != self.session:
            raise ValueError('NATIVE_CONTEXT_CHANGED')
        self.check_native()
        # 内部观察需要两种身份；后端入口仍保留它自身的原生会话对象。
        return dict(session, **self.controller_context)

    def outward(self, evidence):
        value = copy.deepcopy(evidence)
        value['native_controller_binding'] = value['session']
        value['session'] = copy.deepcopy(self.session)
        self.check_native()
        return value

    async def prepare(self, target, session):
        binding = self.binding(target, session)
        return self.outward(await self.preparer.prepare(target, binding))

    async def confirm(self, target, session):
        binding = self.binding(target, session)
        return self.outward(await self.preparer.confirm(target, binding))
