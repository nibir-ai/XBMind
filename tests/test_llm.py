"""Tests for LLM providers and conversation memory."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xbmind.config import MemoryConfig, OllamaConfig
from xbmind.llm.base import LLMMessage, LLMResponse, ToolCall, ToolDefinition
from xbmind.llm.memory import ConversationMemory
from xbmind.llm.ollama import OllamaLLM


class TestLLMDataClasses:
    """Tests for LLM data classes."""

    def test_tool_call(self) -> None:
        """Test ToolCall creation."""
        tc = ToolCall(name="weather", arguments={"location": "London"}, id="call_1")
        assert tc.name == "weather"
        assert tc.arguments == {"location": "London"}

    def test_llm_message(self) -> None:
        """Test LLMMessage creation."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls == []

    def test_llm_response(self) -> None:
        """Test LLMResponse creation."""
        response = LLMResponse(content="Hi there!", finish_reason="stop", model="test")
        assert response.content == "Hi there!"
        assert response.finish_reason == "stop"
        assert response.tool_calls == []

    def test_tool_definition(self) -> None:
        """Test ToolDefinition creation."""
        td = ToolDefinition(
            name="test",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )
        assert td.name == "test"


class TestOllamaLLM:
    """Tests for OllamaLLM."""

    def test_init(self, ollama_config: OllamaConfig) -> None:
        """Test Ollama provider initialisation."""
        llm = OllamaLLM(ollama_config)
        assert "Ollama" in llm.name
        assert llm._client is None

    @pytest.mark.asyncio
    async def test_generate_without_start(self, ollama_config: OllamaConfig) -> None:
        """Test that generating without starting raises RuntimeError."""
        llm = OllamaLLM(ollama_config)
        with pytest.raises(RuntimeError, match="not started"):
            await llm.generate([LLMMessage(role="user", content="test")])

    @pytest.mark.asyncio
    async def test_stop_clears_client(self, ollama_config: OllamaConfig) -> None:
        """Test that stopping clears the client."""
        llm = OllamaLLM(ollama_config)
        llm._client = AsyncMock()
        await llm.stop()
        assert llm._client is None

    def test_format_messages(self, ollama_config: OllamaConfig) -> None:
        """Test message formatting for the Ollama API."""
        llm = OllamaLLM(ollama_config)
        messages = [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="Hello"),
        ]
        formatted = llm._format_messages(messages)
        assert len(formatted) == 2
        assert formatted[0]["role"] == "system"
        assert formatted[1]["content"] == "Hello"

    def test_format_tools(self, ollama_config: OllamaConfig) -> None:
        """Test tool definition formatting."""
        llm = OllamaLLM(ollama_config)
        tools = [
            ToolDefinition(
                name="weather",
                description="Get weather",
                parameters={"type": "object", "properties": {}},
            )
        ]
        formatted = llm._format_tools(tools)
        assert len(formatted) == 1
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "weather"

    def test_parse_response_no_tool_calls(self, ollama_config: OllamaConfig) -> None:
        """Test parsing a simple text response."""
        llm = OllamaLLM(ollama_config)
        data = {
            "message": {"content": "Hello!", "role": "assistant"},
            "model": "llama3.2",
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        result = llm._parse_response(data)
        assert result.content == "Hello!"
        assert result.finish_reason == "stop"
        assert result.tool_calls == []

    def test_parse_response_with_tool_calls(self, ollama_config: OllamaConfig) -> None:
        """Test parsing a response with tool calls."""
        llm = OllamaLLM(ollama_config)
        data = {
            "message": {
                "content": "",
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "weather",
                            "arguments": {"location": "London"},
                        }
                    }
                ],
            },
            "model": "llama3.2",
        }
        result = llm._parse_response(data)
        assert result.finish_reason == "tool_calls"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "weather"
        assert result.tool_calls[0].arguments == {"location": "London"}


class TestConversationMemory:
    """Tests for ConversationMemory."""

    @pytest.mark.asyncio
    async def test_start_creates_db(self, memory_config: MemoryConfig) -> None:
        """Test that starting creates the database file."""
        memory = ConversationMemory(memory_config)
        await memory.start()
        assert Path(memory_config.db_path).exists()
        await memory.stop()

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self, memory_config: MemoryConfig) -> None:
        """Test adding and retrieving messages."""
        memory = ConversationMemory(memory_config)
        await memory.start()

        msg = LLMMessage(role="user", content="Hello!")
        await memory.add_message("test_session", msg)

        messages = await memory.get_messages("test_session")
        assert len(messages) >= 1
        user_msgs = [m for m in messages if m.role == "user"]
        assert any(m.content == "Hello!" for m in user_msgs)

        await memory.stop()

    @pytest.mark.asyncio
    async def test_message_count(self, memory_config: MemoryConfig) -> None:
        """Test message counting."""
        memory = ConversationMemory(memory_config)
        await memory.start()

        for i in range(5):
            await memory.add_message(
                "test_session", LLMMessage(role="user", content=f"Message {i}")
            )

        count = await memory.get_message_count("test_session")
        assert count == 5

        await memory.stop()

    @pytest.mark.asyncio
    async def test_should_summarize(self, memory_config: MemoryConfig) -> None:
        """Test summarization threshold detection."""
        memory = ConversationMemory(memory_config)
        await memory.start()

        # Add messages up to the threshold
        for i in range(memory_config.max_messages):
            await memory.add_message(
                "test_session", LLMMessage(role="user", content=f"Message {i}")
            )

        should = await memory.should_summarize("test_session")
        assert should is True

        await memory.stop()

    @pytest.mark.asyncio
    async def test_clear_session(self, memory_config: MemoryConfig) -> None:
        """Test clearing a session."""
        memory = ConversationMemory(memory_config)
        await memory.start()

        await memory.add_message("test_session", LLMMessage(role="user", content="Hello"))
        await memory.clear_session("test_session")

        count = await memory.get_message_count("test_session")
        assert count == 0

        await memory.stop()
