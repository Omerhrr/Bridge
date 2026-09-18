"""Structured logging with correlation identifiers.

Events such as ``workflow.started`` / ``sms.sent`` are logged with
``workflow_run_id`` / ``conversation_id`` / ``call_id`` so a single
communication session can be traced across the whole system (spec §33).
"""

import json
import logging
import sys
from datetime import UTC, datetime


class BridgeLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "logger": record.name,
        }
        for field in ("workflow_run_id", "conversation_id", "call_id", "node_id", "detail"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, default=str)


def get_logger(name: str = "bridge") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(BridgeLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_event(
    event: str,
    logger: logging.Logger | None = None,
    level: int = logging.INFO,
    **correlation,
) -> None:
    """Log a structured domain event with correlation identifiers."""
    (logger or get_logger()).log(level, event, extra={"event": event, **correlation})
