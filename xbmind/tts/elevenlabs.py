"""ElevenLabs TTS provider.

Optional cloud-based TTS using the ElevenLabs API.
Requires the ``ELEVENLABS_API_KEY`` environment variable.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx

from xbmind.tts.base import TTSProvider
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import ElevenLabsConfig

log = get_logger(__name__)

_ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs cloud TTS provider.

    Uses the ElevenLabs REST API for high-quality voice synthesis.

    Example::

        tts = ElevenLabsTTS(config)
        await tts.start()
        audio = await tts.synthesize("Hello!")
    """

    def __init__(self, config: ElevenLabsConfig) -> None:
        """Initialise the ElevenLabs provider.

        Args:
            config: ElevenLabs configuration section.
        """
        self._config = config
        self._api_key: str = ""
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        """Human-readable name of this TTS provider."""
        return "ElevenLabs"

    @property
    def sample_rate(self) -> int:
        """Output audio sample rate (ElevenLabs default)."""
        return 44100

    async def start(self) -> None:
        """Create the HTTP client and validate the API key."""
        self._api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not self._api_key:
            log.warning("tts.elevenlabs.no_api_key")

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        log.info("tts.elevenlabs.started", voice_id=self._config.voice_id)

    async def stop(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("tts.elevenlabs.stopped")

    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech using the ElevenLabs API.

        Args:
            text: The text to convert to speech.

        Returns:
            Audio data as bytes (MP3 format from ElevenLabs, or empty).

        Raises:
            RuntimeError: If the client is not started or API call fails.
        """
        if not text.strip():
            return b""

        if self._client is None:
            raise RuntimeError("Client not started — call start() first")

        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY environment variable not set")

        url = f"{_ELEVENLABS_API_URL}/{self._config.voice_id}"

        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload = {
            "text": text,
            "model_id": self._config.model_id,
            "voice_settings": {
                "stability": self._config.stability,
                "similarity_boost": self._config.similarity_boost,
            },
        }

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            audio_data = response.content

            log.info(
                "tts.elevenlabs.synthesized",
                text_length=len(text),
                audio_bytes=len(audio_data),
            )

            return audio_data

        except httpx.HTTPStatusError as exc:
            log.error(
                "tts.elevenlabs.api_error",
                status_code=exc.response.status_code,
                detail=exc.response.text[:200],
            )
            raise RuntimeError(
                f"ElevenLabs API error: {exc.response.status_code}"
            ) from exc
        except httpx.TimeoutException as exc:
            log.error("tts.elevenlabs.timeout")
            raise RuntimeError("ElevenLabs API timed out") from exc
