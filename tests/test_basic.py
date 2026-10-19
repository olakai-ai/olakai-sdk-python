"""Tests for the simplified olakaisdk package."""

import pytest
import asyncio
from src.olakaisdk import OlakaiEventParams, __version__


def test_version():
    """Test that version is accessible."""
    assert __version__ == "1.8.0"


def test_import():
    """Test that main functions can be imported."""
    from src.olakaisdk import (
        olakai_config,
        olakai_monitor,
        olakai_event,
        olakai,
    )

    assert callable(olakai_config)
    assert callable(olakai_monitor)
    assert callable(olakai_event)
    assert callable(olakai)


def test_olakai_config():
    """Test olakai_config function."""
    from src.olakaisdk import olakai_config, get_config

    # Test basic configuration
    olakai_config("test-api-key", "https://test.com", debug=True)

    config = get_config()
    assert config is not None
    assert config.api_key == "test-api-key"
    assert config.endpoint == "https://test.com"
    assert config.debug is True


def test_olakai_config_missing_api_key():
    """Test that missing API key raises error."""
    from src.olakaisdk import olakai_config
    from src.olakaisdk.shared.exceptions import APIKeyMissingError

    with pytest.raises(APIKeyMissingError):
        olakai_config("", "https://test.com")


def test_monitor_decorator():
    """Test that the monitor decorator can be applied."""
    from src.olakaisdk import olakai_monitor, olakai_config

    olakai_config("test-key", "https://test.com")

    @olakai_monitor()
    def test_function(x: int) -> int:
        return x * 2

    # Test that the function still works when wrapped
    result = test_function(5)
    assert result == 10


def test_monitor_decorator_with_options():
    """Test monitor decorator with custom options."""
    from src.olakaisdk import olakai_monitor, olakai_config

    olakai_config("test-key", "https://test.com")

    @olakai_monitor(
        userEmail="test@example.com",
        userId="user-123",
        task="test-task",
        customData={"env": "test", "score": 0.95},
    )
    def test_function_with_options(x: int) -> int:
        return x + 10

    result = test_function_with_options(5)
    assert result == 15


def test_monitor_decorator_error_handling():
    """Test that monitor decorator doesn't break error propagation."""
    from src.olakaisdk import olakai_monitor, olakai_config

    olakai_config("test-key", "https://test.com")

    @olakai_monitor()
    def error_function():
        raise ValueError("Test error")

    # Test that errors are still raised
    with pytest.raises(ValueError, match="Test error"):
        error_function()


def test_async_monitor_decorator():
    """Test monitor decorator with async functions."""
    from src.olakaisdk import olakai_monitor, olakai_config

    olakai_config("test-key", "https://test.com")

    @olakai_monitor()
    async def async_test_function(x: int) -> int:
        return x * 3

    # Test that the async function still works when wrapped
    result = asyncio.run(async_test_function(4))
    assert result == 12


def test_olakai_event():
    """Test olakai_event function."""
    from src.olakaisdk import olakai_event, olakai_config

    olakai_config("test-key", "https://test.com")

    params = OlakaiEventParams(
        prompt="Test prompt",
        response="Test response",
        userEmail="test@example.com",
        task="test-task",
    )

    # Test basic reporting
    olakai_event(params)


def test_olakai_event_with_custom_data():
    """Test olakai event function."""
    from src.olakaisdk import olakai, olakai_config, OlakaiEventParams

    olakai_config("test-key", "https://test.com")

    params = OlakaiEventParams(
        prompt="Test prompt",
        response="Test response",
        userEmail="test@example.com",
        task="test-task",
        customData={"dim1": "test", "metric1": 0.95},
    )

    # Test event tracking
    olakai(params)


def test_types_import():
    """Test that types can be imported."""
    from src.olakaisdk import OlakaiConfig, OlakaiEventParams, MonitorOptions

    # Test basic instantiation
    config = OlakaiConfig(api_key="test", endpoint="https://test.com")
    assert config.api_key == "test"

    event_params = OlakaiEventParams(
        prompt="test",
        response="response",
        userEmail="test@example.com",
    )
    assert event_params.prompt == "test"

    monitor_opts = MonitorOptions(task="test-task")
    assert monitor_opts.task == "test-task"


def test_legacy_compatibility():
    """Test that legacy functions still work.

    Note: In sync context without an event loop, API calls are skipped
    but the function still returns correctly.
    """
    from src.olakaisdk import olakai_supervisor, olakai_config

    olakai_config("test-key", "https://test.com")

    # Test legacy decorator
    @olakai_supervisor()
    def legacy_function(x: int) -> int:
        return x * 2

    # Function works even without event loop (API calls skipped gracefully)
    result = legacy_function(5)
    assert result == 10


def test_get_config():
    """Test get_config function."""
    from src.olakaisdk import get_config, olakai_config

    # Initialize with specific config
    olakai_config(api_key="config_test_key", endpoint="https://test.com")

    config = get_config()
    assert config is not None
    assert config.api_key == "config_test_key"
    assert config.endpoint == "https://test.com"


def test_all_exports():
    """Test that all expected exports are available."""
    import src.olakaisdk

    expected_exports = [
        "olakai_config",
        "olakai_monitor",
        "olakai_event",
        "olakai",
        "get_config",
        "MonitorOptions",
        "OlakaiEventParams",
        "OlakaiConfig",
        "OlakaiBlockedError",
        "olakai_supervisor",  # Legacy
    ]

    for export in expected_exports:
        assert hasattr(src.olakaisdk, export), f"Missing export: {export}"


def test_api_integration():
    """Test that monitored functions work correctly.

    Note: In sync context without a running event loop, API calls are
    skipped gracefully but the function still executes and returns.
    """
    from src.olakaisdk import olakai_config, olakai_monitor

    olakai_config("test-key", "https://test.com")

    @olakai_monitor()
    def test_function():
        return "test result"

    # Call the function - it should work even without event loop
    result = test_function()
    assert result == "test result"


def test_custom_data():
    """Test custom data functionality."""
    from src.olakaisdk import olakai_monitor, olakai_config, OlakaiEventParams

    olakai_config("test-key", "https://test.com")

    @olakai_monitor(
        customData={
            "model": "gpt-4",
            "language": "en",
            "tokens": 150,
            "latency": 2.5,
        }
    )
    def test_function():
        return "response"

    result = test_function()
    assert result == "response"

    # Test OlakaiEventParams with custom data
    params = OlakaiEventParams(
        prompt="test",
        response="response",
        customData={"dim1": "production", "metric1": 0.95},
    )

    assert params.customData["dim1"] == "production"
    assert params.customData["metric1"] == 0.95
