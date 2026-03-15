# Troubleshooting

## Bluetooth Issues

### Speaker not found
- Ensure the speaker is in **pairing mode**
- Check `bluetoothctl devices` to see discovered devices
- Verify `device_name` in config matches your speaker (substring)
- Try setting `device_mac` directly in config

### Audio not routing to speaker
- Check `pactl list sinks short` — look for a `bluez_sink` entry
- Run `pactl set-default-sink <sink-name>` manually
- Restart PipeWire: `systemctl --user restart pipewire`

### Frequent disconnections
- Move the speaker closer to the Bluetooth adapter
- Use a USB Bluetooth 5.0 adapter for better range
- Increase `reconnect_max_delay` in config

## Microphone Issues

### No audio input detected
- List devices: `python3 -c "import sounddevice; print(sounddevice.query_devices())"`
- Set `input_device` in config to the correct index
- Check ALSA: `arecord -l`
- Ensure mic isn't muted: `alsamixer`

### Poor recognition accuracy
- Use a USB microphone (built-in laptop mics are often poor)
- Reduce background noise
- Increase `vad.threshold` to filter noise
- Try a larger Whisper model (`small` or `medium`)

## Wake Word Issues

### Too many false positives
- Increase `wake_word.threshold` (try 0.6–0.8)
- Ensure mic isn't picking up TV/radio as wake words

### Not detecting wake word
- Decrease `wake_word.threshold` (try 0.3–0.4)
- Speak clearly and at a normal volume
- Check logs for detection scores

## STT Issues

### Slow transcription
- Use a smaller model: `tiny` or `base`
- Use `compute_type: int8` for CPU
- If you have a GPU, set `device: cuda`

### Wrong language detected
- Set `language: en` explicitly in config

## LLM Issues

### Ollama not responding
- Check Ollama is running: `ollama list`
- Start if needed: `ollama serve`
- Verify the model is downloaded: `ollama pull llama3.2`
- Check URL: `curl http://localhost:11434/api/tags`

### Slow responses
- Use a smaller model (e.g., `llama3.2` instead of `llama3.1:70b`)
- Reduce `max_tokens` in config
- Check system resources: `htop`

## TTS Issues

### Piper not found
- Run `./scripts/download_models.sh`
- Check path: `which piper` or verify `models/piper/piper` exists
- Update `tts.piper.executable` in config

### No audio output
- Check default sink: `pactl info | grep "Default Sink"`
- Test playback: `aplay /usr/share/sounds/alsa/Front_Center.wav`

## Health Check

Verify system status:
```bash
curl http://localhost:7070/health | python3 -m json.tool
```

## Logs

```bash
# Direct run
python -m xbmind.main 2>&1 | tee xbmind.log

# Systemd
journalctl --user -u xbmind -f

# Debug mode
XBMIND_LOGGING__LEVEL=debug python -m xbmind.main
```
