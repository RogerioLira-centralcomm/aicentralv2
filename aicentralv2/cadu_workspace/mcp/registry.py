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
                "readOnlyHint": self.effect == "read", "destructiveHint": False,
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
    from .tools import planner, reports, workspace  # noqa: F401
    return registry
