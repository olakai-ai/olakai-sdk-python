"""Anthropic SDK instrumentation via monkey patching."""

import time
import warnings
from typing import Any, Callable, Iterator, Optional

from ..config import require_config, get_config
from ..context import get_current_context
from ..extractors.anthropic_extractor import AnthropicExtractor
from ..client.api import enqueue_monitoring
from ..shared.types import MonitorPayload

# Store original methods
_original_sync_create = None
_original_async_create = None
_is_instrumented = False
_instrumentation_options = {}


def instrument_anthropic(
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    capture_api_keys: Optional[bool] = None,
) -> None:
    """
    Instrument Anthropic SDK for automatic monitoring.

    This uses monkey patching to wrap Messages.create
    methods (both sync and async) to automatically capture telemetry.

    Args:
        capture_inputs: Capture prompt/messages (default: True)
        capture_outputs: Capture responses (default: True)
        capture_api_keys: Deprecated, ignored. The SDK never sends
            provider API keys. Passing True emits a DeprecationWarning.

    Raises:
        RuntimeError: If SDK not configured with olakai_config()
        ImportError: If Anthropic SDK is not installed

    Example:
        >>> from olakaisdk import olakai_config, instrument_anthropic
        >>> olakai_config("your-api-key")
        >>> instrument_anthropic()
        >>> # Now all Anthropic calls are automatically monitored
    """
    global _original_sync_create, _original_async_create
    global _is_instrumented, _instrumentation_options

    if _is_instrumented:
        config = get_config()
        if config and config.debug:
            print("[Olakai SDK] Anthropic already instrumented, skipping")
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
        from anthropic.resources.messages import (
            Messages,
            AsyncMessages,
        )
    except ImportError:
        raise ImportError(
            "Anthropic SDK not installed. Install with: pip install anthropic"
        )

    # Store original sync method
    _original_sync_create = Messages.create

    # Wrap sync method
    def wrapped_sync_create(self, *args, **kwargs):
        """Wrapped synchronous messages.create method."""
        return _trace_anthropic_call_sync(
            self,
            _original_sync_create,
            args,
            kwargs,
            capture_inputs,
            capture_outputs,
            capture_api_keys,
        )

    # Apply sync patch
    Messages.create = wrapped_sync_create

    # Store original async method
    _original_async_create = AsyncMessages.create

    # Wrap async method
    async def wrapped_async_create(self, *args, **kwargs):
        """Wrapped asynchronous messages.create method."""
        return await _trace_anthropic_call_async(
            self,
            _original_async_create,
            args,
            kwargs,
            capture_inputs,
            capture_outputs,
            capture_api_keys,
        )

    # Apply async patch
    AsyncMessages.create = wrapped_async_create

    _is_instrumented = True

    if config.debug:
        print("[Olakai SDK] Anthropic SDK instrumented successfully")


def uninstrument_anthropic() -> None:
    """
    Remove Anthropic instrumentation.

    Restores original Messages methods.
    """
    global _is_instrumented
    global _original_sync_create, _original_async_create

    if not _is_instrumented:
        return

    try:
        from anthropic.resources.messages import (
            Messages,
            AsyncMessages,
        )

        # Restore originals
        if _original_sync_create:
            Messages.create = _original_sync_create

        if _original_async_create:
            AsyncMessages.create = _original_async_create

        _is_instrumented = False

        config = get_config()
        if config and config.debug:
            print("[Olakai SDK] Anthropic SDK uninstrumented")

    except ImportError:
        pass


def is_anthropic_instrumented() -> bool:
    """
    Check if Anthropic is currently instrumented.

    Returns:
        True if instrumented, False otherwise
    """
    return _is_instrumented


def _trace_anthropic_call_sync(
    client_instance: Any,
    original_method: Callable,
    args: tuple,
    kwargs: dict,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool,
) -> Any:
    """
    Trace a synchronous Anthropic call.

    Handles both regular and streaming responses.
    """
    config = get_config()
    start_time = time.time()

    # Check if streaming
    is_streaming = kwargs.get("stream", False)

    # Build request_kwargs for the extractor
    request_kwargs = dict(kwargs)

    try:
        if is_streaming:
            response_stream = original_method(client_instance, *args, **kwargs)
            return _wrap_stream_sync(
                response_stream,
                client_instance,
                request_kwargs,
                start_time,
                capture_inputs,
                capture_outputs,
                capture_api_keys,
            )
        else:
            response = original_method(client_instance, *args, **kwargs)

            # Extract and send telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            extractor = AnthropicExtractor(
                capture_inputs, capture_outputs, capture_api_keys
            )
            payload = extractor.extract(
                request_kwargs=request_kwargs,
                response=response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context(),
            )

            # Get sessionId from config
            payload.chatId = config.sessionId

            # Send telemetry (fire-and-forget)
            _send_telemetry_sync(payload)

            return response

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(
            request_kwargs,
            client_instance,
            e,
            duration_ms,
            capture_api_keys,
        )
        raise


async def _trace_anthropic_call_async(
    client_instance: Any,
    original_method: Callable,
    args: tuple,
    kwargs: dict,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool,
) -> Any:
    """
    Trace an asynchronous Anthropic call.

    Handles both regular and streaming responses.
    """
    config = get_config()
    start_time = time.time()

    # Check if streaming
    is_streaming = kwargs.get("stream", False)

    # Build request_kwargs for the extractor
    request_kwargs = dict(kwargs)

    try:
        if is_streaming:
            response_stream = await original_method(
                client_instance, *args, **kwargs
            )
            return _wrap_stream_async(
                response_stream,
                client_instance,
                request_kwargs,
                start_time,
                capture_inputs,
                capture_outputs,
                capture_api_keys,
            )
        else:
            response = await original_method(client_instance, *args, **kwargs)

            # Extract and send telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            extractor = AnthropicExtractor(
                capture_inputs, capture_outputs, capture_api_keys
            )
            payload = extractor.extract(
                request_kwargs=request_kwargs,
                response=response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context(),
            )

            # Get sessionId from config
            payload.chatId = config.sessionId

            # Send telemetry (fire-and-forget)
            enqueue_monitoring(config, payload)

            return response

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(
            request_kwargs,
            client_instance,
            e,
            duration_ms,
            capture_api_keys,
        )
        raise


def _wrap_stream_sync(
    stream: Iterator,
    client_instance: Any,
    request_kwargs: dict,
    start_time: float,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool,
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
            yield chunk

        # Stream complete - reconstruct response and send telemetry
        if chunks:
            complete_response = _reconstruct_from_chunks(chunks)
            duration_ms = int((time.time() - start_time) * 1000)

            extractor = AnthropicExtractor(
                capture_inputs, capture_outputs, capture_api_keys
            )
            payload = extractor.extract(
                request_kwargs=request_kwargs,
                response=complete_response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context(),
            )

            _send_telemetry_sync(payload)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(
            request_kwargs,
            client_instance,
            e,
            duration_ms,
            capture_api_keys,
        )
        raise


async def _wrap_stream_async(
    stream: Any,
    client_instance: Any,
    request_kwargs: dict,
    start_time: float,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool,
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
            yield chunk

        # Stream complete - reconstruct and send telemetry
        if chunks:
            complete_response = _reconstruct_from_chunks(chunks)
            duration_ms = int((time.time() - start_time) * 1000)

            extractor = AnthropicExtractor(
                capture_inputs, capture_outputs, capture_api_keys
            )
            payload = extractor.extract(
                request_kwargs=request_kwargs,
                response=complete_response,
                client_instance=client_instance,
                duration_ms=duration_ms,
                context=get_current_context(),
            )

            config = get_config()
            if config:
                payload.chatId = config.sessionId
                enqueue_monitoring(config, payload)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _send_error_telemetry(
            request_kwargs,
            client_instance,
            e,
            duration_ms,
            capture_api_keys,
        )
        raise


def _reconstruct_from_chunks(chunks: list) -> Any:
    """
    Reconstruct a complete response object from streaming chunks.

    Creates a mock response object that looks like a regular
    Anthropic response for the extractor to process.

    Anthropic streaming events include:
    - message_start: contains the message object with model info
    - content_block_start: starts a content block
    - content_block_delta: contains text delta
    - content_block_stop: ends a content block
    - message_delta: contains stop_reason and usage
    - message_stop: end of message
    """
    content_parts = []
    model = None
    input_tokens = 0
    output_tokens = 0

    for chunk in chunks:
        # Extract text from content_block_delta events
        if hasattr(chunk, "type"):
            if chunk.type == "content_block_delta":
                delta = getattr(chunk, "delta", None)
                if delta and hasattr(delta, "text"):
                    text = delta.text
                    if text:
                        content_parts.append(text)

            elif chunk.type == "message_start":
                message = getattr(chunk, "message", None)
                if message:
                    model = getattr(message, "model", None)
                    usage = getattr(message, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "input_tokens", 0) or 0

            elif chunk.type == "message_delta":
                usage = getattr(chunk, "usage", None)
                if usage:
                    output_tokens = getattr(usage, "output_tokens", 0) or 0

    class MockTextBlock:
        def __init__(self, text):
            self.text = text
            self.type = "text"

    class MockUsage:
        def __init__(self, input_tokens, output_tokens):
            self.input_tokens = input_tokens
            self.output_tokens = output_tokens

    class MockResponse:
        def __init__(self, text, model, input_tokens, output_tokens):
            self.content = [MockTextBlock(text)]
            self.model = model or "unknown"
            self.usage = MockUsage(input_tokens, output_tokens)
            self.role = "assistant"
            self.stop_reason = "end_turn"

    complete_text = "".join(content_parts)
    return MockResponse(complete_text, model, input_tokens, output_tokens)


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
    capture_api_keys: bool,
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

        model = request_kwargs.get("model", "unknown")
        custom_data.update(
            {
                "model": model,
                "provider": "anthropic",
                "error_type": type(error).__name__,
            }
        )

        # Extract prompt text from messages
        messages = request_kwargs.get("messages", [])
        prompt_str = str(messages) if messages else ""

        payload = MonitorPayload(
            userEmail=(context_data.userEmail if context_data else None)
            or "anonymous@olakai.ai",
            chatId=config.sessionId,
            prompt=prompt_str,
            response=f"Error: {str(error)}",
            tokens=0,
            requestTime=duration_ms,
            task=context_data.task if context_data else None,
            subTask=context_data.subTask if context_data else None,
            customData=custom_data,
            errorMessage=str(error),
            shouldScore=False,
        )

        _send_telemetry_sync(payload)

    except Exception:
        if config.debug:
            print(f"[Olakai SDK] Failed to send error telemetry: {error}")
