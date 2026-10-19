"""
Simplified types for the Olakai SDK.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union, Dict
import math
import uuid

JSONType = Union[
    None, bool, int, float, str, Dict[str, "JSONType"], List["JSONType"]
]


# Backend accepts 0..10000 USD; anything else would reject the event.
MAX_PROVIDER_COST_USD = 10000


def valid_provider_cost(value: object) -> Optional[float]:
    """Return ``value`` as a USD cost if it is a finite number in range."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not 0 <= value <= MAX_PROVIDER_COST_USD:
        return None
    return float(value)


@dataclass
class OlakaiConfig:
    """Simplified configuration for the SDK."""

    api_key: str
    endpoint: str = "https://app.olakai.ai"
    debug: bool = False
    sessionId: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class OlakaiEventParams:
    """Parameters for event tracking."""

    prompt: str
    response: str
    userEmail: Optional[str] = "anonymous@olakai.ai"
    sessionId: Optional[str] = None  # Groups activities into a session/conversation
    taskExecutionId: Optional[str] = None
    task: Optional[str] = None
    subTask: Optional[str] = None
    customData: Optional[Dict[str, Union[str, int, float, bool]]] = None
    shouldScore: bool = True
    tokens: Optional[int] = 0
    requestTime: Optional[int] = 0
    modelName: Optional[str] = None  # Omitted from the payload when None
    # Real provider charge in USD for this call. Omitted when None or invalid.
    providerCostUsd: Optional[float] = None


@dataclass
class MonitorOptions:
    """Options for monitoring functions."""

    userEmail: Optional[str] = "anonymous@olakai.ai"
    userId: Optional[str] = None  # SDK client's user ID for tracking
    task: Optional[str] = None
    subTask: Optional[str] = None
    customData: Optional[Dict[str, Union[str, int, float, bool]]] = None
    shouldScore: bool = True


@dataclass
class MonitorPayload:
    """Payload for monitoring data sent to API."""

    userEmail: str
    userId: Optional[str] = None  # SDK client's user ID for tracking
    chatId: str = ""
    taskExecutionId: Optional[str] = None
    prompt: JSONType = None
    response: JSONType = None
    blocked: Optional[bool] = False
    tokens: Optional[int] = 0
    requestTime: Optional[int] = 0
    task: Optional[str] = None
    subTask: Optional[str] = None
    errorMessage: Optional[str] = None
    sensitivity: Optional[List[str]] = None
    customData: Optional[Dict[str, Union[str, int, float, bool]]] = None
    shouldScore: Optional[bool] = True
    modelName: Optional[str] = None
    providerCostUsd: Optional[float] = None


@dataclass
class ControlPayload:
    """Payload for control data sent to API."""

    prompt: JSONType
    email: Optional[str] = "anonymous@olakai.ai"
    task: Optional[str] = None
    subTask: Optional[str] = None
    tokens: Optional[int] = 0
    overrideControlCriteria: Optional[List[str]] = None


@dataclass
class MonitoringResponse:
    """Response from monitoring API calls."""

    index: int
    success: bool
    promptRequestId: Optional[str] = None
    error: Optional[str] = None


@dataclass
class APIResponse:
    """Response from API calls."""

    success: bool
    totalRequests: int
    successCount: int
    failureCount: int
    results: Optional[List[MonitoringResponse]] = None
    message: Optional[str] = None


@dataclass
class ControlDetails:
    detectedSensitivity: List[str]
    isAllowedPersona: bool


@dataclass
class ControlResponse:
    """Response from control API calls."""

    allowed: bool
    details: ControlDetails
    message: Optional[str] = None
