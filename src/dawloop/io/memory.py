from collections.abc import Sequence

from dawloop.note_plan import NoteEvent


class InMemoryEventStore:
    """仅用于离线测试的确定性读写存储。"""

    def __init__(self) -> None:
        self._events: dict[str, tuple[NoteEvent, ...]] = {}

    def write(self, target_id: str, events: Sequence[NoteEvent]) -> None:
        if not target_id:
            raise ValueError("target_id must not be empty")
        copied = tuple(events)
        if any(not isinstance(event, NoteEvent) for event in copied):
            raise TypeError("events must contain NoteEvent values")
        self._events[target_id] = copied

    def read(self, target_id: str) -> tuple[NoteEvent, ...]:
        return self._events[target_id]
