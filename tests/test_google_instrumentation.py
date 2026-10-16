"""Integration tests for Google Generative AI instrumentation."""

import pytest
from unittest.mock import Mock, patch
from src.olakaisdk import (
    olakai_config,
    instrument_google,
    uninstrument_google,
    is_google_instrumented,
    olakai_context,
)


@pytest.fixture(autouse=True)
def reset_instrumentation():
    """Reset instrumentation state before each test."""
    try:
        uninstrument_google()
    except Exception:
        pass
    yield
    try:
        uninstrument_google()
    except Exception:
        pass


def test_instrument_google_requires_config():
    """Test that instrumentation requires SDK to be configured."""
    import src.olakaisdk.config as config_module

    config_module._global_config = None

    with pytest.raises(RuntimeError, match="not initialized"):
        instrument_google()


def test_instrument_google_requires_google_sdk():
    """Test that instrumentation fails gracefully without Google SDK."""
    olakai_config("test-key", debug=False)

    # Verify is_google_instrumented returns False initially
    assert is_google_instrumented() is False


def test_uninstrument_google_noop_when_not_instrumented():
    """Test that uninstrument is a no-op when not instrumented."""
    # Should not raise
    uninstrument_google()
    assert is_google_instrumented() is False


@patch("src.olakaisdk.client.api.send_to_api_simple")
def test_trace_google_call_sync_direct(mock_send):
    """Test the sync tracing function directly."""
    olakai_config("test-key")

    # Create mock Google GenAI response
    mock_response = Mock()
    mock_response.text = "Test response from Gemini"
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content = Mock()
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = (
        "Test response from Gemini"
    )
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 20
    mock_response.usage_metadata.total_token_count = 30

    # Mock original method
    original_method = Mock(return_value=mock_response)

    # Create mock client (GenerativeModel instance)
    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    # Call the wrapped method
    from src.olakaisdk.instrumentation.google import (
        _trace_google_call_sync,
    )

    result = _trace_google_call_sync(
        mock_client,
        original_method,
        ("Hello, Gemini!",),
        {},
        True,  # capture_inputs
        True,  # capture_outputs
        True,  # capture_api_keys
    )

    assert result == mock_response
    original_method.assert_called_once()


@patch("src.olakaisdk.client.api.send_to_api_simple")
def test_trace_google_with_context(mock_send):
    """Test that context metadata is included in telemetry."""
    olakai_config("test-key")

    # Setup mocks
    mock_response = Mock()
    mock_response.text = "Response"
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content = Mock()
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = "Response"
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 5
    mock_response.usage_metadata.candidates_token_count = 10
    mock_response.usage_metadata.total_token_count = 15

    original_method = Mock(return_value=mock_response)
    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    # Use context
    with olakai_context(
        userEmail="test@example.com", task="Test Task"
    ):
        from src.olakaisdk.instrumentation.google import (
            _trace_google_call_sync,
        )

        result = _trace_google_call_sync(
            mock_client,
            original_method,
            ("test prompt",),
            {},
            True,
            True,
            True,
        )

    assert result == mock_response
    original_method.assert_called_once()


def test_google_extractor_extracts_tokens():
    """Test that extractor properly extracts token counts."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.text = "Test output from Gemini"
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content = Mock()
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = (
        "Test output from Gemini"
    )
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 100
    mock_response.usage_metadata.candidates_token_count = 200
    mock_response.usage_metadata.total_token_count = 300

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    extractor = GoogleExtractor()
    payload = extractor.extract(
        request_kwargs={"contents": "test prompt"},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=500,
        context=None,
    )

    assert payload.tokens == 300
    assert payload.requestTime == 500
    assert payload.customData["model"] == "gemini-pro"
    assert payload.customData["provider"] == "google"
    assert payload.customData["tokens_input"] == 100
    assert payload.customData["tokens_output"] == 200


def test_google_extractor_never_sends_api_key():
    """Provider keys are never sent, even with capture_api_keys=True."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.text = "response"
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 10
    mock_response.usage_metadata.total_token_count = 20

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"
    mock_client._client = Mock()
    mock_client._client.api_key = "AIzaSy-test123"

    extractor = GoogleExtractor(capture_api_keys=True)
    payload = extractor.extract(
        request_kwargs={"contents": "test"},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert "api_key" not in payload.customData
    assert "AIzaSy-test123" not in str(payload)


def test_google_extractor_redacts_when_disabled():
    """Test that extractor redacts data when capture is disabled."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.text = "secret response"
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 10
    mock_response.usage_metadata.total_token_count = 20

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"
    mock_client._client = Mock()
    mock_client._client.api_key = "AIzaSy-secret"

    extractor = GoogleExtractor(
        capture_inputs=False,
        capture_outputs=False,
        capture_api_keys=False,
    )

    payload = extractor.extract(
        request_kwargs={"contents": "secret prompt"},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert payload.prompt == "[redacted]"
    assert payload.response == "[redacted]"
    assert "api_key" not in payload.customData


def test_google_extractor_merges_context():
    """Test that extractor merges context metadata."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )
    from src.olakaisdk.context import OlakaiContextData

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.text = "response"
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 10
    mock_response.usage_metadata.total_token_count = 20

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    context = OlakaiContextData(
        userEmail="user@example.com",
        task="Support",
        customData={"env": "prod", "tier": 5},
    )

    extractor = GoogleExtractor()
    payload = extractor.extract(
        request_kwargs={"contents": "test"},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=context,
    )

    assert payload.userEmail == "user@example.com"
    assert payload.task == "Support"
    assert payload.customData["env"] == "prod"
    assert payload.customData["model"] == "gemini-pro"
    assert payload.customData["tier"] == 5
    assert payload.customData["tokens_total"] == 20


def test_google_extractor_handles_string_prompt():
    """Test that extractor handles string prompt correctly."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.text = "response"
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 5
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 10

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    extractor = GoogleExtractor()
    payload = extractor.extract(
        request_kwargs={"contents": "What is Python?"},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert payload.prompt == "What is Python?"


def test_google_extractor_handles_list_prompt():
    """Test that extractor handles list-based prompt correctly."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock()
    mock_response.text = "response"
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.prompt_token_count = 5
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 10

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    extractor = GoogleExtractor()
    payload = extractor.extract(
        request_kwargs={
            "contents": [
                {"parts": [{"text": "Hello"}, {"text": "World"}]}
            ]
        },
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert payload.prompt == "Hello World"


def test_google_extractor_handles_missing_usage():
    """Test that extractor handles missing usage_metadata gracefully."""
    from src.olakaisdk.extractors.google_extractor import (
        GoogleExtractor,
    )

    olakai_config("test-key")

    mock_response = Mock(spec=[])
    mock_response.text = "response"

    mock_client = Mock()
    mock_client.model_name = "gemini-pro"

    extractor = GoogleExtractor()
    payload = extractor.extract(
        request_kwargs={"contents": "test"},
        response=mock_response,
        client_instance=mock_client,
        duration_ms=100,
        context=None,
    )

    assert payload.tokens == 0
    assert payload.customData["tokens_input"] == 0
    assert payload.customData["tokens_output"] == 0
