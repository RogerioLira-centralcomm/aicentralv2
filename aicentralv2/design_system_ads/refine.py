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


def heal_contrast(system):
    parsed = parse_system(system)
    tokens = dict(parsed.tokens)
    paper = normalize_hex(tokens.get("paper"), "#FFFFFF")
    ink = normalize_hex(tokens.get("ink"), "#1E4D4F")
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
            darker = mix_hex(tokens.get("ink"), "#000000", 0.2) or "#153638"
            set_token("ink", darker, "Tinta mais escura para o título ler no IAB.")
            set_token("muted", mix_hex(darker, "#64748B", 0.35) or "#3D4451", "Apoio acompanha a tinta.")
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
        from .copy import clean_ad_copy

        data["ad_copy"] = clean_ad_copy(
            payload["ad_copy"],
            (data.get("dna") or {}).get("name") or data.get("name"),
        )
    effects = payload.get("effects") if isinstance(payload.get("effects"), dict) else {}
    extra_patches = list(payload.get("patches") or [])
    for key in ("wash-strength", "grain", "overlay", "cta-shadow", "hairline"):
        if effects.get(key) not in (None, ""):
            extra_patches.append({"token_id": key, "css": effects[key], "reason": "Efeito de mídia."})
    parsed = DesignSystemAds.model_validate(data)
    parsed, applied = apply_token_patches(parsed, lock_token_patches(parsed, extra_patches))
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
        "Escreva o Advertising OS desta MARCA em português. Não é campanha. "
        "Use fidelity: tinta travada, setor, tom, produtos, forbidden e assets. "
        "JSON: dna{name,personality[3-5 traços concretos desta marca],must[],avoid[]}, "
        "archetype, ad_copy{headline,support,cta,legal} o que a marca vende e para quem, "
        "patches[{token_id,css,reason}] só se o token falhar e só na família da tinta travada, "
        "effects{wash-strength,grain,overlay,cta-shadow}, "
        "tracks[{id,prompt}] packshot,kv,lifestyle,wash com material, luz, recorte e hex, notes[]. "
        "Se fidelity.assets já tiver URL para uma trilha, não invente outra imagem. "
        "Wash é CSS (wash-strength), não peça foto de gradiente. "
        "Proibido: reconhecível, direta, de marca, Saiba mais, no primeiro olhar, design system, "
        "tinta certa, herda o tema, Tailwind, cream, terracotta, card SaaS. "
        "Wash é a lavagem DESTA tinta, não um campo genérico."
    )
    content = [{"type": "text", "text": json.dumps(brief, ensure_ascii=False)}]
    for url in [item for item in (reference_urls or []) if item][:4]:
        content.append({"type": "image_url", "image_url": {"url": url}})
    response = text_callable(
        [
            {
                "role": "system",
                "content": (
                    "Você é o diretor de arte desta marca. "
                    "Copy de anúncio em português, fiel aos pixels. "
                    "Nunca escreva sobre o laboratório ou o design system. JSON only."
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
    from .copy import brand_ad_copy
    from .materialize import GENERIC_TRAITS, _dna_from_evidence

    parsed = parse_system(system)
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
    return apply_compose(
        parsed,
        {
            "dna": dna,
            "archetype": parsed.archetype or "brand",
            "ad_copy": copy,
            "notes": ["Linha da marca assentada no loop, sem traço genérico."],
        },
    )


def compose_campaign_design_system(system, campaign=None, *, text_callable=None):
    parsed = parse_system(system)
    campaign = campaign if isinstance(campaign, dict) else {}
    if text_callable is None:
        return seed_campaign_compose(parsed, campaign)
    brief = advertising_brief(parsed)
    brief["scope"] = "campaign"
    brief["campaign"] = {
        "name": campaign.get("name") or parsed.name,
        "objective": campaign.get("objective") or "",
        "campaign_text": campaign.get("campaign_text") or "",
        "cta_text": campaign.get("cta_text") or "",
        "creative_line": campaign.get("creative_line") or parsed.creative_line,
    }
    brief["ask"] = (
        "Escreva a CAMPANHA desta marca em português. Não reescreva ink, paper nem accent. "
        "JSON: creative_line (uma frase da temporada), ad_copy{headline,support,cta,legal} da oferta, "
        "archetype (product-hero|lifestyle|promotion|brand), "
        "tracks[{id,prompt}] só kv e lifestyle com a linha da campanha, "
        "ground-kind paper|wash|image, notes[]. "
        "Proibido: copiar a headline institucional da marca, Saiba mais, design system."
    )
    response = text_callable(
        [
            {
                "role": "system",
                "content": (
                    "Você é o diretor de arte da campanha. "
                    "A tinta da marca está travada. Copy e KV mudam. JSON only."
                ),
            },
            {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
        ],
        model=resolve_chat_model(COMPOSE_MODEL),
        max_tokens=900,
        temperature=0.35,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception as exc:
                raise ValueError("O OpenRouter não devolveu a campanha.") from exc
    return apply_campaign_compose(parsed, raw)


def seed_campaign_compose(system, campaign=None):
    campaign = campaign if isinstance(campaign, dict) else {}
    parsed = parse_system(system)
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
    return apply_campaign_compose(
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
    )


def apply_campaign_compose(system, raw):
    from .components import ARCHETYPES, apply_background
    from .copy import clean_ad_copy
    from .tracks import merge_tracks

    parsed = parse_system(system)
    data = dump_system(parsed)
    data["scope"] = "campaign"
    payload = raw if isinstance(raw, dict) else {}
    if payload.get("creative_line"):
        data["creative_line"] = str(payload["creative_line"]).strip()[:240]
    if isinstance(payload.get("ad_copy"), dict):
        data["ad_copy"] = clean_ad_copy(payload["ad_copy"], data.get("name"))
    archetype = str(payload.get("archetype") or data.get("archetype") or "brand")
    if archetype in ARCHETYPES:
        data["archetype"] = archetype
    if payload.get("ground-kind"):
        data["tokens"] = apply_background(
            data.get("tokens") or {},
            payload.get("ground-kind"),
            image_url=(payload.get("tokens") or {}).get("ground") if isinstance(payload.get("tokens"), dict) else None,
        )
    if isinstance(payload.get("tracks"), list):
        data["tracks"] = merge_tracks(data.get("tracks"), payload.get("tracks"))
    composed = DesignSystemAds.model_validate(data)
    report = DesignSystemPass(
        attempt=len(composed.passes) + 1,
        passed=True,
        score=0.86,
        notes=[str(item)[:200] for item in (payload.get("notes") or ["Campanha montada."])][:6],
        patches=[],
    )
    return _append_pass(composed, report), report


def review_fidelity(system, *, text_callable=None, reference_urls=None):
    from .copy import is_stock_copy

    parsed = parse_system(system)
    if text_callable is None:
        score = 0.74 if parsed.contrast.get("passed") and not is_stock_copy(parsed.ad_copy) else 0.48
        notes = ["Revisão local: tinta da marca travada e copy sem estoque."]
        reviewed = mark_reviewed(parsed, score=score, notes=notes)
        report = DesignSystemPass(
            attempt=len(reviewed.passes) + 1,
            passed=score >= 0.7,
            score=score,
            notes=notes,
            patches=[],
        )
        return _append_pass(reviewed, report), report

    brief = advertising_brief(parsed)
    brief["ask"] = (
        "Revise a FIDELIDADE deste Advertising OS contra fidelity "
        "(tinta travada, setor, tom, produtos, assets). "
        "JSON: passed, score 0-1, notes[], defects[], "
        "dna{name,personality,must,avoid} só se o DNA for genérico, "
        "ad_copy{headline,support,cta,legal} só se a copy for estoque ou meta, "
        "patches[{token_id,css,reason}] só na família de fidelity.locked_tokens. "
        "Proibido trocar ink/paper/accent por outra marca. "
        "Nunca use teal CentralComm se a tinta da marca não for teal."
    )
    content = [{"type": "text", "text": json.dumps(brief, ensure_ascii=False)}]
    for url in [item for item in (reference_urls or []) if item][:4]:
        content.append({"type": "image_url", "image_url": {"url": url}})
    try:
        response = text_callable(
            [
                {
                    "role": "system",
                    "content": (
                        "Você revisa fidelidade de Advertising OS. "
                        "A tinta extraída é lei. Copy de anúncio em português. JSON only."
                    ),
                },
                {"role": "user", "content": content},
            ],
            model=resolve_chat_model(COMPOSE_MODEL),
            max_tokens=900,
            temperature=0.15,
        )
    except Exception:
        reviewed = mark_reviewed(parsed, score=0.5, notes=["A revisão não concluiu."])
        report = DesignSystemPass(
            attempt=len(reviewed.passes) + 1,
            passed=bool(parsed.contrast.get("passed")),
            score=0.5,
            defects=["A revisão de fidelidade não concluiu."],
            patches=[],
        )
        return _append_pass(reviewed, report), report
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception:
                raw = {"passed": False, "notes": ["A revisão não devolveu JSON."]}
    composed, report = apply_compose(parsed, raw)
    try:
        score = float(raw.get("score") or report.score or 0)
    except (TypeError, ValueError):
        score = report.score or 0.0
    reviewed = mark_reviewed(composed, score=score, notes=report.notes)
    return reviewed, report


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
    elif info["action"] == "review":
        parsed, report = review_fidelity(
            parsed, text_callable=text_callable, reference_urls=reference_urls
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
        patches=lock_token_patches(
            parsed,
            [item for item in (raw.get("patches") or []) if isinstance(item, dict)][:12],
        ),
    )
