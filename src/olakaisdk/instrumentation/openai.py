"""OpenAI SDK instrumentation via monkey patching."""

import time
import warnings
from typing import Any, Callable, Dict, Iterator, Optional

from ..config import require_config, get_config
from ..context import get_current_context
from ..extractors.openai_extractor import (
    OpenAIExtractor,
    detect_openai_provider,
)
from ..client.api import enqueue_monitoring
from ..shared.types import MonitorPayload

# Store original methods
_original_sync_create = None
_original_async_create = None
_is_instrumented = False
_instrumentation_options: Dict[str, Any] = {}


def instrument_openai(
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    capture_api_keys: Optional[bool] = None
) -> None:
    """
    Instrument OpenAI SDK for automatic monitoring.

    This uses monkey patching to wrap OpenAI's chat.completions.create
    methods (both sync and async) to automatically capture telemetry.

    Args:
        capture_inputs: Capture prompt/messages (default: True)
        capture_outputs: Capture responses (default: True)
        capture_api_keys: Deprecated, ignored. The SDK never sends
            provider API keys. Passing True emits a DeprecationWarning.

    Raises:
        RuntimeError: If SDK not configured with olakai_config()
        ImportError: If OpenAI SDK is not installed

    Example:
        >>> from olakaisdk import olakai_config, instrument_openai
        >>> olakai_config("your-api-key")
        >>> instrument_openai()
        >>> # Now all OpenAI calls are automatically monitored
    """
    global _original_sync_create, _original_async_create, _is_instrumented, _instrumentation_options

    if _is_instrumented:
        config = get_config()
        if config and config.debug:
            print("[Olakai SDK] OpenAI already instrumented, skipping")
        return

    # Verify SDK is configured
    config = require_config()

    if capture_api_keys:
        warnings.warn(
            "capture_api_keys is deprecated and ignored: the Olakai SDK "
            "never sends provider API keys.",
            DeprecationWarning,
            stacklevel=2,
        )
    capture_api_keys = False

    # Store instrumentation options
    _instrumentation_options = {
        "capture_inputs": capture_inputs,
        "capture_outputs": capture_outputs,
        "capture_api_keys": capture_api_keys,
    }

    try:
        from openai.resources.chat import completions
    except ImportError:
        raise ImportError(
            "OpenAI SDK not installed. Install with: pip install openai"
        )

    # Store originals
    _original_sync_create = completions.Completions.create

    # Wrap sync method
    def wrapped_sync_create(self, *args, **kwargs):
        """Wrapped synchronous create method."""
        return _trace_openai_call_sync(
            self,
            _original_sync_create,
            args,
            kwargs,
            capture_inputs,
            capture_outputs,
            capture_api_keys
        )

    # Apply sync patch
    completions.Completions.create = wrapped_sync_create

    # Wrap async method if it exists
    if hasattr(completions, "AsyncCompletions"):
        _original_async_create = completions.AsyncCompletions.create

        async def wrapped_async_create(self, *args, **kwargs):
            """Wrapped asynchronous create method."""
            return await _trace_openai_call_async(
                self,
                _original_async_create,
                args,
                kwargs,
                capture_inputs,
                capture_outputs,
                capture_api_keys
            )

        completions.AsyncCompletions.create = wrapped_async_create

    _is_instrumented = True

    if config.debug:
        print("[Olakai SDK] OpenAI SDK instrumented successfully")


def uninstrument_openai() -> None:
    """
    Remove OpenAI instrumentation.

    Restores original OpenAI methods.
    """
    global _is_instrumented, _original_sync_create, _original_async_create

    if not _is_instrumented:
        return

    try:
        from openai.resources.chat import completions

        # Restore originals
        if _original_sync_create:
            completions.Completions.create = _original_sync_create

        if _original_async_create and hasattr(completions, "AsyncCompletions"):
            completions.AsyncCompletions.create = _original_async_create

        _is_instrumented = False

        config = get_config()
        if config and config.debug:
            print("[Olakai SDK] OpenAI SDK uninstrumented")

    except ImportError:
        pass


def is_openai_instrumented() -> bool:
    """
    Check if OpenAI is currently instrumented.

    Returns:
        True if instrumented, False otherwise
    """
    return _is_instrumented


def _trace_openai_call_sync(
    client_instance: Any,
    original_method: Callable,
    args: tuple,
    kwargs: dict,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool
) -> Any:
    """
    Trace a synchronous OpenAI call.

    Handles both regular and streaming responses.
    """
    config = get_config()
    start_time = time.time()

    # Check if streaming
    is_streaming = kwargs.get("stream", False)

    try:
        if is_streaming:
            # Handle streaming: wrap the generator
            response_stream = original_method(client_instance, *args, **kwargs)
            return _wrap_stream_sync(
                response_stream,
                client_instance,
                kwargs,
                start_time,
                capture_inputs,
                capture_outputs,
                capture_api_keys
            )
        else:
            # Regular non-streaming call
            response = original_method(client_instance, *args, **kwargs)

            # Extract and send telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            extractor = OpenAIExtractor(capture_inputs, capture_outputs, capture_api_keys)
            payload = extractor.extract(
                request_kwargs=kwargs,
                response=response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context()
            )

            # Get sessionId from config
            payload.chatId = config.sessionId

            # Send telemetry (fire-and-forget)
            _send_telemetry_sync(payload)

            return response

    except Exception as e:
        # Track error
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(kwargs, client_instance, e, duration_ms, capture_api_keys)
        raise


async def _trace_openai_call_async(
    client_instance: Any,
    original_method: Callable,
    args: tuple,
    kwargs: dict,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool
) -> Any:
    """
    Trace an asynchronous OpenAI call.

    Handles both regular and streaming responses.
    """
    config = get_config()
    start_time = time.time()

    # Check if streaming
    is_streaming = kwargs.get("stream", False)

    try:
        if is_streaming:
            # Handle streaming: wrap the async generator
            response_stream = await original_method(client_instance, *args, **kwargs)
            return _wrap_stream_async(
                response_stream,
                client_instance,
                kwargs,
                start_time,
                capture_inputs,
                capture_outputs,
                capture_api_keys
            )
        else:
            # Regular non-streaming call
            response = await original_method(client_instance, *args, **kwargs)

            # Extract and send telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            extractor = OpenAIExtractor(capture_inputs, capture_outputs, capture_api_keys)
            payload = extractor.extract(
                request_kwargs=kwargs,
                response=response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context()
            )
            # Get sessionId from config
            payload.chatId = config.sessionId

            # Send telemetry (fire-and-forget)
            enqueue_monitoring(config, payload)

            return response

    except Exception as e:
        # Track error
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(kwargs, client_instance, e, duration_ms, capture_api_keys)
        raise


def _wrap_stream_sync(
    stream: Iterator,
    client_instance: Any,
    request_kwargs: dict,
    start_time: float,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool
) -> Iterator:
    """
    Wrap a synchronous streaming response to collect telemetry.

    Buffers all chunks, yields them to the user, then sends telemetry
    when the stream is complete.
    """
    chunks = []

    try:
        for chunk in stream:
            chunks.append(chunk)
            yield chunk  # Pass through to user

        # Stream complete - reconstruct response and send telemetry
        if chunks:
            complete_response = _reconstruct_from_chunks(chunks)
            duration_ms = int((time.time() - start_time) * 1000)

            extractor = OpenAIExtractor(capture_inputs, capture_outputs, capture_api_keys)
            payload = extractor.extract(
                request_kwargs=request_kwargs,
                response=complete_response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context()
            )

            _send_telemetry_sync(payload)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(request_kwargs, client_instance, e, duration_ms, capture_api_keys)
        raise


async def _wrap_stream_async(
    stream: Any,
    client_instance: Any,
    request_kwargs: dict,
    start_time: float,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool
) -> Any:
    """
    Wrap an asynchronous streaming response to collect telemetry.

    Buffers all chunks, yields them to the user, then sends telemetry
    when the stream is complete.
    """
    chunks = []

    try:
        async for chunk in stream:
            chunks.append(chunk)
            yield chunk  # Pass through to user

        # Stream complete - reconstruct response and send telemetry
        if chunks:
            complete_response = _reconstruct_from_chunks(chunks)
            duration_ms = int((time.time() - start_time) * 1000)

            extractor = OpenAIExtractor(capture_inputs, capture_outputs, capture_api_keys)
            payload = extractor.extract(
                request_kwargs=request_kwargs,
                response=complete_response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context()
            )

            config = get_config()
            if config:
                # Get sessionId from config
                payload.chatId = config.sessionId
                enqueue_monitoring(config, payload)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(request_kwargs, client_instance, e, duration_ms, capture_api_keys)
        raise


def _reconstruct_from_chunks(chunks: list) -> Any:
    """
    Reconstruct a complete response object from streaming chunks.

    This creates a mock response object that looks like a regular
    OpenAI response for the extractor to process.
    """
    # Aggregate content from all chunks
    content_parts = []
    model = None
    finish_reason = None

    for chunk in chunks:
        if hasattr(chunk, "model"):
            model = chunk.model

        if hasattr(chunk, "choices") and len(chunk.choices) > 0:
            choice = chunk.choices[0]
            if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                if choice.delta.content:
                    content_parts.append(choice.delta.content)
            if hasattr(choice, "finish_reason") and choice.finish_reason:
                finish_reason = choice.finish_reason

    # Build a mock response object
    class MockMessage:
        def __init__(self, content):
            self.content = content
            self.role = "assistant"

    class MockChoice:
        def __init__(self, message, finish_reason):
            self.message = message
            self.finish_reason = finish_reason or "stop"

    class MockUsage:
        def __init__(self):
            # Note: Streaming doesn't provide token counts in chunks
            # These will be 0, backend will need to calculate
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.total_tokens = 0

    class MockResponse:
        def __init__(self, content, model):
            self.choices = [MockChoice(MockMessage(content), finish_reason)]
            self.model = model or "unknown"
            self.usage = MockUsage()

    complete_content = "".join(content_parts)
    return MockResponse(complete_content, model)


def _send_telemetry_sync(payload: MonitorPayload) -> None:
    """Send telemetry in background (fire-and-forget for sync calls)."""
    config = get_config()
    if not config:
        return

    enqueue_monitoring(config, payload)


def _send_error_telemetry(
    request_kwargs: dict,
    client_instance: Any,
    error: Exception,
    duration_ms: int,
    capture_api_keys: bool
) -> None:
    """Send error telemetry."""
    config = get_config()
    if not config:
        return

    try:
        context_data = get_current_context()

        custom_data = {}
        if context_data:
            custom_data = dict(context_data.customData or {})

        custom_data.update({
            "model": request_kwargs.get("model", "unknown"),
            "provider": detect_openai_provider(client_instance),
            "error_type": type(error).__name__,
        })

        payload = MonitorPayload(
            userEmail=(context_data.userEmail if context_data else None) or "anonymous@olakai.ai",
            chatId=config.sessionId,
            prompt=str(request_kwargs.get("messages", [])),
            response=f"Error: {str(error)}",
            tokens=0,
            requestTime=duration_ms,
            task=context_data.task if context_data else None,
            subTask=context_data.subTask if context_data else None,
            customData=custom_data,
            errorMessage=str(error),
            shouldScore=False
        )

        _send_telemetry_sync(payload)

    except Exception:
        # Don't let telemetry errors affect the application
        if config.debug:
            print(f"[Olakai SDK] Failed to send error telemetry: {error}")
