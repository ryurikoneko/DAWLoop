from __future__ import annotations

"""可选的 Windows WASAPI 环回录音，基于 MIT 许可来源改编。"""

from dataclasses import dataclass
from pathlib import Path
import wave


@dataclass(frozen=True)
class LoopbackDevice:
    index: int
    name: str
    sample_rate: int
    channels: int


def list_loopback_devices() -> tuple[LoopbackDevice, ...]:
    try:
        import pyaudiowpatch as pyaudio
    except ImportError as error:
        raise ImportError('install "dawloop[production-loopback]" for Windows WASAPI loopback') from error
    pa = pyaudio.PyAudio()
    try:
        out = []
        for index in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(index)
            if info.get("isLoopbackDevice"):
                out.append(LoopbackDevice(
                    index=int(index),
                    name=str(info["name"]),
                    sample_rate=int(info["defaultSampleRate"]),
                    channels=int(info["maxInputChannels"]),
                ))
        return tuple(out)
    finally:
        pa.terminate()


def record_loopback(path: str | Path, seconds: float, device_index: int | None = None) -> LoopbackDevice:
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    try:
        import numpy as np
        import pyaudiowpatch as pyaudio
    except ImportError as error:
        raise ImportError('install "dawloop[production-loopback]" for Windows WASAPI loopback') from error
    pa = pyaudio.PyAudio()
    try:
        info = (
            pa.get_default_wasapi_loopback()
            if device_index is None
            else pa.get_device_info_by_index(int(device_index))
        )
        sample_rate = int(info["defaultSampleRate"])
        channels = int(info["maxInputChannels"])
        if channels <= 0:
            raise RuntimeError("selected loopback device has no input channels")
        block = 1024
        stream = pa.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=info["index"],
            frames_per_buffer=block,
        )
        try:
            needed = int(sample_rate * seconds)
            buffers = []
            frames = 0
            while frames < needed:
                raw = stream.read(block, exception_on_overflow=False)
                values = np.frombuffer(raw, dtype=np.float32)
                buffers.append(values)
                frames += len(values) // channels
        finally:
            stream.stop_stream()
            stream.close()
        audio = np.concatenate(buffers)[:needed * channels].reshape(-1, channels)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(channels)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
        return LoopbackDevice(int(info["index"]), str(info["name"]), sample_rate, channels)
    finally:
        pa.terminate()
