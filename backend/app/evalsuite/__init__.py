"""Seeded FleetTwin analytics evaluation suite."""


def run_suite(seed: int = 42, fast: bool = True):
    """Lazily load the runner so ``python -m app.evalsuite.runner`` is clean."""
    from .runner import run_suite as _run_suite

    return _run_suite(seed=seed, fast=fast)


__all__ = ["run_suite"]
