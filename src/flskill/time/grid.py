from dataclasses import dataclass


def _positive_int(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class MusicalGrid:
    """PPQ 与拍号定义的整数 tick 网格。"""

    ppq: int
    beats_per_bar: int = 4
    beat_unit: int = 4

    def __post_init__(self) -> None:
        _positive_int("ppq", self.ppq)
        _positive_int("beats_per_bar", self.beats_per_bar)
        _positive_int("beat_unit", self.beat_unit)
        if self.beat_unit not in (1, 2, 4, 8, 16):
            raise ValueError("beat_unit must be a standard power-of-two denominator")
        ticks_per_beat_numerator = self.ppq * 4
        if ticks_per_beat_numerator % self.beat_unit:
            raise ValueError("ppq must resolve beat_unit to an integer tick count")

    @property
    def ticks_per_beat(self) -> int:
        return self.ppq * 4 // self.beat_unit

    @property
    def ticks_per_bar(self) -> int:
        return self.ticks_per_beat * self.beats_per_bar


@dataclass(frozen=True)
class MusicalPosition:
    """一基小节和拍；tick 是拍内从零开始的偏移。"""

    bar: int
    beat: int
    tick: int = 0

    def __post_init__(self) -> None:
        _positive_int("bar", self.bar)
        _positive_int("beat", self.beat)
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError("tick must be a non-negative integer")


def resolve_absolute_tick(
    position: MusicalPosition,
    grid: MusicalGrid,
    section_start_tick: int = 0,
) -> int:
    if not isinstance(position, MusicalPosition) or not isinstance(grid, MusicalGrid):
        raise TypeError("position and grid must use FLSkill time types")
    if type(section_start_tick) is not int or section_start_tick < 0:
        raise ValueError("section_start_tick must be a non-negative integer")
    if position.beat > grid.beats_per_bar:
        raise ValueError("beat is outside the musical grid")
    if position.tick >= grid.ticks_per_beat:
        raise ValueError("tick is outside the beat")
    return (
        section_start_tick
        + (position.bar - 1) * grid.ticks_per_bar
        + (position.beat - 1) * grid.ticks_per_beat
        + position.tick
    )
