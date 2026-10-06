"""一次性受支持界面动作的文件交接；不自行执行输入或证明提交。"""

import asyncio
import copy
import json
from pathlib import Path
import time


class AcceptActionExchange:
    def __init__(self, directory, *, main_origin, sky_window_id, timeout=10,
                 clock=time.monotonic):
        self.directory = Path(directory)
        self.main_origin = list(main_origin)
        self.sky_window_id = sky_window_id
        self.timeout, self.clock = timeout, clock
        self.attempted = False

    def _write_once(self, name, value):
        with (self.directory/name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)

    async def action(self, context, control, revalidate):
        if self.attempted:
            raise ValueError('ACCEPT_EXCHANGE_BUDGET_EXHAUSTED')
        self.attempted = True
        request = dict(context=copy.deepcopy(context), control=copy.deepcopy(control),
            main_origin=self.main_origin, sky_window_id=self.sky_window_id, pending=True)
        self._write_once('action_request.json', request)
        deadline = self.clock() + self.timeout
        checked = False
        while self.clock() < deadline:
            check = self.directory/'fresh_check_request.json'
            if check.exists() and not checked:
                checked = True
                supplied = json.loads(check.read_text(encoding='utf-8'))
                generation = supplied.get('generation')
                if (not isinstance(generation, str) or not generation
                        or supplied != dict(context=context, control=control, generation=generation)):
                    raise ValueError('ACCEPT_EXCHANGE_CHECK_MISMATCH')
                latest = await revalidate()
                if self.clock() >= deadline:
                    raise TimeoutError('ACCEPT_EXCHANGE_RESULT_UNKNOWN')
                self._write_once('fresh_check_answer.json', dict(latest, generation=generation))
            answer = self.directory/'action_answer.json'
            if answer.exists():
                value = json.loads(answer.read_text(encoding='utf-8'))
                if not checked or value.get('context') != context or value.get('control_id') != control['control_id']:
                    raise ValueError('ACCEPT_EXCHANGE_ANSWER_UNPROVEN')
                return value
            await asyncio.sleep(0.01)
        # 超时只终止等待，不能宣称已撤销外部点击；意图文件保留且不能重用。
        raise TimeoutError('ACCEPT_EXCHANGE_RESULT_UNKNOWN')
