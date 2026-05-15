import logging
import sys
from pathlib import Path

import structlog
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"


def _console_renderer(_, __, event_dict: dict) -> str:
    """Human-readable colored console output."""
    level = event_dict.pop("level", "info").upper()
    timestamp = event_dict.pop("timestamp", "")
    skill_id = event_dict.pop("skill_id", "-")
    event = event_dict.pop("event", "")
    run_id = event_dict.pop("run_id", "")

    color_map = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.MAGENTA,
    }
    level_color = color_map.get(level, "")

    parts = [f"{Fore.WHITE}{timestamp}", f"[{level_color}{level}{Fore.WHITE}]"]
    if skill_id:
        parts.append(f"[{Fore.BLUE}{skill_id}{Fore.WHITE}]")
    parts.append(event)
    if event_dict:
        extras = " ".join(f"{k}={v}" for k, v in event_dict.items())
        parts.append(f"{Style.DIM}{extras}{Style.NORMAL}")

    return " ".join(parts) + Style.RESET_ALL


def setup_logging(level: str = "INFO", json_file: bool = True) -> None:
    """
    Configure structlog for both console (colored) and file (JSON) output.

    Args:
        level: Log level for console output.
        json_file: Whether to also write JSON-line logs to data/logs/.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Standard library logging bridge
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=True),
        structlog.dev.set_exc_info,
    ]

    if json_file:
        structlog.configure(
            processors=processors + [structlog.dev.ConsoleRenderer()],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=processors + [_console_renderer],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


def get_logger(name: str = "metaphysics") -> structlog.stdlib.BoundLogger:
    """Get a bound structlog logger instance."""
    return structlog.get_logger(name)
