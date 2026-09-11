"""Loop de fidelidade: até 4 passes, patches de token, gpt-4o-mini."""

from __future__ import annotations

import json
import os

from ..creative_modeling_generation import _json_content
from ..services.openrouter_service import resolve_chat_model
from .schema import (
    MAX_PASSES,
    MIN_CONTRAST,
    DesignSystemAds,
    DesignSystemPass,
    contrast_ratio,
    dump_system,
    normalize_hex,
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


def heal_contrast(system):
    parsed = parse_system(system)
    tokens = dict(parsed.tokens)
    paper = normalize_hex(tokens.get("paper"), "#FFFFFF")
    ink = normalize_hex(tokens.get("ink"), "#1E4D4F")
    accent = normalize_hex(tokens.get("accent"), ink)
    cta_ink = normalize_hex(tokens.get("cta_ink"), "#FFFFFF")
    patches = []
    if contrast_ratio(ink, paper) < MIN_CONTRAST:
        tokens["ink"] = "#1E4D4F" if paper.upper() in {"#FFFFFF", "#F8F9FA", "#FFF"} else "#FFFFFF"
        patches.append({"token_id": "ink", "css": tokens["ink"], "reason": "Contraste ink/paper abaixo de 4.5."})
    if contrast_ratio(cta_ink, accent) < MIN_CONTRAST:
        tokens["accent"] = tokens.get("ink") or "#1E4D4F"
        tokens["cta_ink"] = "#FFFFFF"
        patches.append({"token_id": "accent", "css": tokens["accent"], "reason": "CTA sem contraste. Fill da tinta da marca."})
        patches.append({"token_id": "cta_ink", "css": "#FFFFFF", "reason": "Texto do CTA em branco."})
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
        copy = dict(parsed.ad_copy or {})
        for key in COPY_KEYS:
            if ad_copy.get(key) is None:
                continue
            copy[key] = str(ad_copy.get(key) or "").strip()[:180]
        data = dump_system(parsed)
        data["ad_copy"] = copy
        parsed = DesignSystemAds.model_validate(data)
    return parsed, applied


def improve_system(system, intent):
    """Melhoria local e visível. Não é o refino com modelo."""
    kind = str(intent or "").strip().lower()
    if kind not in IMPROVE_INTENTS:
        raise ValueError("Escolha o que melhorar: contraste, tipo, CTA, compacto ou arejado.")
    parsed = parse_system(system)
    tokens = dict(parsed.tokens)
    patches = []

    def set_token(key, value, reason):
        if str(tokens.get(key) or "") == str(value):
            return
        tokens[key] = value
        patches.append({"token_id": key, "css": value, "reason": reason})

    if kind == "contrast":
        healed, heal_patches = heal_contrast(parsed)
        tokens = dict(healed.tokens)
        patches = list(heal_patches)
        if not patches:
            darker = _mix_hex(tokens.get("ink"), "#000000", 0.2) or "#153638"
            set_token("ink", darker, "Tinta mais escura para o título ler no IAB.")
            set_token("muted", _mix_hex(darker, "#64748B", 0.35) or "#3D4451", "Apoio acompanha a tinta.")
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

    data = dump_system(parsed)
    data["tokens"] = tokens
    improved = DesignSystemAds.model_validate(data)
    improved, extra = heal_contrast(improved)
    if extra:
        patches.extend(extra)
    report = DesignSystemPass(
        attempt=len(improved.passes) + 1,
        passed=bool(improved.contrast.get("passed")),
        score=0.86 if patches else 0.7,
        notes=[_intent_note(kind)],
        patches=patches,
    )
    return _append_pass(improved, report), report


def _intent_note(intent):
    return {
        "contrast": "Melhoria: contraste e tinta.",
        "type": "Melhoria: peso e tracking do título.",
        "cta": "Melhoria: botão da peça.",
        "compact": "Melhoria: voz compacta.",
        "airy": "Melhoria: voz arejada.",
    }.get(intent, "Melhoria na mesa.")


def _mix_hex(color, other, amount):
    left = normalize_hex(color)
    right = normalize_hex(other)
    if not left or not right:
        return ""
    mix = max(0.0, min(1.0, float(amount)))

    def channel(hex_color, index):
        return int(hex_color.lstrip("#")[index : index + 2], 16)

    parts = []
    for index in (0, 2, 4):
        value = int(channel(left, index) * (1 - mix) + channel(right, index) * mix)
        parts.append(f"{max(0, min(255, value)):02X}")
    return f"#{''.join(parts)}"


def advertising_brief(system):
    parsed = parse_system(system)
    return {
        "framework": "design-system-ads",
        "name": parsed.name,
        "dna": parsed.dna,
        "archetype": parsed.archetype,
        "tokens": parsed.tokens,
        "contrast": parsed.contrast,
        "copy": parsed.ad_copy,
        "rules": parsed.rules,
        "backgrounds": parsed.backgrounds,
        "tracks": parsed.tracks,
        "must": [
            "Advertising OS, not a website kit.",
            "Keep approved ink/paper/accent unless contrast fails.",
            "Short copy. Recompose IAB, never resize.",
            "Do not invent cream, terracotta, acid green or SaaS cards.",
        ],
    }


def apply_compose(system, raw):
    from .components import ARCHETYPES, compile_rules
    from .tracks import merge_tracks

    parsed = parse_system(system)
    data = dump_system(parsed)
    payload = raw if isinstance(raw, dict) else {}
    if isinstance(payload.get("dna"), dict):
        current = dict(data.get("dna") or {})
        for key in ("name", "personality", "must", "avoid"):
            if payload["dna"].get(key) not in (None, "", []):
                current[key] = payload["dna"][key]
        data["dna"] = current
    archetype = str(payload.get("archetype") or data.get("archetype") or "brand")
    if archetype in ARCHETYPES:
        data["archetype"] = archetype
    data["rules"] = compile_rules(data.get("dna"), data.get("archetype"))
    if isinstance(payload.get("ad_copy"), dict):
        copy = dict(data.get("ad_copy") or {})
        for key in COPY_KEYS:
            if payload["ad_copy"].get(key):
                copy[key] = str(payload["ad_copy"][key]).strip()[:180]
        data["ad_copy"] = copy
    parsed = DesignSystemAds.model_validate(data)
    parsed, applied = apply_token_patches(parsed, payload.get("patches") or [])
    parsed, _ = heal_contrast(parsed)
    data = dump_system(parsed)
    data["tracks"] = merge_tracks(data.get("tracks"), payload.get("tracks"))
    composed = DesignSystemAds.model_validate(data)
    report = DesignSystemPass(
        attempt=len(composed.passes) + 1,
        passed=bool(composed.contrast.get("passed")),
        score=0.88 if applied or payload.get("tracks") or payload.get("dna") else 0.6,
        notes=[str(item)[:200] for item in (payload.get("notes") or ["Sistema montado no OpenRouter."])][:6],
        patches=applied,
    )
    return _append_pass(composed, report), report


def compose_design_system(system, *, text_callable=None, reference_urls=None):
    parsed = parse_system(system)
    if text_callable is None:
        raise ValueError("OpenRouter não está configurado para montar o sistema.")
    brief = advertising_brief(parsed)
    brief["ask"] = (
        "Compose the best Advertising Design System for this brand. "
        "Return JSON: dna{name,personality[],must[],avoid[]}, archetype, "
        "ad_copy{headline,support,cta,legal}, patches[{token_id,css,reason}], "
        "tracks[{id,prompt}] for packshot,kv,lifestyle,wash, notes[]. "
        "Track prompts must name ink/paper hex and leave space for type. "
        "Patches only when a token is wrong for ads."
    )
    content = [{"type": "text", "text": json.dumps(brief, ensure_ascii=False)}]
    for url in [item for item in (reference_urls or []) if item][:4]:
        content.append({"type": "image_url", "image_url": {"url": url}})
    response = text_callable(
        [
            {
                "role": "system",
                "content": (
                    "You are the advertising design director for this brand. "
                    "Build an Advertising Operating System, not a website theme. "
                    "Fidelity to the brand pixels first. JSON only."
                ),
            },
            {"role": "user", "content": content},
        ],
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
    return apply_compose(parsed, raw)


def seed_local_compose(system):
    parsed = parse_system(system)
    dna = dict(parsed.dna or {})
    name = dna.get("name") or parsed.name or "a marca"
    if not dna.get("personality"):
        dna["personality"] = ["clara", "de mídia", "reconhecível"]
    if not dna.get("must"):
        dna["must"] = ["logo reconhecível", "headline curta", "CTA com 4.5:1"]
    if not dna.get("avoid"):
        dna["avoid"] = ["resize cego", "card SaaS", "copy longa"]
    dna["name"] = name
    return apply_compose(
        parsed,
        {
            "dna": dna,
            "archetype": parsed.archetype or "brand",
            "notes": ["DNA assentado no loop local."],
        },
    )


def advance_loop(system, *, text_callable=None, reference_urls=None):
    """Um passo do loop contínuo. Não gera imagem — a mesa pede a trilha."""
    from .catalog import inspect_loop
    from .components import compile_rules

    parsed = parse_system(system)
    info = inspect_loop(parsed)
    report = None
    if info["action"] == "compose":
        if text_callable is not None:
            parsed, report = compose_design_system(
                parsed, text_callable=text_callable, reference_urls=reference_urls
            )
        else:
            parsed, report = seed_local_compose(parsed)
    elif info["action"] == "contrast":
        parsed, report = improve_system(parsed, "contrast")
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
):
    current = parse_system(system)
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
            return current, reports
        budget = max(0, budget - 1)

    if text_callable is None or budget <= 0:
        return current, reports

    last_score = reports[-1].score if reports else 0.0
    for step in range(budget):
        attempt = len(current.passes) + 1
        review = _review_tokens(
            current,
            attempt=attempt,
            text_callable=text_callable,
            reference_urls=reference_urls,
        )
        if review.patches:
            current, applied = apply_token_patches(current, review.patches)
            review.patches = applied
            current, _ = heal_contrast(current)
        current = _append_pass(current, review)
        reports.append(review)
        if review.passed:
            break
        if review.score and last_score and review.score < last_score:
            break
        last_score = review.score
    return current, reports


def _append_pass(system, report):
    data = dump_system(system)
    passes = list(data.get("passes") or [])
    passes.append(report.model_dump() if isinstance(report, DesignSystemPass) else report)
    data["passes"] = passes[-MAX_PASSES:]
    data["version"] = max(1, int(data.get("version") or 1))
    return DesignSystemAds.model_validate(data)


def _review_tokens(system, *, attempt, text_callable, reference_urls=None):
    parsed = parse_system(system)
    brief = advertising_brief(parsed)
    brief["attempt"] = attempt
    brief["ask"] = (
        "Review this Advertising OS. Return JSON: passed, score 0-1, defects[], notes[], "
        "patches[{token_id,css,reason}]. Patch only tokens that fail ads (contrast, CTA, type). "
        "Never rewrite the system. Never invent a generic palette."
    )
    payload = json.dumps(brief, ensure_ascii=False)
    images = [url for url in (reference_urls or []) if url]
    content = [{"type": "text", "text": payload}]
    for url in images[:4]:
        content.append({"type": "image_url", "image_url": {"url": url}})
    try:
        response = text_callable(
            [
                {
                    "role": "system",
                    "content": (
                        "You review an Advertising Design System. "
                        "DNA, contrast, type and CTA. Patches only. Never rewrite."
                    ),
                },
                {"role": "user", "content": content},
            ],
            model=resolve_chat_model(REFINE_MODEL),
            max_tokens=700,
            temperature=0.1,
        )
    except Exception:
        return DesignSystemPass(
            attempt=attempt,
            passed=bool(parsed.contrast.get("passed")),
            score=0.5,
            defects=["O refino não concluiu."],
            patches=[],
        )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception:
                raw = {"passed": False, "defects": ["O refino não devolveu JSON."]}
    try:
        score = float(raw.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return DesignSystemPass(
        attempt=attempt,
        passed=bool(raw.get("passed")),
        score=max(0.0, min(1.0, score)),
        defects=[str(item)[:200] for item in (raw.get("defects") or [])][:8],
        notes=[str(item)[:200] for item in (raw.get("notes") or [])][:8],
        patches=[item for item in (raw.get("patches") or []) if isinstance(item, dict)][:12],
    )
