from app.security.rate_limit import RateLimiter


def test_rate_limiter_expires_hits():
    limiter = RateLimiter(limit=2, window_s=10)
    assert limiter.allow("client", now=100)
    assert limiter.allow("client", now=101)
    assert not limiter.allow("client", now=102)
    assert limiter.allow("client", now=111)
