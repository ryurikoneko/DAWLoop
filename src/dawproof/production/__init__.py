"""DAWProof Production Pipeline 的可复用工具。"""

from .orchestration import (
    InstrumentRange,
    choose_instrument_for_phrase,
    find_register_gaps,
    source_note_coverage,
)
from .smf import MidiFileSummary, MidiNoteOn, MidiTrackSummary, parse_smf, recommend_dense_window

__all__ = [
    "FaderCalibration",
    "InstrumentRange",
    "LevelMeasurement",
    "MidiFileSummary",
    "MidiNoteOn",
    "MidiTrackSummary",
    "active_rms",
    "choose_instrument_for_phrase",
    "find_register_gaps",
    "parse_smf",
    "plan_fader_db",
    "recommend_dense_window",
    "source_note_coverage",
]


def __getattr__(name: str):
    if name in {"FaderCalibration", "LevelMeasurement", "active_rms", "plan_fader_db"}:
        from . import mix

        return getattr(mix, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
