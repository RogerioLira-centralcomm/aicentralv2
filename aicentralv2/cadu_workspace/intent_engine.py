"""Canonical pt-BR intent interpretation shared by Chat and MCP surfaces.

Interpretation is deliberately side-effect free. Authorization and execution
remain the responsibility of the tool registry and its transport principal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any

from .conversations.guardrails import normalize_colloquial


_REFERENCE = re.compile(
    r"\b(?:isso|isto|aquilo|disso|disto|daquilo|esse|essa|este|esta|desse|dessa|deste|desta|aquele|aquela)\b|"
    r"\b(?:[uú]ltima|[uú]ltimo)\s+(?:resposta|texto|resumo|vers[aã]o)\b|"
    r"\bo\s+que\s+(?:voc[eê]\s+)?(?:escreveu|respondeu|gerou|fez|montou)\b|"
    r"\b(?:nossa|essa)\s+conversa\b",
    re.IGNORECASE,
)
_PERSIST = re.compile(
    r"\b(?:salv\w*|guard\w*|registr\w*|arquiv\w*|adicion\w*|inclu\w*|anex\w*|"
    r"vincul\w*|aproveit\w*|sub\w*|jog\w*|bot\w*|p(?:o|õ)e|coloc\w*|mand\w*)\b"
    r".{0,70}\b(?:projeto|campanha|biblioteca|pasta|workspace|trabalho)\b|"
    r"\b(?:projeto|campanha|biblioteca|pasta|workspace)\b.{0,70}"
    r"\b(?:salv\w*|guard\w*|registr\w*|adicion\w*|inclu\w*|anex\w*|vincul\w*|jog\w*|coloc\w*)\b",
    re.IGNORECASE,
)
_CREATE = re.compile(
    r"\b(?:cri\w*|fa[çc]\w*|mont\w*|ger\w*|transform\w*|convert\w*|vir\w*|"
    r"organiz\w*|estrutur\w*|fech\w*|consolid\w*|coloc\w*)\b.{0,70}"
    r"\b(?:artefato|arquivo|documento|doc|rascunho|entrega|apresenta[cç][aã]o|slides?|planilha|nota)\b|"
    r"\b(?:artefato|arquivo|documento|doc|rascunho|entrega|apresenta[cç][aã]o|slides?|planilha|nota)\b"
    r".{0,50}\b(?:disso|disto|daquilo|desse|dessa|edit[aá]vel)\b",
    re.IGNORECASE,
)
_KEEP = re.compile(
    r"\b(?:guard\w*|salv\w*|registr\w*|arquiv\w*|deix\w*\s+salv\w*)\b"
    r".{0,70}\b(?:isso|isto|aquilo|esse|essa|texto|resumo|resposta|conte[uú]do|material)\b|"
    r"\b(?:isso|isto|aquilo|esse|essa|texto|resumo|resposta|conte[uú]do|material)\b"
    r".{0,70}\b(?:guard\w*|salv\w*|registr\w*|arquiv\w*)\b",
    re.IGNORECASE,
)
_NEGATE_CREATE = re.compile(
    r"\b(?:n[aã]o|nem|sem|ainda\s+n[aã]o)\b.{0,50}"
    r"\b(?:cri\w*|ger\w*|mont\w*|transform\w*|artefato|documento|rascunho)\b",
    re.IGNORECASE,
)
_NEGATE_SAVE = re.compile(
    r"\b(?:n[aã]o|nem|sem|ainda\s+n[aã]o)\b.{0,55}"
    r"\b(?:salv\w*|guard\w*|registr\w*|adicion\w*|inclu\w*|mand\w*|projeto)\b",
    re.IGNORECASE,
)
_CONFIRM = re.compile(
    r"^\s*(?:sim|pode|pode\s+(?:fazer|seguir|criar|salvar|mandar)|manda\s+ver|"
    r"vai\s+nessa|segue|fechou|beleza|perfeito|[ée]\s+isso|ok+)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_PERSON_RESEARCH = re.compile(
    r"\b(?:quem\s+(?:[ée]|foi)|biografia|hist[oó]ria|trajet[oó]ria|carreira|legado)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IntentResult:
    intent_id: str
    intent: str
    source: str
    destination: str
    format: str
    explicit: bool
    negated: bool
    confidence: str
    requires_confirmation: bool
    proposed_tool: str | None
    missing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["missing"] = list(self.missing)
        return value


def _format(text: str) -> str:
    if re.search(r"\b(?:apresenta[cç][aã]o|slides?|pptx?)\b", text):
        return "presentation"
    if re.search(r"\b(?:planilha|xlsx?|excel)\b", text):
        return "spreadsheet"
    if re.search(r"\b(?:nota|anota[cç][aã]o)\b", text):
        return "note"
    return "document"


def interpret(message: str, *, has_project: bool = False, has_source: bool = False,
              pending_action: bool = False, surface: str = "chat") -> IntentResult:
    text = normalize_colloquial(message)[:20_000]
    reference = bool(_REFERENCE.search(text))
    persist = bool(_PERSIST.search(text))
    create = bool(_CREATE.search(text))
    keep = bool(_KEEP.search(text))
    negate_create = bool(_NEGATE_CREATE.search(text))
    negate_save = bool(_NEGATE_SAVE.search(text))
    confirms = bool(_CONFIRM.match(text))
    intent, destination, proposed_tool = "answer", "none", None
    explicit, negated, requires_confirmation = False, False, False
    missing: list[str] = []

    if confirms and pending_action:
        intent, explicit = "confirm_pending_action", True
    elif create and negate_create:
        intent, negated = "answer", True
    elif persist and negate_save:
        intent, destination, negated = ("create_artifact" if create else "answer"), "session", True
        proposed_tool = "artifacts.create_draft" if create else None
    elif persist:
        intent, destination, explicit = "persist_content", "active_project", True
        proposed_tool = "artifacts.create_draft"
        if not has_project:
            missing.append("project")
    elif keep:
        intent, destination, explicit = "create_artifact", "session", True
        proposed_tool = "artifacts.create_draft"
    elif create:
        intent, destination, explicit = "create_artifact", "session", True
        proposed_tool = "artifacts.create_draft"
    elif _PERSON_RESEARCH.search(text):
        intent, destination = "research_entity", "response"
        proposed_tool = "web.search"

    source = "referenced_content" if reference else "inline_content" if has_source else "current_request"
    if intent in {"persist_content", "create_artifact"} and reference and not has_source and surface == "public_mcp":
        missing.append("source")
    confidence = "high" if explicit or intent == "research_entity" else "low"
    stable = json.dumps({"text": text, "intent": intent, "source": source, "destination": destination,
                         "format": _format(text)}, ensure_ascii=False, sort_keys=True)
    return IntentResult(
        intent_id="intent_" + sha256(stable.encode()).hexdigest()[:24], intent=intent,
        source=source, destination=destination, format=_format(text), explicit=explicit,
        negated=negated, confidence=confidence, requires_confirmation=requires_confirmation,
        proposed_tool=proposed_tool, missing=tuple(dict.fromkeys(missing)),
    )
