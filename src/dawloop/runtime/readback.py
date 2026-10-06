from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import math


class ReadbackFreshness(str, Enum):
    FRESH = 'FRESH'
    STALE = 'STALE'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True)
class TargetBoundReadback:
    freshness: ReadbackFreshness
    target_bound: bool
    error_code: str | None


def _target_key(snapshot):
    names = ('pattern_index', 'pattern_name', 'channel_index', 'channel_name', 'ppq')
    observations = [getattr(snapshot, name) for name in names]
    if any(item is None for item in observations):
        return None
    return tuple((item.value, item.index_basis, item.context_binding) for item in observations)


def assess_readback(expected, before, after, *, request_generation=None, export_generation=None,
                    request_started=None, export_started=None, export_completed=None, same_monotonic_clock=False,
                    producer_target=None, producer_binding_verified=False):
    wanted, initial, final = map(_target_key, (expected, before, after))
    if wanted is None or initial is None or final is None:
        return TargetBoundReadback(ReadbackFreshness.UNKNOWN, False, 'IDENTITY_UNAVAILABLE')
    if wanted != initial or wanted != final:
        return TargetBoundReadback(ReadbackFreshness.UNKNOWN, False, 'TARGET_CHANGED')
    if not isinstance(request_generation, str) or not request_generation or not isinstance(export_generation, str) or not export_generation:
        return TargetBoundReadback(ReadbackFreshness.UNKNOWN, False, 'READBACK_GENERATION_UNAVAILABLE')
    if request_generation != export_generation:
        return TargetBoundReadback(ReadbackFreshness.STALE, False, 'STALE_GENERATION')
    times = (request_started, export_started, export_completed)
    if not same_monotonic_clock or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times):
        return TargetBoundReadback(ReadbackFreshness.UNKNOWN, False, 'EXPORT_ORDER_UNPROVEN')
    if export_started < request_started or export_completed < export_started:
        return TargetBoundReadback(ReadbackFreshness.STALE, False, 'EXPORT_PRECEDES_REQUEST')
    # 首尾一致不能排除中途切到另一目标又切回；导出方必须提供实际读取目标。
    if not producer_binding_verified or producer_target is None:
        return TargetBoundReadback(ReadbackFreshness.FRESH, False, 'PRODUCER_TARGET_UNPROVEN')
    if _target_key(producer_target) != wanted:
        return TargetBoundReadback(ReadbackFreshness.FRESH, False, 'TARGET_CHANGED')
    return TargetBoundReadback(ReadbackFreshness.FRESH, True, None)


READ_ONLY_NOTE_EXPRESSION = """{
    'ppq': score.PPQ,
    'note_count': score.noteCount,
    'notes': [
        {'pitch': note.number, 'start': note.time, 'length': note.length, 'velocity': note.velocity}
        for index in range(score.noteCount)
        for note in [score.getNote(index)]
    ]
}"""


def validate_read_only_expression(source):
    if not isinstance(source, str) or len(source) > 4096:
        raise ValueError('只读表达式无效')
    try:
        actual = ast.parse(source, mode='eval')
    except (SyntaxError, ValueError) as error:
        raise ValueError('只允许固定只读表达式') from error
    expected = ast.parse(READ_ONLY_NOTE_EXPRESSION, mode='eval')
    if ast.dump(actual, include_attributes=False) != ast.dump(expected, include_attributes=False):
        raise ValueError('表达式不匹配已审查的只读模板')
    return True
