# Adding Custom Tools

XBMind's tool system lets you extend the assistant with custom capabilities. Tools are Python classes that the LLM can call during conversations.

## Creating a Tool

### 1. Create a Tool File

Create `xbmind/llm/tools/your_tool.py`:

```python
from typing import Any
from xbmind.llm.base import ToolDefinition
from xbmind.llm.tools.base_tool import BaseTool

class YourTool(BaseTool):
    """Description of what your tool does."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="your_tool_name",
            description="Clear description the LLM uses to decide when to call this tool",
            parameters={
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "What this parameter does",
                    },
                },
                "required": ["param1"],
            },
        )

    async def execute(self, **kwargs: Any) -> str:
        param1 = kwargs.get("param1", "")
        # Your logic here
        return f"Result for {param1}"
```

### 2. Register the Tool

In `xbmind/main.py`, add to `_register_tools()`:

```python
from xbmind.llm.tools.your_tool import YourTool

def _register_tools(self) -> None:
    # ... existing tools ...
    self._tools["your_tool_name"] = YourTool()
```

### 3. Add Config Toggle (Optional)

In `xbmind/config.py`, add to `ToolsEnabledConfig`:
```python
class ToolsEnabledConfig(BaseModel):
    your_tool: bool = True
```

## Best Practices

- **Return strings** — Tools always return text for the LLM
- **Handle errors gracefully** — Return error messages, don't raise
- **Use async** — Use `httpx` for HTTP, `asyncio` for I/O
- **Keep it concise** — LLMs work better with shorter tool outputs
- **Add type hints** — Follow the project's typing standard
- **Document parameters** — The LLM uses descriptions to understand usage
