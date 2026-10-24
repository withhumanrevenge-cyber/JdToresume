"""Logging setup.

- Local development: readable one-line logs.
- Everywhere else: one JSON object per line (easy to search in CloudWatch).
- Every log line carries the current request id, so all lines from one request can be found together.
- Emails and phone numbers are masked before anything is written (resumes are full of personal data).
- Logging never blocks a request: records are handed to a background writer thread.
"""

from __future__ import annotations

import atexit
import json
import logging
import queue
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import QueueHandler, QueueListener

# Set by RequestIdMiddleware for the duration of each request; "-" outside a request.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)")


def redact(text: str) -> str:
    """Mask email addresses and phone-like numbers."""
    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", text))


class _RedactAndTagFilter(logging.Filter):
    """Masks personal data in the final message and attaches the request id."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(entry, ensure_ascii=False)


class _HandOffHandler(QueueHandler):
    """Puts records on a queue instead of writing them. The filter has already rendered and redacted the message
    in the caller's context (where the request id is known), so the record is passed on as it is."""

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


_listener: QueueListener | None = None


def configure_logging(level: str, json_output: bool) -> None:
    """Replace the root logger's handlers. Safe to call more than once (tests create several apps).

    Writing a log line never blocks a request: the server hands each record to a queue, and a background thread
    writes it out. Otherwise a slow or backed-up output (a container's stdout under load) would freeze the event
    loop, and with it every request and stream on this server.
    """
    global _listener
    writer = logging.StreamHandler()
    if json_output:
        writer.setFormatter(_JsonFormatter())
    else:
        writer.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"))

    if _listener is not None:
        _listener.stop()  # writes out anything still queued from the previous configuration
    records: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    _listener = QueueListener(records, writer)
    _listener.start()

    hand_off = _HandOffHandler(records)
    hand_off.addFilter(_RedactAndTagFilter())  # runs in the caller's context: redact, and tag with the request id
    root = logging.getLogger()
    root.handlers = [hand_off]
    root.setLevel(level)
    # Uvicorn's own access log duplicates our request log line; keep its errors only.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def flush_logs() -> None:
    """Write out everything queued so far (tests, and before the process exits)."""
    if _listener is not None:
        _listener.stop()
        _listener.start()


atexit.register(flush_logs)
