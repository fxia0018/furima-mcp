import pytest

from furima_mcp import core, http


@pytest.fixture(autouse=True)
def _fast_and_fresh(monkeypatch):
    """No politeness delay and an empty result cache in every test."""
    monkeypatch.setattr(http, "MIN_INTERVAL", 0.0)
    core._cache.clear()
    http._last_request.clear()
