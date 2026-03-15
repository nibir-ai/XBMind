"""Shell command tool with configurable allowlist.

Executes shell commands from a whitelist of allowed commands.
Disabled by default for security.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from xbmind.llm.base import ToolDefinition
from xbmind.llm.tools.base_tool import BaseTool
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import ShellToolConfig

log = get_logger(__name__)


class ShellTool(BaseTool):
    """Executes allowlisted shell commands.

    Commands are checked against a configurable allowlist before
    execution.  The output is truncated to prevent excessive
    token usage.

    Example::

        tool = ShellTool(config)
        result = await tool.execute(command="uptime")
    """

    def __init__(self, config: ShellToolConfig) -> None:
        """Initialise the shell tool.

        Args:
            config: Shell tool configuration with ``allowlist``.
        """
        self._config = config

    @property
    def definition(self) -> ToolDefinition:
        """Tool definition for the LLM."""
        allowed = ", ".join(f"'{cmd}'" for cmd in self._config.allowlist)
        return ToolDefinition(
            name="shell",
            description=(
                f"Execute a shell command on the host machine. "
                f"Only these commands are allowed: {allowed}. "
                f"Returns the command output."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(self, **kwargs: Any) -> str:
        """Execute a shell command if it's on the allowlist.

        Args:
            **kwargs: Must include ``command`` (str).

        Returns:
            Command output or error message.
        """
        command = kwargs.get("command", "").strip()
        if not command:
            return "Error: No command provided."

        # Check against allowlist
        if not self._is_allowed(command):
            allowed_cmds = ", ".join(self._config.allowlist)
            return (
                f"Error: Command '{command}' is not allowed. "
                f"Allowed commands: {allowed_cmds}"
            )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._config.timeout,
                )
            except TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self._config.timeout}s."

            output = stdout.decode("utf-8", errors="replace").strip()
            error_output = stderr.decode("utf-8", errors="replace").strip()

            result_parts: list[str] = []

            if output:
                if len(output) > self._config.max_output_length:
                    output = output[: self._config.max_output_length] + "\n... (truncated)"
                result_parts.append(output)

            if error_output:
                if len(error_output) > self._config.max_output_length:
                    error_output = error_output[: self._config.max_output_length] + "\n... (truncated)"
                result_parts.append(f"STDERR: {error_output}")

            if process.returncode != 0:
                result_parts.append(f"Exit code: {process.returncode}")

            result = "\n".join(result_parts) if result_parts else "(no output)"

            log.info(
                "tool.shell.executed",
                command=command,
                exit_code=process.returncode,
                output_length=len(result),
            )

            return result

        except OSError:
            log.exception("tool.shell.os_error", command=command)
            return f"Error: Failed to execute command '{command}'."

    def _is_allowed(self, command: str) -> bool:
        """Check if a command matches the allowlist.

        Performs prefix matching: the command must start with one of the
        allowed command prefixes.

        Args:
            command: The command string to check.

        Returns:
            ``True`` if the command is allowed.
        """
        for allowed in self._config.allowlist:
            if command == allowed or command.startswith(allowed + " "):
                return True
        return False
