from __future__ import annotations

"""Deterministic audio-level and fader-planning helpers.

Adapted from whale-music-pipeline's active-rms.py, fader-plan.py and
level-balance.py (MIT). Project-specific track names and mix targets were
removed; callers supply their own targets and calibration points.
"""

from dataclasses import dataclass
import math
from pathlib import Path
import wave

try:
    import numpy as np
except ImportError as error:  # optional dependency by design
    raise ImportError(
        "Optional dependency 'numpy' is required for DSH audio analysis. "
        'Install with: pip install "flskill[dsh]"'
    ) from error


@dataclass(frozen=True)
class LevelMeasurement:
    all_rms_dbfs: float
    active_rms_dbfs: float
    active_ratio: float
    peak_dbfs: float
    max_frame_dbfs: float


def _db(value: float) -> float:
    return 20.0 * math.log10(value) if value > 0 else float("-inf")


def _decode_pcm(path: str | Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        raw = handle.readframes(frame_count)
    if sample_width == 2:
        audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported PCM sample width: {sample_width}")
    if channels <= 0 or len(audio) % channels:
        raise ValueError("invalid PCM channel layout")
    mono = audio.reshape(-1, channels).mean(axis=1)
    return mono, sample_rate


def active_rms(
    path: str | Path,
    *,
    frame_ms: int = 100,
    floor_dbfs: float = -65.0,
) -> LevelMeasurement:
    """Measure all-frame and active-frame RMS for a PCM WAV file.

    Active-frame RMS avoids over-boosting sparse instruments. The original DSH
    implementation used 100 ms frames and a -65 dBFS floor after field tests;
    both values are exposed here instead of being hard-coded policy.
    """
    if frame_ms <= 0:
        raise ValueError("frame_ms must be positive")
    audio, sample_rate = _decode_pcm(path)
    if audio.size == 0:
        raise ValueError("audio file is empty")
    frame_size = max(int(sample_rate * frame_ms / 1000), 1)
    frame_count = len(audio) // frame_size
    if frame_count == 0:
        raise ValueError("audio is shorter than one analysis frame")
    frames = audio[:frame_count * frame_size].reshape(frame_count, frame_size)
    frame_rms = np.sqrt((frames ** 2).mean(axis=1))
    frame_dbfs = np.array([_db(float(value)) for value in frame_rms])
    active = frame_dbfs > floor_dbfs
    active_value = (
        _db(float(np.sqrt(np.mean(frame_rms[active] ** 2))))
        if active.any()
        else float("-inf")
    )
    return LevelMeasurement(
        all_rms_dbfs=_db(float(np.sqrt(np.mean(audio ** 2)))),
        active_rms_dbfs=active_value,
        active_ratio=float(active.mean()),
        peak_dbfs=_db(float(np.max(np.abs(audio)))),
        max_frame_dbfs=float(frame_dbfs.max()),
    )


@dataclass(frozen=True)
class FaderCalibration:
    """Monotonic mapping between normalized fader values and read-back dB."""

    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("at least two calibration points are required")
        by_value = sorted(self.points)
        if tuple(by_value) != self.points:
            raise ValueError("calibration points must be sorted by fader value")
        values = [value for value, _ in self.points]
        dbs = [db for _, db in self.points]
        if any(not math.isfinite(value) or not math.isfinite(db) for value, db in self.points):
            raise ValueError("calibration points must be finite")
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("fader values must be within 0..1")
        if len(set(values)) != len(values) or any(a >= b for a, b in zip(dbs, dbs[1:])):
            raise ValueError("calibration must be strictly increasing in value and dB")

    def db_for_value(self, value: float) -> float:
        values = np.array([point[0] for point in self.points], dtype=float)
        dbs = np.array([point[1] for point in self.points], dtype=float)
        return float(np.interp(value, values, dbs))

    def value_for_db(self, db: float) -> float:
        dbs = np.array([point[1] for point in self.points], dtype=float)
        values = np.array([point[0] for point in self.points], dtype=float)
        return float(np.interp(db, dbs, values))


DSH_FL_STUDIO_2025_CALIBRATION = FaderCalibration((
    (0.15, -24.9),
    (0.25, -19.0),
    (0.35, -14.6),
    (0.42, -12.0),
    (0.50, -9.2),
    (0.60, -6.0),
    (0.65, -4.4),
    (0.697, -3.0),
    (0.75, -1.4),
    (0.80, 0.0),
    (0.85, 1.4),
    (0.90, 2.8),
    (0.95, 4.2),
    (1.00, 5.6),
))


def plan_fader_db(
    *,
    measured_active_dbfs: float,
    target_active_dbfs: float,
    current_fader_value: float,
    calibration: FaderCalibration,
    max_correction_db: float = 12.0,
) -> tuple[float, float]:
    """Return (planned_fader_value, expected_readback_db).

    The returned dB is a plan derived from a calibration table, not proof of
    the resulting FL Studio state. FLSkill callers must still write, read back,
    and verify the real mixer value before returning PASS.
    """
    correction = max(
        -max_correction_db,
        min(max_correction_db, target_active_dbfs - measured_active_dbfs),
    )
    current_db = calibration.db_for_value(current_fader_value)
    target_fader_db = current_db + correction
    value = calibration.value_for_db(target_fader_db)
    return value, calibration.db_for_value(value)
