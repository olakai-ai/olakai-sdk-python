"""Extract telemetry data from Google Generative AI API responses."""

from typing import Any, Dict, Optional
from ..shared.types import MonitorPayload
from ..context import OlakaiContextData
from .base_extractor import BaseExtractor
from ..config import require_config


class GoogleExtractor(BaseExtractor):
    """Extract telemetry data from Google Generative AI API calls."""

    def extract(
        self,
        request_kwargs: Dict[str, Any],
        response: Any,
        client_instance: Any,
        duration_ms: int,
        context: Optional[OlakaiContextData] = None,
    ) -> MonitorPayload:
        """
        Extract telemetry data from Google GenAI request/response.

        Args:
            request_kwargs: Arguments passed to generate_content()
            response: Google GenAI response object
            client_instance: GenerativeModel instance
            duration_ms: Request duration in milliseconds
            context: Current Olakai context

        Returns:
            MonitorPayload ready to send
        """
        # Extract model name from the client instance
        model = getattr(client_instance, "model_name", "unknown")

        # Extract token counts from usage_metadata
        tokens_input = 0
        tokens_output = 0
        tokens_total = 0

        usage = getattr(response, "usage_metadata", None)
        if usage:
            tokens_input = getattr(usage, "prompt_token_count", 0) or 0
            tokens_output = (
                getattr(usage, "candidates_token_count", 0) or 0
            )
            tokens_total = (
                getattr(usage, "total_token_count", 0) or 0
            )

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
                "provider": "google",
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
        Extract prompt text from generate_content arguments.

        Args:
            request_kwargs: Arguments passed to generate_content()

        Returns:
            Extracted prompt text
        """
        contents = request_kwargs.get("contents", None)

        if contents is None:
            return ""

        # String content
        if isinstance(contents, str):
            return contents

        # List of content parts
        if isinstance(contents, list):
            text_parts = []
            for item in contents:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    # Content dict with "parts"
                    parts = item.get("parts", [])
                    for part in parts:
                        if isinstance(part, str):
                            text_parts.append(part)
                        elif isinstance(part, dict):
                            text = part.get("text", "")
                            if text:
                                text_parts.append(text)
                elif hasattr(item, "parts"):
                    # Content object with parts attribute
                    for part in item.parts:
                        if hasattr(part, "text") and part.text:
                            text_parts.append(part.text)
            return " ".join(text_parts) if text_parts else str(contents)

        return str(contents)

    def _extract_response(self, response: Any) -> str:
        """
        Extract response text from Google GenAI response object.

        Args:
            response: Google GenAI response object

        Returns:
            Extracted response text
        """
        try:
            # Try .text property first (most common)
            if hasattr(response, "text"):
                return response.text

            # Try candidates
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    parts = getattr(candidate.content, "parts", [])
                    text_parts = []
                    for part in parts:
                        if hasattr(part, "text") and part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        return " ".join(text_parts)
        except Exception:
            pass

        return str(response)

