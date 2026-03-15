"""OpenAI API LLM provider.

Optional cloud-based LLM using the OpenAI chat completions API.
Requires the ``OPENAI_API_KEY`` environment variable.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from xbmind.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolDefinition
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from xbmind.config import OpenAIConfig

log = get_logger(__name__)


class OpenAILLM(LLMProvider):
    """OpenAI API LLM provider.

    Uses the official ``openai`` Python SDK for chat completions
    with function calling support.

    Example::

        llm = OpenAILLM(config)
        await llm.start()
        response = await llm.generate(messages, tools)
    """

    def __init__(self, config: OpenAIConfig) -> None:
        """Initialise the OpenAI provider.

        Args:
            config: OpenAI configuration section.
        """
        self._config = config
        self._client: AsyncOpenAI | None = None

    @property
    def name(self) -> str:
        """Human-readable name of this LLM provider."""
        return f"OpenAI ({self._config.model})"

    async def start(self) -> None:
        """Create the OpenAI client."""
        from openai import AsyncOpenAI

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            log.warning("llm.openai.no_api_key")

        self._client = AsyncOpenAI(api_key=api_key)
        log.info("llm.openai.started", model=self._config.model)

    async def stop(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.close()
            self._client = None
        log.info("llm.openai.stopped")

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Generate a response using OpenAI's chat completions API.

        Args:
            messages: Conversation messages.
            tools: Optional tool definitions for function calling.

        Returns:
            An :class:`LLMResponse` with the model's output.

        Raises:
            RuntimeError: If the client has not been started.
        """
        if self._client is None:
            raise RuntimeError("Client not started — call start() first")

        import json as json_module

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": self._format_messages(messages),
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }

        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json_module.loads(args)
                    except json_module.JSONDecodeError:
                        args = {"raw": args}
                tool_calls.append(
                    ToolCall(name=tc.function.name, arguments=args, id=tc.id or "")
                )

        usage_tokens = 0
        if response.usage:
            usage_tokens = response.usage.total_tokens

        finish = "tool_calls" if tool_calls else str(choice.finish_reason or "stop")

        log.info(
            "llm.openai.response",
            content_length=len(message.content or ""),
            tool_calls=len(tool_calls),
            tokens=usage_tokens,
        )

        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            finish_reason=finish,
            model=self._config.model,
            usage_tokens=usage_tokens,
        )

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert internal messages to OpenAI API format.

        Args:
            messages: List of :class:`LLMMessage` objects.

        Returns:
            List of dicts in OpenAI's message format.
        """
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_calls:
                import json as json_module

                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json_module.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            formatted.append(entry)
        return formatted
