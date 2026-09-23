"""Clean user-provided reference messages and derive factual project context."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse


def clean_user_message(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).replace("\\_", "_")
    text = "".join(character for character in text if character in "\n\t" or unicodedata.category(character) != "Cc")
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1: \2", text, flags=re.IGNORECASE)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _user_context(message: str, url: str) -> str:
    value = message.replace(url, " ")
    value = re.sub(r"https?://[^\s]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(
        r"^\s*(?:por favor\s*,?\s*)?(?:adicione|adicionar|salve|salvar|registre|registrar|anexe|anexar|importe|importar)"
        r"(?:\s+(?:este|esse|o|um))?\s+(?:link|url|refer[eê]ncia)?\s*(?:ao|no|para o)?\s*projeto?\s*[:\-]?",
        "", value, flags=re.IGNORECASE,
    )
    value = re.sub(r"\b(?:pode\s+aprovar\s+por\s+mim|sem\s+(?:pedir\s+)?confirma[cç][aã]o)\b", "", value, flags=re.IGNORECASE)
    return " ".join(value.split()).strip(" .,:;–—-")[:1000]


PROJECT_ITEM_KINDS = {"reference", "activity", "task", "decision", "document_reference"}


def reference_context(*, message: str = "", url: str, descriptor: dict, meeting: dict | None = None,
                      requested_kind: str = "") -> dict:
    cleaned = clean_user_message(message)[:5000]
    meeting = meeting if isinstance(meeting, dict) else {}
    title = str(descriptor.get("title") or "").strip()
    provider = str(meeting.get("platform") or descriptor.get("provider") or urlparse(url).hostname or "Link")
    if meeting:
        starts = str(meeting.get("starts_at") or "")
        when = ""
        if starts:
            try:
                date, clock = starts[:10].split("-"), starts[11:16]
                when = f", em {date[2]}/{date[1]}/{date[0]} às {clock}"
            except (ValueError, IndexError):
                when = ""
        summary = f"Reunião “{title}” via {provider}{when}."
        event_type, event_label = "meeting_reference_added", "Reunião adicionada"
        item_kind = "activity"
    else:
        supplied = _user_context(cleaned, url)
        generic_titles = {"", str(descriptor.get("provider") or ""), (urlparse(url).hostname or "").removeprefix("www.")}
        inferred_title = supplied[:180] if supplied else title
        title = inferred_title or title
        summary = supplied or f"Referência de {provider}: {title}."
        if re.search(r"\b(?:tarefa|entrega|prazo|to[ -]?do|a[cç][aã]o)\b", supplied, re.IGNORECASE):
            item_kind, event_type, event_label = "task", "task_reference_added", "Tarefa adicionada"
        elif re.search(r"\b(?:decis[aã]o|aprovad[oa]|defini[cç][aã]o)\b", supplied, re.IGNORECASE):
            item_kind, event_type, event_label = "decision", "decision_reference_added", "Decisão adicionada"
        elif descriptor.get("resource_kind") in {"document", "drive_file", "spreadsheet", "presentation"}:
            item_kind, event_type, event_label = "document_reference", "document_reference_added", "Documento adicionado"
        else:
            item_kind, event_type, event_label = "reference", "link_reference_added", "Referência adicionada"
    if requested_kind in PROJECT_ITEM_KINDS:
        item_kind = requested_kind
    return {
        "user_message": cleaned or None,
        "context_summary": summary[:1000],
        "suggested_title": title[:180],
        "project_item_kind": item_kind,
        "timeline": {
            "event_type": event_type, "label": event_label,
            "detail": summary[:1000], "occurred_at": meeting.get("starts_at"), "item_kind": item_kind,
        },
    }
