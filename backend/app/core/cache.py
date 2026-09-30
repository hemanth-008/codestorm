"""A dependency-free TTL cache for small, process-local computations."""

from __future__ import annotations

import asyncio
import functools
import inspect
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast


F = TypeVar("F", bound=Callable[..., Any])
_KWARGS_MARKER = object()


def _cache_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, ...]:
    """Build a deterministic key; callers should use hashable arguments."""

    return args + (_KWARGS_MARKER,) + tuple(sorted(kwargs.items()))


def ttl_cache(seconds: float) -> Callable[[F], F]:
    """Cache a function result for ``seconds`` of monotonic time.

    The cache is intentionally local to the decorated function: it avoids a
    network dependency for health and demo workloads and expires stale values
    even when the process clock moves backwards.
    """

    if seconds <= 0:
        raise ValueError("TTL must be positive")

    def decorator(func: F) -> F:
        cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
        lock = threading.RLock()

        def clear() -> None:
            with lock:
                cache.clear()

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _cache_key(args, kwargs)
                now = time.monotonic()
                with lock:
                    item = cache.get(key)
                    if item is not None and now - item[0] < seconds:
                        return item[1]
                value = await func(*args, **kwargs)
                with lock:
                    cache[key] = (time.monotonic(), value)
                return value

            async_wrapper.cache_clear = clear  # type: ignore[attr-defined]
            return cast(F, async_wrapper)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _cache_key(args, kwargs)
            now = time.monotonic()
            with lock:
                item = cache.get(key)
                if item is not None and now - item[0] < seconds:
                    return item[1]
            value = func(*args, **kwargs)
            with lock:
                cache[key] = (time.monotonic(), value)
            return value

        wrapper.cache_clear = clear  # type: ignore[attr-defined]
        return cast(F, wrapper)

    return decorator
