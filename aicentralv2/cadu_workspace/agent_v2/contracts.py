"""Small, provider-neutral contracts used by the V2 agent runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SURFACES = frozenset({"conversations", "workspace", "planner", "studio", "reports"})
RESPONSE_MODES = frozenset({"direct", "analysis", "decision", "artifact_first", "clarification"})
COMPLEXITIES = frozenset({"low", "medium", "high"})
EXECUTION_MODES = frozenset({"fast", "analysis", "agentic"})


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
    request_id: str | None = None
    project_ref: str | None = None
    brand_ref: str | None = None
    active_object: ActiveObject | None = None
    capabilities: tuple[str, ...] = ()
    selected_context: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.surface not in SURFACES:
            raise ValueError("Superfície inválida.")
        if self.organization_id <= 0 or self.client_id <= 0:
            raise ValueError("O contexto V2 precisa de uma agência e um cliente válidos.")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        # Legacy database writes still use this field internally. The agent,
        # model payload and delegated context are scoped by client_id only.
        value.pop("organization_id", None)
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
    max_duration_ms: int = 90000


def execution_mode_for(route: IntentRoute, requested: str = "") -> str:
    requested = str(requested or "").strip().lower()
    aliases = {"focus": "fast", "deep": "analysis"}
    requested = aliases.get(requested, requested)
    # Confirmations, executable HTML, project maps and genuinely complex work
    # need the operator runtime. Text artifacts remain on the analysis runtime:
    # opening an editor must not promote a short note or meeting summary to the
    # most expensive execution path.
    if route.requires_confirmation or route.artifact_type in {"html", "project_map"} or route.complexity == "high":
        return "agentic"
    if route.artifact_type:
        return "analysis"
    if requested in EXECUTION_MODES:
        if requested == "agentic" and not (route.artifact_type or route.requires_confirmation or route.complexity == "high"):
            return "analysis"
        return requested
    if route.complexity == "low" and not route.needs_tools:
        return "fast"
    return "analysis"


@dataclass
class AgentResponse:
    answer: str
    confidence: str = "medium"
    assumptions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    artifact_patch: dict[str, Any] | None = None
    citations: list[dict[str, str]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    task_proposal: dict[str, Any] | None = None
    plugin: dict[str, str] | None = None
