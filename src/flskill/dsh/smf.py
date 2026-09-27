from __future__ import annotations

"""Small Standard MIDI File reader used for agent-side inspection.

Adapted from whale-music-pipeline/scripts/mix/midi-windows.py (MIT).
The implementation stays intentionally dependency-free and exposes structured
results instead of printing them, so an AI agent can inspect MIDI activity
before deciding which section to measure or edit.
"""

from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass(frozen=True)
class MidiNoteOn:
    tick: int
    pitch: int
    velocity: int


@dataclass(frozen=True)
class MidiTrackSummary:
    index: int
    name: str
    notes: tuple[MidiNoteOn, ...]


@dataclass(frozen=True)
class MidiFileSummary:
    format: int
    division: int
    tracks: tuple[MidiTrackSummary, ...]


def _read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        if offset >= len(data):
            raise ValueError("truncated variable-length quantity")
        current = data[offset]
        offset += 1
        value = (value << 7) | (current & 0x7F)
        if not current & 0x80:
            return value, offset


def parse_smf(path: str | Path) -> MidiFileSummary:
    data = Path(path).read_bytes()
    if data[:4] != b"MThd" or len(data) < 14:
        raise ValueError("not a Standard MIDI File")
    header_length = struct.unpack(">I", data[4:8])[0]
    if header_length < 6:
        raise ValueError("invalid MIDI header length")
    fmt, track_count, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise ValueError("SMPTE time division is not supported")

    cursor = 8 + header_length
    tracks: list[MidiTrackSummary] = []
    for track_index in range(track_count):
        if data[cursor:cursor + 4] != b"MTrk":
            raise ValueError(f"missing MTrk chunk at track {track_index}")
        length = struct.unpack(">I", data[cursor + 4:cursor + 8])[0]
        body = data[cursor + 8:cursor + 8 + length]
        cursor += 8 + length
        offset = 0
        tick = 0
        running_status: int | None = None
        name: str | None = None
        notes: list[MidiNoteOn] = []
        while offset < len(body):
            delta, offset = _read_vlq(body, offset)
            tick += delta
            if offset >= len(body):
                raise ValueError("truncated MIDI event")
            status = body[offset]
            if status == 0xFF:
                offset += 1
                if offset >= len(body):
                    raise ValueError("truncated MIDI meta event")
                meta_type = body[offset]
                offset += 1
                size, offset = _read_vlq(body, offset)
                payload = body[offset:offset + size]
                if len(payload) != size:
                    raise ValueError("truncated MIDI meta payload")
                offset += size
                if meta_type == 0x03:
                    name = payload.decode("utf-8", errors="replace")
                elif meta_type == 0x2F:
                    break
                continue
            if status in (0xF0, 0xF7):
                offset += 1
                size, offset = _read_vlq(body, offset)
                offset += size
                continue
            if status & 0x80:
                running_status = status
                offset += 1
            elif running_status is None:
                raise ValueError("running status used before a status byte")
            status = running_status
            assert status is not None
            kind = status & 0xF0
            data_length = 1 if kind in (0xC0, 0xD0) else 2
            payload = body[offset:offset + data_length]
            if len(payload) != data_length:
                raise ValueError("truncated MIDI channel event")
            offset += data_length
            if kind == 0x90 and payload[1] > 0:
                notes.append(MidiNoteOn(tick=tick, pitch=payload[0], velocity=payload[1]))
        tracks.append(MidiTrackSummary(track_index, name or "(unnamed)", tuple(notes)))
    return MidiFileSummary(fmt, division, tuple(tracks))


def recommend_dense_window(
    track: MidiTrackSummary,
    *,
    division: int,
    beats_per_bar: int,
    window_bars: int = 3,
) -> tuple[int, int] | None:
    """Return a 1-based bar window with the highest note-on density."""
    if not track.notes:
        return None
    if division <= 0 or beats_per_bar <= 0 or window_bars <= 0:
        raise ValueError("division, beats_per_bar and window_bars must be positive")
    ticks_per_bar = division * beats_per_bar
    bars = [note.tick / ticks_per_bar for note in track.notes]
    first = int(min(bars))
    last = int(max(bars))
    best_bar = first
    best_count = -1
    for start in range(first, max(first + 1, last + 1)):
        count = sum(1 for value in bars if start <= value < start + window_bars)
        if count > best_count:
            best_count = count
            best_bar = start
    return best_bar + 1, best_bar + window_bars
