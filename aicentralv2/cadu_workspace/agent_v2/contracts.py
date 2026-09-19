"""Small, provider-neutral contracts used by the V2 agent runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SURFACES = frozenset({"conversations", "workspace", "planner", "studio", "reports"})
RESPONSE_MODES = frozenset({"direct", "analysis", "decision", "artifact_first", "clarification"})
COMPLEXITIES = frozenset({"low", "medium", "high"})


@dataclass(frozen=True)
class ActiveObject:
    type: str
    id: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RequestContext:
    organization_id: int
    client_id: int
    user_id: int
    conversation_id: str | None
    surface: str
    project_ref: str | None = None
    brand_ref: str | None = None
    active_object: ActiveObject | None = None
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.surface not in SURFACES:
            raise ValueError("Superfície inválida.")
        if self.organization_id != self.client_id:
            raise ValueError("O contexto V2 não permite trocar de tenant.")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["capabilities"] = list(self.capabilities)
        return value


@dataclass(frozen=True)
class IntentRoute:
    domain: str
    action: str
    complexity: str
    response_mode: str
    needs_context: tuple[str, ...] = ()
    needs_tools: tuple[str, ...] = ()
    artifact_type: str | None = None
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if self.complexity not in COMPLEXITIES:
            raise ValueError("Complexidade inválida.")
        if self.response_mode not in RESPONSE_MODES:
            raise ValueError("Modo de resposta inválido.")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["needs_context"] = list(self.needs_context)
        value["needs_tools"] = list(self.needs_tools)
        return value


@dataclass(frozen=True)
class ExecutionBudget:
    max_llm_calls: int = 1
    max_tool_calls: int = 4
    max_context_chars: int = 16000
    max_output_tokens: int = 1200


@dataclass
class AgentResponse:
    answer: str
    confidence: str = "medium"
    assumptions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    artifact_patch: dict[str, Any] | None = None
    citations: list[dict[str, str]] = field(default_factory=list)
