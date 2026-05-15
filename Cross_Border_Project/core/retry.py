import asyncio
import functools
import logging
from core.logger import get_logger
import random
import time
from collections.abc import Callable
from typing import TypeVar

from core.exceptions import MaxRetriesExceeded

logger = get_logger("metaphysics.retry")
F = TypeVar("F", bound=Callable)


def retry_on_failure(
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    Exponential backoff retry decorator with optional jitter.

    After exhausting retries, re-raises MaxRetriesExceeded wrapping the original error.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        break
                    delay = min(
                        base_delay_seconds * (exponential_base ** (attempt - 1)),
                        max_delay_seconds,
                    )
                    if jitter:
                        delay *= random.uniform(0.8, 1.2)
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs: %s",
                        attempt,
                        max_attempts,
                        func.__name__,
                        delay,
                        e,
                    )
                    time.sleep(delay)
            raise MaxRetriesExceeded(
                f"{func.__name__} failed after {max_attempts} attempts"
            ) from last_exception

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        break
                    delay = min(
                        base_delay_seconds * (exponential_base ** (attempt - 1)),
                        max_delay_seconds,
                    )
                    if jitter:
                        delay *= random.uniform(0.8, 1.2)
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs: %s",
                        attempt,
                        max_attempts,
                        func.__name__,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
            raise MaxRetriesExceeded(
                f"{func.__name__} failed after {max_attempts} attempts"
            ) from last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator
