import asyncio
import functools
import logging
import time as _time
from typing import Callable, Tuple, Type, Optional

logger = logging.getLogger(__name__)


def retry(
    attempts: int = 3,
    interval: float = 0.5,
    backoff: float = 2.0,
    exclude_exc: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable:
    """
    Retry decorator with exponential backoff and exception exclusion.

    Adapted from thevickypedia/Jarvis retry pattern.
    Works for both sync and async functions.

    Args:
        attempts: Max retry attempts before giving up.
        interval: Initial wait between retries (seconds).
        backoff: Exponential multiplier (2.0 = double each retry).
        exclude_exc: Exception types that should NOT be retried.

    Usage:
        @retry(attempts=3, exclude_exc=(ValueError,))
        async def unstable_api_call():
            ...
    """
    def decorator(func):
        is_async = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            exclusions = (exclude_exc or ()) + (asyncio.CancelledError,)
            last_exc = None
            for i in range(1, attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    if i > 1:
                        logger.info(f"{func.__name__} succeeded on attempt {i}/{attempts}")
                    return result
                except exclusions:
                    raise
                except Exception as e:
                    last_exc = e
                    if i < attempts:
                        wait = interval * (backoff ** (i - 1))
                        logger.warning(
                            f"{func.__name__} failed (attempt {i}/{attempts}): {e}. "
                            f"Retrying in {wait:.1f}s..."
                        )
                        await asyncio.sleep(wait)
            logger.error(f"{func.__name__} failed after {attempts} attempts")
            raise last_exc

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            exclusions = exclude_exc or ()
            last_exc = None
            for i in range(1, attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if i > 1:
                        logger.info(f"{func.__name__} succeeded on attempt {i}/{attempts}")
                    return result
                except exclusions:
                    raise
                except Exception as e:
                    last_exc = e
                    if i < attempts:
                        wait = interval * (backoff ** (i - 1))
                        logger.warning(
                            f"{func.__name__} failed (attempt {i}/{attempts}): {e}. "
                            f"Retrying in {wait:.1f}s..."
                        )
                        _time.sleep(wait)
            logger.error(f"{func.__name__} failed after {attempts} attempts")
            raise last_exc

        return async_wrapper if is_async else sync_wrapper
    return decorator
