"""
Core simplified API for the Olakai SDK.
"""

import time
import asyncio
from typing import Any, Callable, Dict, Literal, Optional, Union
from .shared.types import OlakaiEventParams, MonitorPayload
from .client.api import (
    enqueue_monitoring,
    enqueue_send,
    send_feedback_to_api,
)
from .config import get_config, require_config


def olakai(params: OlakaiEventParams) -> None:
    """
    Track an event with the Olakai API.

    Args:
        params: Event parameters
    """
    config = require_config()

    # Convert to MonitorPayload for API compatibility
    payload = MonitorPayload(
        userEmail=params.userEmail or "anonymous@olakai.ai",
        chatId=params.sessionId or config.sessionId,
        taskExecutionId=params.taskExecutionId,
        prompt=params.prompt,
        response=params.response,
        tokens=params.tokens,
        requestTime=params.requestTime,
        task=params.task,
        subTask=params.subTask,
        customData=params.customData,
        shouldScore=params.shouldScore,
        modelName=params.modelName,
    )

    # Fire-and-forget via the background sender (works with or without
    # a running event loop; never blocks the caller)
    enqueue_monitoring(config, payload)


def olakai_event(params: OlakaiEventParams) -> None:
    """
    Direct reporting function for simple event tracking.

    Args:
        params: The input data
    """

    olakai(params)


FeedbackRating = Literal["UP", "DOWN"]


def olakai_feedback(
    session_id: str,
    rating: FeedbackRating,
    *,
    turn_index: Optional[int] = None,
    comment: Optional[str] = None,
    user_email: Optional[str] = None,
    custom_data: Optional[Dict[str, Union[str, int, float, bool, None]]] = None,
) -> None:
    """Report explicit user feedback on a prior agent interaction.

    Fire-and-forget, like ``olakai_event()``. Never raises — any
    configuration or transport errors are swallowed so that user
    code is not affected.

    Posts directly to the dedicated ``/api/monitoring/feedback``
    endpoint. The Olakai backend resolves the target interaction
    via session inference (most recent ``PromptRequest`` with
    ``chatId == session_id``) and persists the feedback to the
    ``UserFeedback`` table with a proper FK — no ``PromptRequest``
    row is created and ``customData`` is not polluted.

    Args:
        session_id: The session/conversation ID of the interaction
            being rated. Should match the ``sessionId`` used when
            reporting the original event.
        rating: ``"UP"`` or ``"DOWN"`` — the user's feedback.
        turn_index: Optional zero-based turn index within the
            session, for turn-level feedback correlation.
        comment: Optional free-text comment alongside the rating.
        user_email: Optional override for the user who gave the
            feedback.
        custom_data: Accepted for signature backward compatibility
            with v1.4.0, but no longer forwarded to the server —
            the dedicated feedback endpoint owns the schema.

    Example:
        >>> olakai_feedback(
        ...     session_id="chat_abc123",
        ...     rating="UP",
        ...     turn_index=3,
        ...     comment="Very helpful answer",
        ... )
    """
    # Silence unused-arg warning — intentionally accepted for signature
    # parity with v1.4.0 but not forwarded to the wire.
    del custom_data

    try:
        config = get_config()
        if config is None:
            # SDK not initialized — nothing to do. Stay silent (no
            # debug config to honour).
            return

        # Build a clean wire payload. Only include optional keys when
        # they have a value — mirrors the TypeScript SDK exactly.
        payload: Dict[str, Any] = {
            "sessionId": session_id,
            "rating": rating,
        }
        if turn_index is not None:
            payload["turnIndex"] = turn_index
        if comment is not None:
            payload["comment"] = comment
        if user_email is not None:
            payload["email"] = user_email

        if config.debug:
            print(
                f"[Olakai SDK] Sending feedback: "
                f"sessionId={session_id} rating={rating} "
                f"turnIndex={turn_index}"
            )

        # Fire-and-forget via the background sender.
        enqueue_send(config, lambda: send_feedback_to_api(config, payload))
    except Exception as e:  # noqa: BLE001 - fire-and-forget
        # Never raise from feedback reporting. Best-effort debug log
        # only if the SDK is configured with debug=True.
        try:
            config = get_config()
            if config is not None and config.debug:
                print(f"[Olakai SDK] olakai_feedback failed: {e}")
        except Exception:
            pass


def olakai_monitor(fn: Callable = None, **options):
    """
    Decorator for automatic function monitoring.

    Args:
        fn: Function to monitor (when used as decorator)
        **options: Monitoring options (email, chatId, task, subTask, etc.)
    """

    def decorator(func: Callable) -> Callable:
        def sync_wrapper(*args, **kwargs):
            start_time = time.time() * 1000

            try:
                # Execute the function
                result = func(*args, **kwargs)

                # Create event parameters
                params = OlakaiEventParams(
                    prompt=str(args) + str(kwargs),
                    response=str(result),
                    userEmail=options.get("userEmail", "anonymous@olakai.ai"),
                    sessionId=options.get("sessionId"),
                    task=options.get("task"),
                    subTask=options.get("subTask"),
                    customData=options.get("customData"),
                    shouldScore=options.get("shouldScore", True),
                    tokens=0,
                    requestTime=int(time.time() * 1000 - start_time),
                )

                # Track the event
                olakai(params)

                return result

            except Exception as e:
                # Track error event
                params = OlakaiEventParams(
                    prompt=str(args) + str(kwargs),
                    response=f"Error: {str(e)}",
                    userEmail=options.get("userEmail", "anonymous@olakai.ai"),
                    sessionId=options.get("sessionId"),
                    task=options.get("task"),
                    subTask=options.get("subTask"),
                    customData=options.get("customData"),
                    shouldScore=options.get("shouldScore", True),
                    tokens=0,
                    requestTime=int(time.time() * 1000 - start_time),
                )

                olakai(params)
                raise

        async def async_wrapper(*args, **kwargs):
            start_time = time.time() * 1000

            try:
                # Execute the async function
                result = await func(*args, **kwargs)

                # Create event parameters
                params = OlakaiEventParams(
                    prompt=str(args) + str(kwargs),
                    response=str(result),
                    userEmail=options.get("userEmail", "anonymous@olakai.ai"),
                    sessionId=options.get("sessionId"),
                    task=options.get("task"),
                    subTask=options.get("subTask"),
                    customData=options.get("customData"),
                    shouldScore=options.get("shouldScore", True),
                    tokens=0,
                    requestTime=int(time.time() * 1000 - start_time),
                )

                # Track the event
                olakai(params)

                return result

            except Exception as e:
                # Track error event
                params = OlakaiEventParams(
                    prompt=str(args) + str(kwargs),
                    response=f"Error: {str(e)}",
                    userEmail=options.get("userEmail", "anonymous@olakai.ai"),
                    sessionId=options.get("sessionId"),
                    task=options.get("task"),
                    subTask=options.get("subTask"),
                    customData=options.get("customData"),
                    shouldScore=options.get("shouldScore", True),
                    tokens=0,
                    requestTime=int(time.time() * 1000 - start_time),
                )

                olakai(params)
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    # Handle both @olakai_monitor and @olakai_monitor(options) usage
    if fn is None:
        return decorator
    else:
        return decorator(fn)
