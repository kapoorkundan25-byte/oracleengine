"""
utils/logger.py — Structured, colour-coded logging for OracleEngine.

Uses Python's standard ``logging`` module with:
* Colour-coded console output via a custom formatter.
* Rotating file handler writing to ``logs/oracleengine.log``.
* Log level controlled by the ``LOG_LEVEL`` environment variable.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ---------------------------------------------------------------------------
# ANSI colour codes
# ---------------------------------------------------------------------------
_RESET = "\033[0m"
_COLOURS: dict[int, str] = {
    logging.DEBUG: "\033[36m",     # cyan
    logging.INFO: "\033[32m",      # green
    logging.WARNING: "\033[33m",   # yellow
    logging.ERROR: "\033[31m",     # red
    logging.CRITICAL: "\033[35m",  # magenta
}


class _ColourFormatter(logging.Formatter):
    """Formatter that prepends a colour code based on log level."""

    _FMT = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        colour = _COLOURS.get(record.levelno, _RESET)
        formatter = logging.Formatter(
            f"{colour}{self._FMT}{_RESET}",
            datefmt=self._DATE_FMT,
        )
        return formatter.format(record)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with console + rotating file handlers.

    Args:
        name: Logger name — typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance ready to use.
    """
    from config import LOG_LEVEL  # local import to avoid circular deps

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(_ColourFormatter())

    # File handler (rotating: 5 MB × 3 backups)
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        logs_dir / "oracleengine.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
