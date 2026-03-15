# Hardware Tested

XBMind has been designed and tested with the following hardware combinations.

## Bluetooth Speakers

| Speaker | Bluetooth | A2DP | Status |
|---------|-----------|------|--------|
| **Sony SRS-XB100** | 5.3 | ✅ | Primary target, fully supported |
| Sony SRS-XB13 | 4.2 | ✅ | Works well |
| JBL Flip 6 | 5.1 | ✅ | Works well |
| JBL Go 3 | 5.1 | ✅ | Works, limited volume |
| Anker Soundcore 2 | 5.0 | ✅ | Works well |

## Microphones

| Microphone | Type | Status |
|-----------|------|--------|
| **Blue Snowball** | USB Condenser | Recommended |
| ReSpeaker USB Mic Array | USB Array | Excellent (far-field) |
| Laptop built-in mic | Internal | Works, limited range |
| Cheap USB mic | USB | Works, adequate |

## Computing Platforms

| Platform | CPU | RAM | STT Model | Notes |
|----------|-----|-----|-----------|-------|
| **Desktop (x86_64)** | i5/Ryzen 5+ | 8 GB+ | `base`/`small` | Best performance |
| Raspberry Pi 5 | BCM2712 | 8 GB | `tiny`/`base` | Good, use `int8` |
| Raspberry Pi 4 | BCM2711 | 4 GB+ | `tiny` | Adequate, slower STT |
| Jetson Nano | Tegra X1 | 4 GB | `base` (CUDA) | GPU acceleration |

## Bluetooth Adapters

| Adapter | BT Version | Status |
|---------|-----------|--------|
| Built-in (most laptops) | 5.0+ | Works |
| TP-Link UB500 | 5.0 | Recommended USB dongle |
| Plugable USB-BT4 | 4.0 | Works, shorter range |

## Recommended Setup

For the best experience:
- **Speaker**: Sony SRS-XB100 (small, loud, excellent BT)
- **Microphone**: ReSpeaker USB Mic Array (360° pickup)
- **Computer**: Any x86_64 Linux box with 8 GB+ RAM
- **Bluetooth**: Built-in or TP-Link UB500 USB
