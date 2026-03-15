"""Abstract base class for Speech-to-Text providers.

All STT implementations must inherit from :class:`STTProvider` and
implement the :meth:`transcribe` method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TranscriptionResult:
    """Result of a speech-to-text transcription.

    Attributes:
        text: The transcribed text.
        confidence: Confidence score between 0.0 and 1.0.
        language: Detected language code (e.g. ``"en"``).
        duration: Duration of the transcribed audio in seconds.
    """

    text: str
    confidence: float
    language: str = "en"
    duration: float = 0.0


class STTProvider(ABC):
    """Abstract base class for speech-to-text providers.

    Subclasses must implement :meth:`transcribe` and may optionally
    override :meth:`start` and :meth:`stop` for resource management.
    """

    @abstractmethod
    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe audio data to text.

        Args:
            audio: Audio data as a float32 numpy array (mono, 16kHz).
            sample_rate: Sample rate of the audio data.

        Returns:
            A :class:`TranscriptionResult` with the transcribed text.
        """

    async def start(self) -> None:
        """Initialise the STT provider (e.g. load models).

        Override in subclasses if initialisation is needed.
        """

    async def stop(self) -> None:
        """Clean up the STT provider resources.

        Override in subclasses if cleanup is needed.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this STT provider."""
