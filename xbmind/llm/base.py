"""Abstract base class for LLM providers.

All LLM implementations must inherit from :class:`LLMProvider` and
implement the :meth:`generate` method.  Supports structured tool
definitions for function calling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """Represents a tool/function call requested by the LLM.

    Attributes:
        name: The name of the tool to call.
        arguments: The arguments to pass to the tool as a dict.
        id: Optional unique identifier for the tool call.
    """

    name: str
    arguments: dict[str, Any]
    id: str = ""


@dataclass
class LLMMessage:
    """A single message in a conversation.

    Attributes:
        role: Message role (``"system"``, ``"user"``, ``"assistant"``, ``"tool"``).
        content: Text content of the message.
        tool_calls: Tool calls made by the assistant (if any).
        tool_call_id: ID of the tool call this message is responding to.
        name: Name of the tool (for tool response messages).
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


@dataclass(frozen=True)
class LLMResponse:
    """Response from an LLM provider.

    Attributes:
        content: The text response from the model.
        tool_calls: Any tool calls the model wants to make.
        finish_reason: Why the model stopped (``"stop"``, ``"tool_calls"``).
        model: Name of the model that generated the response.
        usage_tokens: Total tokens used (prompt + completion).
    """

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""
    usage_tokens: int = 0


@dataclass(frozen=True)
class ToolDefinition:
    """Schema definition for a tool that the LLM can call.

    Attributes:
        name: Tool name (used in function calls).
        description: Human-readable description for the LLM.
        parameters: JSON Schema object describing the parameters.
    """

    name: str
    description: str
    parameters: dict[str, Any]


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement :meth:`generate`.  Override :meth:`start`
    and :meth:`stop` for resource management.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            messages: List of conversation messages.
            tools: Optional list of tool definitions for function calling.

        Returns:
            An :class:`LLMResponse` with the model's output.
        """

    async def start(self) -> None:
        """Initialise the LLM provider.

        Override in subclasses if initialisation is needed.
        """

    async def stop(self) -> None:
        """Clean up the LLM provider resources.

        Override in subclasses if cleanup is needed.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this LLM provider."""
