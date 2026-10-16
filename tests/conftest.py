"""Shared fixtures: no test talks to the real Olakai API."""

from unittest.mock import patch

import pytest

from src.olakaisdk.client.api import olakai_flush


@pytest.fixture(autouse=True)
def _isolate_background_sender():
    """Block real HTTP from the background sender and drain it per test.

    Tests that need real HTTP (to a local stub server) restore
    ``requests`` on ``src.olakaisdk.client.api`` themselves.
    """
    olakai_flush(timeout=5.0)
    with patch("src.olakaisdk.client.api.requests"):
        yield
        olakai_flush(timeout=5.0)
