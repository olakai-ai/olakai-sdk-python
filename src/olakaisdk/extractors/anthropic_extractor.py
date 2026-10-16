"""Extract telemetry data from Anthropic API responses."""

from typing import Any, Dict, Optional
from ..shared.types import MonitorPayload
from ..context import OlakaiContextData
from .base_extractor import BaseExtractor
from ..config import require_config


class AnthropicExtractor(BaseExtractor):
    """Extract telemetry data from Anthropic API calls."""

    def extract(
        self,
        request_kwargs: Dict[str, Any],
        response: Any,
        client_instance: Any,
        duration_ms: int,
        context: Optional[OlakaiContextData] = None,
    ) -> MonitorPayload:
        """
        Extract telemetry data from Anthropic request/response.

        Args:
            request_kwargs: Arguments passed to messages.create()
            response: Anthropic response object
            client_instance: Messages resource instance
            duration_ms: Request duration in milliseconds
            context: Current Olakai context

        Returns:
            MonitorPayload ready to send
        """
        # Extract model name from request kwargs
        model = request_kwargs.get("model", "unknown")

        # Extract token counts from usage
        tokens_input = 0
        tokens_output = 0
        tokens_total = 0

        usage = getattr(response, "usage", None)
        if usage:
            tokens_input = getattr(usage, "input_tokens", 0) or 0
            tokens_output = getattr(usage, "output_tokens", 0) or 0
            tokens_total = tokens_input + tokens_output

        # Extract text content
        prompt_text = (
            self._extract_prompt(request_kwargs)
            if self.capture_inputs
            else "[redacted]"
        )
        response_text = (
            self._extract_response(response)
            if self.capture_outputs
            else "[redacted]"
        )

        # Get context data or use defaults
        context_data = context or OlakaiContextData()

        # Build custom data (merge with context)
        custom_data = dict(context_data.customData or {})
        custom_data.update(
            {
                "model": model,
                "provider": "anthropic",
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tokens_total": tokens_total,
            }
        )

        # Get chatId from config sessionId
        config = require_config()
        chatId = config.sessionId

        # Build payload
        payload = MonitorPayload(
            userEmail=context_data.userEmail or "anonymous@olakai.ai",
            chatId=chatId,
            prompt=prompt_text,
            response=response_text,
            tokens=tokens_total,
            requestTime=duration_ms,
            task=context_data.task,
            subTask=context_data.subTask,
            customData=custom_data,
            shouldScore=True,
        )

        return payload

    def _extract_prompt(self, request_kwargs: Dict[str, Any]) -> str:
        """
        Extract prompt text from messages.create arguments.

        Args:
            request_kwargs: Arguments passed to messages.create()

        Returns:
            Extracted prompt text
        """
        messages = request_kwargs.get("messages", None)

        if messages is None:
            return ""

        # Messages is a list of {"role": ..., "content": ...}
        if isinstance(messages, list):
            text_parts = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        text_parts.append(f"{role}: {content}")
                    elif isinstance(content, list):
                        # Content blocks
                        for block in content:
                            if isinstance(block, dict):
                                text = block.get("text", "")
                                if text:
                                    text_parts.append(f"{role}: {text}")
                            elif hasattr(block, "text"):
                                text_parts.append(f"{role}: {block.text}")
                elif hasattr(msg, "role") and hasattr(msg, "content"):
                    text_parts.append(f"{msg.role}: {msg.content}")
            return " | ".join(text_parts) if text_parts else str(messages)

        return str(messages)

    def _extract_response(self, response: Any) -> str:
        """
        Extract response text from Anthropic response object.

        Args:
            response: Anthropic response object

        Returns:
            Extracted response text
        """
        try:
            # Anthropic returns content as a list of blocks
            if hasattr(response, "content") and response.content:
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        text_parts.append(block.text)
                if text_parts:
                    return " ".join(text_parts)
        except Exception:
            pass

        return str(response)

