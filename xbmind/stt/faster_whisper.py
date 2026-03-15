"""faster-whisper STT provider.

Uses the CTranslate2-accelerated ``faster-whisper`` library for
offline speech-to-text transcription.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import numpy as np

from xbmind.stt.base import STTProvider, TranscriptionResult
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from faster_whisper import WhisperModel as _WhisperModel

    from xbmind.config import FasterWhisperConfig

log = get_logger(__name__)


class FasterWhisperSTT(STTProvider):
    """Offline STT using faster-whisper (CTranslate2).

    Loads the model once on :meth:`start` and runs inference in a
    thread pool to avoid blocking the event loop.

    Example::

        stt = FasterWhisperSTT(config)
        await stt.start()
        result = await stt.transcribe(audio_array)
        print(result.text)
    """

    def __init__(self, config: FasterWhisperConfig) -> None:
        """Initialise the faster-whisper provider.

        Args:
            config: faster-whisper configuration section.
        """
        self._config = config
        self._model: _WhisperModel | None = None

    @property
    def name(self) -> str:
        """Human-readable name of this STT provider."""
        return f"faster-whisper ({self._config.model_size})"

    async def start(self) -> None:
        """Load the Whisper model in a thread executor."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_model)
        log.info(
            "stt.faster_whisper.loaded",
            model=self._config.model_size,
            device=self._config.device,
            compute_type=self._config.compute_type,
        )

    async def stop(self) -> None:
        """Release model resources."""
        self._model = None
        log.info("stt.faster_whisper.stopped")

    async def transcribe(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> TranscriptionResult:
        """Transcribe audio using faster-whisper.

        Args:
            audio: Float32 numpy array of audio samples (mono).
            sample_rate: Sample rate of the input audio.

        Returns:
            A :class:`TranscriptionResult` with the transcribed text.

        Raises:
            RuntimeError: If the model has not been loaded.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded — call start() first")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._transcribe_sync, audio, sample_rate
        )
        return result

    def _load_model(self) -> None:
        """Load the Whisper model (blocking)."""
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self._config.model_size,
            device=self._config.device,
            compute_type=self._config.compute_type,
        )

    def _transcribe_sync(
        self, audio: np.ndarray, sample_rate: int
    ) -> TranscriptionResult:
        """Run transcription synchronously.

        Args:
            audio: Float32 audio array.
            sample_rate: Sample rate.

        Returns:
            Transcription result.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded")

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        segments, info = self._model.transcribe(
            audio,
            beam_size=self._config.beam_size,
            language=self._config.language,
            vad_filter=True,
        )

        # Collect all segments
        texts: list[str] = []
        total_prob = 0.0
        segment_count = 0

        for segment in segments:
            texts.append(segment.text.strip())
            total_prob += segment.avg_log_prob
            segment_count += 1

        full_text = " ".join(texts).strip()
        duration = len(audio) / sample_rate

        # Convert avg log prob to a 0-1 confidence approximation
        avg_log_prob = total_prob / segment_count if segment_count > 0 else -1.0
        confidence = max(0.0, min(1.0, 1.0 + avg_log_prob))

        detected_lang = info.language if info.language else "en"

        log.info(
            "stt.transcribed",
            text=full_text[:80],
            confidence=round(confidence, 3),
            language=detected_lang,
            duration=round(duration, 2),
        )

        return TranscriptionResult(
            text=full_text,
            confidence=confidence,
            language=detected_lang,
            duration=duration,
        )
