from dataclasses import dataclass
from typing import Any

from dawproof.time import MusicalGrid


@dataclass(frozen=True)
class NoteEvent:
    start_tick: int
    duration: int
    pitch: int
    velocity: int

    def __post_init__(self) -> None:
        if type(self.start_tick) is not int or self.start_tick < 0:
            raise ValueError("start_tick must be a non-negative integer")
        if type(self.duration) is not int or self.duration <= 0:
            raise ValueError("duration must be a positive integer")
        if type(self.pitch) is not int or not 0 <= self.pitch <= 127:
            raise ValueError("pitch must be an integer from 0 through 127")
        if type(self.velocity) is not int or not 1 <= self.velocity <= 127:
            raise ValueError("velocity must be an integer from 1 through 127")

    def to_dict(self) -> dict[str, int]:
        return {
            "start_tick": self.start_tick,
            "duration": self.duration,
            "pitch": self.pitch,
            "velocity": self.velocity,
        }


@dataclass(frozen=True)
class NotePlan:
    target_id: str
    grid: MusicalGrid
    section_start_tick: int
    section_bars: int
    events: tuple[NoteEvent, ...]
    version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError("target_id must be a non-empty string")
        if not isinstance(self.grid, MusicalGrid):
            raise TypeError("grid must be a MusicalGrid")
        if type(self.section_start_tick) is not int or self.section_start_tick < 0:
            raise ValueError("section_start_tick must be a non-negative integer")
        if type(self.section_bars) is not int or self.section_bars <= 0:
            raise ValueError("section_bars must be a positive integer")
        if type(self.version) is not int or self.version != 1:
            raise ValueError("unsupported Note Plan version")
        if not isinstance(self.events, tuple) or any(
            not isinstance(event, NoteEvent) for event in self.events
        ):
            raise TypeError("events must be a tuple of NoteEvent values")
        end_tick = self.section_start_tick + self.section_bars * self.grid.ticks_per_bar
        for event in self.events:
            if event.start_tick < self.section_start_tick or event.start_tick + event.duration > end_tick:
                raise ValueError("note event must fit within the planned section")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "target_id": self.target_id,
            "grid": {
                "ppq": self.grid.ppq,
                "beats_per_bar": self.grid.beats_per_bar,
                "beat_unit": self.grid.beat_unit,
            },
            "section_start_tick": self.section_start_tick,
            "section_bars": self.section_bars,
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NotePlan":
        if not isinstance(value, dict):
            raise TypeError("Note Plan must be an object")
        expected = {
            "version", "target_id", "grid", "section_start_tick", "section_bars", "events"
        }
        if set(value) != expected:
            raise ValueError("Note Plan fields do not match version 1")
        grid_value = value["grid"]
        if not isinstance(grid_value, dict) or set(grid_value) != {
            "ppq", "beats_per_bar", "beat_unit"
        }:
            raise ValueError("grid fields do not match the Note Plan schema")
        if not isinstance(value["events"], list):
            raise TypeError("events must be an array")
        events = []
        for item in value["events"]:
            if not isinstance(item, dict) or set(item) != {
                "start_tick", "duration", "pitch", "velocity"
            }:
                raise ValueError("event fields do not match the Note Plan schema")
            events.append(NoteEvent(**item))
        return cls(
            target_id=value["target_id"],
            grid=MusicalGrid(**grid_value),
            section_start_tick=value["section_start_tick"],
            section_bars=value["section_bars"],
            events=tuple(events),
            version=value["version"],
        )
