# Custom Wake Word

XBMind uses [openWakeWord](https://github.com/dscripka/openWakeWord) for wake word detection. You can use built-in models or train a custom one.

## Built-in Models

| Model Name | Wake Phrase |
|-----------|-------------|
| `hey_jarvis` | "Hey Jarvis" (default) |
| `alexa` | "Alexa" |
| `hey_mycroft` | "Hey Mycroft" |
| `timer` | Timer detection |

Change in `config/local.yaml`:
```yaml
wake_word:
  model_name: "alexa"
```

## Training a Custom Wake Word

### 1. Collect Audio Samples

Record 50+ clips of your desired wake phrase:
```bash
# Record 2-second clips
for i in $(seq 1 50); do
    echo "Say your wake phrase (clip $i/50)..."
    arecord -d 2 -f S16_LE -r 16000 -c 1 "samples/positive_$i.wav"
    sleep 1
done
```

### 2. Collect Negative Samples

Gather background audio and non-wake-word speech (100+ clips).

### 3. Train with openWakeWord

```python
from openwakeword.train import train_model

train_model(
    positive_clips="samples/positive_*.wav",
    negative_clips="samples/negative_*.wav",
    output_path="models/custom_wakeword.onnx",
    epochs=100,
)
```

### 4. Configure XBMind

```yaml
wake_word:
  model_name: "models/custom_wakeword.onnx"
  threshold: 0.6  # May need tuning
```

## Tuning Tips

- **Lower threshold** (0.3–0.4): More sensitive, more false positives
- **Higher threshold** (0.6–0.8): Less sensitive, fewer false positives
- Test in your actual environment (background noise matters)
