from __future__ import annotations

"""Reusable orchestration helpers derived from DSH's orchestration workflow.

The DSH source used register-aware melody handoff, explicit midrange-coverage
checks, and source-note coverage checks. This module extracts those ideas into
small deterministic helpers without carrying over composition-specific score
data or instrument assignments.
"""

from dataclasses import dataclass
from typing import Iterable, Sequence

from flskill.note_plan import NoteEvent


@dataclass(frozen=True)
class InstrumentRange:
    name: str
    low: int
    high: int
    preferred_low: int | None = None
    preferred_high: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("instrument name must not be empty")
        if not 0 <= self.low <= self.high <= 127:
            raise ValueError("instrument range must fit MIDI 0..127")
        if self.preferred_low is not None and not self.low <= self.preferred_low <= self.high:
            raise ValueError("preferred_low must fall inside the playable range")
        if self.preferred_high is not None and not self.low <= self.preferred_high <= self.high:
            raise ValueError("preferred_high must fall inside the playable range")
        if (
            self.preferred_low is not None
            and self.preferred_high is not None
            and self.preferred_low > self.preferred_high
        ):
            raise ValueError("preferred range is reversed")

    def playable(self, pitch: int) -> bool:
        return self.low <= pitch <= self.high

    def comfort_penalty(self, pitch: int) -> int:
        if not self.playable(pitch):
            return 10_000 + min(abs(pitch - self.low), abs(pitch - self.high))
        lo = self.preferred_low if self.preferred_low is not None else self.low
        hi = self.preferred_high if self.preferred_high is not None else self.high
        if lo <= pitch <= hi:
            return 0
        return min(abs(pitch - lo), abs(pitch - hi))


def choose_instrument_for_phrase(
    events: Sequence[NoteEvent],
    instruments: Sequence[InstrumentRange],
) -> InstrumentRange:
    """Choose a playable instrument using phrase register and comfort range.

    This implements the useful part of DSH's "melody changes instrument by
    register" rule without hard-coding a particular orchestra.
    """
    if not events:
        raise ValueError("phrase must contain at least one note")
    if not instruments:
        raise ValueError("at least one instrument is required")
    pitches = [event.pitch for event in events]
    candidates = [
        instrument for instrument in instruments
        if all(instrument.playable(pitch) for pitch in pitches)
    ]
    if not candidates:
        raise ValueError("no instrument can play the complete phrase")
    center = round(sum(pitches) / len(pitches))
    return min(
        candidates,
        key=lambda instrument: (
            sum(instrument.comfort_penalty(pitch) for pitch in pitches),
            instrument.comfort_penalty(center),
            instrument.name,
        ),
    )


def find_register_gaps(
    parts: Iterable[Iterable[NoteEvent]],
    *,
    start_tick: int,
    end_tick: int,
    step_ticks: int,
    low_pitch: int = 60,
    high_pitch: int = 72,
) -> tuple[int, ...]:
    """Return sampled ticks where no sounding note occupies a pitch band."""
    if start_tick < 0 or end_tick <= start_tick or step_ticks <= 0:
        raise ValueError("invalid time window")
    if not 0 <= low_pitch <= high_pitch <= 127:
        raise ValueError("invalid pitch band")
    all_parts = [tuple(part) for part in parts]
    gaps: list[int] = []
    for tick in range(start_tick, end_tick, step_ticks):
        occupied = False
        for part in all_parts:
            if any(
                event.start_tick <= tick < event.start_tick + event.duration
                and low_pitch <= event.pitch <= high_pitch
                for event in part
            ):
                occupied = True
                break
        if not occupied:
            gaps.append(tick)
    return tuple(gaps)


def source_note_coverage(
    source: Iterable[NoteEvent],
    arranged_parts: Iterable[Iterable[NoteEvent]],
    *,
    allow_octave_equivalence: bool = False,
) -> tuple[NoteEvent, ...]:
    """Return source events with no matching arranged onset/pitch.

    DSH used this kind of coverage check to avoid silently dropping source
    material during orchestration. FLSkill exposes the check as evidence; it
    does not require every arrangement to preserve every note.
    """
    arranged = [event for part in arranged_parts for event in part]
    missing: list[NoteEvent] = []
    for event in source:
        match_index = None
        for index, candidate in enumerate(arranged):
            if candidate.start_tick != event.start_tick:
                continue
            if allow_octave_equivalence:
                if candidate.pitch % 12 == event.pitch % 12:
                    match_index = index
                    break
            elif candidate.pitch == event.pitch:
                match_index = index
                break
        if match_index is None:
            missing.append(event)
        else:
            arranged.pop(match_index)
    return tuple(missing)
