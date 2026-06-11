"""
Structured logging configuration for OpenBioOps API.

Supports two modes:
- Development: Human-readable colored output
- Production: JSON structured logging for log aggregation (ELK, Datadog, etc.)

The format is controlled by the LOG_FORMAT environment variable:
- LOG_FORMAT=json  -> JSON output (default in production)
- LOG_FORMAT=text  -> Human-readable output (default in development)
"""
from __future__ import annotations
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs logs in JSON format suitable for log aggregation systems.
    Includes correlation ID from the extra dict if present.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info for errors
        if record.levelno >= logging.ERROR:
            log_data["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields (request_id, duration_ms, etc.)
        if hasattr(record, "__dict__"):
            extra_fields = {
                k: v for k, v in record.__dict__.items()
                if k not in {
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "taskName",
                }
                and not k.startswith("_")
            }
            if extra_fields:
                log_data["extra"] = extra_fields

        return json.dumps(log_data, default=str)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development.

    Includes colors for better readability in terminals.
    """

    COLORS = {
        "DEBUG": "/033[36m",     # Cyan
        "INFO": "/033[32m",      # Green
        "WARNING": "/033[33m",   # Yellow
        "ERROR": "/033[31m",     # Red
        "CRITICAL": "/033[35m",  # Magenta
    }
    RESET = "/033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Add color if terminal supports it
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Build base message
        msg = f"{timestamp} {color}[{record.levelname:>8}]{reset} {record.name}: {record.getMessage()}"

        # Add request_id if present
        if hasattr(record, "request_id") and record.request_id:
            msg = f"{timestamp} {color}[{record.levelname:>8}]{reset} [{record.request_id[:8]}] {record.name}: {record.getMessage()}"

        # Add extra fields
        if hasattr(record, "__dict__"):
            extra_fields = {
                k: v for k, v in record.__dict__.items()
                if k not in {
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "request_id", "taskName",
                }
                and not k.startswith("_")
            }
            if extra_fields:
                extras = " ".join(f"{k}={v}" for k, v in extra_fields.items())
                msg += f" | {extras}"

        # Add exception info
        if record.exc_info:
            msg += f"/n{self.formatException(record.exc_info)}"

        return msg


def configure_logging(log_format: str | None = None, log_level: str | None = None) -> None:
    """Configure logging for the application.

    Args:
        log_format: 'json' or 'text'. Defaults to LOG_FORMAT env var or 'text'.
        log_level: Logging level. Defaults to LOG_LEVEL env var or 'INFO'.
    """
    format_type = log_format or os.getenv("LOG_FORMAT", "text")
    level_name = log_level or os.getenv("LOG_LEVEL", "INFO")

    # Get log level
    level = getattr(logging, level_name.upper(), logging.INFO)

    # Select formatter
    if format_type.lower() == "json":
        formatter = StructuredFormatter()
    else:
        formatter = DevelopmentFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Configure logging on module import
configure_logging()
