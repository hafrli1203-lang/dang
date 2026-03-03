"""Centralized logging for daangn_ad_reporter."""
import logging
import sys
from collections import deque

from app.paths import LOG_PATH

# ── In-memory ring buffer for recent log entries (UI에서 표시용) ──────────────
_LOG_BUFFER: deque = deque(maxlen=200)


class _BufferHandler(logging.Handler):
    """Stores formatted log records in a ring buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _LOG_BUFFER.append(self.format(record))
        except Exception:
            pass


def get_recent_logs(n: int = 50) -> list[str]:
    """Return the *n* most recent log lines."""
    items = list(_LOG_BUFFER)
    return items[-n:]


# ── Setup ────────────────────────────────────────────────────────────────────
_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

# File handler — writes to DATA_DIR/app.log (absolute)
_log_path = LOG_PATH
_file_handler = logging.FileHandler(_log_path, encoding="utf-8")
_file_handler.setFormatter(_formatter)
_file_handler.setLevel(logging.DEBUG)

# Stream handler — stderr
_stream_handler = logging.StreamHandler(sys.stderr)
_stream_handler.setFormatter(_formatter)
_stream_handler.setLevel(logging.WARNING)

# Buffer handler — in-memory for UI
_buffer_handler = _BufferHandler()
_buffer_handler.setFormatter(_formatter)
_buffer_handler.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with file + buffer handlers pre-attached."""
    logger = logging.getLogger(f"daangn.{name}")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_file_handler)
        logger.addHandler(_stream_handler)
        logger.addHandler(_buffer_handler)
    return logger
