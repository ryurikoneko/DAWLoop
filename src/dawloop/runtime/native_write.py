"""受限新增音符模板和实验执行状态，不提供任意源码入口。"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import ast
import hashlib
import json
import os
from pathlib import Path
import re
from .diagnostics import observe

from .models import ExecutionMode, OperationPlan


NATIVE_BATCH_ADD = 'piano_roll.notes.batch_add.native'
MAX_TICK = 2147483647
TARGET_FIELDS = ('expected_pattern_index', 'expected_pattern_name',
                 'expected_channel_index', 'expected_channel_name')


class NativeWriteState(str, Enum):
    PLANNED = 'PLANNED'
    TARGET_PREPARED = 'TARGET_PREPARED'
    SOURCE_VALIDATED = 'SOURCE_VALIDATED'
    DISPATCHED = 'DISPATCHED'
    PREVIEW_OBSERVED = 'PREVIEW_OBSERVED'
    LOCAL_PREVIEW_READY = 'LOCAL_PREVIEW_READY'
    WAITING_FOR_ACCEPT = 'WAITING_FOR_ACCEPT'
    ACCEPTED = 'ACCEPTED'
    APPLICATION_OBSERVED = 'APPLICATION_OBSERVED'
    COMPLETION_CONFIRMED = 'COMPLETION_CONFIRMED'
    COMPLETION_UNKNOWN = 'COMPLETION_UNKNOWN'
    ABORTED = 'ABORTED'


class AcceptPolicy(str, Enum):
    MANUAL_ACCEPT = 'MANUAL_ACCEPT'
    GUARDED_AUTO_ACCEPT = 'GUARDED_AUTO_ACCEPT'


def normalized_notes(notes):
    if not isinstance(notes, (list, tuple)) or not 1 <= len(notes) <= 128:
        raise ValueError('CAPABILITY_LIMIT_EXCEEDED')
    output = []
    for note in notes:
        if not isinstance(note, dict) or set(note) != {'number', 'time', 'length', 'velocity'}:
            raise ValueError('INVALID_NOTE_FIELDS')
        number, tick, length = (note[k] for k in ('number', 'time', 'length'))
        if (any(type(v) is not int for v in (number, tick, length))
                or not 0 <= number <= 127 or not 0 <= tick <= MAX_TICK
                or not 1 <= length <= MAX_TICK or tick + length > MAX_TICK):
            raise ValueError('INVALID_NOTE_RANGE')
        if type(note['velocity']) not in (int, float):
            raise ValueError('INVALID_VELOCITY')
        try:
            value = Decimal(str(note['velocity']))
            scaled = value * 1000000
            if not value.is_finite() or not 0 <= value <= 1 or scaled != scaled.to_integral_value():
                raise ValueError('INVALID_VELOCITY')
            output.append([number, tick, length, int(scaled)])
        except InvalidOperation as error:
            raise ValueError('INVALID_VELOCITY') from error
    return output


def canonical_source(rows):
    payload = json.dumps(rows, separators=(',', ':'), allow_nan=False)
    return ('import flpianoroll as flp\n\nNOTES = ' + payload + '\n\n'
            'def createDialog() -> flp.ScriptDialog:\n'
            '    return flp.ScriptDialog("DAWLoop Native Add", "Experimental add-only preview.")\n\n'
            'def apply(form: flp.ScriptDialog) -> None:\n'
            '    for number, tick, length, velocity in NOTES:\n'
            '        note = flp.Note()\n'
            '        note.number = number\n'
            '        note.time = tick\n'
            '        note.length = length\n'
            '        note.velocity = velocity / 1000000\n'
            '        flp.score.addNote(note)\n').encode('utf-8')


@dataclass(frozen=True)
class RenderedPianoRollScript:
    source: bytes
    sha256: str
    template_hash: str
    note_count: int
    source_size: int


class PianoRollScriptRenderer:
    def __init__(self, diagnostics=None):
        self.diagnostics = diagnostics

    def render(self, notes):
        observe(self.diagnostics, 'rendering_begin')
        source = canonical_source(normalized_notes(notes))
        result = RenderedPianoRollScript(source, hashlib.sha256(source).hexdigest(),
            hashlib.sha256(canonical_source([])).hexdigest(), len(notes), len(source))
        self.validate(notes, result)
        observe(self.diagnostics, 'rendering_complete')
        return result

    def validate(self, notes, rendered):
        rows = normalized_notes(notes)
        observe(self.diagnostics, 'hash_validation_begin')
        if (rendered.source != canonical_source(rows)
                or rendered.sha256 != hashlib.sha256(rendered.source).hexdigest()
                or rendered.template_hash != hashlib.sha256(canonical_source([])).hexdigest()
                or rendered.note_count != len(rows) or rendered.source_size != len(rendered.source)):
            raise ValueError('SOURCE_TEMPLATE_MISMATCH')
        observe(self.diagnostics, 'hash_validation_complete')
        observe(self.diagnostics, 'AST_validation_begin')
        tree = ast.parse(rendered.source)
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        if calls != {'flp.ScriptDialog', 'flp.Note', 'flp.score.addNote'}:
            raise ValueError('SOURCE_CALL_NOT_ALLOWED')
        if any(isinstance(n, ast.ImportFrom) for n in ast.walk(tree)):
            raise ValueError('SOURCE_IMPORT_NOT_ALLOWED')
        # 唯一变化槽是整数字面量列表，其他语法树必须与规范模板完全相同。
        tree.body[1].value = ast.List(elts=[], ctx=ast.Load())
        if ast.dump(tree) != ast.dump(ast.parse(canonical_source([]))):
            raise ValueError('SOURCE_AST_MISMATCH')
        observe(self.diagnostics, 'AST_validation_complete')


@dataclass(frozen=True)
class PianoRollBatchAddPlan:
    target: dict
    notes: tuple[dict, ...]
    operation_id: str

    def operation_plan(self):
        return OperationPlan(NATIVE_BATCH_ADD, dict(self.target),
            parameters={'notes': [dict(n) for n in self.notes]}, mode=ExecutionMode.FAST,
            metadata={'operation_id': self.operation_id, 'experimental_authorized': True})


def validate_plan(plan, diagnostics=None):
    if plan.operation != NATIVE_BATCH_ADD or set(plan.parameters) != {'notes'} or plan.note_plan is not None:
        raise ValueError('ADD_ONLY_PLAN_REQUIRED')
    if set(plan.target) != set(TARGET_FIELDS):
        raise ValueError('EXPLICIT_TARGET_REQUIRED')
    if (type(plan.target['expected_pattern_index']) is not int or plan.target['expected_pattern_index'] < 1
            or type(plan.target['expected_channel_index']) is not int or plan.target['expected_channel_index'] < 0
            or any(not isinstance(plan.target[k], str) or not plan.target[k].strip()
                   for k in ('expected_pattern_name', 'expected_channel_name'))):
        raise ValueError('INVALID_TARGET')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', str(plan.metadata.get('operation_id', ''))):
        raise ValueError('OPERATION_ID_REQUIRED')
    return PianoRollScriptRenderer(diagnostics).render(plan.parameters['notes'])


class NativeWriteJournal:
    def __init__(self, directory):
        self.directory = Path(directory)

    def reserve(self, operation_id, session, source_hash):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', operation_id):
            raise ValueError('INVALID_OPERATION_ID')
        self.directory.mkdir(parents=True, exist_ok=True)
        data = dict(operation_id=operation_id, session=session, source_hash=source_hash, dispatch_budget=1)
        generation = session.get('host_generation')
        if not generation:
            raise ValueError('HOST_GENERATION_REQUIRED')
        host_key = hashlib.sha256(generation.encode('utf-8')).hexdigest()
        # 意图先落盘；进程中断或结果未知之后也不能恢复同一预算。
        for name in (operation_id + '.json', 'host_' + host_key + '.json'):
            try:
                with (self.directory / name).open('x', encoding='utf-8') as stream:
                    json.dump(data, stream, ensure_ascii=False)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError as error:
                raise ValueError('SINGLE_DISPATCH_BUDGET_EXHAUSTED') from error
