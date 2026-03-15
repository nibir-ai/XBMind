# XBMind Roadmap

## v0.1.0 — Foundation (Current)

- [x] Core pipeline: Wake → Listen → Transcribe → Think → Speak
- [x] Bluetooth auto-pair with exponential backoff reconnect
- [x] Offline STT (faster-whisper) and TTS (Piper)
- [x] Ollama LLM integration with tool calling
- [x] SQLite conversation memory
- [x] Built-in tools: weather, datetime, timer, wikipedia, shell
- [x] Systemd service and health check endpoint

## v0.2.0 — Polish & UX

- [ ] Multi-room support (multiple BT speakers, zone-aware)
- [ ] Conversation context carry-over across sessions
- [ ] Streaming STT (real-time partial transcripts)
- [ ] Streaming TTS (start speaking before full response)
- [ ] Custom wake word training CLI
- [ ] Audio ducking (lower music volume during interaction)

## v0.3.0 — Smart Home

- [ ] Home Assistant integration (REST + WebSocket)
- [ ] MQTT device control
- [ ] Music playback (MPD/Mopidy integration)
- [ ] Routine/automation scheduling ("Good morning" routines)
- [ ] Multi-language support (auto-detect and respond)

## v0.4.0 — Advanced AI

- [ ] RAG (Retrieval Augmented Generation) with local documents
- [ ] Voice cloning for personalized TTS
- [ ] Speaker identification (who is talking?)
- [ ] Emotion detection in voice
- [ ] Proactive notifications (calendar, weather alerts)

## v1.0.0 — Production Release

- [ ] Comprehensive test coverage (>90%)
- [ ] Docker container support
- [ ] Web-based configuration UI
- [ ] Plugin system for third-party tools
- [ ] Performance benchmarks and optimization
- [ ] Raspberry Pi 4/5 optimized builds
