"""Wake word detection using openWakeWord.

Runs the model in a dedicated OS thread and publishes
``WAKE_WORD_DETECTED`` events when the configured wake word is heard.
Includes ANSI-coloured terminal status display.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

import numpy as np

from xbmind.utils.events import Event, EventBus, EventType
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import WakeWordConfig

log = get_logger(__name__)

# ANSI colour codes for terminal display
_RESET = "\033[0m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_DIM = "\033[2m"


class WakeWordDetector:
    """openWakeWord-based wake word detector.

    Runs inference in a dedicated OS thread (via ``asyncio.to_thread``)
    to avoid blocking the event loop.  Publishes a
    ``WAKE_WORD_DETECTED`` event and plays a chime when the wake word
    is heard.

    Example::

        detector = WakeWordDetector(config, event_bus)
        await detector.start()
        # Process audio chunks via feed_audio()
        await detector.stop()
    """

    def __init__(self, config: WakeWordConfig, event_bus: EventBus) -> None:
        """Initialise the wake word detector.

        Args:
            config: Wake word configuration section.
            event_bus: Event bus for publishing detections.
        """
        self._config = config
        self._event_bus = event_bus
        self._model: object | None = None  # openwakeword.Model
        self._running: bool = False
        self._listening: bool = True
        self._last_score: float = 0.0

    @property
    def is_listening(self) -> bool:
        """Whether the detector is actively listening for the wake word."""
        return self._running and self._listening

    def pause(self) -> None:
        """Temporarily pause wake word detection (e.g. during TTS playback)."""
        self._listening = False
        log.debug("wake_word.paused")

    def resume(self) -> None:
        """Resume wake word detection."""
        self._listening = True
        log.debug("wake_word.resumed")

    async def start(self) -> None:
        """Load the openWakeWord model and start listening.

        The model is loaded in a thread to avoid blocking startup.
        """
        await asyncio.to_thread(self._load_model)
        self._running = True
        self._event_bus.subscribe(EventType.AUDIO_CHUNK, self._on_audio_chunk)
        log.info(
            "wake_word.started",
            model=self._config.model_name,
            threshold=self._config.threshold,
        )
        self._print_status("Listening...")

    async def stop(self) -> None:
        """Stop the wake word detector."""
        self._running = False
        self._print_status("Stopped")
        log.info("wake_word.stopped")

    def _load_model(self) -> None:
        """Load the openWakeWord model (blocking, runs in thread)."""
        import openwakeword
        from openwakeword.model import Model

        openwakeword.utils.download_models()

        self._model = Model(
            wakeword_models=[self._config.model_name],
            inference_framework=self._config.inference_framework,
        )
        log.info("wake_word.model_loaded", model=self._config.model_name)

    async def _on_audio_chunk(self, event: Event) -> None:
        """Process an audio chunk for wake word detection.

        Args:
            event: An ``AUDIO_CHUNK`` event with numpy audio data.
        """
        if not self._running or not self._listening or self._model is None:
            return

        chunk: np.ndarray = event.data

        # Run inference in thread pool
        scores = await asyncio.to_thread(self._predict, chunk)

        if scores is None:
            return

        # Check each model's score
        for model_name, score in scores.items():
            self._last_score = score
            self._print_status(f"Score: {score:.3f}")

            if score >= self._config.threshold:
                log.info(
                    "wake_word.detected",
                    model=model_name,
                    score=round(score, 3),
                )
                self._print_status("🎤 WAKE WORD DETECTED!")

                await self._event_bus.publish(
                    Event(
                        EventType.WAKE_WORD_DETECTED,
                        data={"model": model_name, "score": score},
                        source="wake_word",
                    )
                )

                # Reset the model to avoid repeated triggers
                await asyncio.to_thread(self._reset_model)
                break

    def _predict(self, chunk: np.ndarray) -> dict[str, float] | None:
        """Run wake word prediction on an audio chunk.

        Args:
            chunk: Audio data as a float32 numpy array.

        Returns:
            Dict mapping model names to confidence scores, or ``None``.
        """
        if self._model is None:
            return None

        # openWakeWord expects int16 audio
        audio_int16 = (chunk * 32767).astype(np.int16)

        # Feed audio to model
        prediction = self._model.predict(audio_int16)  # type: ignore[union-attr]

        return dict(prediction)

    def _reset_model(self) -> None:
        """Reset model state after a detection."""
        if self._model is not None:
            self._model.reset()  # type: ignore[union-attr]

    def _print_status(self, message: str) -> None:
        """Print an ANSI-coloured status line to the terminal.

        Args:
            message: Status message to display.
        """
        if not sys.stderr.isatty():
            return

        # Build status line
        model_name = self._config.model_name
        state = f"{_GREEN}●{_RESET}" if self._listening else f"{_YELLOW}○{_RESET}"
        line = f"\r{_DIM}[WakeWord]{_RESET} {state} {_CYAN}{model_name}{_RESET} | {message}"

        # Pad to clear previous content and write
        sys.stderr.write(f"{line:<80}\r")
        sys.stderr.flush()
