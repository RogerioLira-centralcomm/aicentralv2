"""Fingerprint do contrato e ValidationReport. Sem HTML, sem run, sem Playwright."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator

from .revision import read_revision
from .runtime_policy import IDENTITY_TOKEN_IDS
from .schema import dump_system, parse_system

VALID_STATES = ("ok", "stale", "unchecked")
COPY_KEYS = ("headline", "support", "cta", "legal")


class ValidationReport(BaseModel):
    passed: bool = False
    score: float = 0.0
    defects: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    fingerprint: str = ""
    fingerprint_short: str = ""
    checked_formats: List[str] = Field(default_factory=list)
    formats: Dict[str, str] = Field(default_factory=dict)
    stale_count: int = 0
    render: str = "skipped"

    @field_validator("render")
    @classmethod
    def _render(cls, value):
        text = str(value or "skipped").strip().lower()
        return text if text in {"skipped", "passed", "failed"} else "skipped"


def contract_payload(system):
    """Contrato estável: tinta protegida, DNA, copy, URLs de trilha, revision."""
    parsed = parse_system(system)
    tokens = parsed.tokens or {}
    copy = parsed.ad_copy or {}
    dna = parsed.dna or {}
    tracks = []
    for item in parsed.tracks or []:
        if not isinstance(item, dict):
            continue
        track_id = str(item.get("id") or "").strip()
        if not track_id:
            continue
        tracks.append({"id": track_id, "url": str(item.get("url") or "")})
    tracks.sort(key=lambda item: item["id"])
    return {
        "revision": read_revision(parsed),
        "tokens": {key: str(tokens.get(key) or "") for key in IDENTITY_TOKEN_IDS},
        "dna": {
            "name": str(dna.get("name") or ""),
            "personality": [str(item) for item in (dna.get("personality") or [])],
            "must": [str(item) for item in (dna.get("must") or [])],
            "avoid": [str(item) for item in (dna.get("avoid") or [])],
        },
        "ad_copy": {key: str(copy.get(key) or "") for key in COPY_KEYS},
        "ad_copy_by_format": {
            str(key): {
                field: str((payload or {}).get(field) or "")
                for field in COPY_KEYS
                if str((payload or {}).get(field) or "").strip()
            }
            for key, payload in sorted((getattr(parsed, "ad_copy_by_format", None) or {}).items())
            if isinstance(payload, dict)
        },
        "tracks": tracks,
    }


def contract_fingerprint(system):
    payload = contract_payload(system)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_short(digest):
    return str(digest or "")[:8]


def format_keys():
    from .adapt import list_iab_formats

    return [str(item.get("key") or "") for item in list_iab_formats() if item.get("key")]


def stored_validation(system):
    evidence = getattr(system, "evidence", None) or {}
    if isinstance(system, dict):
        evidence = system.get("evidence") or {}
    raw = evidence.get("validation") if isinstance(evidence, dict) else None
    if not isinstance(raw, dict):
        return {"fingerprint": "", "formats": {}}
    formats = {}
    incoming = raw.get("formats") if isinstance(raw.get("formats"), dict) else {}
    for key, state in incoming.items():
        text = str(state or "unchecked").strip().lower()
        formats[str(key)] = text if text in VALID_STATES else "unchecked"
    return {
        "fingerprint": str(raw.get("fingerprint") or ""),
        "formats": formats,
    }


def reconcile_formats(previous, fingerprint):
    keys = format_keys()
    previous = previous if isinstance(previous, dict) else {}
    stored_fp = str(previous.get("fingerprint") or "")
    stored_formats = previous.get("formats") if isinstance(previous.get("formats"), dict) else {}
    formats = {}
    changed = bool(stored_fp) and stored_fp != fingerprint
    for key in keys:
        previous_state = str(stored_formats.get(key) or "unchecked")
        if previous_state not in VALID_STATES:
            previous_state = "unchecked"
        if not stored_fp:
            formats[key] = "unchecked"
        elif changed:
            formats[key] = "stale"
        else:
            formats[key] = previous_state
    return formats


def contract_defects(system):
    parsed = parse_system(system)
    defects = []
    contrast = parsed.contrast or {}
    if not contrast.get("passed"):
        defects.append("Contraste abaixo de 4.5:1.")
    tokens = parsed.tokens or {}
    if not str(tokens.get("ink") or "").strip():
        defects.append("Tinta ausente.")
    if not str(tokens.get("paper") or "").strip():
        defects.append("Papel ausente.")
    return defects[:8]


def build_validation_report(system, *, previous=None):
    parsed = parse_system(system)
    digest = contract_fingerprint(parsed)
    stored = previous if previous is not None else stored_validation(parsed)
    formats = reconcile_formats(stored, digest)
    defects = contract_defects(parsed)
    stale = sum(1 for state in formats.values() if state == "stale")
    passed = not defects
    notes = []
    if stale:
        notes.append(f"{stale} formato{'s' if stale != 1 else ''} stale.")
    elif not stored.get("fingerprint"):
        notes.append("Formatos ainda não conferidos.")
    return ValidationReport(
        passed=passed,
        score=1.0 if passed and not stale else (0.7 if passed else 0.4),
        defects=defects,
        notes=notes,
        fingerprint=digest,
        fingerprint_short=fingerprint_short(digest),
        checked_formats=[key for key, state in formats.items() if state != "unchecked"],
        formats=formats,
        stale_count=stale,
        render="skipped",
    )


def validation_summary(report):
    """O que entra no JSON canônico. Defeitos ficam só na resposta."""
    data = report if isinstance(report, ValidationReport) else ValidationReport.model_validate(report)
    return {
        "fingerprint": data.fingerprint,
        "formats": dict(data.formats),
    }


def mark_format_state(system, format_key, state="ok"):
    parsed = parse_system(system)
    chosen = str(state or "unchecked").strip().lower()
    if chosen not in VALID_STATES:
        chosen = "unchecked"
    data = dump_system(parsed)
    evidence = dict(data.get("evidence") or {})
    current = stored_validation(parsed)
    formats = dict(current.get("formats") or {})
    key = str(format_key or "").strip()
    if key:
        formats[key] = chosen
    evidence["validation"] = {
        "fingerprint": current.get("fingerprint") or contract_fingerprint(parsed),
        "formats": formats,
    }
    data["evidence"] = evidence
    return parse_system(data)


def stamp_validation(system, previous=None):
    parsed = parse_system(system)
    report = build_validation_report(parsed, previous=previous)
    data = dump_system(parsed)
    evidence = dict(data.get("evidence") or {})
    evidence["validation"] = validation_summary(report)
    data["evidence"] = evidence
    return parse_system(data), report


def attach_validation_payload(data, system, *, previous=None, report=None):
    parsed = parse_system(system)
    report = (
        report
        if isinstance(report, ValidationReport)
        else build_validation_report(parsed, previous=previous)
    )
    payload = data if isinstance(data, dict) else {}
    dumped = report.model_dump()
    payload["fingerprint"] = dumped["fingerprint"]
    payload["fingerprint_short"] = dumped["fingerprint_short"]
    payload["validation"] = dumped
    catalog = payload.get("catalog")
    if isinstance(catalog, dict) and isinstance(catalog.get("iab_formats"), list):
        catalog["iab_formats"] = [
            {**item, "valid": report.formats.get(item.get("key"), "unchecked")}
            for item in catalog["iab_formats"]
            if isinstance(item, dict)
        ]
        payload["iab_formats"] = catalog["iab_formats"]
    from .pendencies import attach_pendencies

    payload = attach_pendencies(payload, parsed, report=report)
    evidence = payload.get("evidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("validation"), dict):
        evidence["validation"] = validation_summary(report)
    return payload
