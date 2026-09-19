"""Semantic tool registry shared by Conversations V2 and MCP transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..agent_v2.contracts import RequestContext


class ToolError(RuntimeError):
    code = "tool_failed"


class ToolNotFound(ToolError):
    code = "tool_not_found"


class ToolForbidden(ToolError):
    code = "tool_forbidden"


class ToolInputError(ToolError):
    code = "invalid_tool_input"


def _matches_type(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return expected in checks and checks[expected](value)


def _validate(value: Any, schema: dict[str, Any], path: str = "arguments") -> None:
    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected] if expected else []
    if expected_types and not any(_matches_type(value, item) for item in expected_types):
        raise ToolInputError(f"{path} possui tipo inválido.")
    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in value:
                raise ToolInputError(f"Campo obrigatório ausente: {name}.")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ToolInputError(f"Campo não permitido: {extra[0]}.")
        for name, item in value.items():
            if name in properties:
                _validate(item, properties[name], f"{path}.{name}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            raise ToolInputError(f"{path} é muito curto.")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            raise ToolInputError(f"{path} excede o tamanho permitido.")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolInputError(f"{path} está abaixo do mínimo permitido.")
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolInputError(f"{path} excede o máximo permitido.")
    if "enum" in schema and value not in schema["enum"]:
        raise ToolInputError(f"{path} possui valor inválido.")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    capability: str
    effect: str
    input_schema: dict[str, Any]
    handler: Callable[[RequestContext, dict[str, Any]], Any]
    requires_project: bool = False
    version: str = "1.0.0"
    exposures: tuple[str, ...] = ("internal",)
    output_schema: dict[str, Any] | None = None

    def public_schema(self) -> dict[str, Any]:
        value = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "readOnlyHint": self.effect == "read", "destructiveHint": self.effect == "write",
                "idempotentHint": self.effect == "read",
            },
            "_meta": {"cadu/toolVersion": self.version, "cadu/effect": self.effect},
        }
        if self.output_schema:
            value["outputSchema"] = self.output_schema
        return value


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Ferramenta duplicada: {definition.name}")
        if definition.effect not in {"read", "draft", "write"}:
            raise ValueError("Efeito de ferramenta inválido.")
        self._tools[definition.name] = definition

    def list(self, context: RequestContext, exposure: str = "internal") -> list[dict[str, Any]]:
        return [self._tools[name].public_schema() for name in sorted(self._tools)
                if self._tools[name].capability in context.capabilities
                and exposure in self._tools[name].exposures]

    def execute(self, name: str, arguments: dict[str, Any], context: RequestContext,
                exposure: str = "internal") -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise ToolNotFound("Ferramenta indisponível.")
        if tool.capability not in context.capabilities:
            raise ToolForbidden("Esta capacidade não está disponível neste contexto.")
        if exposure not in tool.exposures:
            raise ToolForbidden("Esta ferramenta não está disponível para este tipo de agente.")
        if tool.requires_project and not context.project_ref:
            raise ToolInputError("Selecione um projeto para executar esta ação.")
        if not isinstance(arguments, dict):
            raise ToolInputError("Os argumentos da ferramenta precisam ser um objeto.")
        _validate(arguments, tool.input_schema)
        return tool.handler(context, arguments)


registry = ToolRegistry()


def register_tool(*, name: str, description: str, capability: str, effect: str = "read",
                  input_schema: dict[str, Any] | None = None, requires_project: bool = False,
                  version: str = "1.0.0", exposures: tuple[str, ...] = ("internal",),
                  output_schema: dict[str, Any] | None = None):
    def decorator(handler):
        registry.register(ToolDefinition(
            name=name, description=description, capability=capability, effect=effect,
            input_schema=input_schema or {"type": "object", "properties": {}, "additionalProperties": False},
            handler=handler, requires_project=requires_project, version=version,
            exposures=exposures, output_schema=output_schema,
        ))
        return handler
    return decorator


def load_builtin_tools() -> ToolRegistry:
    # Imports register functions once through Python's module cache.
    from .tools import artifacts, brands, planner, projects, reports, workspace  # noqa: F401
    return registry
