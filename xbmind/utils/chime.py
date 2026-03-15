"""Chime / notification sound playback.

Plays a short WAV chime when the wake word is detected.  Falls back to
generating a simple sine-wave beep if no WAV file is provided.
"""

from __future__ import annotations

import asyncio
import struct
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from xbmind.utils.logger import get_logger

log = get_logger(__name__)

# Default chime parameters (sine-wave beep)
_DEFAULT_FREQ_HZ = 880
_DEFAULT_DURATION_S = 0.15
_DEFAULT_SAMPLE_RATE = 22050
_DEFAULT_AMPLITUDE = 0.4


def _generate_beep(
    freq: int = _DEFAULT_FREQ_HZ,
    duration: float = _DEFAULT_DURATION_S,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
    amplitude: float = _DEFAULT_AMPLITUDE,
) -> np.ndarray:
    """Generate a simple sine-wave beep as a numpy array.

    Args:
        freq: Frequency in Hz.
        duration: Duration in seconds.
        sample_rate: Output sample rate.
        amplitude: Peak amplitude (0.0–1.0).

    Returns:
        A 1-D float32 numpy array of audio samples.
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False, dtype=np.float32)
    wave_data = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)

    # Apply a short fade-in/fade-out to avoid clicks
    fade_samples = min(int(sample_rate * 0.01), len(wave_data) // 4)
    if fade_samples > 0:
        fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
        fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
        wave_data[:fade_samples] *= fade_in
        wave_data[-fade_samples:] *= fade_out

    return wave_data


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file into a numpy array.

    Args:
        path: Path to the WAV file.

    Returns:
        Tuple of (audio data as float32 array, sample rate).

    Raises:
        FileNotFoundError: If the WAV file does not exist.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Chime WAV file not found: {path}")

    with wave.open(str(path), "rb") as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_width == 2:
        fmt = f"<{n_frames * n_channels}h"
        samples = struct.unpack(fmt, raw)
        data = np.array(samples, dtype=np.float32) / 32768.0
    elif sample_width == 4:
        fmt = f"<{n_frames * n_channels}i"
        samples = struct.unpack(fmt, raw)
        data = np.array(samples, dtype=np.float32) / 2147483648.0
    else:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    # Mix to mono if stereo
    if n_channels == 2:
        data = data.reshape(-1, 2).mean(axis=1)

    return data, sample_rate


class ChimePlayer:
    """Plays chime sounds asynchronously.

    Supports loading a custom WAV file or falling back to a generated
    sine-wave beep.
    """

    def __init__(self, chime_path: str | None = None, output_device: int | None = None) -> None:
        """Initialise the chime player.

        Args:
            chime_path: Optional path to a custom WAV chime file.
            output_device: Output device index (``None`` for default).
        """
        self._output_device = output_device
        self._audio_data: np.ndarray
        self._sample_rate: int

        if chime_path:
            self._audio_data, self._sample_rate = _load_wav(Path(chime_path))
            log.info("chime.loaded_wav", path=chime_path)
        else:
            self._audio_data = _generate_beep()
            self._sample_rate = _DEFAULT_SAMPLE_RATE
            log.info("chime.using_default_beep")

    async def play(self) -> None:
        """Play the chime sound asynchronously.

        Runs the blocking ``sounddevice.play`` call in a thread executor.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._play_sync)

    def _play_sync(self) -> None:
        """Synchronous chime playback."""
        try:
            sd.play(self._audio_data, samplerate=self._sample_rate, device=self._output_device)
            sd.wait()
        except sd.PortAudioError:
            log.exception("chime.playback_error")
