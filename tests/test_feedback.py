"""Tests for olakai_feedback() wire format and endpoint routing."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.olakaisdk import olakai_config, olakai_feedback


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset global config between tests for isolation."""
    import src.olakaisdk.config as config_module

    original = config_module._global_config
    config_module._global_config = None
    yield
    config_module._global_config = original


def _run_coroutines(loop):
    """Wait for the background sender so fire-and-forget sends run."""
    del loop
    from src.olakaisdk.client.api import olakai_flush

    assert olakai_flush(timeout=5.0)


def test_olakai_feedback_posts_to_feedback_endpoint():
    """Feedback posts to /api/monitoring/feedback, not /api/monitoring/prompt."""
    olakai_config("test-key", endpoint="https://example.test")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with patch("src.olakaisdk.client.api.requests") as mock_requests:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post = MagicMock(return_value=mock_response)

        async def _invoke():
            olakai_feedback("chat_abc", "UP")

        loop.run_until_complete(_invoke())
        _run_coroutines(loop)

        mock_requests.post.assert_called_once()
        call_kwargs = mock_requests.post.call_args
        url = call_kwargs.args[0]
        assert url == "https://example.test/api/monitoring/feedback"

    loop.close()


def test_olakai_feedback_minimal_wire_payload():
    """Minimal payload only has sessionId and rating."""
    olakai_config("test-key", endpoint="https://example.test")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with patch("src.olakaisdk.client.api.requests") as mock_requests:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post = MagicMock(return_value=mock_response)

        async def _invoke():
            olakai_feedback("chat_abc", "DOWN")

        loop.run_until_complete(_invoke())
        _run_coroutines(loop)

        body = mock_requests.post.call_args.kwargs["json"]
        assert body == {"sessionId": "chat_abc", "rating": "DOWN"}

    loop.close()


def test_olakai_feedback_full_wire_payload():
    """All optional fields flow through when provided."""
    olakai_config("test-key", endpoint="https://example.test")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with patch("src.olakaisdk.client.api.requests") as mock_requests:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post = MagicMock(return_value=mock_response)

        async def _invoke():
            olakai_feedback(
                "chat_abc",
                "UP",
                turn_index=3,
                comment="Great answer",
                user_email="user@example.com",
            )

        loop.run_until_complete(_invoke())
        _run_coroutines(loop)

        body = mock_requests.post.call_args.kwargs["json"]
        assert body == {
            "sessionId": "chat_abc",
            "rating": "UP",
            "turnIndex": 3,
            "comment": "Great answer",
            "email": "user@example.com",
        }

    loop.close()


def test_olakai_feedback_uses_api_key_header():
    """x-api-key header is set from global config."""
    olakai_config("secret-key-123", endpoint="https://example.test")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with patch("src.olakaisdk.client.api.requests") as mock_requests:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post = MagicMock(return_value=mock_response)

        async def _invoke():
            olakai_feedback("chat_abc", "UP")

        loop.run_until_complete(_invoke())
        _run_coroutines(loop)

        headers = mock_requests.post.call_args.kwargs["headers"]
        assert headers["x-api-key"] == "secret-key-123"

    loop.close()


def test_olakai_feedback_no_customdata_markers_on_wire():
    """Wire payload carries no eventType/feedbackRating/customData keys."""
    olakai_config("test-key", endpoint="https://example.test")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with patch("src.olakaisdk.client.api.requests") as mock_requests:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post = MagicMock(return_value=mock_response)

        async def _invoke():
            # Caller still passes custom_data for backward compat; it
            # must NOT appear on the wire.
            olakai_feedback(
                "chat_abc",
                "UP",
                custom_data={"foo": "bar"},
            )

        loop.run_until_complete(_invoke())
        _run_coroutines(loop)

        body = mock_requests.post.call_args.kwargs["json"]
        assert "customData" not in body
        assert "eventType" not in body
        assert "feedbackRating" not in body
        assert "prompt" not in body
        assert "response" not in body

    loop.close()


def test_olakai_feedback_never_raises_on_http_error():
    """Fire-and-forget: HTTP errors are swallowed."""
    olakai_config("test-key", endpoint="https://example.test")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with patch("src.olakaisdk.client.api.requests") as mock_requests:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=Exception("boom")
        )
        mock_requests.post = MagicMock(return_value=mock_response)

        async def _invoke():
            # Must not raise.
            olakai_feedback("chat_abc", "UP")

        loop.run_until_complete(_invoke())
        _run_coroutines(loop)

    loop.close()


def test_olakai_feedback_never_raises_when_not_configured():
    """Missing config is handled silently, not raised."""
    # No olakai_config() call — global config is None.
    # Must not raise.
    olakai_feedback("chat_abc", "UP")


def test_olakai_feedback_no_event_loop_is_safe():
    """Calling from sync context without a loop does not raise."""
    olakai_config("test-key", endpoint="https://example.test")
    # No event loop running — should be skipped gracefully.
    olakai_feedback("chat_abc", "UP")
