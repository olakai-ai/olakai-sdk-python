"""Base interface for LLM provider instrumentation."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseInstrumentation(ABC):
    """
    Base class for LLM provider instrumentation.

    This provides a common interface for instrumenting different
    LLM providers (OpenAI, Anthropic, etc.).
    """

    def __init__(self):
        self._is_instrumented = False

    @abstractmethod
    def instrument(
        self,
        capture_inputs: bool = True,
        capture_outputs: bool = True,
        capture_api_keys: Optional[bool] = None,
    ) -> None:
        """
        Instrument the LLM provider SDK.

        Args:
            capture_inputs: Whether to capture prompt/input data
            capture_outputs: Whether to capture response/output data
            capture_api_keys: Deprecated, ignored. The SDK never sends
                provider API keys. Passing True emits a DeprecationWarning.
        """
        pass

    @abstractmethod
    def uninstrument(self) -> None:
        """Remove instrumentation from the LLM provider SDK."""
        pass

    def is_instrumented(self) -> bool:
        """
        Check if the provider is currently instrumented.

        Returns:
            True if instrumented, False otherwise
        """
        return self._is_instrumented
