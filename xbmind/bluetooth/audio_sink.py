"""PipeWire / PulseAudio audio sink management.

Sets the connected Bluetooth device as the default audio output sink
so that TTS playback is routed through the speaker.
"""

from __future__ import annotations

import asyncio
import subprocess

from xbmind.utils.logger import get_logger

log = get_logger(__name__)


class AudioSinkManager:
    """Manages audio output routing to a Bluetooth speaker.

    Uses ``pactl`` (PulseAudio/PipeWire CLI) to discover and set the
    default audio sink.

    Example::

        sink = AudioSinkManager()
        await sink.set_bluetooth_sink("SRS-XB100")
    """

    def __init__(self) -> None:
        """Initialise the audio sink manager."""
        self._current_sink: str | None = None

    @property
    def current_sink(self) -> str | None:
        """The name of the currently active audio sink."""
        return self._current_sink

    async def list_sinks(self) -> list[dict[str, str]]:
        """List all available audio output sinks.

        Returns:
            A list of dicts with ``name`` and ``description`` keys.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._list_sinks_sync)

    def _list_sinks_sync(self) -> list[dict[str, str]]:
        """Synchronously list audio sinks via ``pactl``."""
        sinks: list[dict[str, str]] = []
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                log.warning("audio_sink.pactl_error", stderr=result.stderr.strip())
                return sinks

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    sinks.append({"name": parts[1], "description": parts[1]})
        except FileNotFoundError:
            log.error("audio_sink.pactl_not_found")
        except subprocess.TimeoutExpired:
            log.error("audio_sink.pactl_timeout")

        return sinks

    async def set_bluetooth_sink(self, device_name_fragment: str) -> bool:
        """Find and set a Bluetooth audio sink as default.

        Args:
            device_name_fragment: Substring to match against sink names
                (case-insensitive).

        Returns:
            ``True`` if a matching sink was found and set as default.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._set_bluetooth_sink_sync, device_name_fragment)

    def _set_bluetooth_sink_sync(self, device_name_fragment: str) -> bool:
        """Synchronously find and set the Bluetooth sink."""
        sinks = self._list_sinks_sync()
        fragment_lower = device_name_fragment.lower().replace(":", "_").replace("-", "_")

        for sink in sinks:
            sink_name_lower = sink["name"].lower()
            if "bluez" in sink_name_lower or "bluetooth" in sink_name_lower:
                if fragment_lower in sink_name_lower or not device_name_fragment:
                    return self._set_default_sink(sink["name"])

        # Fallback: try any sink matching the device name
        for sink in sinks:
            if fragment_lower in sink["name"].lower():
                return self._set_default_sink(sink["name"])

        log.warning("audio_sink.no_bt_sink_found", fragment=device_name_fragment)
        return False

    def _set_default_sink(self, sink_name: str) -> bool:
        """Set a sink as the default output.

        Args:
            sink_name: The full PulseAudio/PipeWire sink name.

        Returns:
            ``True`` on success.
        """
        try:
            result = subprocess.run(
                ["pactl", "set-default-sink", sink_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                self._current_sink = sink_name
                log.info("audio_sink.set_default", sink=sink_name)
                return True
            log.warning("audio_sink.set_failed", sink=sink_name, stderr=result.stderr.strip())
        except FileNotFoundError:
            log.error("audio_sink.pactl_not_found")
        except subprocess.TimeoutExpired:
            log.error("audio_sink.pactl_timeout")

        return False

    async def set_sink_volume(self, volume_percent: int) -> bool:
        """Set the volume of the current default sink.

        Args:
            volume_percent: Volume level (0–150).

        Returns:
            ``True`` on success.
        """
        volume_percent = max(0, min(150, volume_percent))
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._set_volume_sync, volume_percent)

    def _set_volume_sync(self, volume_percent: int) -> bool:
        """Synchronously set sink volume."""
        try:
            result = subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume_percent}%"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                log.info("audio_sink.volume_set", volume=volume_percent)
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            log.exception("audio_sink.volume_error")
        return False
