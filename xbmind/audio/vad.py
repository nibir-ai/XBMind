"""Voice Activity Detection using Silero VAD.

Detects speech start/end events with a 500 ms pre-roll circular buffer
so that the beginning of an utterance is never lost.
"""

from __future__ import annotations

import asyncio
import collections
from typing import TYPE_CHECKING

import numpy as np
import torch

from xbmind.utils.events import Event, EventBus, EventType
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import AudioConfig, VADConfig

log = get_logger(__name__)


class VoiceActivityDetector:
    """Silero VAD wrapper with circular pre-roll buffer.

    Listens to ``AUDIO_CHUNK`` events from the event bus and publishes
    ``VAD_SPEECH_START`` / ``VAD_SPEECH_END`` with the accumulated speech
    audio.

    Example::

        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        await vad.start()
    """

    def __init__(
        self,
        config: VADConfig,
        audio_config: AudioConfig,
        event_bus: EventBus,
    ) -> None:
        """Initialise the VAD.

        Args:
            config: VAD configuration section.
            audio_config: Audio configuration for sample rate info.
            event_bus: Event bus for pub/sub communication.
        """
        self._config = config
        self._sample_rate = audio_config.sample_rate
        self._event_bus = event_bus

        # Silero VAD model
        self._model: torch.jit.ScriptModule | None = None

        # Pre-roll circular buffer (stores audio *before* speech starts)
        pre_roll_samples = int(self._sample_rate * config.pre_roll_duration)
        self._pre_roll_size = max(1, pre_roll_samples // audio_config.block_size)
        self._pre_roll: collections.deque[np.ndarray] = collections.deque(
            maxlen=self._pre_roll_size
        )

        # Speech state
        self._is_speaking: bool = False
        self._speech_chunks: list[np.ndarray] = []
        self._silence_counter: float = 0.0
        self._speech_duration: float = 0.0
        self._max_samples = int(self._sample_rate * config.max_recording_duration)
        self._total_samples: int = 0

        self._running: bool = False

    async def start(self) -> None:
        """Load the Silero VAD model and subscribe to audio events."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_model)

        self._event_bus.subscribe(EventType.AUDIO_CHUNK, self._on_audio_chunk)
        self._running = True
        log.info("vad.started", threshold=self._config.threshold)

    async def stop(self) -> None:
        """Stop VAD processing."""
        self._running = False
        log.info("vad.stopped")

    def _load_model(self) -> None:
        """Load the Silero VAD model from torch hub."""
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self._model = model
        log.info("vad.model_loaded")

    def _get_speech_probability(self, audio_chunk: np.ndarray) -> float:
        """Run VAD inference on an audio chunk.

        Args:
            audio_chunk: Audio data as a float32 numpy array.

        Returns:
            Speech probability between 0.0 and 1.0.
        """
        if self._model is None:
            return 0.0

        tensor = torch.from_numpy(audio_chunk).float()
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)

        with torch.no_grad():
            prob = self._model(tensor, self._sample_rate).item()

        return float(prob)

    async def _on_audio_chunk(self, event: Event) -> None:
        """Handle incoming audio chunks for VAD processing.

        Args:
            event: An ``AUDIO_CHUNK`` event with numpy audio data.
        """
        if not self._running or self._model is None:
            return

        chunk: np.ndarray = event.data
        chunk_duration = len(chunk) / self._sample_rate

        # Run VAD in thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        prob = await loop.run_in_executor(None, self._get_speech_probability, chunk)

        is_speech = prob >= self._config.threshold

        if is_speech and not self._is_speaking:
            # Speech detected — start recording, include pre-roll
            self._is_speaking = True
            self._speech_chunks = list(self._pre_roll)
            self._speech_chunks.append(chunk)
            self._silence_counter = 0.0
            self._speech_duration = chunk_duration
            self._total_samples = sum(len(c) for c in self._speech_chunks)

            await self._event_bus.publish(
                Event(EventType.VAD_SPEECH_START, source="vad")
            )
            log.info("vad.speech_start", probability=round(prob, 3))

        elif is_speech and self._is_speaking:
            # Continued speech
            self._speech_chunks.append(chunk)
            self._silence_counter = 0.0
            self._speech_duration += chunk_duration
            self._total_samples += len(chunk)

        elif not is_speech and self._is_speaking:
            # Silence during speech — accumulate
            self._speech_chunks.append(chunk)
            self._silence_counter += chunk_duration
            self._total_samples += len(chunk)

            # Check end conditions
            if self._silence_counter >= self._config.silence_duration:
                await self._end_speech("silence_timeout")
            elif self._total_samples >= self._max_samples:
                await self._end_speech("max_duration")

        else:
            # No speech, no active recording — just buffer for pre-roll
            self._pre_roll.append(chunk)

    async def _end_speech(self, reason: str) -> None:
        """Finalise a speech segment and publish it.

        Args:
            reason: Why speech ended (``"silence_timeout"`` or ``"max_duration"``).
        """
        if not self._speech_chunks:
            self._is_speaking = False
            return

        # Check minimum speech duration
        if self._speech_duration < self._config.min_speech_duration:
            log.debug("vad.speech_too_short", duration=round(self._speech_duration, 3))
            self._is_speaking = False
            self._speech_chunks.clear()
            return

        # Concatenate all chunks into one array
        audio = np.concatenate(self._speech_chunks)

        await self._event_bus.publish(
            Event(
                EventType.VAD_SPEECH_END,
                data=audio,
                source="vad",
            )
        )

        log.info(
            "vad.speech_end",
            reason=reason,
            duration=round(self._speech_duration, 2),
            samples=len(audio),
        )

        # Reset state
        self._is_speaking = False
        self._speech_chunks.clear()
        self._silence_counter = 0.0
        self._speech_duration = 0.0
        self._total_samples = 0
        self._pre_roll.clear()
