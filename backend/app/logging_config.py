from __future__ import annotations

import logging
import re
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = (
    "ts=%(asctime)s level=%(levelname)s logger=%(name)s request_id=%(request_id)s %(message)s"
)

_secrets: set[str] = set()


# Registers a value that must never appear in log output.
def register_secret(value: str) -> None:
    if value and len(value) >= 4:
        _secrets.add(value)


# Replaces registered secrets and bearer tokens in text with [REDACTED].
def redact(text: str) -> str:
    for secret in _secrets:
        text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+", r"\1[REDACTED]", text)


class RequestIdFilter(logging.Filter):
    # Attaches the current request ID to every log record.
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RedactingFormatter(logging.Formatter):
    # Formats the log record and strips any secrets from the result.
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


# Installs the app's log handler, replacing only handlers it installed earlier.
def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(_LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    for h in list(root.handlers):
        if getattr(h, "_ada_handler", False):
            root.removeHandler(h)
    handler._ada_handler = True
    root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("openai", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
