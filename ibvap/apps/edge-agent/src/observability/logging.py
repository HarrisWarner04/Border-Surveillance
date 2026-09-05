"""
Structured logging configuration.

Uses structlog for JSON-formatted, context-enriched logs.
JSON in production, coloured console output in development.

IMPORTANT: Never log RTSP credentials, API keys, tokens, or secrets.

configure_logging() must be called once at application startup.
get_logger() may be called at any time after that.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.stdlib import BoundLogger


def configure_logging(log_level: str = "INFO", app_env: str = "development") -> None:
    """
    Configure structlog for the application.

    Call once at startup, before any logging occurs.

    Parameters
    ----------
    log_level : str
        Logging level string: DEBUG | INFO | WARNING | ERROR | CRITICAL
    app_env : str
        Application environment: development | production | test
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if app_env == "development":
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(numeric_level)

    # Suppress noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "ultralytics"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> BoundLogger:
    """Return a bound structlog logger for the given module name."""
    logger: BoundLogger = structlog.get_logger(name)
    return logger
