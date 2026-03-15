"""Google Cloud Speech-to-Text provider.

Optional cloud-based STT using the Google Cloud Speech API.
Requires ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable.
"""

from __future__ import annotations

import asyncio
import io
import wave
from typing import TYPE_CHECKING

import numpy as np

from xbmind.stt.base import STTProvider, TranscriptionResult
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import GoogleCloudSTTConfig

log = get_logger(__name__)


class GoogleCloudSTT(STTProvider):
    """Google Cloud Speech-to-Text provider.

    Sends audio to Google's cloud API for transcription.  This is an
    optional provider for higher accuracy when an internet connection
    is available.

    Example::

        stt = GoogleCloudSTT(config)
        await stt.start()
        result = await stt.transcribe(audio_array)
    """

    def __init__(self, config: GoogleCloudSTTConfig) -> None:
        """Initialise the Google Cloud STT provider.

        Args:
            config: Google Cloud STT configuration section.
        """
        self._config = config
        self._client: object | None = None

    @property
    def name(self) -> str:
        """Human-readable name of this STT provider."""
        return "Google Cloud STT"

    async def start(self) -> None:
        """Initialise the Google Cloud Speech client."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_client)
        log.info("stt.google_cloud.started")

    async def stop(self) -> None:
        """Clean up the client."""
        self._client = None
        log.info("stt.google_cloud.stopped")

    async def transcribe(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> TranscriptionResult:
        """Transcribe audio using Google Cloud Speech.

        Args:
            audio: Float32 numpy array of audio samples.
            sample_rate: Sample rate of the audio.

        Returns:
            A :class:`TranscriptionResult` with the transcribed text.

        Raises:
            RuntimeError: If the client has not been initialised.
        """
        if self._client is None:
            raise RuntimeError("Client not initialised — call start() first")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._transcribe_sync, audio, sample_rate
        )

    def _init_client(self) -> None:
        """Initialise the speech client (blocking)."""
        from google.cloud import speech  # type: ignore[import-untyped]

        self._client = speech.SpeechClient()

    def _transcribe_sync(
        self, audio: np.ndarray, sample_rate: int
    ) -> TranscriptionResult:
        """Run Google Cloud transcription synchronously.

        Args:
            audio: Float32 audio array.
            sample_rate: Sample rate.

        Returns:
            Transcription result.
        """
        from google.cloud import speech  # type: ignore[import-untyped]

        # Convert to int16 WAV bytes
        audio_int16 = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        wav_bytes = buf.getvalue()

        audio_content = speech.RecognitionAudio(content=wav_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            language_code=self._config.language_code,
            model=self._config.model,
            enable_automatic_punctuation=True,
        )

        response = self._client.recognize(config=config, audio=audio_content)  # type: ignore[union-attr]

        texts: list[str] = []
        total_confidence = 0.0
        count = 0

        for result in response.results:
            if result.alternatives:
                best = result.alternatives[0]
                texts.append(best.transcript)
                total_confidence += best.confidence
                count += 1

        full_text = " ".join(texts).strip()
        confidence = total_confidence / count if count > 0 else 0.0
        duration = len(audio) / sample_rate

        log.info(
            "stt.google_cloud.transcribed",
            text=full_text[:80],
            confidence=round(confidence, 3),
        )

        return TranscriptionResult(
            text=full_text,
            confidence=confidence,
            language=self._config.language_code.split("-")[0],
            duration=duration,
        )
