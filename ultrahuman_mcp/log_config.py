# File: log_config.py
# Description: Watson-style structured logging (JSON, trace_id, duration) for Ultrahuman MCP.
# Created: 2026-03-15
# Last updated: 2026-03-15

"""
Structured logging: one JSON object per log line with timestamp, level, module, message, and extra.
Enable with ULTRAHUMAN_LOG_JSON=1 or call configure_logging(use_json=True).
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class StructuredJsonFormatter(logging.Formatter):
    """Format each record as a single-line JSON object (Watson-style)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if getattr(record, "trace_id", None):
            payload["trace_id"] = record.trace_id
        if getattr(record, "duration_ms", None) is not None:
            payload["duration_ms"] = record.duration_ms
        if getattr(record, "error_code", None):
            payload["error_code"] = record.error_code
        # Merge extra (everything that isn't standard LogRecord)
        for k, v in record.__dict__.items():
            if k not in (
                "name", "msg", "args", "created", "filename", "funcName", "levelname", "levelno",
                "lineno", "module", "msecs", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName", "message", "taskName",
                "trace_id", "duration_ms", "error_code",
            ) and v is not None:
                payload[k] = v
        return json.dumps(payload, default=str)


def configure_logging(
    use_json: bool | None = None,
    level: str = "INFO",
) -> None:
    """Configure root logger for ultrahuman_mcp. use_json: True = JSON formatter, False = plain, None = from env ULTRAHUMAN_LOG_JSON."""
    if use_json is None:
        use_json = os.getenv("ULTRAHUMAN_LOG_JSON", "").strip().lower() in ("1", "true", "yes")
    root = logging.getLogger("ultrahuman_mcp")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(root.level)
        if use_json:
            handler.setFormatter(StructuredJsonFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(handler)
    # Prevent duplicate logs from parent loggers
    root.propagate = False
