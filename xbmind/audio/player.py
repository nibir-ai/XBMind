"""Async audio player with interrupt queue.

Plays WAV audio data through the system output (or a named PipeWire sink)
with support for interrupting the current playback when new TTS output
arrives.
"""

from __future__ import annotations

import asyncio
import io
import wave

import numpy as np
import sounddevice as sd

from xbmind.utils.logger import get_logger

log = get_logger(__name__)


class AudioPlayer:
    """Asynchronous audio player with interrupt support.

    Queues audio playback requests and plays them sequentially.  New
    requests can interrupt the current playback (e.g. for a new TTS
    response that supersedes the previous one).

    Example::

        player = AudioPlayer(sample_rate=22050)
        await player.start()
        await player.play(audio_bytes)
        await player.stop()
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        output_device: int | None = None,
    ) -> None:
        """Initialise the audio player.

        Args:
            sample_rate: Default sample rate for raw audio data.
            output_device: Output device index (``None`` for default).
        """
        self._sample_rate = sample_rate
        self._output_device = output_device
        self._queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue()
        self._running: bool = False
        self._task: asyncio.Task[None] | None = None
        self._current_playback: asyncio.Event = asyncio.Event()
        self._interrupt: bool = False

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently being played."""
        return not self._current_playback.is_set() and self._running

    async def start(self) -> None:
        """Start the playback worker."""
        self._running = True
        self._current_playback.set()
        self._task = asyncio.create_task(self._playback_loop(), name="audio_player")
        log.info("audio_player.started")

    async def stop(self) -> None:
        """Stop the player and cancel any current playback."""
        self._running = False
        self._interrupt = True
        await self._queue.put(None)
        if self._task:
            await self._task
            self._task = None
        log.info("audio_player.stopped")

    async def play(self, audio_data: bytes | np.ndarray, sample_rate: int | None = None) -> None:
        """Queue audio data for playback.

        Args:
            audio_data: Raw PCM bytes, WAV bytes, or a float32 numpy array.
            sample_rate: Sample rate of the audio. If ``None``, uses default.
        """
        if isinstance(audio_data, bytes):
            array, sr = self._decode_audio(audio_data)
            if sr:
                self._sample_rate = sr
        elif isinstance(audio_data, np.ndarray):
            array = audio_data.astype(np.float32) if audio_data.dtype != np.float32 else audio_data
        else:
            log.warning("audio_player.invalid_data_type", type=type(audio_data).__name__)
            return

        if sample_rate:
            self._sample_rate = sample_rate

        await self._queue.put(array)

    async def interrupt(self) -> None:
        """Interrupt the current playback immediately."""
        self._interrupt = True

        # Drain the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, sd.stop)
        log.info("audio_player.interrupted")

    def _decode_audio(self, audio_bytes: bytes) -> tuple[np.ndarray, int | None]:
        """Decode WAV or raw PCM bytes to a numpy array.

        Args:
            audio_bytes: Audio data as bytes.

        Returns:
            Tuple of (float32 numpy array, sample rate or None).
        """
        # Try WAV first
        try:
            buf = io.BytesIO(audio_bytes)
            with wave.open(buf, "rb") as wf:
                sr = wf.getframerate()
                n_frames = wf.getnframes()
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                raw = wf.readframes(n_frames)

            if sample_width == 2:
                data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

            if n_channels == 2:
                data = data.reshape(-1, 2).mean(axis=1)

            return data, sr
        except (wave.Error, EOFError):
            pass

        # Fall back to raw int16 PCM
        data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return data, None

    async def _playback_loop(self) -> None:
        """Worker loop that dequeues and plays audio."""
        while self._running:
            audio = await self._queue.get()
            if audio is None:
                break

            self._interrupt = False
            self._current_playback.clear()

            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, self._play_sync, audio, self._sample_rate)
            except Exception:
                log.exception("audio_player.playback_error")
            finally:
                self._current_playback.set()
                self._queue.task_done()

    def _play_sync(self, audio: np.ndarray, sample_rate: int) -> None:
        """Synchronous playback using sounddevice.

        Args:
            audio: Float32 numpy array of audio samples.
            sample_rate: Playback sample rate.
        """
        if self._interrupt:
            return

        try:
            sd.play(audio, samplerate=sample_rate, device=self._output_device)
            sd.wait()
        except sd.PortAudioError:
            log.exception("audio_player.portaudio_error")

    async def wait_until_done(self) -> None:
        """Wait until the current playback finishes."""
        await self._current_playback.wait()
