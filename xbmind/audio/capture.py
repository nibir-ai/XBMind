"""Audio capture using sounddevice.

Opens a non-blocking ``InputStream``, auto-selects the best input device,
and feeds raw audio chunks to the event bus for VAD and wake-word processing.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd

from xbmind.utils.events import Event, EventBus, EventType
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import AudioConfig

log = get_logger(__name__)


def _select_input_device(preferred: int | None = None) -> int | None:
    """Select the best available audio input device.

    Args:
        preferred: Preferred device index. If ``None``, auto-selects.

    Returns:
        Device index, or ``None`` to use the system default.
    """
    if preferred is not None:
        try:
            info = sd.query_devices(preferred, kind="input")
            if info and info.get("max_input_channels", 0) > 0:  # type: ignore[union-attr]
                log.info("audio.using_preferred_device", index=preferred, name=info.get("name"))
                return preferred
        except (sd.PortAudioError, ValueError):
            log.warning("audio.preferred_device_unavailable", index=preferred)

    # Try to find a USB microphone first (often the best choice)
    devices = sd.query_devices()
    if isinstance(devices, dict):
        devices = [devices]

    for idx, dev in enumerate(devices):
        if not isinstance(dev, dict):
            continue
        name = str(dev.get("name", "")).lower()
        max_in = dev.get("max_input_channels", 0)
        if max_in > 0 and ("usb" in name or "microphone" in name):
            log.info("audio.auto_selected_device", index=idx, name=dev.get("name"))
            return idx

    # Fall back to the system default
    log.info("audio.using_default_device")
    return None


class AudioCapture:
    """Captures audio from a microphone and publishes chunks to the event bus.

    Example::

        capture = AudioCapture(config, event_bus)
        await capture.start()
        # Audio chunks are published as AUDIO_CHUNK events
        await capture.stop()
    """

    def __init__(self, config: AudioConfig, event_bus: EventBus) -> None:
        """Initialise audio capture.

        Args:
            config: Audio configuration section.
            event_bus: Event bus for publishing audio chunks.
        """
        self._config = config
        self._event_bus = event_bus
        self._stream: sd.InputStream | None = None
        self._running: bool = False
        self._device_index: int | None = None

    @property
    def is_running(self) -> bool:
        """Whether the capture stream is active."""
        return self._running

    async def start(self) -> None:
        """Start the audio capture stream.

        Runs device selection and stream setup in a thread executor.
        """
        loop = asyncio.get_running_loop()
        self._device_index = _select_input_device(self._config.input_device)

        def _open_stream() -> None:
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=self._config.sample_rate,
                channels=self._config.channels,
                blocksize=self._config.block_size,
                dtype=self._config.dtype,
                callback=self._audio_callback,
            )
            self._stream.start()

        await loop.run_in_executor(None, _open_stream)
        self._running = True
        log.info(
            "audio.capture_started",
            device=self._device_index,
            rate=self._config.sample_rate,
            block_size=self._config.block_size,
        )

    async def stop(self) -> None:
        """Stop the audio capture stream."""
        self._running = False
        if self._stream:
            loop = asyncio.get_running_loop()

            def _close() -> None:
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None

            await loop.run_in_executor(None, _close)
        log.info("audio.capture_stopped")

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,  # type: ignore[type-arg]
        status: sd.CallbackFlags,
    ) -> None:
        """Callback invoked by sounddevice for each audio block.

        Args:
            indata: Recorded audio data as a numpy array.
            frames: Number of frames in the block.
            time_info: Timing information dict.
            status: PortAudio status flags.
        """
        if status:
            log.warning("audio.stream_status", status=str(status))

        if not self._running:
            return

        # Copy to avoid the buffer being recycled
        chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy().flatten()

        self._event_bus.publish_nowait(
            Event(EventType.AUDIO_CHUNK, data=chunk, source="audio_capture")
        )
