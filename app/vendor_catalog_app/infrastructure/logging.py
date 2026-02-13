from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from vendor_catalog_app.core.env import (
    TVENDOR_LOG_CAPTURE_ROOT,
    TVENDOR_LOG_JSON,
    TVENDOR_LOG_LEVEL,
    get_env,
    get_env_bool,
)

_LOGGING_CONFIGURED = False
_RESERVED_LOG_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_FIELDS:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=True)


def setup_app_logging() -> None:
    global _LOGGING_CONFIGURED  # pylint: disable=global-statement
    if _LOGGING_CONFIGURED:
        return

    level_name = get_env(TVENDOR_LOG_LEVEL, "INFO").upper() or "INFO"
    level = getattr(logging, level_name, logging.INFO)
    use_json = get_env_bool(TVENDOR_LOG_JSON, default=False)
    capture_root = get_env_bool(TVENDOR_LOG_CAPTURE_ROOT, default=False)

    formatter: logging.Formatter
    if use_json:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)

    app_logger = logging.getLogger("vendor_catalog_app")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(level)
    app_logger.propagate = False

    if capture_root:
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(level)

    logging.getLogger(__name__).info(
        "Application logging configured. level=%s json=%s capture_root=%s",
        level_name,
        str(use_json).lower(),
        str(capture_root).lower(),
    )
    _LOGGING_CONFIGURED = True
