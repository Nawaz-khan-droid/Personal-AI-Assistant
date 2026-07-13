import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class FunctionTimeoutError(asyncio.TimeoutError):
    """Raised when a function exceeds its timeout."""


async def timeout(seconds: float, func, *args, **kwargs) -> Any:
    """
    Run an async function with a timeout.

    Args:
        seconds: Maximum execution time.
        func: Async function to run.
        *args, **kwargs: Passed to func.

    Returns:
        The return value of func.

    Raises:
        FunctionTimeoutError: If execution exceeds the timeout.

    Usage:
        result = await timeout(30, some_async_fn, arg1, arg2)
    """
    try:
        result = await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
        return result
    except asyncio.TimeoutError:
        logger.error(f"Timeout ({seconds}s) exceeded for {getattr(func, '__name__', str(func))}")
        raise FunctionTimeoutError(
            f"Function {getattr(func, '__name__', str(func))} timed out after {seconds}s"
        )
