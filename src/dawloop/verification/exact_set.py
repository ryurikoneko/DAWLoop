from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from dawloop.io.protocol import Reader, Writer
from dawloop.note_plan import NoteEvent, NotePlan


_FIELDS = ("start_tick", "duration", "pitch", "velocity")


@dataclass(frozen=True)
class EventMismatch:
    planned: NoteEvent
    actual: NoteEvent
    fields: tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    status: str
    scope: str
    label: str
    planned_count: int
    actual_count: int
    missing: tuple[NoteEvent, ...] = ()
    extra: tuple[NoteEvent, ...] = ()
    mismatches: tuple[EventMismatch, ...] = ()
    write_error: str | None = None
    read_error: str | None = None


def _ordered(events: Sequence[NoteEvent]) -> list[NoteEvent]:
    return sorted(events, key=lambda event: tuple(getattr(event, name) for name in _FIELDS))


def _differences(planned: NoteEvent, actual: NoteEvent) -> tuple[str, ...]:
    return tuple(name for name in _FIELDS if getattr(planned, name) != getattr(actual, name))


def compare_events(
    planned: Sequence[NoteEvent], actual: Sequence[NoteEvent]
) -> tuple[tuple[NoteEvent, ...], tuple[NoteEvent, ...], tuple[EventMismatch, ...]]:
    """比较事件多重集合；配对差异只用于诊断，PASS 只看精确集合。"""
    planned_counts = Counter(planned)
    actual_counts = Counter(actual)
    missing = []
    extra = []
    for event in sorted(planned_counts, key=lambda item: tuple(getattr(item, f) for f in _FIELDS)):
        missing.extend([event] * max(0, planned_counts[event] - actual_counts[event]))
    for event in sorted(actual_counts, key=lambda item: tuple(getattr(item, f) for f in _FIELDS)):
        extra.extend([event] * max(0, actual_counts[event] - planned_counts[event]))

    remaining_extra = list(extra)
    mismatches = []
    for expected in missing:
        if not remaining_extra:
            break
        best_index = min(
            range(len(remaining_extra)),
            key=lambda index: (
                len(_differences(expected, remaining_extra[index])),
                tuple(getattr(remaining_extra[index], field) for field in _FIELDS),
            ),
        )
        observed = remaining_extra.pop(best_index)
        mismatches.append(EventMismatch(expected, observed, _differences(expected, observed)))
    return tuple(missing), tuple(extra), tuple(mismatches)


def write_read_verify(plan: NotePlan, writer: Writer, reader: Reader) -> VerificationResult:
    write_error = None
    read_error = None
    actual: tuple[NoteEvent, ...] = ()
    try:
        writer.write(plan.target_id, plan.events)
    except Exception as error:
        write_error = f"{type(error).__name__}: {error}"
    try:
        actual = tuple(reader.read(plan.target_id))
        if any(not isinstance(event, NoteEvent) for event in actual):
            raise TypeError("reader returned a non-NoteEvent value")
    except Exception as error:
        read_error = f"{type(error).__name__}: {error}"

    missing, extra, mismatches = compare_events(plan.events, actual)
    passed = not write_error and not read_error and not missing and not extra
    return VerificationResult(
        status="PASS" if passed else "STOP",
        scope="offline",
        label="Offline Algorithm Verified" if passed else "STOP",
        planned_count=len(plan.events),
        actual_count=len(actual),
        missing=missing,
        extra=extra,
        mismatches=mismatches,
        write_error=write_error,
        read_error=read_error,
    )
