"""Base extractor interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..shared.types import MonitorPayload
from ..context import OlakaiContextData


class BaseExtractor(ABC):
    """
    Base class for extracting telemetry data from LLM API calls.
    """

    def __init__(
        self,
        capture_inputs: bool = True,
        capture_outputs: bool = True,
        capture_api_keys: bool = False  # deprecated, ignored
    ):
        self.capture_inputs = capture_inputs
        self.capture_outputs = capture_outputs
        self.capture_api_keys = capture_api_keys

    @abstractmethod
    def extract(
        self,
        request_kwargs: Dict[str, Any],
        response: Any,
        client_instance: Any,
        duration_ms: int,
        context: Optional[OlakaiContextData] = None
    ) -> MonitorPayload:
        """
        Extract telemetry data from an LLM API call.

        Args:
            request_kwargs: Arguments passed to the API call
            response: Response object from the API
            client_instance: The client instance making the call
            duration_ms: Request duration in milliseconds
            context: Current Olakai context data

        Returns:
            MonitorPayload ready to send to Olakai API
        """
        pass
