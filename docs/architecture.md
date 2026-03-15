# Architecture

XBMind follows a **pipeline architecture** with an async event bus for decoupled communication between subsystems.

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                          │
│                    (asyncio event loop)                       │
│                                                              │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐    │
│  │Bluetooth│──▶│  Audio   │──▶│  Wake   │──▶│   VAD   │    │
│  │ Manager │   │ Capture  │   │  Word   │   │ (Silero)│    │
│  └─────────┘   └─────────┘   └─────────┘   └────┬────┘    │
│                                                   │          │
│                                            ┌──────▼──────┐  │
│                                            │    STT      │  │
│                                            │  (Whisper)  │  │
│                                            └──────┬──────┘  │
│                                                   │          │
│  ┌─────────────┐                           ┌──────▼──────┐  │
│  │   Memory    │◀─────────────────────────▶│    LLM      │  │
│  │  (SQLite)   │                           │  (Ollama)   │  │
│  └─────────────┘                           └──────┬──────┘  │
│                                                   │          │
│  ┌─────────────┐                           ┌──────▼──────┐  │
│  │   Tools     │◀─────────────────────────▶│    TTS      │  │
│  │  (5 built-  │                           │  (Piper)    │  │
│  │   in)       │                           └──────┬──────┘  │
│  └─────────────┘                                  │          │
│                                            ┌──────▼──────┐  │
│                                            │   Audio     │  │
│                                            │   Player    │  │
│                                            └──────┬──────┘  │
│                                                   │          │
│                                            ┌──────▼──────┐  │
│                                            │  BT Sink    │  │
│                                            │  (PipeWire) │  │
│                                            └─────────────┘  │
│                                                              │
│  ┌──────────┐     ┌──────────┐                               │
│  │  Health   │     │  Event   │                               │
│  │  Server   │     │   Bus    │                               │
│  └──────────┘     └──────────┘                               │
└──────────────────────────────────────────────────────────────┘
```

## Event Bus

The event bus is an async pub/sub system using `asyncio.Queue`. Components publish typed events; subscribers handle them without direct coupling.

### Event Flow

1. **AUDIO_CHUNK** — Audio capture publishes raw audio frames
2. **WAKE_WORD_DETECTED** — Wake word detector triggers on keyword
3. **VAD_SPEECH_START** — VAD detects speech beginning
4. **VAD_SPEECH_END** — VAD detects speech ending (includes audio data)
5. **STT_RESULT** — Transcription complete
6. **LLM_RESPONSE** — LLM response generated
7. **TTS_START / TTS_DONE** — TTS synthesis and playback

## Provider System

All major components use abstract base classes for swappability:

| Component | Base Class | Default | Alternatives |
|-----------|-----------|---------|-------------|
| STT | `STTProvider` | faster-whisper | Google Cloud |
| LLM | `LLMProvider` | Ollama | OpenAI, Claude, Gemini |
| TTS | `TTSProvider` | Piper | ElevenLabs |

## Data Flow

1. Microphone → `sounddevice` InputStream → event bus
2. Audio chunks → openWakeWord (OS thread) → wake event
3. Audio chunks → Silero VAD (pre-roll buffer) → speech audio
4. Speech audio → faster-whisper (thread pool) → text
5. Text → Ollama HTTP API (tool loop) → response
6. Response → Piper TTS (subprocess pipe) → WAV audio
7. WAV audio → `sounddevice` output → Bluetooth speaker

## Threading Model

- **Main thread**: asyncio event loop
- **Audio callback**: sounddevice PortAudio thread (non-blocking)
- **Wake word**: `asyncio.to_thread` (OS thread)
- **STT inference**: thread pool executor
- **Piper TTS**: subprocess (separate process)
- **D-Bus**: thread pool executor (dbus-python is synchronous)
