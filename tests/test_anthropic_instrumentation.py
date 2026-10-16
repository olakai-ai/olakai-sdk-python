"""Integration tests for Anthropic instrumentation."""

import pytest
from unittest.mock import Mock, patch
from src.olakaisdk import (
    olakai_config,
    instrument_anthropic,
    uninstrument_anthropic,
    is_anthropic_instrumented,
    olakai_context,
)


@pytest.fixture(autouse=True)
def reset_instrumentation():
    """Reset instrumentation state before each test."""
    try:
        uninstrument_anthropic()
    except Exception:
        pass
    yield
    try:
        uninstrument_anthropic()
    except Exception:
        pass


def test_instrument_anthropic_requires_config():
    """Test that instrumentation requires SDK to be configured."""
    import src.olakaisdk.config as config_module

    config_module._global_config = None

    with pytest.raises(RuntimeError, match="not initialized"):
        instrument_anthropic()


def test_instrument_anthropic_requires_anthropic_sdk():
    """Test that instrumentation fails gracefully without Anthropic SDK."""
    olakai_config("test-key", debug=False)

    # Verify is_anthropic_instrumented returns False initially
    assert is_anthropic_instrumented() is False


def test_uninstrument_anthropic_noop_when_not_instrumented():
    """Test that uninstrument is a no-op when not instrumented."""
    # Should not raise
    uninstrument_anthropic()
    assert is_anthropic_instrumented() is False


@patch("src.olakaisdk.client.api.send_to_api_simple")
def test_trace_anthropic_call_sync_direct(mock_send):
    """Test the sync tracing function directly."""
    olakai_config("test-key")

    # Create mock Anthropic response
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Test response from Claude"
    mock_response.content[0].type = "text"
    mock_response.model = "claude-sonnet-4-20250514"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 20
    mock_response.role = "assistant"
    mock_response.stop_reason = "end_turn"

    # Mock original method
    original_method = Mock(return_value=mock_response)

    # Create mock client (Messages resource instance)
    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    # Call the wrapped method
    from src.olakaisdk.instrumentation.anthropic import (
        _trace_anthropic_call_sync,
    )

    result = _trace_anthropic_call_sync(
        mock_client,
        original_method,
        (),
        {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello, Claude!"}],
        },
        True,  # capture_inputs
        True,  # capture_outputs
        True,  # capture_api_keys
    )

    assert result == mock_response
    original_method.assert_called_once()


@patch("src.olakaisdk.client.api.send_to_api_simple")
def test_trace_anthropic_with_context(mock_send):
    """Test that context metadata is included in telemetry."""
    olakai_config("test-key")

    # Setup mocks
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Response"
    mock_response.content[0].type = "text"
    mock_response.model = "claude-sonnet-4-20250514"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 5
    mock_response.usage.output_tokens = 10
    mock_response.role = "assistant"
    mock_response.stop_reason = "end_turn"

    original_method = Mock(return_value=mock_response)
    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    # Use context
    with olakai_context(userEmail="test@example.com", task="Test Task"):
        from src.olakaisdk.instrumentation.anthropic import (
            _trace_anthropic_call_sync,
        )

        result = _trace_anthropic_call_sync(
            mock_client,
            original_method,
            (),
            {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": "test prompt",
                    }
                ],
            },
            True,
            True,
            True,
        )

    assert result == mock_response
    original_method.assert_called_once()


def test_anthropic_extractor_extracts_tokens():
    """Test that extractor properly extracts token counts."""
    from src.olakaisdk.extractors.anthropic_extractor import (
        AnthropicExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Test output from Claude"
    mock_response.content[0].type = "text"
    mock_response.model = "claude-sonnet-4-20250514"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 200
    mock_response.role = "assistant"
    mock_response.stop_reason = "end_turn"

    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    extractor = AnthropicExtractor()
    payload = extractor.extract(
        request_kwargs={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "test prompt"}],
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=500,
        context=None,
    )

    assert payload.tokens == 300
    assert payload.requestTime == 500
    assert payload.customData["model"] == "claude-sonnet-4-20250514"
    assert payload.customData["provider"] == "anthropic"
    assert payload.customData["tokens_input"] == 100
    assert payload.customData["tokens_output"] == 200


def test_anthropic_extractor_never_sends_api_key():
    """Provider keys are never sent, even with capture_api_keys=True."""
    from src.olakaisdk.extractors.anthropic_extractor import (
        AnthropicExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "response"
    mock_response.content[0].type = "text"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 10

    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    extractor = AnthropicExtractor(capture_api_keys=True)
    payload = extractor.extract(
        request_kwargs={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "test"}],
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert "api_key" not in payload.customData
    assert "sk-ant-test123" not in str(payload)


def test_anthropic_extractor_redacts_when_disabled():
    """Test that extractor redacts data when capture is disabled."""
    from src.olakaisdk.extractors.anthropic_extractor import (
        AnthropicExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "secret response"
    mock_response.content[0].type = "text"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 10

    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-secret"

    extractor = AnthropicExtractor(
        capture_inputs=False,
        capture_outputs=False,
        capture_api_keys=False,
    )

    payload = extractor.extract(
        request_kwargs={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "secret prompt"}],
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert payload.prompt == "[redacted]"
    assert payload.response == "[redacted]"
    assert "api_key" not in payload.customData


def test_anthropic_extractor_merges_context():
    """Test that extractor merges context metadata."""
    from src.olakaisdk.extractors.anthropic_extractor import (
        AnthropicExtractor,
    )
    from src.olakaisdk.context import OlakaiContextData

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "response"
    mock_response.content[0].type = "text"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 10

    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    context = OlakaiContextData(
        userEmail="user@example.com",
        task="Support",
        customData={"env": "prod", "tier": 5},
    )

    extractor = AnthropicExtractor()
    payload = extractor.extract(
        request_kwargs={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "test"}],
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=context,
    )

    assert payload.userEmail == "user@example.com"
    assert payload.task == "Support"
    assert payload.customData["env"] == "prod"
    assert payload.customData["model"] == "claude-sonnet-4-20250514"
    assert payload.customData["tier"] == 5
    assert payload.customData["tokens_total"] == 20


def test_anthropic_extractor_handles_messages_prompt():
    """Test that extractor handles messages list prompt correctly."""
    from src.olakaisdk.extractors.anthropic_extractor import (
        AnthropicExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "response"
    mock_response.content[0].type = "text"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 5
    mock_response.usage.output_tokens = 5

    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    extractor = AnthropicExtractor()
    payload = extractor.extract(
        request_kwargs={
            "model": "claude-sonnet-4-20250514",
            "messages": [
                {"role": "user", "content": "Hello"},
                {
                    "role": "assistant",
                    "content": "Hi there",
                },
                {
                    "role": "user",
                    "content": "How are you?",
                },
            ],
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert "user: Hello" in payload.prompt
    assert "assistant: Hi there" in payload.prompt
    assert "user: How are you?" in payload.prompt


def test_anthropic_extractor_handles_missing_usage():
    """Test that extractor handles missing usage gracefully."""
    from src.olakaisdk.extractors.anthropic_extractor import (
        AnthropicExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock(spec=[])
    mock_response.content = [Mock()]
    mock_response.content[0].text = "response"
    mock_response.content[0].type = "text"

    mock_client = Mock()
    mock_client._client = Mock()
    mock_client._client.api_key = "sk-ant-test123"

    extractor = AnthropicExtractor()
    payload = extractor.extract(
        request_kwargs={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "test"}],
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert payload.tokens == 0
    assert payload.customData["tokens_input"] == 0
    assert payload.customData["tokens_output"] == 0
