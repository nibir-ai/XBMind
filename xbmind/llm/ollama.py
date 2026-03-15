"""Ollama LLM provider.

Primary offline LLM provider using the Ollama HTTP API with full
tool/function calling support.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from xbmind.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolDefinition
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import OllamaConfig

log = get_logger(__name__)


class OllamaLLM(LLMProvider):
    """Ollama HTTP API LLM provider.

    Communicates with a locally running Ollama instance for fully offline
    LLM inference with tool calling support.

    Example::

        llm = OllamaLLM(config)
        await llm.start()
        response = await llm.generate(messages, tools)
    """

    def __init__(self, config: OllamaConfig) -> None:
        """Initialise the Ollama provider.

        Args:
            config: Ollama configuration section.
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        """Human-readable name of this LLM provider."""
        return f"Ollama ({self._config.model})"

    async def start(self) -> None:
        """Create the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=httpx.Timeout(self._config.timeout, connect=10.0),
        )
        log.info("llm.ollama.started", model=self._config.model, base_url=self._config.base_url)

    async def stop(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        log.info("llm.ollama.stopped")

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Generate a response using Ollama's chat API.

        Args:
            messages: Conversation messages.
            tools: Optional tool definitions for function calling.

        Returns:
            An :class:`LLMResponse` with the model's output.

        Raises:
            RuntimeError: If the client has not been started.
            httpx.HTTPStatusError: If the API returns an error status.
        """
        if self._client is None:
            raise RuntimeError("Client not started — call start() first")

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": self._format_messages(messages),
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        if tools:
            payload["tools"] = self._format_tools(tools)

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()

        data = response.json()
        return self._parse_response(data)

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert internal messages to Ollama API format.

        Args:
            messages: List of :class:`LLMMessage` objects.

        Returns:
            List of dicts in Ollama's message format.
        """
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            formatted.append(entry)
        return formatted

    def _format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert tool definitions to Ollama API format.

        Args:
            tools: List of :class:`ToolDefinition` objects.

        Returns:
            List of dicts in Ollama's tool format.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse an Ollama API response into an :class:`LLMResponse`.

        Args:
            data: Raw JSON response from Ollama.

        Returns:
            Parsed :class:`LLMResponse`.
        """
        message = data.get("message", {})
        content = message.get("content", "")

        tool_calls: list[ToolCall] = []
        raw_tool_calls = message.get("tool_calls", [])
        for i, tc in enumerate(raw_tool_calls):
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            arguments = func.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}
            tool_calls.append(
                ToolCall(name=tool_name, arguments=arguments, id=f"call_{i}")
            )

        finish_reason = "tool_calls" if tool_calls else "stop"

        # Ollama provides eval_count and prompt_eval_count
        usage = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

        log.info(
            "llm.ollama.response",
            content_length=len(content),
            tool_calls=len(tool_calls),
            tokens=usage,
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=data.get("model", self._config.model),
            usage_tokens=usage,
        )
