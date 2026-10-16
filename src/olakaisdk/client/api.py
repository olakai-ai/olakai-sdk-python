"""
Simplified API communication module for the Olakai SDK.
"""

from dataclasses import asdict
from typing import Any, Awaitable, Callable, Dict, Optional, Union, Literal
import asyncio
import atexit
import os
import queue
import threading
import time
from ..shared import (
    APITimeoutError,
    APIResponseError,
    RetryExhaustedError,
    MonitorPayload,
    ControlPayload,
    OlakaiConfig,
    APIResponse,
    ControlResponse,
    ControlDetails,
)

# Import requests only when needed
try:
    import requests
except ImportError:
    requests = None


async def make_api_call(
    config: OlakaiConfig,
    payload: Union[MonitorPayload, ControlPayload],
    call_type: Literal["monitoring", "control"] = "monitoring",
) -> Union[APIResponse, ControlResponse]:
    """Make API call with optional logging."""

    if requests is None:
        raise ImportError(
            "requests library is required for API calls. Install with: pip install requests"
        )

    headers = {"x-api-key": config.api_key}
    data_dict = asdict(payload)

    # Clean up None values
    if call_type == "monitoring":
        if "errorMessage" in data_dict and data_dict["errorMessage"] is None:
            del data_dict["errorMessage"]
        if (
            "taskExecutionId" in data_dict
            and data_dict["taskExecutionId"] is None
        ):
            del data_dict["taskExecutionId"]
        if "task" in data_dict and data_dict["task"] is None:
            del data_dict["task"]
        if "subTask" in data_dict and data_dict["subTask"] is None:
            del data_dict["subTask"]
        if "customData" in data_dict and data_dict["customData"] is None:
            del data_dict["customData"]
        if "shouldScore" in data_dict and data_dict["shouldScore"] is None:
            del data_dict["shouldScore"]
        if "modelName" in data_dict and data_dict["modelName"] is None:
            del data_dict["modelName"]
    else:
        if (
            "overrideControlCriteria" in data_dict
            and data_dict["overrideControlCriteria"] is None
        ):
            del data_dict["overrideControlCriteria"]
        if "task" in data_dict and data_dict["task"] is None:
            del data_dict["task"]
        if "subTask" in data_dict and data_dict["subTask"] is None:
            del data_dict["subTask"]

    try:
        # Determine URL based on call type
        if call_type == "monitoring":
            url = f"{config.endpoint}/api/monitoring/prompt"
        else:
            url = f"{config.endpoint}/api/control/prompt"

        response = requests.post(
            url,
            json=data_dict,
            headers=headers,
            timeout=30,  # Fixed timeout
        )

        if config.debug:
            print(f"[Olakai SDK] API call to {url}: {response.status_code}")

        response.raise_for_status()
        result = response.json()

        if call_type == "monitoring":
            return APIResponse(**result)
        else:
            result["details"] = ControlDetails(**result["details"])
            return ControlResponse(**result)

    except requests.exceptions.Timeout as err:
        raise APITimeoutError("Request timed out after 30 seconds") from err
    except requests.exceptions.HTTPError as err:
        raise APIResponseError(
            f"HTTP error: {err.response.status_code} - {err.response.text}"
        ) from err
    except requests.exceptions.RequestException as err:
        raise APIResponseError(f"Request failed: {str(err)}") from err
    except Exception as err:
        raise APIResponseError(
            f"Unexpected error during API call: {str(err)}"
        ) from err


async def send_with_retry(
    config: OlakaiConfig,
    payload: Union[MonitorPayload, ControlPayload],
    call_type: Literal["monitoring", "control"] = "monitoring",
    max_retries: int = 3,
) -> Union[APIResponse, ControlResponse]:
    """Send payload with retry logic."""

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await make_api_call(config, payload, call_type)
            if config.debug:
                print("[Olakai SDK] API call successful")
            return result
        except (APITimeoutError, APIResponseError) as err:
            last_error = err

            if config.debug:
                print(
                    f"[Olakai SDK] Attempt {attempt + 1}/{max_retries + 1} failed: {err}"
                )

            if attempt < max_retries:
                delay = min(1000 * (2**attempt), 30000)  # Exponential backoff
                await asyncio.sleep(delay / 1000)  # Convert to seconds

    if config.debug:
        print(f"[Olakai SDK] All retry attempts failed: {last_error}")
    raise RetryExhaustedError(
        f"All {max_retries + 1} retry attempts failed. Last error: {last_error}"
    ) from last_error


async def send_to_api_simple(
    config: OlakaiConfig,
    payload: MonitorPayload,
) -> Optional[Union[APIResponse, ControlResponse]]:
    """Send payload to monitoring API.

    Fire-and-forget: any transport, retry, or HTTP errors are swallowed so
    that user code is never affected by telemetry failures. Returns the
    response on success or ``None`` on any failure. Callers are not expected
    to use the return value.
    """
    try:
        return await send_with_retry(config, payload, "monitoring")
    except Exception as e:  # noqa: BLE001 - fire-and-forget telemetry
        if config.debug:
            print(f"[Olakai SDK] Error sending payload to API: {e}")
        return None


async def send_feedback_to_api(
    config: OlakaiConfig,
    payload: Dict[str, Any],
) -> None:
    """Send a feedback payload to the dedicated feedback endpoint.

    Fire-and-forget: any transport or HTTP errors are swallowed so that
    user code is never affected. The endpoint owns the schema — the
    caller is expected to have already built a clean wire payload
    containing only ``sessionId``, ``rating``, and optional
    ``turnIndex`` / ``comment`` / ``email`` keys.
    """

    if requests is None:
        if config.debug:
            print(
                "[Olakai SDK] requests library not available — "
                "skipping feedback send"
            )
        return

    url = f"{config.endpoint}/api/monitoring/feedback"
    headers = {"x-api-key": config.api_key}

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if config.debug:
            print(
                f"[Olakai SDK] Feedback API call to {url}: "
                f"{response.status_code}"
            )

        response.raise_for_status()
    except Exception as err:  # noqa: BLE001 - fire-and-forget
        if config.debug:
            print(f"[Olakai SDK] Failed to send feedback: {err}")


# Legacy function for backward compatibility
async def send_to_api(
    config: OlakaiConfig,
    payload: Union[MonitorPayload, ControlPayload],
    options: dict = {},
) -> Optional[Union[APIResponse, ControlResponse]]:
    """Send payload to API (legacy function for backward compatibility).

    For monitoring payloads this is fire-and-forget — the return value may
    be ``None`` on any failure. For control payloads, errors propagate.
    """
    if isinstance(payload, MonitorPayload):
        return await send_to_api_simple(config, payload)
    else:
        return await send_with_retry(config, payload, "control")


# --- Background sender -------------------------------------------------------
#
# Every fire-and-forget send (monitoring events, feedback) goes through one
# bounded queue drained by one daemon thread. Callers only enqueue, so the
# user's thread or event loop never waits on the network. The worker runs the
# existing coroutines (send_to_api_simple -> send_with_retry) on its own loop,
# so retry/backoff behaviour is unchanged. The control (blocking) path does
# not use this queue.
#
# When the queue is full, the NEW item is dropped (drop-newest) and a debug
# line is printed. Queue and thread are re-created after os.fork().

_QUEUE_MAXSIZE = 1000

_SendJob = Callable[[], Awaitable[Any]]

_queue: Optional[queue.Queue] = None
_pid: Optional[int] = None
_lock = threading.Lock()


def _worker(q: queue.Queue) -> None:
    loop = asyncio.new_event_loop()
    while True:
        job = q.get()
        try:
            loop.run_until_complete(job())
        except Exception:  # noqa: BLE001, S110 - never kill the worker
            pass
        finally:
            q.task_done()


def _get_queue() -> queue.Queue:
    global _queue, _pid
    pid = os.getpid()
    if _queue is None or _pid != pid:
        with _lock:
            if _queue is None or _pid != pid:
                q: queue.Queue = queue.Queue(_QUEUE_MAXSIZE)
                threading.Thread(
                    target=_worker,
                    args=(q,),
                    name="olakai-sdk-sender",
                    daemon=True,
                ).start()
                _queue, _pid = q, pid
    return _queue


def enqueue_send(config: OlakaiConfig, job: _SendJob) -> None:
    """Schedule ``job`` on the background sender. Never blocks or raises."""
    try:
        _get_queue().put_nowait(job)
    except queue.Full:
        if config.debug:
            print("[Olakai SDK] Send queue full, dropping event")
    except Exception as e:  # noqa: BLE001 - fire-and-forget
        if config.debug:
            print(f"[Olakai SDK] Failed to enqueue event: {e}")


def enqueue_monitoring(config: OlakaiConfig, payload: MonitorPayload) -> None:
    """Fire-and-forget a monitoring payload via the background sender."""
    enqueue_send(config, lambda: send_to_api_simple(config, payload))


def olakai_flush(timeout: float = 5.0) -> bool:
    """Wait until queued telemetry is sent, or ``timeout`` seconds pass.

    Returns True if the queue drained, False on timeout. Never raises.
    Registered with ``atexit`` so short-lived scripts deliver their events.
    """
    try:
        q = _queue
        if q is None or _pid != os.getpid():
            return True
        deadline = time.monotonic() + timeout
        with q.all_tasks_done:
            while q.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                q.all_tasks_done.wait(remaining)
        return True
    except Exception:  # noqa: BLE001
        return False


atexit.register(olakai_flush)
