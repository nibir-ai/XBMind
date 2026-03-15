"""Structured logging setup using structlog.

Provides coloured console output for development and JSON output for
production.  Call :func:`setup_logging` once at startup.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from xbmind.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Configure structlog and stdlib logging.

    Args:
        config: Logging configuration section from :class:`XBMindSettings`.
    """
    log_level = getattr(logging, config.level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if config.format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    # File handler if configured
    file_handler: logging.FileHandler | None = None
    if config.file:
        file_handler = logging.FileHandler(config.file, encoding="utf-8")
        file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    if file_handler:
        root_logger.addHandler(file_handler)
    root_logger.setLevel(log_level)

    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "aiohttp", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structlog logger.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)
