# Contributing to XBMind

Thank you for your interest in contributing to XBMind! This document provides
guidelines and information for contributors.

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/xbmind.git
   cd xbmind
   ```
3. **Install** using the master installer:
   ```bash
   ./scripts/install.sh
   ```
4. **Activate** the virtual environment:
   ```bash
   source .venv/bin/activate        # bash / zsh
   source .venv/bin/activate.fish   # fish
   # Or run directly: .venv/bin/python -m xbmind.main
   ```
5. **Install dev dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```
6. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Code Style

- **Python 3.11+** with full type hints on every function.
- **Google-style docstrings** on every public class and method.
- **Ruff** for linting and formatting:
  ```bash
  ruff check xbmind/
  ruff format xbmind/
  ```
- No bare `except` clauses.
- No placeholders or `TODO` comments in submitted code.

### Running Tests

```bash
pytest tests/ -v
pytest tests/ -v -m "not integration"  # Skip hardware-dependent tests
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add weather tool timezone support`
- `fix: bluetooth reconnect loop on suspend/resume`
- `docs: update installation guide for Raspberry Pi 5`
- `test: add VAD silence detection edge cases`

## Pull Request Process

1. Update documentation if your change affects user-facing behavior.
2. Add tests for new functionality.
3. Ensure all tests pass and linting is clean.
4. Update `CHANGELOG.md` with your changes under `[Unreleased]`.
5. Submit a PR against the `main` branch.

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:

- Your OS and Python version
- Audio hardware (mic, speaker model)
- Full error output / logs
- Steps to reproduce

## Feature Requests

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
All contributors are expected to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
