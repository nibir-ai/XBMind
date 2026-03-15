# Configuration Reference

XBMind uses a YAML configuration file with environment variable overrides.

## Config File Priority

1. Environment variables (`XBMIND_<SECTION>__<KEY>`)
2. `config/local.yaml` (user overrides)
3. `config/config.yaml` (defaults)

## Sections

### `bluetooth`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `device_name` | string | `"SRS-XB100"` | Target BT device name (substring match) |
| `device_mac` | string | `""` | MAC address for direct connect |
| `auto_pair` | bool | `true` | Auto-pair discovered devices |
| `reconnect_enabled` | bool | `true` | Auto-reconnect on disconnect |
| `reconnect_base_delay` | float | `1.0` | Initial reconnect delay (seconds) |
| `reconnect_max_delay` | float | `60.0` | Max backoff delay |
| `reconnect_max_attempts` | int | `0` | Max attempts (0 = infinite) |

### `audio`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `input_device` | int\|null | `null` | Device index (null = auto) |
| `sample_rate` | int | `16000` | Capture sample rate |
| `channels` | int | `1` | Mono (required for STT) |
| `block_size` | int | `512` | Samples per callback |

### `vad`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `threshold` | float | `0.5` | Speech detection threshold |
| `min_speech_duration` | float | `0.3` | Min speech to trigger (seconds) |
| `silence_duration` | float | `1.5` | Silence before end (seconds) |
| `pre_roll_duration` | float | `0.5` | Pre-roll buffer (seconds) |
| `max_recording_duration` | float | `30.0` | Safety cutoff (seconds) |

### `wake_word`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model_name` | string | `"hey_jarvis"` | openWakeWord model |
| `threshold` | float | `0.5` | Detection threshold |
| `inference_framework` | string | `"onnx"` | `"onnx"` or `"tflite"` |
| `play_chime` | bool | `true` | Play sound on detection |
| `chime_path` | string\|null | `null` | Custom chime WAV path |

### `stt`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | `"faster_whisper"` | `"faster_whisper"` or `"google_cloud"` |

#### `stt.faster_whisper`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model_size` | string | `"base"` | `tiny/base/small/medium/large-v3` |
| `device` | string | `"auto"` | `cpu/cuda/auto` |
| `compute_type` | string | `"int8"` | `int8/float16/float32` |
| `language` | string\|null | `null` | Force language (null = auto) |
| `beam_size` | int | `5` | Decoding beam size |

### `llm`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | `"ollama"` | `ollama/openai/claude/gemini` |
| `system_prompt` | string | (see config.yaml) | System prompt |

### `tts`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | `"piper"` | `"piper"` or `"elevenlabs"` |

### `tools.enabled`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `weather` | bool | `true` | Enable weather tool |
| `datetime` | bool | `true` | Enable datetime tool |
| `timer` | bool | `true` | Enable timer tool |
| `wikipedia` | bool | `true` | Enable wikipedia tool |
| `shell` | bool | `false` | Enable shell tool (security sensitive) |

### `health`
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable health server |
| `host` | string | `"127.0.0.1"` | Bind address |
| `port` | int | `7070` | Bind port |

## Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
ELEVENLABS_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```
