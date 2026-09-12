"""Plano único do Trocr: hash, conflitos e no-op. Sem LLM no debounce."""

from __future__ import annotations

import hashlib
import json
import os
import re

from .swap import (
    needs_recrop,
    prepare_swap,
    quote_swap,
    resolve_aspect_ratio,
    swap_logo_url,
    swap_mode,
    swap_risk,
    _quality,
    _reference,
)


PLANNER_VERSION = "trocr-plan-4"
TYPE_FIELDS = {
    "headline": "headline",
    "support": "secondary",
    "price": "price",
    "cta": "cta",
}
NOTE_HINTS = (
    (re.compile(r"\b(pre[cç]o|r\$|\/m[eê]s|reais)\b", re.I), "price"),
    (re.compile(r"\b(headline|t[ií]tulo|t[ií]tular)\b", re.I), "headline"),
    (re.compile(r"\b(apoio|quota|gb|mega)\b", re.I), "secondary"),
    (re.compile(r"\b(cta|bot[aã]o|contratar|assine)\b", re.I), "cta"),
    (re.compile(r"\b(logo|marca|logotipo)\b", re.I), "logo"),
    (re.compile(r"\b(pessoa|elenco|modelo|rosto)\b", re.I), "people"),
    (re.compile(r"\b(fundo|background)\b", re.I), "background"),
)


def flag_on(name, default=True):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "off", "no"}


def build_swap_plan(payload=None, brand=None):
    data = prepare_swap(payload)
    brand = brand if isinstance(brand, dict) else {}
    operations = _operations(data)
    conflicts = _conflicts(data, operations, brand)
    blocking = [item for item in conflicts if item.get("blocking")]
    noop = _is_noop(data, operations)
    mode = "noop" if noop else swap_mode(data)
    require_region = flag_on("CREATIVE_FORMAT_SWAP_REQUIRE_REGION", True)
    if require_region and mode == "typeset" and _type_only(data) and not _has_region(data):
        conflicts.append(_conflict(
            "needs_region",
            "Selecione a região do item. Sem caixa o Trocr não pinta no escuro.",
            True,
        ))
        blocking = [item for item in conflicts if item.get("blocking")]
        mode = "blocked"
    blocked = _is_blocked(conflicts, data)
    quote = _quote(data, noop=noop, blocked=blocked)
    plan_hash = _hash_plan(data, operations, brand)
    return {
        "plan_id": f"pln_{plan_hash[:12]}",
        "plan_hash": plan_hash,
        "planner_version": PLANNER_VERSION,
        "mode": mode,
        "noop": noop,
        "blocked": blocked,
        "operations": operations,
        "conflicts": conflicts,
        "qa_criteria": _qa_criteria(data, mode),
        "protected": list(data.get("preserve") or []),
        "locks": list(data.get("locks") or []),
        "quote": quote,
        "risk": swap_risk(data),
        "aspect_ratio": resolve_aspect_ratio(data),
        "quality": _quality(data),
        "payload": data,
    }


def assert_swap_plan(payload=None, brand=None):
    """Recalcula o plano. Hash divergente ou conflito sem confirmação bloqueia."""
    incoming = payload if isinstance(payload, dict) else {}
    plan = build_swap_plan(incoming, brand)
    sent = str(incoming.get("plan_hash") or "").strip()
    if sent and flag_on("CREATIVE_FORMAT_SWAP_STRICT_PLAN", True) and sent != plan["plan_hash"]:
        raise ValueError("O plano mudou. Atualize o preview e gere de novo.")
    if plan["blocked"]:
        first = next((item for item in plan["conflicts"] if item.get("blocking")), {})
        raise ValueError(first.get("message") or "Confirme o conflito antes de gerar.")
    if plan["noop"]:
        return plan
    return plan


def _operations(data):
    alter = set(data.get("alter") or [])
    rows = []
    for field, token in TYPE_FIELDS.items():
        if token not in alter:
            continue
        original = _original(data, field)
        current = str(data.get(field) or "").strip()
        rows.append({
            "element_id": _element_id(data, field),
            "field": field,
            "from": original,
            "to": current,
        })
    return rows


def _conflicts(data, operations, brand):
    items = []
    preserve = set(data.get("preserve") or [])
    alter = set(data.get("alter") or [])
    overlap = sorted(preserve & alter)
    if overlap:
        labels = {
            "people": "pessoas",
            "logo": "logo",
            "background": "fundo",
            "colors": "cores",
            "graphic": "grafismo",
            "product": "produto",
        }
        named = ", ".join(labels.get(key, key) for key in overlap)
        items.append(_conflict(
            "preserve_and_alter",
            f"O mesmo item não pode ser preservado e alterado: {named}.",
            True,
        ))
    for field, token in TYPE_FIELDS.items():
        original = _original(data, field)
        current = str(data.get(field) or "").strip()
        if original and current != original and token not in alter:
            items.append(_conflict(
                "field_without_operation",
                f"{_label(field)} mudou sem estar em Alterar.",
                True,
            ))
    if needs_recrop(data) and "layout" in preserve:
        items.append(_conflict(
            "layout_vs_format",
            "O formato muda e o layout está marcado para preservar. Confirme a recomposição.",
            True,
        ))
    if "logo" in preserve and swap_logo_url(data, brand):
        items.append(_conflict(
            "logo_locked",
            "A logo está protegida. O Trocr não troca o mark só porque a marca está ligada.",
            False,
        ))
    note = str(data.get("note") or "").strip()
    if note:
        hinted = {token for pattern, token in NOTE_HINTS if pattern.search(note)}
        missing = sorted(token for token in hinted if token not in alter and token not in {"logo"})
        if "logo" in hinted and "logo" in preserve:
            missing.append("logo")
        if missing:
            items.append(_conflict(
                "note_mismatch",
                "A instrução pede algo que não está em Alterar. Confirme ou marque o item.",
                True,
            ))
    return items


def _is_noop(data, operations):
    if data.get("force_image") or data.get("prompt_override"):
        return False
    if needs_recrop(data):
        return False
    if str(data.get("note") or "").strip():
        return False
    alter = set(data.get("alter") or [])
    if not alter:
        return True
    if alter - set(TYPE_FIELDS.values()):
        return False
    return not any(item["from"] != item["to"] for item in operations)


def _type_only(data):
    alter = set(data.get("alter") or [])
    return bool(alter) and alter <= {"headline", "secondary", "cta", "price"}


def _is_blocked(conflicts, data):
    hard = any(item.get("code") == "needs_region" and item.get("blocking") for item in conflicts)
    soft = any(
        item.get("blocking") and item.get("code") != "needs_region"
        for item in conflicts
    )
    return hard or (soft and not data.get("confirm_conflicts"))


def _has_region(data):
    regions = data.get("regions") if isinstance(data.get("regions"), dict) else {}
    for value in regions.values():
        if isinstance(value, dict) and value.get("x0") is not None:
            return True
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return True
    for item in data.get("elements") or []:
        if isinstance(item, dict) and item.get("bbox_px"):
            return True
    return False


def _original(data, field):
    role = "logo" if field == "logo_text" else field
    current = str(data.get(field) or "").strip()
    for item in data.get("elements") or []:
        if not isinstance(item, dict) or item.get("role") != role:
            continue
        original = str(item.get("text_original") or "").strip()
        if not original:
            continue
        if item.get("source") == "ocr":
            return original
        if original != current:
            return original
    return ""


def _element_id(data, field):
    role = "logo" if field == "logo_text" else field
    for item in data.get("elements") or []:
        if isinstance(item, dict) and item.get("role") == role and item.get("id"):
            return item["id"]
    return ""


def _hash_plan(data, operations, brand):
    seed = {
        "planner_version": PLANNER_VERSION,
        "reference": _reference_key(data),
        "operations": operations,
        "preserve": list(data.get("preserve") or []),
        "alter": list(data.get("alter") or []),
        "note": str(data.get("note") or ""),
        "client_id": str(data.get("client_id") or brand.get("client_id") or ""),
        "brand_name": str(data.get("brand_name") or brand.get("name") or ""),
        "aspect_ratio": resolve_aspect_ratio(data),
        "aspect_hint": str(data.get("aspect_hint") or ""),
        "force_image": bool(data.get("force_image")),
        "prompt_override": str(data.get("prompt_override") or ""),
        "regions": _region_seed(data, operations),
    }
    raw = json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _region_seed(data, operations):
    from .swap import _region_for_slot

    rows = []
    for item in operations:
        slot = "secondary" if item["field"] == "support" else item["field"]
        box = _region_for_slot(data, slot)
        if box:
            rows.append({"field": item["field"], "bbox": box})
    return rows


def _reference_key(data):
    explicit = str(data.get("reference_id") or data.get("base_id") or "").strip()
    if explicit:
        return explicit
    return _fingerprint(_reference(data))


def _fingerprint(reference):
    text = str(reference or "")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _quote(data, *, noop=False, blocked=False):
    if noop or blocked:
        from ..creative_modeling_fx import annotate_cost

        return annotate_cost({
            "estimated_cost_usd": None,
            "image_api_cost_usd": 0,
            "model": "noop" if noop else "blocked",
            "passes": 0,
            "quality": "noop" if noop else _quality(data),
            "later": {"image": False, "video": False},
            "label": "Sem geração",
        })
    quote = dict(quote_swap(data))
    if swap_mode(data) == "typeset":
        quote["image_api_cost_usd"] = 0
        quote["label"] = "Sem custo de geração de imagem por API"
        quote.pop("estimated_cost_usd", None)
        quote["cost_usd"] = 0
    return quote


def _qa_criteria(data, mode):
    return {
        "decode": True,
        "same_size": mode in {"typeset", "noop"},
        "pixels_outside_mask": False,
        "requested_copy": [item["to"] for item in _operations(data) if item["to"]],
        "locks": list(data.get("locks") or []),
    }


def _conflict(code, message, blocking):
    return {"code": code, "message": message, "blocking": blocking}


def _label(field):
    return {
        "headline": "A headline",
        "support": "O apoio",
        "price": "O preço",
        "cta": "O CTA",
    }.get(field, field)
