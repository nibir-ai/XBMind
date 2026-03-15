"""Abstract base class for Text-to-Speech providers.

All TTS implementations must inherit from :class:`TTSProvider` and
implement the :meth:`synthesize` method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base class for text-to-speech providers.

    Subclasses must implement :meth:`synthesize`.  Override :meth:`start`
    and :meth:`stop` for resource management.
    """

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech from text.

        Args:
            text: The text to convert to speech.

        Returns:
            WAV audio data as bytes.
        """

    async def start(self) -> None:
        """Initialise the TTS provider.

        Override in subclasses if initialisation is needed.
        """

    async def stop(self) -> None:
        """Clean up the TTS provider resources.

        Override in subclasses if cleanup is needed.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this TTS provider."""

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output audio sample rate in Hz."""
