# Custom TTS Voice

XBMind uses [Piper TTS](https://github.com/rhasspy/piper) for offline text-to-speech. You can choose from many pre-trained voices or train your own.

## Available Voices

Browse all Piper voices: https://rhasspy.github.io/piper-samples/

Popular choices:
| Voice | Language | Quality |
|-------|----------|---------|
| `en_US-lessac-medium` | English (US) | Good (default) |
| `en_US-lessac-high` | English (US) | Better (larger) |
| `en_US-amy-medium` | English (US) | Good, female |
| `en_GB-alan-medium` | English (UK) | Good, male |

## Downloading a New Voice

```bash
# Download from Hugging Face
VOICE="en_US-amy-medium"
wget "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/${VOICE}.onnx" \
    -O "models/piper/${VOICE}.onnx"
wget "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/${VOICE}.onnx.json" \
    -O "models/piper/${VOICE}.onnx.json"
```

## Configuration

```yaml
tts:
  provider: "piper"
  piper:
    model_path: "models/piper/en_US-amy-medium.onnx"
    length_scale: 1.0      # Speed (lower = faster)
    sentence_silence: 0.2  # Pause between sentences
```

## Voice Parameters

- **`length_scale`**: Controls speaking speed. `1.0` is normal, `0.8` is faster, `1.2` is slower.
- **`sentence_silence`**: Pause between sentences in seconds.
- **`sample_rate`**: Must match the voice model (usually 22050 Hz).

## Training a Custom Voice

Piper supports fine-tuning on custom voice data:

1. Prepare 1-10 hours of clean speech audio with text transcripts
2. Follow the [Piper training guide](https://github.com/rhasspy/piper/blob/master/TRAINING.md)
3. Export the model as `.onnx`
4. Place in `models/piper/` and update config
