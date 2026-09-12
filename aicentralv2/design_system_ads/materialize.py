"""Compila o DS Ads a partir da marca. CentralComm usa o preset Tailwind."""

from __future__ import annotations

from ..creative_brand_dna import materialize_brand_dna
from .centralcomm import centralcomm_preset
from .ingest import merge_extracted_tokens
from .refine import heal_contrast
from .schema import FRAMEWORK, DesignSystemAds, normalize_hex, parse_system


def _text(value, default="", limit=80):
    text = str(value or "").strip()
    return (text or default)[:limit]


def _hexes(items):
    colors = []
    for item in items or []:
        if isinstance(item, dict):
            color = normalize_hex(item.get("hex") or item.get("color") or item.get("value"))
        else:
            color = normalize_hex(item)
        if color and color not in colors:
            colors.append(color)
        if len(colors) >= 8:
            break
    return colors


def _fonts(profile, line, dna):
    fonts = profile.get("fonts") if isinstance(profile.get("fonts"), list) else []
    display = ""
    body = ""
    for item in fonts:
        if not isinstance(item, dict):
            family = _text(item, limit=80)
            if family and not display:
                display = family
            continue
        family = _text(item.get("family"), limit=80)
        role = str(item.get("role") or "").strip().lower()
        if not family:
            continue
        if role in {"display", "heading", "headline", "title", "primary"} and not display:
            display = family
        elif not body:
            body = family
    if not display:
        display = _text((dna.get("fonts") or {}).get("primary"), limit=80)
    if not body:
        typography = ((line.get("copy_system") or {}).get("typography") or {})
        body = _text(
            (dna.get("fonts") or {}).get("fallback") or typography.get("family"),
            default=display,
            limit=80,
        )
    from .schema import TYPE_STACK_FALLBACK

    return display or TYPE_STACK_FALLBACK, body or display or TYPE_STACK_FALLBACK


def _existing_system(client, profile):
    stored = profile.get("design_system_ads")
    if isinstance(stored, dict) and (
        stored.get("framework") == FRAMEWORK or stored.get("tokens")
    ):
        parsed = parse_system(stored)
        if client.get("id") and not parsed.client_id:
            parsed.client_id = client.get("id")
        from .provenance import ensure_provenance

        return ensure_provenance(parsed)
    return None


def ensure_brand_design_system(client=None, *, existing=None):
    client = client if isinstance(client, dict) else {}
    profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
    line = profile.get("creative_line") if isinstance(profile.get("creative_line"), dict) else {}
    found = existing if existing is not None else _existing_system(client, profile)
    if found:
        from .fidelity import attach_client_evidence
        from .provenance import ensure_provenance

        return attach_client_evidence(ensure_provenance(parse_system(found)), client)

    from .centralcomm import may_apply_house_preset, resolve_preset_context

    preset_context = resolve_preset_context(client=client, client_id=client.get("id"))
    if may_apply_house_preset(preset_context):
        preset = centralcomm_preset(client_id=client.get("id") or "centralcomm")
        logo = (
            client.get("logo_upload_path")
            or client.get("logo_url")
            or preset.logo_url
        )
        tokens = dict(preset.tokens)
        tokens["logo"] = logo
        from .fidelity import attach_client_evidence
        from .provenance import stamp_centralcomm

        return attach_client_evidence(
            stamp_centralcomm(
                DesignSystemAds.model_validate(
                    {
                        **preset.model_dump(),
                        "client_id": client.get("id") or preset.client_id,
                        "logo_url": logo,
                        "tokens": tokens,
                    }
                )
            ),
            client,
        )

    dna = materialize_brand_dna(client, profile, profile.get("brand_dna"))
    palette = _hexes(
        profile.get("color_palette")
        or line.get("color_palette")
        or (dna.get("colors") or {}).get("palette")
    )
    if client.get("primary_color"):
        palette = _hexes([client.get("primary_color"), *palette])
    if client.get("secondary_color"):
        palette = _hexes([*palette, client.get("secondary_color")])
    from .schema import NEUTRAL_INK, NEUTRAL_MUTED, TYPE_STACK_FALLBACK

    ink = palette[0] if palette else NEUTRAL_INK
    highlight = palette[1] if len(palette) > 1 else (palette[0] if palette else NEUTRAL_INK)
    display, body = _fonts(profile, line, dna)
    logo = (
        (dna.get("logo") or {}).get("asset_url")
        or client.get("logo_upload_path")
        or client.get("logo_url")
        or ""
    )
    name = _text(client.get("name"), default="A marca", limit=80)
    client_id = client.get("id") or "marca"
    tokens = {
        "paper": "#FFFFFF",
        "ink": ink,
        "accent": ink,
        "muted": NEUTRAL_MUTED,
        "cta_ink": "#FFFFFF",
        "highlight": highlight,
        "logo": logo,
        "font-display": display,
        "font-body": body,
    }
    extracted = (
        profile.get("extracted_design_system")
        or profile.get("extract_design_system")
        or client.get("extracted_design_system")
    )
    source = "brand"
    evidence = {}
    if extracted:
        tokens, evidence = merge_extracted_tokens(tokens, extracted, client=client)
        tokens["logo"] = logo or tokens.get("logo") or ""
        source = "extract-design-system"
    system = DesignSystemAds.model_validate(
        {
            "id": f"dsa-{client_id}-v1",
            "scope": "brand",
            "name": f"{name} Ads" if name not in {"Design System Ads", "A marca"} else name,
            "source": source,
            "status": "draft",
            "client_id": client_id,
            "logo_url": logo,
            "tokens": tokens,
            "evidence": evidence,
            "dna": _dna_from_evidence(name, client, profile, dna, evidence),
            "archetype": "brand",
            "ad_copy": {},
        }
    )
    if extracted:
        system, _patches = heal_contrast(system)
    from .fidelity import attach_client_evidence
    from .provenance import stamp_fields

    records = {}
    if extracted:
        for key in ("paper", "ink", "accent", "highlight", "font-display", "font-body"):
            value = str((system.tokens or {}).get(key) or "").strip()
            if key.startswith("font") and (not value or value == TYPE_STACK_FALLBACK):
                records[f"tokens.{key}"] = {
                    "state": "fallback",
                    "origin": "schema-default",
                }
                continue
            records[f"tokens.{key}"] = {
                "state": "inferred",
                "origin": "extract-design-system",
                "evidence_ids": ["extracted_design_system"],
            }
    else:
        if client.get("primary_color"):
            records["tokens.ink"] = {
                "state": "inferred",
                "origin": "primary_color",
                "evidence_ids": ["primary_color"],
            }
            records["tokens.accent"] = {
                "state": "inferred",
                "origin": "primary_color",
                "evidence_ids": ["primary_color"],
            }
        else:
            records["tokens.ink"] = {"state": "fallback", "origin": "schema-default"}
            records["tokens.accent"] = {"state": "fallback", "origin": "schema-default"}
        records["tokens.paper"] = {"state": "fallback", "origin": "schema-default"}
        records["tokens.highlight"] = {
            "state": "inferred" if len(palette) > 1 else "fallback",
            "origin": "palette" if len(palette) > 1 else "schema-default",
        }
        records["tokens.muted"] = {"state": "fallback", "origin": "schema-default"}
        if not display or display == TYPE_STACK_FALLBACK:
            records["tokens.font-display"] = {"state": "fallback", "origin": "schema-default"}
        else:
            records["tokens.font-display"] = {
                "state": "inferred",
                "origin": "brand_profile.fonts",
            }
        if logo:
            records["tokens.logo"] = {
                "state": "inferred",
                "origin": "logo",
                "evidence_ids": ["logo"],
            }
    system = stamp_fields(system, records)
    return attach_client_evidence(system, client)


GENERIC_TRAITS = {"reconhecível", "reconhecivel", "direta", "de marca"}


def _dna_from_evidence(name, client, profile, dna, evidence):
    profile = profile if isinstance(profile, dict) else {}
    dna = dna if isinstance(dna, dict) else {}
    evidence = evidence if isinstance(evidence, dict) else {}
    voice = evidence.get("voice") if isinstance(evidence.get("voice"), dict) else {}
    stored = profile.get("brand_dna") if isinstance(profile.get("brand_dna"), dict) else {}
    personality = _list(
        stored.get("personality")
        or dna.get("personality")
        or dna.get("traits")
    )
    personality = [item for item in personality if item.lower() not in GENERIC_TRAITS]
    tone = _text(
        client.get("tone_of_voice")
        or stored.get("tone")
        or dna.get("tone")
        or evidence.get("tone"),
        limit=40,
    )
    sector = _text(
        client.get("sector")
        or stored.get("sector")
        or dna.get("sector")
        or evidence.get("sector"),
        limit=40,
    )
    products = _list(profile.get("products_services") or evidence.get("products"))
    if products and products[0] not in personality:
        personality.append(products[0])
    if tone and tone not in personality:
        personality.append(tone)
    if sector and sector not in personality:
        personality.append(sector)
    if voice.get("density") == "compact" and "compacta na mídia" not in personality:
        personality.append("compacta na mídia")
    elif voice.get("density") == "airy" and "arejada na mídia" not in personality:
        personality.append("arejada na mídia")
    must = _unique_list(
        _list(stored.get("must") or dna.get("must"))
        + _list(profile.get("mandatory_elements"))
    )
    avoid = _unique_list(
        _list(stored.get("avoid") or dna.get("avoid"))
        + _list(profile.get("forbidden_elements"))
    )
    if logo_hint(client, dna) and not any("logo" in item.lower() for item in must):
        must.append(f"logo de {name} com respiro")
    if not any("cta" in item.lower() for item in must):
        must.append("CTA com 4.5:1")
    if not any("resize" in item.lower() for item in avoid):
        avoid.append("resize cego")
    if not any("saas" in item.lower() for item in avoid):
        avoid.append("card SaaS")
    return {
        "name": name,
        "personality": personality[:5],
        "must": must[:6],
        "avoid": avoid[:6],
    }


def logo_hint(client, dna):
    client = client if isinstance(client, dict) else {}
    dna = dna if isinstance(dna, dict) else {}
    return bool(
        client.get("logo_url")
        or client.get("logo_upload_path")
        or (dna.get("logo") or {}).get("asset_url")
    )


def _list(value):
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()][:8]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()][:8]
    return []


def _unique_list(items):
    seen = set()
    unique = []
    for item in items or []:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:8]
