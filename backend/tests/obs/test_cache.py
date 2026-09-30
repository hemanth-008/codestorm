import asyncio

import pytest

from app.core.cache import ttl_cache


def test_ttl_cache_reuses_then_expires(monkeypatch):
    clock = iter([10.0, 10.1, 10.2, 11.2, 11.3])
    monkeypatch.setattr("app.core.cache.time.monotonic", lambda: next(clock))
    calls = []

    @ttl_cache(1.0)
    def value(x):
        calls.append(x)
        return len(calls)

    assert value("a") == 1
    assert value("a") == 1
    assert value("a") == 2
    assert calls == ["a", "a"]


def test_ttl_cache_supports_async_functions():
    calls = []

    @ttl_cache(10.0)
    async def value(x):
        calls.append(x)
        return len(calls)

    async def run():
        assert await value(1) == 1
        assert await value(1) == 1

    asyncio.run(run())
    assert calls == [1]


def test_ttl_cache_rejects_non_positive_ttl():
    with pytest.raises(ValueError):
        ttl_cache(0)
