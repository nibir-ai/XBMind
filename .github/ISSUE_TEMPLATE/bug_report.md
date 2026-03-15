---
name: Bug Report
about: Report a bug or issue with XBMind
title: '[BUG] '
labels: bug
assignees: ''
---

## Describe the Bug
A clear and concise description of the bug.

## To Reproduce
Steps to reproduce the behavior:
1. Start XBMind with '...'
2. Say "Hey Jarvis, ..."
3. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Logs
```
Paste relevant log output here.
Run with: XBMIND_LOGGING__LEVEL=debug python -m xbmind.main 2>&1 | tee debug.log
```

## Environment
- **OS**: Ubuntu 22.04 / Raspberry Pi OS / etc.
- **Python version**: 3.11 / 3.12
- **XBMind version**: 0.1.0
- **Audio hardware**: (mic model, speaker model)
- **Bluetooth adapter**: (built-in / USB dongle model)

## Health Check Output
```json
Paste output of: curl http://localhost:7070/health
```

## Additional Context
Add any other context about the problem here.
