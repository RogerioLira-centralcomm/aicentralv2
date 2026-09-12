"""Loop de fidelidade: até 4 passes, patches de token, gpt-4o-mini."""

from __future__ import annotations

import json
import os

from ..creative_modeling_generation import _json_content
from ..services.openrouter_service import resolve_chat_model
from .fidelity import compile_fidelity, lock_token_patches, mark_reviewed
from .schema import (
    MAX_PASSES,
    MIN_CONTRAST,
    DesignSystemAds,
    DesignSystemPass,
    contrast_ratio,
    dump_system,
    mix_hex,
    normalize_hex,
    nudge_hex_for_contrast,
    parse_system,
)

REFINE_MODEL = os.getenv("DESIGN_SYSTEM_ADS_MODEL", "openai/gpt-4o-mini")
COMPOSE_MODEL = os.getenv("DESIGN_SYSTEM_ADS_COMPOSE_MODEL") or os.getenv(
    "DESIGN_SYSTEM_ADS_MODEL", "openai/gpt-4o"
)
IMPROVE_INTENTS = ("contrast", "type", "cta", "compact", "airy")
COPY_KEYS = ("headline", "support", "cta", "legal")


def clamp_passes(value):
    try:
        return max(1, min(MAX_PASSES, int(value)))
    except (TypeError, ValueError):
        return 1


def apply_token_patches(system, patches):
    parsed = parse_system(system)
    tokens = dict(parsed.tokens)
    applied = []
    for item in patches or []:
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("token_id") or item.get("id") or "").strip()
        css = item.get("css") if item.get("css") is not None else item.get("value")
        if not token_id or css is None or token_id not in tokens:
            continue
        if token_id in {"paper", "ink", "accent", "muted", "cta_ink", "highlight", "hairline"}:
            color = normalize_hex(css)
            if not color:
                continue
            tokens[token_id] = color
        else:
            tokens[token_id] = str(css).strip()[:120]
        applied.append(
            {
                "token_id": token_id,
                "css": tokens[token_id],
                "reason": str(item.get("reason") or "")[:240],
            }
        )
    data = dump_system(parsed)
    data["tokens"] = tokens
    data["passes"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in parsed.passes]
    return DesignSystemAds.model_validate(data), applied


def heal_contrast(system, *, force=False):
    parsed = parse_system(system)
    if parsed.status == "approved" and not force:
        return parsed, []
    tokens = dict(parsed.tokens)
    paper = normalize_hex(tokens.get("paper"), "#FFFFFF")
    ink = normalize_hex(tokens.get("ink"), "#111111")
    accent = normalize_hex(tokens.get("accent"), ink)
    cta_ink = normalize_hex(tokens.get("cta_ink"), "#FFFFFF")
    patches = []
    if contrast_ratio(ink, paper) < MIN_CONTRAST:
        tokens["ink"], _ = nudge_hex_for_contrast(ink, paper)
        patches.append({
            "token_id": "ink",
            "css": tokens["ink"],
            "reason": "Contraste ink/paper abaixo de 4.5; a tinta da marca foi escurecida, não trocada.",
        })
    if contrast_ratio(cta_ink, accent) < MIN_CONTRAST:
        light_on_accent = contrast_ratio("#FFFFFF", accent)
        dark_on_accent = contrast_ratio("#0F172A", accent)
        if light_on_accent >= MIN_CONTRAST or light_on_accent >= dark_on_accent:
            tokens["cta_ink"] = "#FFFFFF"
        else:
            tokens["cta_ink"] = "#0F172A"
        patches.append({
            "token_id": "cta_ink",
            "css": tokens["cta_ink"],
            "reason": "Texto do CTA no extremo que lê sobre o fill da marca.",
        })
        if contrast_ratio(tokens["cta_ink"], accent) < MIN_CONTRAST:
            tokens["accent"], _ = nudge_hex_for_contrast(accent, tokens["cta_ink"])
            patches.append({
                "token_id": "accent",
                "css": tokens["accent"],
                "reason": "CTA da marca empurrado só o suficiente para 4.5:1.",
            })
    data = dump_system(parsed)
    data["tokens"] = tokens
    healed = DesignSystemAds.model_validate(data)
    return healed, patches


def patch_system(system, tokens=None, ad_copy=None, dna=None, archetype=None):
    parsed = parse_system(system)
    patches = []
    if isinstance(tokens, dict):
        patches = [
            {"token_id": key, "css": value, "reason": "Ajuste na mesa."}
            for key, value in tokens.items()
        ]
    parsed, applied = apply_token_patches(parsed, patches)
    if isinstance(dna, dict) or archetype:
        from .components import ARCHETYPES, compile_rules

        data = dump_system(parsed)
        if isinstance(dna, dict):
            current = dict(data.get("dna") or {})
            if dna.get("name"):
                current["name"] = str(dna.get("name") or "")[:80]
            for key in ("personality", "must", "avoid"):
                if dna.get(key) is None:
                    continue
                raw = dna.get(key)
                if isinstance(raw, str):
                    current[key] = [part.strip() for part in raw.split(",") if part.strip()][:8]
                elif isinstance(raw, list):
                    current[key] = [str(part).strip() for part in raw if str(part).strip()][:8]
            data["dna"] = current
        chosen = str(archetype or data.get("archetype") or "brand")
        if chosen in ARCHETYPES:
            data["archetype"] = chosen
            from .catalog import _track_url
            from .components import TRACK_FOR_ARCHETYPE, apply_background

            arch = ARCHETYPES[chosen]
            track_id = TRACK_FOR_ARCHETYPE.get(chosen)
            image = _track_url(parsed, track_id) if track_id else ""
            data["tokens"] = apply_background(data.get("tokens") or {}, arch["ground"], image_url=image)
        data["rules"] = compile_rules(data.get("dna"), data.get("archetype"))
        parsed = DesignSystemAds.model_validate(data)
    kind = None
    if isinstance(tokens, dict):
        kind = tokens.get("ground-kind")
    if kind or (isinstance(tokens, dict) and tokens.get("ground") is not None):
        from .components import apply_background

        data = dump_system(parsed)
        data["tokens"] = apply_background(
            data["tokens"],
            kind or data["tokens"].get("ground-kind") or "paper",
            image_url=(tokens or {}).get("ground"),
        )
        parsed = DesignSystemAds.model_validate(data)
    if isinstance(ad_copy, dict):
        from .copy import clean_ad_copy

        merged = dict(parsed.ad_copy or {})
        for key in COPY_KEYS:
            if ad_copy.get(key) is None:
                continue
            merged[key] = str(ad_copy.get(key) or "").strip()[:180]
        data = dump_system(parsed)
        data["ad_copy"] = clean_ad_copy(merged, parsed.name)
        parsed = DesignSystemAds.model_validate(data)
    if applied:
        from .provenance import stamp_fields

        parsed = stamp_fields(
            parsed,
            {
                f"tokens.{item['token_id']}": {
                    "state": "inferred",
                    "origin": "mesa",
                }
                for item in applied
            },
        )
    return parsed, applied


def improve_system(system, intent, *, client=None, client_id=None):
    """Melhoria local e visível. Não é o refino com modelo."""
    from .prompt_context import build_ads_prompt_context, stamp_runtime_context

    kind = str(intent or "").strip().lower()
    if kind not in IMPROVE_INTENTS:
        raise ValueError("Escolha o que melhorar: contraste, tipo, CTA, compacto ou arejado.")
    parsed = parse_system(system)
    context = build_ads_prompt_context(
        "refine",
        parsed,
        intent=kind,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    improved, report = apply_refine(
        parsed,
        _local_intent_payload(parsed, kind),
        intent=kind,
        policy_context=context,
        source="local",
    )
    improved = stamp_runtime_context(improved, context, compose_mode="local")
    return _append_pass(improved, report), report


def _local_intent_payload(system, kind):
    tokens = dict(system.tokens or {})
    patches = []

    def set_token(key, value, reason):
        if str(tokens.get(key) or "") == str(value):
            return
        tokens[key] = value
        patches.append({"token_id": key, "css": value, "reason": reason})

    if kind == "contrast":
        healed, heal_patches = heal_contrast(system, force=True)
        tokens = dict(healed.tokens)
        patches = list(heal_patches)
        if not patches:
            darker = mix_hex(tokens.get("ink"), "#000000", 0.2) or "#153638"
            set_token("ink", darker, "Tinta mais escura para o título ler no IAB.")
            set_token("muted", mix_hex(darker, "#64748B", 0.35) or "#4B5563", "Apoio acompanha a tinta.")
    elif kind == "type":
        set_token("weight-display", "800", "Título mais pesado, de peça.")
        set_token("tracking", "-0.03em", "Tracking fechado de anúncio, não de site.")
        set_token("weight-cta", "700", "CTA um degrau abaixo do título.")
    elif kind == "cta":
        set_token("cta-pad", "0.85em 1.45em", "Miolo de botão de mídia.")
        set_token("cta-radius", "0.15rem", "Canto de anúncio, não pílula.")
        if str(tokens.get("cta-shadow") or "none") == "none":
            set_token("cta-shadow", "0 6px 14px rgba(15, 23, 42, 0.18)", "Elevação só no CTA.")
        else:
            set_token("cta-shadow", "none", "CTA plano, sem sombra de card.")
    elif kind == "compact":
        set_token("safe", "4%", "Margem compacta.")
        set_token("cta-pad", "0.55em 0.95em", "Botão curto.")
        set_token("tracking", "-0.03em", "Título mais fechado.")
    elif kind == "airy":
        set_token("safe", "8%", "Margem arejada.")
        set_token("cta-pad", "0.9em 1.55em", "Botão com ar.")
        set_token("tracking", "0", "Título sem tracking fechado.")
    return {"patches": patches, "notes": [_intent_note(kind)]}


def apply_refine(system, raw, *, intent=None, policy_context=None, source="llm"):
    """Aplica só o eixo pedido. Não reescreve DNA, copy nem trilhas."""
    from .runtime_policy import (
        apply_ground_payload,
        filter_identity_patches,
        keep_required_legal,
        refine_scope,
        stamp_policy_outcome,
    )
    from .provenance import extract_llm_refine

    parsed = parse_system(system)
    axis, scope = refine_scope(intent)
    payload = extract_llm_refine(raw)
    conflicts = []
    rejected = []
    corrected = []
    extra_patches = []
    for item in payload.get("patches") or []:
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("token_id") or item.get("id") or "").strip()
        css = item.get("css") if item.get("css") is not None else item.get("value")
        if not token_id:
            continue
        if css is None:
            rejected.append({"field": token_id, "reason": "null não apaga token."})
            continue
        if token_id not in scope["allowed_tokens"]:
            rejected.append({"field": token_id, "reason": "fora do eixo", "id": "ADS.REFINE.SCOPE"})
            conflicts.append(
                {
                    "id": "ADS.REFINE.SCOPE",
                    "status": "conflict",
                    "token_id": token_id,
                    "detail": f"{token_id} fora do eixo {axis or 'tokens'}.",
                }
            )
            continue
        extra_patches.append(item)
    extra_patches, dropped = filter_identity_patches(
        parsed, extra_patches, source=source
    )
    conflicts.extend(dropped)
    rejected.extend(
        {"field": item.get("token_id"), "reason": item.get("detail"), "id": item.get("id")}
        for item in dropped
    )
    extra_patches = lock_token_patches(parsed, extra_patches)
    working, applied = apply_token_patches(parsed, extra_patches)
    if payload.get("ground-kind"):
        if not scope["allows_ground"]:
            conflicts.append(
                {
                    "id": "ADS.REFINE.SCOPE",
                    "status": "conflict",
                    "token_id": "ground-kind",
                    "detail": "Fundo fora do eixo.",
                }
            )
            rejected.append({"field": "ground-kind", "reason": "fora do eixo", "id": "ADS.REFINE.SCOPE"})
        else:
            tokens, ground_conflict = apply_ground_payload(
                working.tokens,
                payload.get("ground-kind"),
                image_url=(working.tokens or {}).get("ground") or "",
            )
            data = dump_system(working)
            data["tokens"] = tokens
            working = DesignSystemAds.model_validate(data)
            if ground_conflict:
                conflicts.append(ground_conflict)
                if ground_conflict.get("status") == "needs_input":
                    rejected.append(
                        {
                            "field": "ground-kind",
                            "reason": ground_conflict.get("detail"),
                            "id": ground_conflict.get("id"),
                        }
                    )
                else:
                    corrected.append(
                        {
                            "field": "ground-kind",
                            "reason": ground_conflict.get("detail"),
                            "id": ground_conflict.get("id"),
                        }
                    )
    if isinstance(raw, dict) and isinstance(raw.get("ad_copy"), dict):
        if not scope["allows_copy"]:
            conflicts.append(
                {
                    "id": "ADS.REFINE.SCOPE",
                    "status": "conflict",
                    "detail": "Copy fora do eixo do refine.",
                }
            )
            rejected.append({"field": "ad_copy", "reason": "fora do eixo", "id": "ADS.REFINE.SCOPE"})
            _, legal_conflict = keep_required_legal(parsed, parsed.ad_copy or {}, incoming={})
            if legal_conflict:
                conflicts.append(legal_conflict)
        else:
            from .copy import clean_ad_copy

            cleaned, legal_conflict = keep_required_legal(
                parsed,
                clean_ad_copy(raw.get("ad_copy"), parsed.name),
                incoming=raw.get("ad_copy"),
            )
            data = dump_system(working)
            data["ad_copy"] = cleaned
            working = DesignSystemAds.model_validate(data)
            if legal_conflict:
                conflicts.append(legal_conflict)
                corrected.append(
                    {"field": "legal", "reason": legal_conflict.get("detail"), "id": "ADS.LEGAL.KEEP"}
                )
    before_heal = dict(working.tokens or {})
    working, heal_patches = heal_contrast(working, force=bool(scope.get("force_contrast")))
    for item in heal_patches:
        applied.append(item)
        corrected.append(
            {
                "field": item.get("token_id"),
                "reason": item.get("reason") or "Correção dependente de contraste.",
                "id": "ADS.CONTRAST.45",
            }
        )
        if item.get("token_id") and before_heal.get(item["token_id"]) != item.get("css"):
            conflicts.append(
                {
                    "id": "ADS.CONTRAST.45",
                    "status": "conflict",
                    "token_id": item.get("token_id"),
                    "detail": "Ajuste dependente de contraste, fora do pedido cru.",
                }
            )
    changed = {
        key: working.tokens.get(key)
        for key, value in (parsed.tokens or {}).items()
        if str(working.tokens.get(key) or "") != str(value or "")
    }
    statuses = {item.get("status") for item in conflicts if isinstance(item, dict)}
    if "needs_input" in statuses:
        outcome = "needs_input"
    elif "incompatible" in statuses and not changed:
        outcome = "blocked"
    elif rejected and applied:
        outcome = "partial"
    elif rejected and not changed:
        outcome = "blocked"
    elif not changed:
        outcome = "noop"
    else:
        outcome = "accepted"
    working = stamp_policy_outcome(working, conflicts)
    working = _stamp_refine_enforcement(
        working,
        {
            "outcome": outcome,
            "intent": axis or "tokens",
            "triggered_rules": list({item.get("id") for item in conflicts if item.get("id")}),
            "rejected_fields": rejected[:12],
            "corrected_fields": corrected[:12],
            "block_reason": next(
                (item.get("detail") for item in conflicts if item.get("status") in {"conflict", "incompatible", "needs_input"}),
                "",
            ),
            "source": source,
        },
    )
    report = DesignSystemPass(
        attempt=len(working.passes) + 1,
        passed=bool(working.contrast.get("passed")) and outcome not in {"blocked", "needs_input"},
        score=0.86 if applied else (0.7 if outcome == "noop" else 0.45),
        notes=[str(item)[:200] for item in (payload.get("notes") or [_intent_note(axis)])][:6],
        patches=applied,
        defects=[item.get("detail") or item.get("id") for item in conflicts][:6],
    )
    return working, report


def _stamp_refine_enforcement(system, summary):
    data = dump_system(system)
    evidence = dict(data.get("evidence") or {})
    policy = dict(evidence.get("policy") or {})
    policy["refine"] = summary
    evidence["policy"] = policy
    data["evidence"] = evidence
    return DesignSystemAds.model_validate(data)


def _stamp_review_enforcement(system, summary):
    data = dump_system(system)
    evidence = dict(data.get("evidence") or {})
    policy = dict(evidence.get("policy") or {})
    policy["review"] = summary
    evidence["policy"] = policy
    data["evidence"] = evidence
    return DesignSystemAds.model_validate(data)


def apply_review(system, raw, *, policy_context=None, source="llm"):
    """Aplica só o juízo de fidelidade. DNA/copy/patches sob escopo; sem tracks."""
    from .copy import clean_ad_copy, dna_is_generic, is_stock_copy
    from .components import compile_rules
    from .provenance import extract_llm_review
    from .runtime_policy import (
        filter_identity_patches,
        keep_required_legal,
        stamp_policy_outcome,
    )

    parsed = parse_system(system)
    payload = extract_llm_review(raw)
    conflicts = []
    rejected = []
    corrected = []
    extra_patches = []
    allows_dna = dna_is_generic(parsed.dna) and parsed.status != "approved"
    allows_copy = is_stock_copy(parsed.ad_copy)
    working = parsed
    if isinstance(raw, dict) and isinstance(raw.get("dna"), dict):
        if parsed.status == "approved":
            conflicts.append(
                {
                    "id": "ADS.IDENTITY.APPROVED_LOCK",
                    "status": "conflict",
                    "detail": "DNA aprovado não aceita o patch do modelo.",
                }
            )
            rejected.append(
                {"field": "dna", "reason": "aprovado", "id": "ADS.IDENTITY.APPROVED_LOCK"}
            )
        elif not allows_dna:
            conflicts.append(
                {
                    "id": "ADS.REVIEW.SCOPE",
                    "status": "conflict",
                    "detail": "DNA específico não aceita reescrita no review.",
                }
            )
            rejected.append({"field": "dna", "reason": "fora do escopo", "id": "ADS.REVIEW.SCOPE"})
        else:
            data = dump_system(working)
            current = dict(data.get("dna") or {})
            incoming = raw.get("dna") or {}
            for key in ("name", "personality", "must", "avoid"):
                if incoming.get(key) not in (None, "", []):
                    current[key] = incoming[key]
            data["dna"] = current
            data["rules"] = compile_rules(current, data.get("archetype"))
            working = DesignSystemAds.model_validate(data)
    if isinstance(raw, dict) and isinstance(raw.get("ad_copy"), dict):
        if not allows_copy:
            conflicts.append(
                {
                    "id": "ADS.REVIEW.SCOPE",
                    "status": "conflict",
                    "detail": "Copy específica não aceita reescrita no review.",
                }
            )
            rejected.append({"field": "ad_copy", "reason": "fora do escopo", "id": "ADS.REVIEW.SCOPE"})
            _, legal_conflict = keep_required_legal(parsed, parsed.ad_copy or {}, incoming={})
            if legal_conflict:
                conflicts.append(legal_conflict)
        else:
            cleaned, legal_conflict = keep_required_legal(
                parsed,
                clean_ad_copy(raw.get("ad_copy"), parsed.name),
                incoming=raw.get("ad_copy"),
            )
            data = dump_system(working)
            data["ad_copy"] = cleaned
            working = DesignSystemAds.model_validate(data)
            if legal_conflict:
                conflicts.append(legal_conflict)
                corrected.append(
                    {"field": "legal", "reason": legal_conflict.get("detail"), "id": "ADS.LEGAL.KEEP"}
                )
    for item in payload.get("patches") or []:
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("token_id") or item.get("id") or "").strip()
        css = item.get("css") if item.get("css") is not None else item.get("value")
        if not token_id:
            continue
        if css is None:
            rejected.append({"field": token_id, "reason": "null não apaga token."})
            continue
        extra_patches.append(item)
    extra_patches, dropped = filter_identity_patches(
        parsed, extra_patches, source=source
    )
    conflicts.extend(dropped)
    rejected.extend(
        {"field": item.get("token_id"), "reason": item.get("detail"), "id": item.get("id")}
        for item in dropped
    )
    extra_patches = lock_token_patches(parsed, extra_patches)
    working, applied = apply_token_patches(working, extra_patches)
    if isinstance(raw, dict) and raw.get("ground-kind"):
        conflicts.append(
            {
                "id": "ADS.REVIEW.SCOPE",
                "status": "conflict",
                "token_id": "ground-kind",
                "detail": "Fundo fora do escopo do review.",
            }
        )
        rejected.append({"field": "ground-kind", "reason": "fora do escopo", "id": "ADS.REVIEW.SCOPE"})
    if isinstance(raw, dict) and raw.get("tracks"):
        conflicts.append(
            {
                "id": "ADS.REVIEW.SCOPE",
                "status": "conflict",
                "detail": "Trilhas fora do escopo do review.",
            }
        )
        rejected.append({"field": "tracks", "reason": "fora do escopo", "id": "ADS.REVIEW.SCOPE"})
    before_heal = dict(working.tokens or {})
    working, heal_patches = heal_contrast(working)
    for item in heal_patches:
        applied.append(item)
        corrected.append(
            {
                "field": item.get("token_id"),
                "reason": item.get("reason") or "Correção dependente de contraste.",
                "id": "ADS.CONTRAST.45",
            }
        )
        if item.get("token_id") and before_heal.get(item["token_id"]) != item.get("css"):
            conflicts.append(
                {
                    "id": "ADS.CONTRAST.45",
                    "status": "conflict",
                    "token_id": item.get("token_id"),
                    "detail": "Ajuste dependente de contraste, fora do pedido cru.",
                }
            )
    changed = {
        key: working.tokens.get(key)
        for key, value in (parsed.tokens or {}).items()
        if str(working.tokens.get(key) or "") != str(value or "")
    }
    if working.ad_copy != parsed.ad_copy:
        changed["ad_copy"] = working.ad_copy
    if working.dna != parsed.dna:
        changed["dna"] = working.dna
    statuses = {item.get("status") for item in conflicts if isinstance(item, dict)}
    if "needs_input" in statuses:
        outcome = "needs_input"
    elif "incompatible" in statuses and not changed:
        outcome = "blocked"
    elif rejected and changed:
        outcome = "partial"
    elif rejected and not changed:
        outcome = "blocked"
    elif not changed:
        outcome = "noop"
    else:
        outcome = "accepted"
    working = stamp_policy_outcome(working, conflicts)
    working = _stamp_review_enforcement(
        working,
        {
            "outcome": outcome,
            "check_kind": "textual",
            "visual_available": False,
            "triggered_rules": list({item.get("id") for item in conflicts if item.get("id")}),
            "rejected_fields": rejected[:12],
            "corrected_fields": corrected[:12],
            "block_reason": next(
                (
                    item.get("detail")
                    for item in conflicts
                    if item.get("status") in {"conflict", "incompatible", "needs_input"}
                ),
                "",
            ),
            "source": source,
        },
    )
    try:
        score = float(payload.get("score")) if payload.get("score") is not None else 0.0
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(1.0, score))
    if "passed" in payload:
        model_passed = bool(payload.get("passed"))
    else:
        model_passed = score >= 0.7
    notes = [str(item)[:200] for item in (payload.get("notes") or ["Revisão de fidelidade."])][:6]
    defects = [str(item)[:200] for item in (payload.get("defects") or [])][:6]
    defects.extend(
        item.get("detail") or item.get("id")
        for item in conflicts
        if item.get("detail") or item.get("id")
    )
    if payload.get("score") is not None:
        report_score = score
    else:
        report_score = 0.86 if applied or changed else (0.7 if outcome == "noop" else 0.45)
    report = DesignSystemPass(
        attempt=len(working.passes) + 1,
        passed=model_passed
        and bool(working.contrast.get("passed"))
        and outcome not in {"blocked", "needs_input"},
        score=report_score,
        notes=notes,
        patches=applied,
        defects=defects[:6],
    )
    return working, report


def _intent_note(intent):
    return {
        "contrast": "Melhoria: contraste e tinta.",
        "type": "Melhoria: peso e tracking do título.",
        "cta": "Melhoria: botão da peça.",
        "compact": "Melhoria: voz compacta.",
        "airy": "Melhoria: voz arejada.",
    }.get(intent, "Melhoria na mesa.")


def _brief_policy(system):
    from .runtime_policy import POLICY_VERSION, preset_context_for, prompt_fragment
    from .skills import skill_bundle

    context = preset_context_for(system)
    bundle = skill_bundle("refine", preset_context=context)
    return {
        "version": POLICY_VERSION,
        "selected": bundle["selected"],
        "rules": bundle["rules"],
        "runtime_loads_markdown": False,
        "constraints": prompt_fragment("refine", preset_context=context),
    }


def advertising_brief(system):
    parsed = parse_system(system)
    tokens = parsed.tokens or {}
    return {
        "framework": "design-system-ads",
        "scope": parsed.scope,
        "name": parsed.name,
        "dna": parsed.dna,
        "archetype": parsed.archetype,
        "tokens": tokens,
        "effects": {
            "wash-strength": tokens.get("wash-strength") or "16%",
            "grain": tokens.get("grain") or "0",
            "overlay": tokens.get("overlay") or "transparent",
            "hairline": tokens.get("hairline") or "",
            "cta-shadow": tokens.get("cta-shadow") or "none",
        },
        "contrast": parsed.contrast,
        "copy": parsed.ad_copy,
        "creative_line": parsed.creative_line,
        "rules": parsed.rules,
        "backgrounds": parsed.backgrounds,
        "tracks": parsed.tracks,
        "evidence": parsed.evidence,
        "fidelity": compile_fidelity(parsed),
        "policy": _brief_policy(parsed),
        "agent": {
            "role": "diretor de arte desta marca, não de um kit genérico",
            "wash_is_css": True,
            "generate_tracks": ["packshot", "kv", "lifestyle"],
            "prefer_assets": True,
            "materials": [
                str(item)
                for item in (
                    (parsed.evidence or {}).get("products")
                    or (compile_fidelity(parsed).get("products") or [])
                )[:4]
            ],
            "avoid_image_defaults": [
                "cream #F4F1EA + terracotta",
                "acid green on near-black",
                "SaaS cards and soft grey shadows",
                "stock handshake or glass office",
                "website chrome, navbar, app UI",
                "reconhecível / direta / de marca",
            ],
        },
        "must": [
            "Advertising OS, not a website kit.",
            "Locked tokens in fidelity.locked_tokens stay in the same color family.",
            "Never replace brand ink with CentralComm teal unless that is already the ink.",
            "Prefer fidelity.assets on tracks before inventing a new image.",
            "Wash is CSS (wash-strength + ink), never a generated gradient photo.",
            "Short copy from this brand. Recompose IAB, never resize.",
            "Do not invent cream, terracotta, acid green or SaaS cards.",
            "DNA and copy come from this brand's evidence, never generic traits.",
        ],
    }


def apply_compose(system, raw, *, policy_context=None):
    from .components import ARCHETYPES, compile_rules
    from .provenance import extract_llm_compose
    from .runtime_policy import (
        apply_ground_payload,
        filter_identity_patches,
        keep_required_legal,
        preset_context_for,
        stamp_policy_outcome,
    )
    from .tracks import merge_tracks

    parsed = parse_system(system)
    preset_context = (policy_context or {}).get("preset_context") or preset_context_for(parsed)
    data = dump_system(parsed)
    payload = extract_llm_compose(raw)
    conflicts = []
    approved = parsed.status == "approved"
    if isinstance(payload.get("dna"), dict) and not approved:
        current = dict(data.get("dna") or {})
        for key in ("name", "personality", "must", "avoid"):
            if payload["dna"].get(key) not in (None, "", []):
                current[key] = payload["dna"][key]
        data["dna"] = current
    elif isinstance(payload.get("dna"), dict) and approved:
        conflicts.append(
            {
                "id": "ADS.IDENTITY.APPROVED_LOCK",
                "status": "conflict",
                "detail": "DNA aprovado não aceita o patch do modelo.",
            }
        )
    archetype = str(payload.get("archetype") or data.get("archetype") or "brand")
    if archetype in ARCHETYPES:
        data["archetype"] = archetype
    data["rules"] = compile_rules(data.get("dna"), data.get("archetype"))
    if isinstance(payload.get("ad_copy"), dict):
        from .copy import clean_ad_copy

        cleaned, legal_conflict = keep_required_legal(
            parsed,
            clean_ad_copy(
                payload["ad_copy"],
                (data.get("dna") or {}).get("name") or data.get("name"),
            ),
            incoming=payload["ad_copy"],
        )
        data["ad_copy"] = cleaned
        if legal_conflict:
            conflicts.append(legal_conflict)
    if isinstance(payload.get("ad_copy_by_format"), dict):
        from .copy import merge_format_copy

        data["ad_copy_by_format"] = merge_format_copy(
            data.get("ad_copy_by_format"),
            payload.get("ad_copy_by_format"),
            data.get("ad_copy"),
        )
    effects = payload.get("effects") if isinstance(payload.get("effects"), dict) else {}
    extra_patches = list(payload.get("patches") or [])
    for key in ("wash-strength", "grain", "overlay", "cta-shadow", "hairline"):
        if effects.get(key) not in (None, ""):
            extra_patches.append({"token_id": key, "css": effects[key], "reason": "Efeito de mídia."})
    extra_patches, dropped = filter_identity_patches(
        parsed, extra_patches, preset_context=preset_context
    )
    conflicts.extend(dropped)
    working = DesignSystemAds.model_validate(data)
    working, applied = apply_token_patches(working, extra_patches)
    if payload.get("ground-kind"):
        tokens, ground_conflict = apply_ground_payload(
            working.tokens,
            payload.get("ground-kind"),
            image_url=(working.tokens or {}).get("ground") or "",
        )
        data = dump_system(working)
        data["tokens"] = tokens
        working = DesignSystemAds.model_validate(data)
        if ground_conflict:
            conflicts.append(ground_conflict)
    working, _ = heal_contrast(working)
    data = dump_system(working)
    data["tracks"] = merge_tracks(data.get("tracks"), payload.get("tracks"))
    composed = stamp_policy_outcome(DesignSystemAds.model_validate(data), conflicts)
    report = DesignSystemPass(
        attempt=len(composed.passes) + 1,
        passed=bool(composed.contrast.get("passed")) and not any(
            item.get("status") == "incompatible" for item in conflicts
        ),
        score=0.88 if applied or payload.get("tracks") or payload.get("dna") else 0.6,
        notes=[str(item)[:200] for item in (payload.get("notes") or ["Sistema montado no OpenRouter."])][:6],
        patches=applied,
        defects=[item.get("detail") or item.get("id") for item in conflicts][:6],
    )
    return _append_pass(composed, report), report


def compose_design_system(
    system,
    *,
    text_callable=None,
    reference_urls=None,
    client=None,
    client_id=None,
    prompt_context=None,
):
    from .prompt_context import build_ads_prompt_context, context_messages, stamp_runtime_context

    parsed = parse_system(system)
    if text_callable is None:
        raise ValueError("OpenRouter não está configurado para montar o sistema.")
    context = prompt_context or build_ads_prompt_context(
        "compose",
        parsed,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    response = text_callable(
        context_messages(context, reference_urls=reference_urls),
        model=resolve_chat_model(COMPOSE_MODEL),
        max_tokens=1200,
        temperature=0.25,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception as exc:
                raise ValueError("O OpenRouter não devolveu o sistema da marca.") from exc
    from .provenance import set_compose_mode

    composed, report = apply_compose(parsed, raw, policy_context=context)
    composed = stamp_runtime_context(
        set_compose_mode(composed, "model"), context, compose_mode="model"
    )
    return composed, report


def seed_local_compose(system, *, client=None, client_id=None):
    from .copy import brand_ad_copy
    from .materialize import GENERIC_TRAITS, _dna_from_evidence
    from .prompt_context import build_ads_prompt_context, stamp_runtime_context

    parsed = parse_system(system)
    context = build_ads_prompt_context(
        "compose",
        parsed,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    name = (parsed.dna or {}).get("name") or parsed.name or "A marca"
    dna = _dna_from_evidence(name, {}, {}, parsed.dna or {}, parsed.evidence or {})
    personality = [
        item for item in (dna.get("personality") or [])
        if str(item).strip().lower() not in GENERIC_TRAITS
    ]
    if not personality:
        short = name.replace(" Ads", "").strip() or "A marca"
        product = next(
            (str(item).strip() for item in (parsed.evidence or {}).get("products") or [] if str(item).strip()),
            short,
        )
        personality = [f"{short} em close", f"{product} no primeiro plano"]
    dna["personality"] = personality[:5]
    dna["name"] = name
    copy = brand_ad_copy(name)
    from .provenance import set_compose_mode

    composed, report = apply_compose(
        parsed,
        {
            "dna": dna,
            "archetype": parsed.archetype or "brand",
            "ad_copy": copy,
            "notes": ["Linha da marca assentada no loop, sem traço genérico."],
        },
        policy_context=context,
    )
    return stamp_runtime_context(
        set_compose_mode(composed, "local_seed"), context, compose_mode="local_seed"
    ), report


def compose_campaign_design_system(
    system,
    campaign=None,
    *,
    text_callable=None,
    client=None,
    client_id=None,
    prompt_context=None,
):
    from .prompt_context import build_ads_prompt_context, context_messages, stamp_runtime_context
    from .provenance import set_compose_mode

    parsed = parse_system(system)
    campaign = campaign if isinstance(campaign, dict) else {}
    context = prompt_context or build_ads_prompt_context(
        "campaign",
        parsed,
        campaign_context=campaign,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    if text_callable is None:
        return seed_campaign_compose(
            parsed,
            campaign,
            client=client,
            client_id=client_id,
            prompt_context=context,
        )
    try:
        response = text_callable(
            context_messages(context),
            model=resolve_chat_model(COMPOSE_MODEL),
            max_tokens=900,
            temperature=0.35,
        )
    except Exception as exc:
        raise ValueError("O compose da campanha não concluiu.") from exc
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception as exc:
                raise ValueError("O OpenRouter não devolveu a campanha.") from exc
    composed, report = apply_campaign_compose(
        parsed, raw, policy_context=context, source="llm"
    )
    return stamp_runtime_context(
        set_compose_mode(composed, "model"), context, compose_mode="model"
    ), report


def seed_campaign_compose(
    system,
    campaign=None,
    *,
    client=None,
    client_id=None,
    prompt_context=None,
):
    from .prompt_context import build_ads_prompt_context, stamp_runtime_context
    from .provenance import set_compose_mode

    campaign = campaign if isinstance(campaign, dict) else {}
    parsed = parse_system(system)
    context = prompt_context or build_ads_prompt_context(
        "campaign",
        parsed,
        campaign_context=campaign,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    name = str(campaign.get("name") or parsed.name or "Campanha").replace(" Ads", "").strip()
    line = str(
        campaign.get("creative_line")
        or campaign.get("objective")
        or parsed.creative_line
        or f"{name} nesta temporada"
    ).strip()[:240]
    headline = str(
        campaign.get("headline")
        or campaign.get("campaign_text")
        or name
    ).strip().splitlines()[0][:80]
    composed, report = apply_campaign_compose(
        parsed,
        {
            "creative_line": line,
            "ad_copy": {
                "headline": headline or name,
                "support": line,
                "cta": campaign.get("cta_text") or "Reservar",
                "legal": parsed.ad_copy.get("legal") if parsed.ad_copy else name,
            },
            "archetype": "promotion" if campaign.get("cta_text") else parsed.archetype or "lifestyle",
            "ground-kind": "image" if campaign.get("assets") else "wash",
            "notes": ["Campanha herda a tinta. Copy e linha mudam."],
        },
        policy_context=context,
        source="local",
    )
    return stamp_runtime_context(
        set_compose_mode(composed, "local_seed"), context, compose_mode="local_seed"
    ), report


def _stamp_campaign_enforcement(system, summary):
    data = dump_system(system)
    evidence = dict(data.get("evidence") or {})
    policy = dict(evidence.get("policy") or {})
    policy["campaign"] = summary
    evidence["policy"] = policy
    data["evidence"] = evidence
    return DesignSystemAds.model_validate(data)


def apply_campaign_compose(system, raw, *, policy_context=None, source="llm"):
    from .components import ARCHETYPES
    from .copy import COPY_KEYS, clean_ad_copy
    from .policy import MUTABLE_TRACKS, PROTECTED_TOKEN_IDS, lock_campaign_tokens
    from .provenance import extract_llm_campaign
    from .runtime_policy import apply_ground_payload, keep_required_legal, stamp_policy_outcome
    from .tracks import merge_tracks

    del policy_context
    parsed = parse_system(system)
    data = dump_system(parsed)
    data["scope"] = "campaign"
    payload = extract_llm_campaign(raw)
    conflicts = []
    rejected = []
    corrected = []
    if isinstance(raw, dict) and isinstance(raw.get("dna"), dict):
        conflicts.append(
            {
                "id": "ADS.CAMPAIGN.SCOPE",
                "status": "conflict",
                "detail": "DNA da marca não se reescreve na campanha.",
            }
        )
        rejected.append({"field": "dna", "reason": "fora do escopo", "id": "ADS.CAMPAIGN.SCOPE"})
    if isinstance(raw, dict) and raw.get("status"):
        conflicts.append(
            {
                "id": "ADS.CAMPAIGN.SCOPE",
                "status": "conflict",
                "detail": "Status não vem do modelo.",
            }
        )
        rejected.append({"field": "status", "reason": "fora do escopo", "id": "ADS.CAMPAIGN.SCOPE"})
    if isinstance(raw, dict) and isinstance(raw.get("tokens"), dict):
        for key in raw.get("tokens") or {}:
            if key in PROTECTED_TOKEN_IDS:
                conflicts.append(
                    {
                        "id": "ADS.CAMPAIGN.SCOPE",
                        "status": "conflict",
                        "token_id": key,
                        "detail": f"{key} da marca está travado na campanha.",
                    }
                )
                rejected.append({"field": key, "reason": "tinta travada", "id": "ADS.CAMPAIGN.SCOPE"})
    if isinstance(raw, dict) and raw.get("patches"):
        conflicts.append(
            {
                "id": "ADS.CAMPAIGN.SCOPE",
                "status": "conflict",
                "detail": "Patches de token não entram no compose da campanha.",
            }
        )
        rejected.append({"field": "patches", "reason": "fora do escopo", "id": "ADS.CAMPAIGN.SCOPE"})
    if payload.get("creative_line"):
        data["creative_line"] = str(payload["creative_line"]).strip()[:240]
    if isinstance(raw, dict) and isinstance(raw.get("ad_copy"), dict):
        merged = dict(parsed.ad_copy or {})
        for key in COPY_KEYS:
            if raw["ad_copy"].get(key) is None:
                continue
            merged[key] = raw["ad_copy"].get(key)
        cleaned, legal_conflict = keep_required_legal(
            parsed,
            clean_ad_copy(merged, data.get("name")),
            incoming=raw.get("ad_copy"),
        )
        data["ad_copy"] = cleaned
        if legal_conflict:
            conflicts.append(legal_conflict)
            corrected.append(
                {"field": "legal", "reason": legal_conflict.get("detail"), "id": "ADS.LEGAL.KEEP"}
            )
    format_copy = payload.get("ad_copy_by_format") if isinstance(payload, dict) else None
    if format_copy is None and isinstance(raw, dict):
        format_copy = raw.get("ad_copy_by_format")
    if isinstance(format_copy, dict):
        from .copy import merge_format_copy

        data["ad_copy_by_format"] = merge_format_copy(
            data.get("ad_copy_by_format"),
            format_copy,
            data.get("ad_copy"),
        )
    archetype = str(payload.get("archetype") or data.get("archetype") or "brand")
    if payload.get("archetype") and archetype not in ARCHETYPES:
        conflicts.append(
            {
                "id": "ADS.CAMPAIGN.SCOPE",
                "status": "conflict",
                "detail": f"Arquétipo {archetype} inválido.",
            }
        )
        rejected.append({"field": "archetype", "reason": "inválido", "id": "ADS.CAMPAIGN.SCOPE"})
    elif archetype in ARCHETYPES:
        data["archetype"] = archetype
    incoming_ground = {
        key: payload.get(key)
        for key in ("ground-kind", "overlay", "wash-strength", "grain")
        if payload.get(key) not in (None, "")
    }
    if incoming_ground.get("ground-kind"):
        tokens, ground_conflict = apply_ground_payload(
            data.get("tokens") or {},
            incoming_ground.get("ground-kind"),
            image_url=(data.get("tokens") or {}).get("ground") or "",
        )
        data["tokens"] = lock_campaign_tokens(tokens, incoming_ground)
        if ground_conflict:
            conflicts.append(ground_conflict)
            if ground_conflict.get("status") == "needs_input":
                rejected.append(
                    {
                        "field": "ground-kind",
                        "reason": ground_conflict.get("detail"),
                        "id": ground_conflict.get("id"),
                    }
                )
            else:
                corrected.append(
                    {
                        "field": "ground-kind",
                        "reason": ground_conflict.get("detail"),
                        "id": ground_conflict.get("id"),
                    }
                )
    elif incoming_ground:
        data["tokens"] = lock_campaign_tokens(data.get("tokens") or {}, incoming_ground)
    if isinstance(payload.get("tracks"), list):
        allowed = []
        for item in payload["tracks"]:
            if not isinstance(item, dict):
                continue
            track_id = str(item.get("id") or "").strip()
            if track_id not in MUTABLE_TRACKS:
                conflicts.append(
                    {
                        "id": "ADS.CAMPAIGN.SCOPE",
                        "status": "conflict",
                        "detail": f"Trilha {track_id or 'vazia'} fora do escopo da campanha.",
                    }
                )
                rejected.append(
                    {"field": track_id or "tracks", "reason": "fora do escopo", "id": "ADS.CAMPAIGN.SCOPE"}
                )
                continue
            allowed.append(item)
        data["tracks"] = merge_tracks(data.get("tracks"), allowed)
    composed = stamp_policy_outcome(DesignSystemAds.model_validate(data), conflicts)
    changed = (
        str(composed.creative_line or "") != str(parsed.creative_line or "")
        or composed.ad_copy != parsed.ad_copy
        or composed.archetype != parsed.archetype
        or str((composed.tokens or {}).get("ground-kind") or "")
        != str((parsed.tokens or {}).get("ground-kind") or "")
    )
    statuses = {item.get("status") for item in conflicts if isinstance(item, dict)}
    if "needs_input" in statuses:
        outcome = "needs_input"
    elif "incompatible" in statuses and not changed:
        outcome = "blocked"
    elif rejected and changed:
        outcome = "partial"
    elif rejected and not changed:
        outcome = "blocked"
    elif not changed:
        outcome = "noop"
    else:
        outcome = "accepted"
    composed = _stamp_campaign_enforcement(
        composed,
        {
            "outcome": outcome,
            "triggered_rules": list({item.get("id") for item in conflicts if item.get("id")}),
            "rejected_fields": rejected[:12],
            "corrected_fields": corrected[:12],
            "block_reason": next(
                (
                    item.get("detail")
                    for item in conflicts
                    if item.get("status") in {"conflict", "incompatible", "needs_input"}
                ),
                "",
            ),
            "source": source,
        },
    )
    report = DesignSystemPass(
        attempt=len(composed.passes) + 1,
        passed=outcome not in {"blocked", "needs_input"},
        score=0.86 if changed else (0.7 if outcome == "noop" else 0.45),
        notes=[str(item)[:200] for item in (payload.get("notes") or ["Campanha montada."])][:6],
        patches=[],
        defects=[item.get("detail") or item.get("id") for item in conflicts if item.get("detail") or item.get("id")][:6],
    )
    return _append_pass(composed, report), report


def review_fidelity(
    system,
    *,
    text_callable=None,
    reference_urls=None,
    client=None,
    client_id=None,
    prompt_context=None,
):
    from .copy import is_stock_copy
    from .prompt_context import build_ads_prompt_context, context_messages, stamp_runtime_context

    parsed = parse_system(system)
    context = prompt_context or build_ads_prompt_context(
        "review",
        parsed,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    if text_callable is None:
        score = 0.74 if parsed.contrast.get("passed") and not is_stock_copy(parsed.ad_copy) else 0.48
        notes = ["Revisão local: tinta da marca travada e copy sem estoque."]
        reviewed = mark_reviewed(parsed, score=score, notes=notes, kind="local")
        reviewed = stamp_runtime_context(reviewed, context, compose_mode="local")
        report = DesignSystemPass(
            attempt=len(reviewed.passes) + 1,
            passed=score >= 0.7,
            score=score,
            notes=notes,
            patches=[],
        )
        return _append_pass(reviewed, report), report

    try:
        response = text_callable(
            context_messages(context, reference_urls=reference_urls),
            model=resolve_chat_model(COMPOSE_MODEL),
            max_tokens=900,
            temperature=0.15,
        )
    except Exception as exc:
        raise ValueError("A revisão não concluiu.") from exc
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception as exc:
                raise ValueError("O OpenRouter não devolveu a revisão.") from exc
    reviewed, report = apply_review(parsed, raw, policy_context=context, source="llm")
    reviewed = mark_reviewed(reviewed, score=report.score, notes=report.notes, kind="model")
    reviewed = stamp_runtime_context(reviewed, context, compose_mode="model")
    return _append_pass(reviewed, report), report


def advance_loop(
    system,
    *,
    text_callable=None,
    reference_urls=None,
    client=None,
    client_id=None,
):
    """Um passo do loop contínuo. Não gera imagem — a mesa pede a trilha."""
    from .catalog import inspect_loop
    from .components import compile_rules

    parsed = parse_system(system)
    info = inspect_loop(parsed)
    report = None
    if info["action"] == "compose":
        if text_callable is not None:
            parsed, report = compose_design_system(
                parsed,
                text_callable=text_callable,
                reference_urls=reference_urls,
                client=client,
                client_id=client_id,
            )
        else:
            parsed, report = seed_local_compose(
                parsed, client=client, client_id=client_id
            )
    elif info["action"] == "contrast":
        parsed, report = improve_system(parsed, "contrast", client=client, client_id=client_id)
    elif info["action"] == "review":
        parsed, report = review_fidelity(
            parsed,
            text_callable=text_callable,
            reference_urls=reference_urls,
            client=client,
            client_id=client_id,
        )
    elif info["action"] == "rules":
        data = dump_system(parsed)
        data["rules"] = compile_rules(data.get("dna"), data.get("archetype"))
        parsed = DesignSystemAds.model_validate(data)
    info = inspect_loop(parsed)
    return parsed, info, report


def refine_design_system(
    system,
    *,
    attempts=4,
    text_callable=None,
    reference_urls=None,
    client=None,
    client_id=None,
    prompt_context=None,
    intent=None,
):
    from .prompt_context import build_ads_prompt_context, stamp_runtime_context

    current = parse_system(system)
    context = prompt_context or build_ads_prompt_context(
        "refine",
        current,
        intent=intent,
        client=client,
        client_id=client_id or current.client_id,
    )
    current, heal_patches = heal_contrast(current)
    limit = clamp_passes(attempts)
    already = len(current.passes)
    remaining = max(0, MAX_PASSES - already)
    budget = min(limit, remaining) if remaining else 0
    reports = []

    if already == 0:
        first = DesignSystemPass(
            attempt=1,
            passed=bool(current.contrast.get("passed")),
            score=1.0 if current.contrast.get("passed") else 0.6,
            defects=[] if current.contrast.get("passed") else ["Contraste ajustado na materialização."],
            notes=["Passo local: tokens da marca e tema Tailwind."],
            patches=heal_patches,
        )
        current = _append_pass(current, first)
        reports.append(first)
        if first.passed and not text_callable:
            return stamp_runtime_context(current, context, compose_mode="local"), reports
        budget = max(0, budget - 1)

    if text_callable is None or budget <= 0:
        return stamp_runtime_context(current, context, compose_mode="local"), reports

    last_score = reports[-1].score if reports else 0.0
    for step in range(budget):
        attempt = len(current.passes) + 1
        raw = _review_tokens(
            current,
            attempt=attempt,
            text_callable=text_callable,
            reference_urls=reference_urls,
            intent=intent,
            client=client,
            client_id=client_id,
            prompt_context=context,
        )
        current, review = apply_refine(
            current,
            raw,
            intent=intent,
            policy_context=context,
            source="llm",
        )
        current = _append_pass(current, review)
        reports.append(review)
        if review.passed:
            break
        if review.score and last_score and review.score < last_score:
            break
        last_score = review.score
    return stamp_runtime_context(current, context, compose_mode="model"), reports


def _append_pass(system, report):
    data = dump_system(system)
    passes = list(data.get("passes") or [])
    passes.append(report.model_dump() if isinstance(report, DesignSystemPass) else report)
    data["passes"] = passes[-MAX_PASSES:]
    data["version"] = max(1, int(data.get("version") or 1))
    return DesignSystemAds.model_validate(data)


def _review_tokens(
    system,
    *,
    attempt,
    text_callable,
    reference_urls=None,
    intent=None,
    client=None,
    client_id=None,
    prompt_context=None,
):
    from .prompt_context import build_ads_prompt_context, context_messages

    parsed = parse_system(system)
    context = prompt_context or build_ads_prompt_context(
        "refine",
        parsed,
        intent=intent,
        client=client,
        client_id=client_id or parsed.client_id,
    )
    user_payload = dict(context["user_payload"])
    user_payload["attempt"] = attempt
    try:
        response = text_callable(
            context_messages({**context, "user_payload": user_payload}, reference_urls=reference_urls),
            model=resolve_chat_model(REFINE_MODEL),
            max_tokens=700,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise ValueError("O refino não concluiu.") from exc
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception as exc:
                raise ValueError("O OpenRouter não devolveu o refino.") from exc
    return raw
