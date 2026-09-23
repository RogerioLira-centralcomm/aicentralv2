"""Canonical artifact capabilities shared by runtime, HTTP and MCP surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from werkzeug.exceptions import BadRequest


@dataclass(frozen=True)
class ArtifactDefinition:
    type: str
    user_label: str
    editor: str
    indexable: bool = True
    publishable: bool = False
    agent_editable: bool = True
    max_content_bytes: int = 1_000_000

    def to_dict(self) -> dict:
        return asdict(self)


DEFINITIONS = {
    item.type: item for item in (
        ArtifactDefinition("brief", "Briefing", "structured_document"),
        ArtifactDefinition("document", "Documento", "rich_document"),
        ArtifactDefinition("note", "Nota", "rich_document"),
        ArtifactDefinition("executive_summary", "Resumo executivo", "rich_document"),
        ArtifactDefinition("media_plan", "Plano de mídia", "structured_document"),
        ArtifactDefinition("scenario", "Cenário", "structured_document"),
        ArtifactDefinition("research", "Pesquisa", "research_document"),
        ArtifactDefinition("project_map", "Mapa do projeto", "project_map", indexable=False),
        ArtifactDefinition("html", "Página interativa", "html", indexable=True,
                           publishable=True, max_content_bytes=2_000_000),
        ArtifactDefinition("meeting_summary", "Resumo de reunião", "meeting"),
        ArtifactDefinition("meeting_agenda", "Pauta de reunião", "meeting"),
        ArtifactDefinition("link_reader", "Referência", "link_reader", indexable=False,
                           agent_editable=False),
    )
}

ALLOWED_TYPES = frozenset(DEFINITIONS)


def definition(artifact_type: str) -> ArtifactDefinition:
    item = DEFINITIONS.get(str(artifact_type or ""))
    if not item:
        raise BadRequest("Tipo de entrega inválido.")
    return item


def describe() -> list[dict]:
    return [DEFINITIONS[name].to_dict() for name in sorted(DEFINITIONS)]
