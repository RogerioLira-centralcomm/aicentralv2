"""Proveniência da identidade: confirmed / inferred / fallback / unknown."""

from __future__ import annotations

from .schema import dump_system, parse_system

STATES = ("confirmed", "inferred", "fallback", "unknown")
COMPOSE_MODES = ("model", "local_seed", "unknown")
REVIEW_KINDS = ("none", "local", "model")
IDENTITY_TOKENS = (
    "paper",
    "ink",
    "accent",
    "highlight",
    "cta_ink",
    "muted",
    "font-display",
    "font-body",
    "logo",
)
SERVER_OWNED = (
    "status",
    "framework",
    "passes",
    "contrast",
    "css_vars",
    "tailwind",
    "specimen_html",
    "revision",
    "version",
    "needs_input",
)
LLM_COMPOSE_KEYS = (
    "dna",
    "archetype",
    "ad_copy",
    "ad_copy_by_format",
    "needs_input",
    "patches",
    "effects",
    "tracks",
    "notes",
    "passed",
    "score",
    "defects",
    "creative_line",
    "ground-kind",
)
LLM_REFINE_KEYS = (
    "passed",
    "score",
    "defects",
    "notes",
    "patches",
    "ground-kind",
)
LLM_REVIEW_KEYS = (
    "passed",
    "score",
    "defects",
    "notes",
    "patches",
    "dna",
    "ad_copy",
)
LLM_CAMPAIGN_KEYS = (
    "creative_line",
    "ad_copy",
    "ad_copy_by_format",
    "archetype",
    "tracks",
    "ground-kind",
    "overlay",
    "wash-strength",
    "grain",
    "notes",
    "passed",
    "score",
    "defects",
)


def empty_provenance():
    return {
        "compose_mode": "unknown",
        "review": {"kind": "none", "score": 0.0, "notes": []},
        "needs_confirmation": True,
        "fields": {},
    }


def field_record(state, origin, evidence_ids=None):
    kind = str(state or "unknown").strip().lower()
    if kind not in STATES:
        kind = "unknown"
    return {
        "state": kind,
        "origin": str(origin or "")[:80],
        "evidence_ids": [str(item)[:120] for item in (evidence_ids or [])][:8],
    }


def get_provenance(system):
    parsed = parse_system(system)
    evidence = parsed.evidence if isinstance(parsed.evidence, dict) else {}
    raw = evidence.get("provenance")
    if not isinstance(raw, dict):
        return empty_provenance()
    fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
    review = raw.get("review") if isinstance(raw.get("review"), dict) else {}
    mode = str(raw.get("compose_mode") or "unknown").strip().lower()
    if mode not in COMPOSE_MODES:
        mode = "unknown"
    kind = str(review.get("kind") or "none").strip().lower()
    if kind not in REVIEW_KINDS:
        kind = "none"
    try:
        score = float(review.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return {
        "compose_mode": mode,
        "review": {
            "kind": kind,
            "score": score,
            "notes": [str(item)[:200] for item in (review.get("notes") or [])][:6],
        },
        "needs_confirmation": bool(raw.get("needs_confirmation", True)),
        "fields": {
            key: field_record(
                (item or {}).get("state"),
                (item or {}).get("origin"),
                (item or {}).get("evidence_ids"),
            )
            for key, item in fields.items()
            if isinstance(item, dict)
        },
    }


def _write_provenance(system, provenance):
    parsed = parse_system(system)
    data = dump_system(parsed)
    evidence = dict(data.get("evidence") or {})
    fields = provenance.get("fields") if isinstance(provenance.get("fields"), dict) else {}
    needs = bool(provenance.get("needs_confirmation"))
    if not needs:
        needs = _compute_needs_confirmation(parsed, provenance)
    evidence["provenance"] = {
        "compose_mode": provenance.get("compose_mode") or "unknown",
        "review": dict(provenance.get("review") or {"kind": "none", "score": 0.0, "notes": []}),
        "needs_confirmation": needs,
        "fields": fields,
    }
    data["evidence"] = evidence
    return parse_system(data)


def _compute_needs_confirmation(parsed, provenance):
    if parsed.source == "tailwind-centralcomm":
        return False
    if parsed.status == "approved":
        review = (provenance.get("review") or {}).get("kind")
        if review == "model":
            return False
    fields = provenance.get("fields") or {}
    for key in IDENTITY_TOKENS:
        record = fields.get(f"tokens.{key}") or {}
        state = record.get("state")
        if state in {"fallback", "unknown"}:
            return True
    if (provenance.get("compose_mode") or "") == "local_seed":
        return True
    if (provenance.get("review") or {}).get("kind") != "model":
        return parsed.source != "tailwind-centralcomm"
    return False


def ensure_provenance(system):
    """Legado sem bloco: unknown. Não atribui confirmed."""
    parsed = parse_system(system)
    evidence = parsed.evidence if isinstance(parsed.evidence, dict) else {}
    if isinstance(evidence.get("provenance"), dict) and evidence["provenance"].get("fields"):
        current = get_provenance(parsed)
        current["needs_confirmation"] = _compute_needs_confirmation(parsed, current)
        return _write_provenance(parsed, current)
    provenance = empty_provenance()
    if parsed.source == "tailwind-centralcomm":
        return stamp_centralcomm(parsed)
    for key in IDENTITY_TOKENS:
        if (parsed.tokens or {}).get(key) not in (None, ""):
            provenance["fields"][f"tokens.{key}"] = field_record("unknown", "legacy")
    provenance["needs_confirmation"] = True
    return _write_provenance(parsed, provenance)


def stamp_field(system, path, state, origin, evidence_ids=None):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    provenance["fields"][path] = field_record(state, origin, evidence_ids)
    provenance["needs_confirmation"] = _compute_needs_confirmation(parsed, provenance)
    return _write_provenance(parsed, provenance)


def stamp_fields(system, records):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    for path, item in (records or {}).items():
        if not isinstance(item, dict):
            continue
        provenance["fields"][path] = field_record(
            item.get("state"),
            item.get("origin"),
            item.get("evidence_ids"),
        )
    provenance["needs_confirmation"] = _compute_needs_confirmation(parsed, provenance)
    return _write_provenance(parsed, provenance)


def stamp_centralcomm(system):
    parsed = parse_system(system)
    provenance = empty_provenance()
    provenance["compose_mode"] = "unknown"
    provenance["review"] = {"kind": "none", "score": 1.0, "notes": ["Preset da casa."]}
    provenance["needs_confirmation"] = False
    for key in IDENTITY_TOKENS:
        provenance["fields"][f"tokens.{key}"] = field_record(
            "confirmed", "preset-centralcomm"
        )
    return _write_provenance(parsed, provenance)


def set_compose_mode(system, mode):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    chosen = str(mode or "unknown").strip().lower()
    provenance["compose_mode"] = chosen if chosen in COMPOSE_MODES else "unknown"
    provenance["needs_confirmation"] = _compute_needs_confirmation(parsed, provenance)
    return _write_provenance(parsed, provenance)


def set_review(system, kind, score=0.0, notes=None):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    chosen = str(kind or "none").strip().lower()
    if chosen not in REVIEW_KINDS:
        chosen = "none"
    provenance["review"] = {
        "kind": chosen,
        "score": float(score or 0),
        "notes": [str(item)[:200] for item in (notes or [])][:6],
    }
    provenance["needs_confirmation"] = _compute_needs_confirmation(parsed, provenance)
    return _write_provenance(parsed, provenance)


def needs_confirmation(system):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    return bool(_compute_needs_confirmation(parsed, provenance))


def identity_label(system):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    if parsed.source == "tailwind-centralcomm":
        return "confirmed"
    if parsed.status == "approved" and not _compute_needs_confirmation(parsed, provenance):
        return "confirmed"
    return "preview"


def sanitize_server_fields(payload):
    """Remove campos administrativos de um dict de entrada (cliente)."""
    data = dict(payload) if isinstance(payload, dict) else {}
    for key in SERVER_OWNED:
        data.pop(key, None)
    evidence = data.get("evidence")
    if isinstance(evidence, dict):
        cleaned = dict(evidence)
        cleaned.pop("reviewed", None)
        cleaned.pop("provenance", None)
        cleaned.pop("fidelity", None)
        cleaned.pop("validation", None)
        if cleaned:
            data["evidence"] = cleaned
        else:
            data.pop("evidence", None)
    return data


def extract_llm_compose(raw):
    """Só chaves autorizadas do compose. Descarta status/provenance/reviewed."""
    payload = raw if isinstance(raw, dict) else {}
    cleaned = {}
    for key in LLM_COMPOSE_KEYS:
        if payload.get(key) not in (None, "", []):
            cleaned[key] = payload[key]
    return cleaned


def extract_llm_refine(raw):
    """Só chaves autorizadas do refine. Descarta dna, copy, status e nested tokens."""
    payload = raw if isinstance(raw, dict) else {}
    cleaned = {}
    for key in LLM_REFINE_KEYS:
        if payload.get(key) not in (None, "", []):
            cleaned[key] = payload[key]
    return cleaned


def extract_llm_review(raw):
    """Só juízo e correções de fidelidade. Descarta tracks, status, fundo e nested tokens."""
    payload = raw if isinstance(raw, dict) else {}
    cleaned = {}
    for key in LLM_REVIEW_KEYS:
        if payload.get(key) not in (None, "", []):
            cleaned[key] = payload[key]
    return cleaned


def extract_llm_campaign(raw):
    """Só linha, copy, arquétipo, fundo e tracks kv/lifestyle. Descarta DNA e tinta."""
    payload = raw if isinstance(raw, dict) else {}
    cleaned = {}
    for key in LLM_CAMPAIGN_KEYS:
        if payload.get(key) not in (None, "", []):
            cleaned[key] = payload[key]
    return cleaned


def banner_for(system):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    identity = identity_label(parsed)
    needs = _compute_needs_confirmation(parsed, provenance)
    ink = (provenance.get("fields") or {}).get("tokens.ink") or {}
    mode = provenance.get("compose_mode") or "unknown"
    review = (provenance.get("review") or {}).get("kind") or "none"
    if identity == "confirmed" and not needs:
        return {"kind": "ok", "text": "Tinta confirmada."}
    parts = []
    state = ink.get("state") or "unknown"
    if state == "fallback":
        parts.append("Ink veio do fallback, não da marca.")
    elif state == "inferred":
        parts.append("Ink inferida da cor primária.")
    elif state == "unknown":
        parts.append("Marca antiga sem origem da tinta.")
    if mode == "local_seed":
        parts.append("Compose local, sem modelo.")
    if review == "local":
        parts.append("A revisão local não é review de modelo.")
    if not parts:
        parts.append("Preview ainda precisa de confirmação.")
    parts.append("Confirme a tinta antes de gerar.")
    return {"kind": "warn", "text": " ".join(parts)}


def summarize_for_payload(system):
    parsed = parse_system(system)
    provenance = get_provenance(parsed)
    return {
        **provenance,
        "needs_confirmation": _compute_needs_confirmation(parsed, provenance),
        "identity": identity_label(parsed),
        "banner": banner_for(parsed),
    }
