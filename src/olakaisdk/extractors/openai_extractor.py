"""Extract telemetry data from OpenAI API responses."""

from typing import Any, Dict, Optional
from urllib.parse import urlparse
from ..shared.types import MonitorPayload
from ..context import OlakaiContextData
from .base_extractor import BaseExtractor
from ..config import require_config


class OpenAIExtractor(BaseExtractor):
    """Extract telemetry data from OpenAI API calls."""

    def extract(
        self,
        request_kwargs: Dict[str, Any],
        response: Any,
        client_instance: Any,
        duration_ms: int,
        context: Optional[OlakaiContextData] = None
    ) -> MonitorPayload:
        """
        Extract telemetry data from OpenAI request/response.

        Args:
            request_kwargs: Arguments passed to create()
            response: OpenAI response object
            client_instance: OpenAI client instance
            duration_ms: Request duration in milliseconds
            context: Current Olakai context

        Returns:
            MonitorPayload ready to send
        """
        # Extract from request
        model = request_kwargs.get("model", "unknown")
        messages = request_kwargs.get("messages", [])

        # Extract from response
        tokens_input = 0
        tokens_output = 0
        tokens_total = 0

        if hasattr(response, "usage") and response.usage:
            tokens_input = getattr(response.usage, "prompt_tokens", 0)
            tokens_output = getattr(response.usage, "completion_tokens", 0)
            tokens_total = getattr(response.usage, "total_tokens", 0)

        # Extract text content
        prompt_text = self._extract_prompt(messages) if self.capture_inputs else "[redacted]"
        response_text = self._extract_response(response) if self.capture_outputs else "[redacted]"

        # Get context data or use defaults
        context_data = context or OlakaiContextData()

        # Build custom data (merge with context)
        custom_data = dict(context_data.customData or {})
        custom_data.update({
            "model": model,
            "provider": detect_openai_provider(client_instance),
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens_total": tokens_total,
        })

        # Get chatId from config sessionId
        config = require_config()
        chatId = config.sessionId

        # Build payload
        payload = MonitorPayload(
            userEmail=context_data.userEmail or "anonymous@olakai.ai",
            chatId=chatId,
            taskExecutionId=context_data.taskExecutionId,
            prompt=prompt_text,
            response=response_text,
            tokens=tokens_total,
            requestTime=duration_ms,
            task=context_data.task,
            subTask=context_data.subTask,
            customData=custom_data,
            shouldScore=True,
            modelName=model,
        )

        return payload

    def _extract_prompt(self, messages: list) -> str:
        """
        Extract prompt text from messages array.

        Args:
            messages: List of message dictionaries

        Returns:
            Extracted prompt text
        """
        if not messages:
            return ""

        # Get last user message
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                # Handle complex content (e.g., with images)
                elif isinstance(content, list):
                    text_parts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ]
                    return " ".join(text_parts)

        # Fallback: return all messages as string
        return str(messages)

    def _extract_response(self, response: Any) -> str:
        """
        Extract response text from OpenAI response object.

        Args:
            response: OpenAI response object

        Returns:
            Extracted response text
        """
        try:
            if hasattr(response, "choices") and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    content = choice.message.content
                    if content:
                        return content
        except Exception:
            pass

        # Fallback: return string representation
        return str(response)


def detect_openai_provider(client_instance: Any) -> str:
    """Name the provider behind an OpenAI-compatible client from its base_url.

    ``client_instance`` is the ``Completions`` resource; its ``_client`` is
    the ``OpenAI`` client. Unknown hosts are reported as the host itself.
    """
    try:
        base_url = getattr(client_instance, "_client", None).base_url
        host = urlparse(str(base_url)).hostname
    except Exception:  # noqa: BLE001 - unknown client shape
        host = None
    if not host or host == "api.openai.com":
        return "openai"
    if host == "openrouter.ai" or host.endswith(".openrouter.ai"):
        return "openrouter"
    if host.endswith(".openai.azure.com"):
        return "azure"
    return host
