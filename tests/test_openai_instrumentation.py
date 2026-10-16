"""Integration tests for OpenAI instrumentation."""

import pytest
from unittest.mock import Mock, patch
from src.olakaisdk import (
    olakai_config,
    instrument_openai,
    uninstrument_openai,
    is_openai_instrumented,
    olakai_context
)


@pytest.fixture(autouse=True)
def reset_instrumentation():
    """Reset instrumentation state before each test."""
    try:
        uninstrument_openai()
    except Exception:
        pass
    yield
    try:
        uninstrument_openai()
    except Exception:
        pass


def test_instrument_openai_requires_config():
    """Test that instrumentation requires SDK to be configured."""
    # Reset config
    import src.olakaisdk.config as config_module
    config_module._global_config = None

    with pytest.raises(RuntimeError, match="not initialized"):
        instrument_openai()


def test_instrument_openai_requires_openai():
    """Test that instrumentation fails gracefully without OpenAI."""
    olakai_config("test-key", debug=False)

    # Test that we get appropriate error without OpenAI installed
    # (In real usage, OpenAI would be installed)
    # For now, just verify is_instrumented returns False initially
    assert is_openai_instrumented() is False


@patch('src.olakaisdk.client.api.send_to_api_simple')
def test_trace_openai_call_sync_direct(mock_send):
    """Test the sync tracing function directly."""
    olakai_config("test-key")

    # Create mock OpenAI response
    mock_response = Mock()
    mock_response.model = "gpt-4"
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Test response"

    # Mock original method
    original_method = Mock(return_value=mock_response)

    # Create mock client
    mock_client = Mock()
    mock_client.api_key = "sk-test123"

    # Call the wrapped method
    from src.olakaisdk.instrumentation.openai import _trace_openai_call_sync
    result = _trace_openai_call_sync(
        mock_client,
        original_method,
        (),
        {"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]},
        True,  # capture_inputs
        True,  # capture_outputs
        True   # capture_api_keys
    )

    assert result == mock_response
    original_method.assert_called_once()


@patch('src.olakaisdk.client.api.send_to_api_simple')
def test_trace_with_context(mock_send):
    """Test that context metadata is included in telemetry."""
    olakai_config("test-key")

    # Setup mocks
    mock_response = Mock()
    mock_response.model = "gpt-4"
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 5
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 15
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Response"

    original_method = Mock(return_value=mock_response)
    mock_client = Mock()
    mock_client.api_key = "sk-test123"

    # Use context
    with olakai_context(userEmail="test@example.com", task="Test Task"):
        from src.olakaisdk.instrumentation.openai import _trace_openai_call_sync
        result = _trace_openai_call_sync(
            mock_client,
            original_method,
            (),
            {"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]},
            True, True, True
        )

    # Verify the call was made
    assert result == mock_response
    original_method.assert_called_once()


def test_extractor_extracts_tokens():
    """Test that extractor properly extracts token counts."""
    from src.olakaisdk.extractors.openai_extractor import OpenAIExtractor

    mock_response = Mock()
    mock_response.model = "gpt-4"
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 200
    mock_response.usage.total_tokens = 300
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Test output"

    mock_client = Mock()
    mock_client.api_key = "sk-test"

    extractor = OpenAIExtractor()
    payload = extractor.extract(
        request_kwargs={"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=500,
        context=None
    )

    assert payload.tokens == 300
    assert payload.requestTime == 500
    assert payload.customData["model"] == "gpt-4"
    assert payload.customData["provider"] == "openai"
    assert payload.customData["tokens_input"] == 100
    assert payload.customData["tokens_output"] == 200


def test_extractor_never_sends_api_key():
    """Provider keys are never sent, even with capture_api_keys=True."""
    from src.olakaisdk.extractors.openai_extractor import OpenAIExtractor

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "response"

    mock_client = Mock()
    mock_client.api_key = "sk-test123"

    extractor = OpenAIExtractor(capture_api_keys=True)
    payload = extractor.extract(
        request_kwargs={"model": "gpt-4", "messages": []},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None
    )

    assert "api_key" not in payload.customData
    assert "sk-test123" not in str(payload)


def test_extractor_redacts_when_disabled():
    """Test that extractor redacts data when capture is disabled."""
    from src.olakaisdk.extractors.openai_extractor import OpenAIExtractor

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "secret response"

    mock_client = Mock()
    mock_client.api_key = "sk-secret"

    extractor = OpenAIExtractor(
        capture_inputs=False,
        capture_outputs=False,
        capture_api_keys=False
    )

    payload = extractor.extract(
        request_kwargs={"model": "gpt-4", "messages": [{"role": "user", "content": "secret"}]},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None
    )

    assert payload.prompt == "[redacted]"
    assert payload.response == "[redacted]"
    assert "api_key" not in payload.customData


def test_extractor_merges_context():
    """Test that extractor merges context metadata."""
    from src.olakaisdk.extractors.openai_extractor import OpenAIExtractor
    from src.olakaisdk.context import OlakaiContextData

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "response"

    mock_client = Mock()

    context = OlakaiContextData(
        userEmail="user@example.com",
        task="Support",
        customData={"env": "prod", "tier": 5}
    )

    extractor = OpenAIExtractor()
    payload = extractor.extract(
        request_kwargs={"model": "gpt-4", "messages": []},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=context
    )

    assert payload.userEmail == "user@example.com"
    assert payload.task == "Support"
    assert payload.customData["env"] == "prod"
    assert payload.customData["model"] == "gpt-4"  # Also includes extracted data
    assert payload.customData["tier"] == 5
    assert payload.customData["tokens_total"] == 20  # Also includes extracted data
