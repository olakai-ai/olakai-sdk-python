"""Google Generative AI SDK instrumentation via monkey patching."""

import time
import warnings
from typing import Any, Callable, Iterator, Optional

from ..config import require_config, get_config
from ..context import get_current_context
from ..extractors.google_extractor import GoogleExtractor
from ..client.api import enqueue_monitoring
from ..shared.types import MonitorPayload

# Store original methods
_original_sync_generate = None
_original_async_generate = None
_is_instrumented = False
_instrumentation_options = {}


def instrument_google(
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    capture_api_keys: Optional[bool] = None,
) -> None:
    """
    Instrument Google Generative AI SDK for automatic monitoring.

    This uses monkey patching to wrap GenerativeModel.generate_content
    methods (both sync and async) to automatically capture telemetry.

    Args:
        capture_inputs: Capture prompt/messages (default: True)
        capture_outputs: Capture responses (default: True)
        capture_api_keys: Deprecated, ignored. The SDK never sends
            provider API keys. Passing True emits a DeprecationWarning.

    Raises:
        RuntimeError: If SDK not configured with olakai_config()
        ImportError: If Google Generative AI SDK is not installed

    Example:
        >>> from olakaisdk import olakai_config, instrument_google
        >>> olakai_config("your-api-key")
        >>> instrument_google()
        >>> # Now all Google GenAI calls are automatically monitored
    """
    global _original_sync_generate, _original_async_generate
    global _is_instrumented, _instrumentation_options

    if _is_instrumented:
        config = get_config()
        if config and config.debug:
            print(
                "[Olakai SDK] Google GenAI already instrumented, skipping"
            )
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
        from google.generativeai import GenerativeModel
    except ImportError:
        raise ImportError(
            "Google Generative AI SDK not installed. "
            "Install with: pip install google-generativeai"
        )

    # Store original sync method
    _original_sync_generate = GenerativeModel.generate_content

    # Wrap sync method
    def wrapped_sync_generate(self, *args, **kwargs):
        """Wrapped synchronous generate_content method."""
        return _trace_google_call_sync(
            self,
            _original_sync_generate,
            args,
            kwargs,
            capture_inputs,
            capture_outputs,
            capture_api_keys,
        )

    # Apply sync patch
    GenerativeModel.generate_content = wrapped_sync_generate

    # Wrap async method if it exists
    if hasattr(GenerativeModel, "generate_content_async"):
        _original_async_generate = (
            GenerativeModel.generate_content_async
        )

        async def wrapped_async_generate(self, *args, **kwargs):
            """Wrapped asynchronous generate_content method."""
            return await _trace_google_call_async(
                self,
                _original_async_generate,
                args,
                kwargs,
                capture_inputs,
                capture_outputs,
                capture_api_keys,
            )

        GenerativeModel.generate_content_async = (
            wrapped_async_generate
        )

    _is_instrumented = True

    if config.debug:
        print(
            "[Olakai SDK] Google Generative AI SDK "
            "instrumented successfully"
        )


def uninstrument_google() -> None:
    """
    Remove Google Generative AI instrumentation.

    Restores original GenerativeModel methods.
    """
    global _is_instrumented
    global _original_sync_generate, _original_async_generate

    if not _is_instrumented:
        return

    try:
        from google.generativeai import GenerativeModel

        # Restore originals
        if _original_sync_generate:
            GenerativeModel.generate_content = (
                _original_sync_generate
            )

        if _original_async_generate and hasattr(
            GenerativeModel, "generate_content_async"
        ):
            GenerativeModel.generate_content_async = (
                _original_async_generate
            )

        _is_instrumented = False

        config = get_config()
        if config and config.debug:
            print(
                "[Olakai SDK] Google Generative AI SDK uninstrumented"
            )

    except ImportError:
        pass


def is_google_instrumented() -> bool:
    """
    Check if Google Generative AI is currently instrumented.

    Returns:
        True if instrumented, False otherwise
    """
    return _is_instrumented


def _trace_google_call_sync(
    client_instance: Any,
    original_method: Callable,
    args: tuple,
    kwargs: dict,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool,
) -> Any:
    """
    Trace a synchronous Google GenAI call.

    Handles both regular and streaming responses.
    """
    config = get_config()
    start_time = time.time()

    # Check if streaming
    is_streaming = kwargs.get("stream", False)

    # Build request_kwargs for the extractor
    # The first positional arg is the contents
    request_kwargs = dict(kwargs)
    if args:
        request_kwargs["contents"] = args[0]

    try:
        if is_streaming:
            response_stream = original_method(
                client_instance, *args, **kwargs
            )
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
            response = original_method(
                client_instance, *args, **kwargs
            )

            # Extract and send telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            extractor = GoogleExtractor(
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


async def _trace_google_call_async(
    client_instance: Any,
    original_method: Callable,
    args: tuple,
    kwargs: dict,
    capture_inputs: bool,
    capture_outputs: bool,
    capture_api_keys: bool,
) -> Any:
    """
    Trace an asynchronous Google GenAI call.

    Handles both regular and streaming responses.
    """
    config = get_config()
    start_time = time.time()

    # Check if streaming
    is_streaming = kwargs.get("stream", False)

    # Build request_kwargs for the extractor
    request_kwargs = dict(kwargs)
    if args:
        request_kwargs["contents"] = args[0]

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
            response = await original_method(
                client_instance, *args, **kwargs
            )

            # Extract and send telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            extractor = GoogleExtractor(
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

            extractor = GoogleExtractor(
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

            extractor = GoogleExtractor(
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
    Google GenAI response for the extractor to process.
    """
    content_parts = []

    for chunk in chunks:
        # Extract text from chunk
        if hasattr(chunk, "text"):
            try:
                text = chunk.text
                if text:
                    content_parts.append(text)
            except Exception:
                pass

        if hasattr(chunk, "candidates") and chunk.candidates:
            for candidate in chunk.candidates:
                if hasattr(candidate, "content"):
                    parts = getattr(candidate.content, "parts", [])
                    for part in parts:
                        if hasattr(part, "text") and part.text:
                            content_parts.append(part.text)

    class MockUsageMetadata:
        def __init__(self):
            self.prompt_token_count = 0
            self.candidates_token_count = 0
            self.total_token_count = 0

    class MockPart:
        def __init__(self, text):
            self.text = text

    class MockContent:
        def __init__(self, text):
            self.parts = [MockPart(text)]

    class MockCandidate:
        def __init__(self, text):
            self.content = MockContent(text)

    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.candidates = [MockCandidate(text)]
            self.usage_metadata = MockUsageMetadata()

    complete_text = "".join(content_parts)
    return MockResponse(complete_text)


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

        model = getattr(client_instance, "model_name", "unknown")
        custom_data.update(
            {
                "model": model,
                "provider": "google",
                "error_type": type(error).__name__,
            }
        )

        # Extract prompt text
        contents = request_kwargs.get("contents", "")
        prompt_str = (
            contents if isinstance(contents, str) else str(contents)
        )

        payload = MonitorPayload(
            userEmail=(
                context_data.userEmail if context_data else None
            )
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
            print(
                f"[Olakai SDK] Failed to send error "
                f"telemetry: {error}"
            )
