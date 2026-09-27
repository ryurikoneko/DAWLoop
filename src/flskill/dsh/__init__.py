"""Reusable music-pipeline utilities adapted from the DSH whale-music-pipeline project.

The original project code is MIT licensed. See THIRD_PARTY_NOTICES.md.
"""

from .mix import FaderCalibration, LevelMeasurement, active_rms, plan_fader_db
from .orchestration import (
    InstrumentRange,
    choose_instrument_for_phrase,
    find_register_gaps,
    source_note_coverage,
)
from .smf import MidiTrackSummary, parse_smf, recommend_dense_window

__all__ = [
    "FaderCalibration",
    "InstrumentRange",
    "LevelMeasurement",
    "MidiTrackSummary",
    "active_rms",
    "choose_instrument_for_phrase",
    "find_register_gaps",
    "parse_smf",
    "plan_fader_db",
    "recommend_dense_window",
    "source_note_coverage",
]
