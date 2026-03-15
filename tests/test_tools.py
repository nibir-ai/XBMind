"""Tests for LLM tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xbmind.config import ShellToolConfig, TimerToolConfig, WeatherToolConfig
from xbmind.llm.tools.datetime_tool import DateTimeTool
from xbmind.llm.tools.shell_tool import ShellTool
from xbmind.llm.tools.timer import TimerTool
from xbmind.llm.tools.weather import WeatherTool
from xbmind.llm.tools.wikipedia import WikipediaTool
from xbmind.utils.events import EventBus


class TestDateTimeTool:
    """Tests for DateTimeTool."""

    def test_definition(self) -> None:
        """Test tool definition structure."""
        tool = DateTimeTool()
        defn = tool.definition
        assert defn.name == "datetime"
        assert "date" in defn.description.lower()

    @pytest.mark.asyncio
    async def test_execute_default_timezone(self) -> None:
        """Test getting datetime with default timezone."""
        tool = DateTimeTool()
        result = await tool.execute()
        assert "Date:" in result
        assert "Time:" in result

    @pytest.mark.asyncio
    async def test_execute_utc(self) -> None:
        """Test getting datetime with UTC timezone."""
        tool = DateTimeTool()
        result = await tool.execute(timezone="UTC")
        assert "UTC" in result
        assert "Date:" in result

    @pytest.mark.asyncio
    async def test_execute_invalid_timezone(self) -> None:
        """Test error handling for invalid timezone."""
        tool = DateTimeTool()
        result = await tool.execute(timezone="Invalid/Timezone")
        assert "Error" in result


class TestWeatherTool:
    """Tests for WeatherTool."""

    def test_definition(self, weather_config: WeatherToolConfig) -> None:
        """Test tool definition structure."""
        tool = WeatherTool(weather_config)
        defn = tool.definition
        assert defn.name == "weather"
        assert "location" in defn.parameters["properties"]

    @pytest.mark.asyncio
    async def test_execute_no_location(self, weather_config: WeatherToolConfig) -> None:
        """Test error when no location provided."""
        tool = WeatherTool(weather_config)
        result = await tool.execute()
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_execute_timeout(self, weather_config: WeatherToolConfig) -> None:
        """Test timeout handling."""
        import httpx

        tool = WeatherTool(weather_config)
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
            result = await tool.execute(location="London")
            assert "timed out" in result.lower()


class TestTimerTool:
    """Tests for TimerTool."""

    def test_definition(self, timer_config: TimerToolConfig, event_bus: EventBus) -> None:
        """Test tool definition structure."""
        tool = TimerTool(timer_config, event_bus)
        defn = tool.definition
        assert defn.name == "set_timer"
        assert "seconds" in defn.parameters["properties"]

    @pytest.mark.asyncio
    async def test_execute_valid_timer(
        self, timer_config: TimerToolConfig, event_bus: EventBus
    ) -> None:
        """Test setting a valid timer."""
        tool = TimerTool(timer_config, event_bus)
        result = await tool.execute(seconds=10, label="test")
        assert "Timer set" in result
        assert "test" in result
        await tool.cancel_all()

    @pytest.mark.asyncio
    async def test_execute_zero_seconds(
        self, timer_config: TimerToolConfig, event_bus: EventBus
    ) -> None:
        """Test error for zero-second timer."""
        tool = TimerTool(timer_config, event_bus)
        result = await tool.execute(seconds=0)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_execute_exceeds_max(
        self, timer_config: TimerToolConfig, event_bus: EventBus
    ) -> None:
        """Test error for timer exceeding max duration."""
        tool = TimerTool(timer_config, event_bus)
        result = await tool.execute(seconds=99999)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_cancel_all(self, timer_config: TimerToolConfig, event_bus: EventBus) -> None:
        """Test cancelling all active timers."""
        tool = TimerTool(timer_config, event_bus)
        await tool.execute(seconds=30, label="timer1")
        await tool.execute(seconds=60, label="timer2")
        assert len(tool._active_timers) == 2
        await tool.cancel_all()
        assert len(tool._active_timers) == 0


class TestShellTool:
    """Tests for ShellTool."""

    def test_definition(self, shell_config: ShellToolConfig) -> None:
        """Test tool definition includes allowlist."""
        tool = ShellTool(shell_config)
        defn = tool.definition
        assert defn.name == "shell"
        assert "echo" in defn.description

    def test_is_allowed(self, shell_config: ShellToolConfig) -> None:
        """Test command allowlist checking."""
        tool = ShellTool(shell_config)
        assert tool._is_allowed("echo hello")
        assert tool._is_allowed("date")
        assert tool._is_allowed("uname -a")
        assert not tool._is_allowed("rm -rf /")
        assert not tool._is_allowed("curl http://example.com")

    @pytest.mark.asyncio
    async def test_execute_allowed_command(self, shell_config: ShellToolConfig) -> None:
        """Test executing an allowed command."""
        tool = ShellTool(shell_config)
        result = await tool.execute(command="echo hello")
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_execute_disallowed_command(self, shell_config: ShellToolConfig) -> None:
        """Test rejection of disallowed commands."""
        tool = ShellTool(shell_config)
        result = await tool.execute(command="rm -rf /")
        assert "not allowed" in result

    @pytest.mark.asyncio
    async def test_execute_empty_command(self, shell_config: ShellToolConfig) -> None:
        """Test error for empty command."""
        tool = ShellTool(shell_config)
        result = await tool.execute(command="")
        assert "Error" in result


class TestWikipediaTool:
    """Tests for WikipediaTool."""

    def test_definition(self) -> None:
        """Test tool definition structure."""
        tool = WikipediaTool()
        defn = tool.definition
        assert defn.name == "wikipedia"
        assert "query" in defn.parameters["properties"]

    @pytest.mark.asyncio
    async def test_execute_no_query(self) -> None:
        """Test error when no query provided."""
        tool = WikipediaTool()
        result = await tool.execute()
        assert "Error" in result
