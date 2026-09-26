from typing import Protocol, Sequence

from flskill.note_plan import NoteEvent


class Writer(Protocol):
    def write(self, target_id: str, events: Sequence[NoteEvent]) -> None: ...


class Reader(Protocol):
    def read(self, target_id: str) -> Sequence[NoteEvent]: ...
