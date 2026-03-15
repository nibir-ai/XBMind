"""Abstract base class for LLM tools.

All tools must inherit from :class:`BaseTool` and implement
:meth:`execute` and :attr:`definition`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xbmind.llm.base import ToolDefinition


class BaseTool(ABC):
    """Abstract base class for callable tools.

    Subclasses define a tool's schema (for the LLM) and its execution
    logic.  Tools are registered with the orchestrator and are invoked
    when the LLM returns a ``tool_calls`` response.
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the JSON-Schema tool definition for the LLM."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with the given arguments.

        Args:
            **kwargs: Arguments from the LLM's tool call.

        Returns:
            A string result to return to the LLM.
        """

    @property
    def name(self) -> str:
        """Tool name (derived from the definition)."""
        return self.definition.name
