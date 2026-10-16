"""
Olakai SDK - Auto-instrumentation for LLM monitoring and tracking.

v0.5.0 introduces automatic instrumentation for OpenAI and other LLM providers.
"""

# New API (v0.5.0)
from .config import olakai_config, get_config, is_initialized
from .context import olakai_context, get_current_context
from .instrumentation import (
    instrument_openai,
    uninstrument_openai,
    is_openai_instrumented,
    instrument_google,
    uninstrument_google,
    is_google_instrumented,
    instrument_anthropic,
    uninstrument_anthropic,
    is_anthropic_instrumented,
)

# Legacy API (will be deprecated in future versions)
from .core import olakai, olakai_event, olakai_feedback, olakai_monitor
from .monitor import olakai_supervisor
from .client.api import olakai_flush

# Types
from .shared import (
    OlakaiBlockedError,
    MonitorOptions,
    OlakaiEventParams,
    OlakaiConfig,
)

__version__ = "1.7.0"

__all__ = [
    # Primary API (1.0.0)
    "olakai_config",  # Initialize SDK
    "instrument_openai",  # Auto-instrument OpenAI
    "uninstrument_openai",  # Remove OpenAI instrumentation
    "instrument_google",  # Auto-instrument Google GenAI
    "uninstrument_google",  # Remove Google GenAI instrumentation
    "is_google_instrumented",  # Check if Google GenAI is instrumented
    "instrument_anthropic",  # Auto-instrument Anthropic
    "uninstrument_anthropic",  # Remove Anthropic instrumentation
    "is_anthropic_instrumented",  # Check if Anthropic is instrumented
    "olakai_context",  # Context manager for metadata
    "get_config",  # Get current config
    "is_initialized",  # Check if initialized
    "is_openai_instrumented",  # Check if OpenAI is instrumented
    "get_current_context",  # Get current context data
    "olakai_event",
    "olakai_feedback",  # Report explicit user feedback
    "olakai_flush",  # Wait for queued telemetry to be sent
    # Legacy API (for backward compatibility)
    "olakai",
    "olakai_monitor",
    "olakai_supervisor",
    # Types
    "MonitorOptions",
    "OlakaiEventParams",
    "OlakaiConfig",
    "OlakaiBlockedError",
]
