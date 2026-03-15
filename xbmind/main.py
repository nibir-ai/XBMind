"""XBMind orchestrator — main entry point.

Wires all subsystems together: Bluetooth → Audio → Wake Word → VAD →
STT → LLM → TTS → Audio Output.  Manages the asyncio event loop,
signal handling, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from typing import Any

from xbmind.audio.capture import AudioCapture
from xbmind.audio.player import AudioPlayer
from xbmind.audio.vad import VoiceActivityDetector
from xbmind.bluetooth.audio_sink import AudioSinkManager
from xbmind.bluetooth.manager import BluetoothManager
from xbmind.config import XBMindSettings, load_settings
from xbmind.llm.base import LLMMessage, LLMProvider
from xbmind.llm.memory import ConversationMemory
from xbmind.llm.tools.base_tool import BaseTool
from xbmind.llm.tools.datetime_tool import DateTimeTool
from xbmind.llm.tools.shell_tool import ShellTool
from xbmind.llm.tools.timer import TimerTool
from xbmind.llm.tools.weather import WeatherTool
from xbmind.llm.tools.wikipedia import WikipediaTool
from xbmind.stt.base import STTProvider
from xbmind.tts.base import TTSProvider
from xbmind.utils.chime import ChimePlayer
from xbmind.utils.events import Event, EventBus, EventType
from xbmind.utils.health import HealthServer
from xbmind.utils.logger import get_logger, setup_logging

log = get_logger(__name__)


class Orchestrator:
    """Main orchestrator that wires all XBMind subsystems.

    Manages the full lifecycle: startup, steady state (listening for
    wake word → transcribe → think → speak), and graceful shutdown.
    """

    def __init__(self, settings: XBMindSettings) -> None:
        """Initialise the orchestrator with application settings.

        Args:
            settings: Validated XBMind configuration.
        """
        self._settings = settings
        self._event_bus = EventBus()
        self._session_id = str(uuid.uuid4())
        self._running = False

        # Components (initialised in start)
        self._bt_manager: BluetoothManager | None = None
        self._audio_sink: AudioSinkManager | None = None
        self._audio_capture: AudioCapture | None = None
        self._vad: VoiceActivityDetector | None = None
        self._wake_detector: Any = None  # WakeWordDetector
        self._stt: STTProvider | None = None
        self._llm: LLMProvider | None = None
        self._tts: TTSProvider | None = None
        self._player: AudioPlayer | None = None
        self._memory: ConversationMemory | None = None
        self._health: HealthServer | None = None
        self._chime: ChimePlayer | None = None
        self._tools: dict[str, BaseTool] = {}

    async def start(self) -> None:
        """Start all subsystems and begin the main event loop."""
        log.info("orchestrator.starting", session_id=self._session_id)
        self._running = True

        # ── Event Bus ─────────────────────────────────────
        await self._event_bus.start()

        # ── Health Server ─────────────────────────────────
        if self._settings.health.enabled:
            self._health = HealthServer(
                host=self._settings.health.host,
                port=self._settings.health.port,
            )
            await self._health.start()

        # ── Conversation Memory ───────────────────────────
        self._memory = ConversationMemory(self._settings.llm.memory)
        await self._memory.start()
        self._set_health("memory", True)

        # ── Bluetooth ─────────────────────────────────────
        self._bt_manager = BluetoothManager(self._settings.bluetooth, self._event_bus)
        self._audio_sink = AudioSinkManager()
        try:
            await self._bt_manager.start()
            await self._audio_sink.set_bluetooth_sink(self._settings.bluetooth.device_name)
            self._set_health("bluetooth", True)
        except Exception:
            log.exception("orchestrator.bluetooth_failed")
            self._set_health("bluetooth", False)

        # ── Audio ─────────────────────────────────────────
        self._audio_capture = AudioCapture(self._settings.audio, self._event_bus)
        try:
            await self._audio_capture.start()
            self._set_health("audio_capture", True)
        except Exception:
            log.exception("orchestrator.audio_capture_failed")
            self._set_health("audio_capture", False)

        self._player = AudioPlayer(
            sample_rate=self._settings.tts.piper.sample_rate,
        )
        await self._player.start()

        # ── Chime ─────────────────────────────────────────
        self._chime = ChimePlayer(chime_path=self._settings.wake_word.chime_path)

        # ── VAD ───────────────────────────────────────────
        self._vad = VoiceActivityDetector(
            self._settings.vad,
            self._settings.audio,
            self._event_bus,
        )
        await self._vad.start()
        self._set_health("vad", True)

        # ── Wake Word ─────────────────────────────────────
        from xbmind.wake_word.detector import WakeWordDetector

        self._wake_detector = WakeWordDetector(self._settings.wake_word, self._event_bus)
        try:
            await self._wake_detector.start()
            self._set_health("wake_word", True)
        except Exception:
            log.exception("orchestrator.wake_word_failed")
            self._set_health("wake_word", False)

        # ── STT ───────────────────────────────────────────
        self._stt = self._create_stt_provider()
        try:
            await self._stt.start()
            self._set_health("stt", True)
        except Exception:
            log.exception("orchestrator.stt_failed")
            self._set_health("stt", False)

        # ── LLM ───────────────────────────────────────────
        self._llm = self._create_llm_provider()
        try:
            await self._llm.start()
            self._set_health("llm", True)
        except Exception:
            log.exception("orchestrator.llm_failed")
            self._set_health("llm", False)

        # ── Tools ─────────────────────────────────────────
        self._register_tools()

        # ── TTS ───────────────────────────────────────────
        self._tts = self._create_tts_provider()
        try:
            await self._tts.start()
            self._set_health("tts", True)
        except Exception:
            log.exception("orchestrator.tts_failed")
            self._set_health("tts", False)

        # ── Event Subscriptions ───────────────────────────
        self._event_bus.subscribe(EventType.WAKE_WORD_DETECTED, self._on_wake_word)
        self._event_bus.subscribe(EventType.VAD_SPEECH_END, self._on_speech_end)
        self._event_bus.subscribe(EventType.TIMER_ALERT, self._on_timer_alert)
        self._event_bus.subscribe(EventType.BT_CONNECTED, self._on_bt_connected)
        self._event_bus.subscribe(EventType.BT_DISCONNECTED, self._on_bt_disconnected)

        log.info("orchestrator.started", session_id=self._session_id)

    async def stop(self) -> None:
        """Gracefully shut down all subsystems."""
        log.info("orchestrator.stopping")
        self._running = False

        # Stop in reverse order
        components: list[tuple[str, Any]] = [
            ("tts", self._tts),
            ("llm", self._llm),
            ("stt", self._stt),
            ("wake_word", self._wake_detector),
            ("vad", self._vad),
            ("player", self._player),
            ("audio_capture", self._audio_capture),
            ("bluetooth", self._bt_manager),
            ("memory", self._memory),
            ("health", self._health),
            ("event_bus", self._event_bus),
        ]

        for name, component in components:
            if component is not None:
                try:
                    await component.stop()
                    log.info("orchestrator.component_stopped", component=name)
                except Exception:
                    log.exception("orchestrator.stop_error", component=name)

        # Cancel timer tasks
        for tool in self._tools.values():
            if isinstance(tool, TimerTool):
                await tool.cancel_all()

        log.info("orchestrator.stopped")

    # ── Event Handlers ────────────────────────────────────────────────────

    async def _on_wake_word(self, event: Event) -> None:
        """Handle wake word detection.

        Args:
            event: The wake word detected event.
        """
        log.info("orchestrator.wake_word_heard", data=event.data)

        # Play chime
        if self._settings.wake_word.play_chime and self._chime:
            await self._chime.play()

        # Pause wake word detection while processing
        if self._wake_detector:
            self._wake_detector.pause()

    async def _on_speech_end(self, event: Event) -> None:
        """Handle end of speech: transcribe → think → speak.

        Args:
            event: The VAD speech end event with audio data.
        """
        if self._stt is None or self._llm is None or self._tts is None:
            log.error("orchestrator.components_missing")
            return

        import numpy as np

        audio: np.ndarray = event.data

        # ── Transcribe ────────────────────────────────────
        try:
            result = await self._stt.transcribe(audio, self._settings.audio.sample_rate)
        except Exception:
            log.exception("orchestrator.stt_error")
            self._resume_wake_word()
            return

        text = result.text.strip()
        if not text or result.confidence < 0.1:
            log.info("orchestrator.empty_transcription")
            self._resume_wake_word()
            return

        log.info("orchestrator.transcribed", text=text, confidence=round(result.confidence, 3))

        # ── LLM Processing ───────────────────────────────
        try:
            response_text = await self._process_llm(text)
        except Exception:
            log.exception("orchestrator.llm_error")
            response_text = "I'm sorry, I encountered an error processing that request."

        # ── Speak Response ────────────────────────────────
        if response_text and self._tts and self._player:
            try:
                audio_bytes = await self._tts.synthesize(response_text)
                if audio_bytes:
                    await self._player.play(audio_bytes, self._tts.sample_rate)
                    await self._player.wait_until_done()
            except Exception:
                log.exception("orchestrator.tts_error")

        # Resume wake word detection
        self._resume_wake_word()

    async def _on_timer_alert(self, event: Event) -> None:
        """Handle timer expiration by speaking the alert.

        Args:
            event: The timer alert event.
        """
        message = event.data.get("message", "Timer is done!")

        if self._tts and self._player:
            try:
                # Interrupt any current playback
                await self._player.interrupt()
                audio_bytes = await self._tts.synthesize(message)
                if audio_bytes:
                    await self._player.play(audio_bytes, self._tts.sample_rate)
            except Exception:
                log.exception("orchestrator.timer_alert_error")

    async def _on_bt_connected(self, event: Event) -> None:
        """Handle Bluetooth connection events.

        Args:
            event: The BT connected event.
        """
        log.info("orchestrator.bt_connected", device=event.data)
        if self._audio_sink:
            await self._audio_sink.set_bluetooth_sink(self._settings.bluetooth.device_name)
        self._set_health("bluetooth", True)

    async def _on_bt_disconnected(self, event: Event) -> None:
        """Handle Bluetooth disconnection events.

        Args:
            event: The BT disconnected event.
        """
        log.warning("orchestrator.bt_disconnected", device=event.data)
        self._set_health("bluetooth", False)

    # ── LLM Processing ──────────────────────────────────────────────────

    async def _process_llm(self, user_text: str) -> str:
        """Process user text through the LLM with tool calling.

        Args:
            user_text: The transcribed user input.

        Returns:
            The LLM's final text response.
        """
        if self._llm is None or self._memory is None:
            return "LLM not available."

        # Load conversation history
        messages = await self._memory.get_messages(self._session_id)

        # Add system prompt if not present
        if not messages or messages[0].role != "system":
            messages.insert(0, LLMMessage(role="system", content=self._settings.llm.system_prompt))

        # Add user message
        user_msg = LLMMessage(role="user", content=user_text)
        messages.append(user_msg)
        await self._memory.add_message(self._session_id, user_msg)

        # Get tool definitions
        tool_defs = [tool.definition for tool in self._tools.values()]

        # LLM generate with tool loop
        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            response = await self._llm.generate(messages, tools=tool_defs if tool_defs else None)

            if not response.tool_calls:
                # No tool calls — we have a final response
                if response.content:
                    assistant_msg = LLMMessage(role="assistant", content=response.content)
                    await self._memory.add_message(self._session_id, assistant_msg)

                    # Auto-summarize if needed
                    if await self._memory.should_summarize(self._session_id):
                        await self._auto_summarize()

                return response.content

            # Process tool calls
            assistant_msg = LLMMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_msg)
            await self._memory.add_message(self._session_id, assistant_msg)

            for tc in response.tool_calls:
                tool = self._tools.get(tc.name)
                if tool:
                    try:
                        result = await tool.execute(**tc.arguments)
                    except Exception as exc:
                        result = f"Error executing {tc.name}: {exc}"
                        log.exception("orchestrator.tool_error", tool=tc.name)
                else:
                    result = f"Unknown tool: {tc.name}"

                tool_msg = LLMMessage(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
                messages.append(tool_msg)
                await self._memory.add_message(self._session_id, tool_msg)

        return "I'm having trouble completing that request."

    async def _auto_summarize(self) -> None:
        """Auto-summarize the conversation using the LLM."""
        if self._llm is None or self._memory is None:
            return

        messages = await self._memory.get_messages(self._session_id)

        summary_prompt = LLMMessage(
            role="user",
            content=(
                "Summarize the key points of our conversation so far in 2-3 sentences. "
                "Focus on important information, decisions, and context."
            ),
        )

        try:
            response = await self._llm.generate([*messages, summary_prompt])
            if response.content:
                await self._memory.store_summary(self._session_id, response.content)
                log.info("orchestrator.conversation_summarized")
        except Exception:
            log.exception("orchestrator.summarize_error")

    # ── Factory Methods ──────────────────────────────────────────────────

    def _create_stt_provider(self) -> STTProvider:
        """Create the configured STT provider.

        Returns:
            An initialised STT provider instance.
        """
        provider = self._settings.stt.provider

        if provider == "google_cloud":
            from xbmind.stt.google_cloud import GoogleCloudSTT
            return GoogleCloudSTT(self._settings.stt.google_cloud)

        from xbmind.stt.faster_whisper import FasterWhisperSTT
        return FasterWhisperSTT(self._settings.stt.faster_whisper)

    def _create_llm_provider(self) -> LLMProvider:
        """Create the configured LLM provider.

        Returns:
            An initialised LLM provider instance.
        """
        provider = self._settings.llm.provider

        if provider == "openai":
            from xbmind.llm.openai_api import OpenAILLM
            return OpenAILLM(self._settings.llm.openai)
        if provider == "claude":
            from xbmind.llm.claude_api import ClaudeLLM
            return ClaudeLLM(self._settings.llm.claude)
        if provider == "gemini":
            from xbmind.llm.gemini_api import GeminiLLM
            return GeminiLLM(self._settings.llm.gemini)

        from xbmind.llm.ollama import OllamaLLM
        return OllamaLLM(self._settings.llm.ollama)

    def _create_tts_provider(self) -> TTSProvider:
        """Create the configured TTS provider.

        Returns:
            An initialised TTS provider instance.
        """
        provider = self._settings.tts.provider

        if provider == "elevenlabs":
            from xbmind.tts.elevenlabs import ElevenLabsTTS
            return ElevenLabsTTS(self._settings.tts.elevenlabs)

        from xbmind.tts.piper import PiperTTS
        return PiperTTS(self._settings.tts.piper)

    def _register_tools(self) -> None:
        """Register all enabled tools."""
        tools_enabled = self._settings.tools.enabled

        if tools_enabled.weather:
            self._tools["weather"] = WeatherTool(self._settings.tools.weather)
        if tools_enabled.datetime:
            self._tools["datetime"] = DateTimeTool()
        if tools_enabled.timer:
            self._tools["set_timer"] = TimerTool(self._settings.tools.timer, self._event_bus)
        if tools_enabled.wikipedia:
            self._tools["wikipedia"] = WikipediaTool()
        if tools_enabled.shell:
            self._tools["shell"] = ShellTool(self._settings.tools.shell)

        log.info("orchestrator.tools_registered", tools=list(self._tools.keys()))

    def _set_health(self, component: str, healthy: bool) -> None:
        """Update health status of a component.

        Args:
            component: Component name.
            healthy: Whether the component is healthy.
        """
        if self._health:
            self._health.set_status(component, healthy)

    def _resume_wake_word(self) -> None:
        """Resume wake word detection after processing."""
        if self._wake_detector:
            self._wake_detector.resume()


async def _run(settings: XBMindSettings) -> None:
    """Run the orchestrator with signal handling.

    Args:
        settings: Application settings.
    """
    orchestrator = Orchestrator(settings)
    shutdown_event = asyncio.Event()

    def _signal_handler(sig: signal.Signals) -> None:
        log.info("orchestrator.signal_received", signal=sig.name)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler, sig)

    await orchestrator.start()

    # Wait for shutdown signal
    await shutdown_event.wait()

    await orchestrator.stop()


def main() -> None:
    """Entry point for the ``xbmind`` command."""
    settings = load_settings()
    setup_logging(settings.logging)

    log.info(
        "xbmind.starting",
        version="0.1.0",
        llm_provider=settings.llm.provider,
        stt_provider=settings.stt.provider,
        tts_provider=settings.tts.provider,
    )

    try:
        asyncio.run(_run(settings))
    except KeyboardInterrupt:
        log.info("xbmind.interrupted")
    finally:
        log.info("xbmind.exited")


if __name__ == "__main__":
    main()
