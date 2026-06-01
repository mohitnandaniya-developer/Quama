"""Centralized logging configuration for the Quama backend."""

from __future__ import annotations

import logging
import sys

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure root logger based on application settings."""
    log_level = logging.DEBUG if settings.debug else logging.INFO
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%dT%H:%M:%S"

    stream_handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[stream_handler],
        force=True,
    )

    if not settings.debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
