"""Piper TTS provider.

Offline text-to-speech using the Piper binary via subprocess pipe.
Streams text to Piper's stdin and reads WAV audio from stdout.
"""

from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from xbmind.tts.base import TTSProvider
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import PiperConfig

log = get_logger(__name__)


class PiperTTS(TTSProvider):
    """Offline TTS using Piper via subprocess pipe.

    Piper is a fast, local neural TTS engine.  This provider spawns
    it as a subprocess and communicates via stdin/stdout pipes.

    Example::

        tts = PiperTTS(config)
        await tts.start()
        audio = await tts.synthesize("Hello, world!")
        await tts.stop()
    """

    def __init__(self, config: PiperConfig) -> None:
        """Initialise the Piper TTS provider.

        Args:
            config: Piper TTS configuration section.
        """
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Human-readable name of this TTS provider."""
        return "Piper TTS"

    @property
    def sample_rate(self) -> int:
        """Output audio sample rate."""
        return self._config.sample_rate

    async def start(self) -> None:
        """Verify that the Piper executable and model exist."""
        model_path = Path(self._config.model_path)
        if not model_path.is_file():
            log.warning(
                "tts.piper.model_not_found",
                path=str(model_path),
                hint="Run scripts/download_models.sh to download the Piper model",
            )

        log.info(
            "tts.piper.started",
            executable=self._config.executable,
            model=self._config.model_path,
        )

    async def stop(self) -> None:
        """Terminate any running Piper process."""
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (TimeoutError, ProcessLookupError):
                if self._process:
                    self._process.kill()
            self._process = None
        log.info("tts.piper.stopped")

    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech from text using Piper.

        Spawns a new Piper process for each synthesis request to avoid
        state issues.  Uses a lock to prevent concurrent invocations.

        Args:
            text: The text to convert to speech.

        Returns:
            WAV audio data as bytes.

        Raises:
            RuntimeError: If Piper fails or is not available.
        """
        if not text.strip():
            return b""

        async with self._lock:
            return await self._run_piper(text)

    async def _run_piper(self, text: str) -> bytes:
        """Run Piper as a subprocess and collect the output.

        Args:
            text: Text to synthesize.

        Returns:
            WAV audio bytes.
        """
        cmd = [
            self._config.executable,
            "--model",
            self._config.model_path,
            "--output-raw",
            "--length-scale",
            str(self._config.length_scale),
            "--sentence-silence",
            str(self._config.sentence_silence),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Send text and close stdin to signal end of input
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=text.encode("utf-8")),
                timeout=30.0,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace").strip()
                log.error(
                    "tts.piper.process_error",
                    returncode=process.returncode,
                    stderr=error_msg[:200],
                )
                raise RuntimeError(f"Piper failed: {error_msg[:200]}")

            if not stdout:
                log.warning("tts.piper.empty_output")
                return b""

            # Convert raw PCM to WAV
            wav_bytes = self._raw_to_wav(stdout)

            log.info(
                "tts.piper.synthesized",
                text_length=len(text),
                audio_bytes=len(wav_bytes),
            )

            return wav_bytes

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Piper executable not found: '{self._config.executable}'. "
                "Install Piper or update the config path."
            ) from exc
        except TimeoutError as exc:
            log.error("tts.piper.timeout", text_length=len(text))
            raise RuntimeError("Piper TTS timed out") from exc

    def _raw_to_wav(self, raw_pcm: bytes) -> bytes:
        """Convert raw PCM audio to WAV format.

        Args:
            raw_pcm: Raw 16-bit mono PCM audio data.

        Returns:
            WAV file bytes.
        """
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self._config.sample_rate)
            wf.writeframes(raw_pcm)
        return buf.getvalue()
