"""
Simplified monitoring decorator functionality.
"""

import asyncio
from typing import Callable
from ..shared import (
    MonitorOptions,
    MonitorPayload,
)
from ..client.api import enqueue_monitoring
from ..config import get_config


def olakai_monitor(**kwargs):
    """
    Monitor a function with the given options (simplified version).

    Kwargs:
        userEmail: str
        task: str
        subTask: str
        customData: Dict[str, Union[str, int, float, bool]]
        shouldScore: bool

    Returns:
        Decorator function
    """
    options = MonitorOptions()
    if len(kwargs) > 0:
        for key, value in kwargs.items():
            if hasattr(options, key):
                try:
                    setattr(options, key, value)
                except Exception as e:
                    print(f"[Olakai SDK] Error setting attribute, check the type of the value: {e}")
            else:
                print(f"[Olakai SDK] Invalid keyword argument: {key}")

    def wrap(f: Callable) -> Callable:
        async def async_wrapped_f(*args, **kwargs):
            try:
                # Execute the function
                result = await f(*args, **kwargs)

                # Create monitoring payload
                config = get_config()
                payload = MonitorPayload(
                    prompt=str(args) + str(kwargs),
                    response=str(result),
                    userEmail=options.userEmail or "anonymous@olakai.ai",
                    userId=options.userId,
                    chatId=config.sessionId if config else "",
                    tokens=0,
                    requestTime=0,  # Simplified - no timing
                    task=options.task,
                    subTask=options.subTask,
                    customData=options.customData,
                    shouldScore=options.shouldScore,
                )

                # Send to API
                if config:
                    enqueue_monitoring(config, payload)

                return result

            except Exception as error:
                # Create error payload
                config = get_config()
                payload = MonitorPayload(
                    prompt=str(args) + str(kwargs),
                    response=f"Error: {str(error)}",
                    userEmail=options.userEmail or "anonymous@olakai.ai",
                    userId=options.userId,
                    chatId=config.sessionId if config else "",
                    tokens=0,
                    requestTime=0,  # Simplified - no timing
                    task=options.task,
                    subTask=options.subTask,
                    customData=options.customData,
                    shouldScore=options.shouldScore,
                )

                # Send error to API
                if config:
                    enqueue_monitoring(config, payload)

                raise error  # Re-raise the original error

        def sync_wrapped_f(*args, **kwargs):
            try:
                result = f(*args, **kwargs)

                # Create monitoring payload
                config = get_config()
                payload = MonitorPayload(
                    prompt=str(args) + str(kwargs),
                    response=str(result),
                    userEmail=options.userEmail or "anonymous@olakai.ai",
                    userId=options.userId,
                    chatId=config.sessionId if config else "",
                    tokens=0,
                    requestTime=0,  # Simplified - no timing
                    task=options.task,
                    subTask=options.subTask,
                    customData=options.customData,
                    shouldScore=options.shouldScore,
                )

                # Send to API in the background
                if config:
                    enqueue_monitoring(config, payload)

                return result

            except Exception as error:
                # Create error payload
                config = get_config()
                payload = MonitorPayload(
                    prompt=str(args) + str(kwargs),
                    response=f"Error: {str(error)}",
                    userEmail=options.userEmail or "anonymous@olakai.ai",
                    userId=options.userId,
                    chatId=config.sessionId if config else "",
                    tokens=0,
                    requestTime=0,  # Simplified - no timing
                    task=options.task,
                    subTask=options.subTask,
                    customData=options.customData,
                    shouldScore=options.shouldScore,
                )

                # Send error to API in the background
                if config:
                    enqueue_monitoring(config, payload)

                raise error

        # Check if the decorated function is async or sync
        if asyncio.iscoroutinefunction(f):
            # For async functions, return the async wrapper directly
            return async_wrapped_f
        else:
            # For sync functions, create a sync wrapper that fires off monitoring in background
            return sync_wrapped_f

    return wrap


# Legacy function for backward compatibility
def olakai_supervisor(**kwargs):
    """
    Legacy function name for backward compatibility.
    Use olakai_monitor instead.
    """
    return olakai_monitor(**kwargs)
