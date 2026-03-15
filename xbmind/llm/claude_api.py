"""Anthropic Claude API LLM provider.

Optional cloud-based LLM using the Anthropic messages API.
Requires the ``ANTHROPIC_API_KEY`` environment variable.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from xbmind.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolDefinition
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

    from xbmind.config import ClaudeConfig

log = get_logger(__name__)


class ClaudeLLM(LLMProvider):
    """Anthropic Claude API LLM provider.

    Uses the official ``anthropic`` Python SDK for message generation
    with tool use support.

    Example::

        llm = ClaudeLLM(config)
        await llm.start()
        response = await llm.generate(messages, tools)
    """

    def __init__(self, config: ClaudeConfig) -> None:
        """Initialise the Claude provider.

        Args:
            config: Claude configuration section.
        """
        self._config = config
        self._client: AsyncAnthropic | None = None

    @property
    def name(self) -> str:
        """Human-readable name of this LLM provider."""
        return f"Claude ({self._config.model})"

    async def start(self) -> None:
        """Create the Anthropic client."""
        from anthropic import AsyncAnthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            log.warning("llm.claude.no_api_key")

        self._client = AsyncAnthropic(api_key=api_key)
        log.info("llm.claude.started", model=self._config.model)

    async def stop(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.close()
            self._client = None
        log.info("llm.claude.stopped")

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Generate a response using Claude's messages API.

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

        # Extract system message
        system_content = ""
        user_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            elif msg.role == "tool":
                user_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            else:
                entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
                user_messages.append(entry)

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": user_messages,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }

        if system_content:
            kwargs["system"] = system_content

        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        response = await self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                        id=block.id,
                    )
                )

        finish = "tool_calls" if tool_calls else str(response.stop_reason or "stop")
        usage_tokens = response.usage.input_tokens + response.usage.output_tokens

        log.info(
            "llm.claude.response",
            content_length=len(content_text),
            tool_calls=len(tool_calls),
            tokens=usage_tokens,
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=finish,
            model=self._config.model,
            usage_tokens=usage_tokens,
        )
