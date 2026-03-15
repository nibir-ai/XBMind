"""Google Gemini API LLM provider.

Optional cloud-based LLM using the Google Generative AI SDK.
Requires the ``GOOGLE_API_KEY`` environment variable.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from xbmind.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolDefinition
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import GeminiConfig

log = get_logger(__name__)


class GeminiLLM(LLMProvider):
    """Google Gemini API LLM provider.

    Uses the ``google-generativeai`` SDK for chat completions
    with function calling support.

    Example::

        llm = GeminiLLM(config)
        await llm.start()
        response = await llm.generate(messages, tools)
    """

    def __init__(self, config: GeminiConfig) -> None:
        """Initialise the Gemini provider.

        Args:
            config: Gemini configuration section.
        """
        self._config = config
        self._model: Any = None

    @property
    def name(self) -> str:
        """Human-readable name of this LLM provider."""
        return f"Gemini ({self._config.model})"

    async def start(self) -> None:
        """Configure the Gemini SDK and create the model."""
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            log.warning("llm.gemini.no_api_key")

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self._config.model)
        log.info("llm.gemini.started", model=self._config.model)

    async def stop(self) -> None:
        """Clean up resources."""
        self._model = None
        log.info("llm.gemini.stopped")

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Generate a response using Gemini's API.

        Args:
            messages: Conversation messages.
            tools: Optional tool definitions for function calling.

        Returns:
            An :class:`LLMResponse` with the model's output.

        Raises:
            RuntimeError: If the model has not been started.
        """
        if self._model is None:
            raise RuntimeError("Model not started — call start() first")

        import google.generativeai as genai

        # Build contents for Gemini
        contents: list[dict[str, Any]] = []
        system_instruction: str | None = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
                continue

            role = "user" if msg.role in ("user", "tool") else "model"
            parts: list[dict[str, Any]] = []

            if msg.content:
                parts.append({"text": msg.content})

            if msg.role == "tool" and msg.name:
                parts = [
                    {
                        "function_response": {
                            "name": msg.name,
                            "response": {"result": msg.content},
                        }
                    }
                ]

            if parts:
                contents.append({"role": role, "parts": parts})

        # Build tool declarations
        gemini_tools = None
        if tools:
            function_declarations = []
            for t in tools:
                function_declarations.append(
                    genai.protos.FunctionDeclaration(
                        name=t.name,
                        description=t.description,
                        parameters=self._convert_schema(t.parameters),
                    )
                )
            gemini_tools = [genai.protos.Tool(function_declarations=function_declarations)]

        # Create model with system instruction if needed
        model = self._model
        if system_instruction:
            model = genai.GenerativeModel(
                self._config.model,
                system_instruction=system_instruction,
            )

        generation_config = genai.GenerationConfig(
            temperature=self._config.temperature,
            max_output_tokens=self._config.max_tokens,
        )

        response = await model.generate_content_async(
            contents,
            tools=gemini_tools,
            generation_config=generation_config,
        )

        # Parse response
        content_text = ""
        tool_calls: list[ToolCall] = []

        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content_text += part.text
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    tool_calls.append(
                        ToolCall(name=fc.name, arguments=args, id=f"gemini_{fc.name}")
                    )

        finish = "tool_calls" if tool_calls else "stop"
        usage_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage_tokens = getattr(response.usage_metadata, "total_token_count", 0)

        log.info(
            "llm.gemini.response",
            content_length=len(content_text),
            tool_calls=len(tool_calls),
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=finish,
            model=self._config.model,
            usage_tokens=usage_tokens,
        )

    def _convert_schema(self, schema: dict[str, Any]) -> Any:
        """Convert JSON Schema to Gemini's protobuf Schema format.

        Args:
            schema: A JSON Schema dict.

        Returns:
            A Gemini-compatible schema object.
        """
        import google.generativeai as genai

        type_mapping = {
            "string": genai.protos.Type.STRING,
            "number": genai.protos.Type.NUMBER,
            "integer": genai.protos.Type.INTEGER,
            "boolean": genai.protos.Type.BOOLEAN,
            "array": genai.protos.Type.ARRAY,
            "object": genai.protos.Type.OBJECT,
        }

        schema_type = type_mapping.get(schema.get("type", "object"), genai.protos.Type.OBJECT)

        properties = {}
        schema_props = schema.get("properties", {})
        for prop_name, prop_schema in schema_props.items():
            prop_type = type_mapping.get(
                prop_schema.get("type", "string"), genai.protos.Type.STRING
            )
            properties[prop_name] = genai.protos.Schema(
                type=prop_type,
                description=prop_schema.get("description", ""),
            )

        return genai.protos.Schema(
            type=schema_type,
            properties=properties if properties else None,
            required=schema.get("required"),
            description=schema.get("description", ""),
        )
