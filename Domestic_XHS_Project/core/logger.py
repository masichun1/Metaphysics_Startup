import logging
import sys
from pathlib import Path

import structlog
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog for XHS project."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=True),
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "xhs") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
