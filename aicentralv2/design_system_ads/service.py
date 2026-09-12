"""Fachada: preset CentralComm, persistência na marca, refine e approve."""

from __future__ import annotations

from .adapt import MIN_LAYERS, MAX_LAYERS, adapt_system, list_iab_formats
from .campaign import (
    CENTRALCOMM_CAMPAIGN_SLUG,
    centralcomm_campaign_brief,
    ensure_campaign_design_system,
    is_campaign_preset_id,
    layer_count_from_elements,
)
from .centralcomm import CENTRALCOMM_SLUG, centralcomm_preset
from .materialize import ensure_brand_design_system
from .catalog import catalog_for
from .refine import IMPROVE_INTENTS, advance_loop, improve_system, patch_system, refine_design_system
from .render import render_specimen, table_html, tailwind_theme
from .schema import dump_system, parse_system

TOKEN_GROUPS = (
    ("cores", "Cores", ("paper", "ink", "accent", "muted", "cta_ink", "highlight", "hairline")),
    ("tipo", "Tipo", ("font-display", "font-body", "weight-display", "weight-cta", "tracking")),
    ("botao", "CTA", ("cta-radius", "cta-pad", "cta-shadow")),
    ("fundo", "Fundo", ("ground-kind", "ground", "overlay", "wash-strength", "grain")),
)


def payload_for(
    system,
    *,
    format_key=None,
    layer_count=None,
    swaps=None,
    archetype=None,
    report=None,
    storage=None,
):
    from .provenance import ensure_provenance, stamp_centralcomm

    parsed = parse_system(system)
    if parsed.source == "tailwind-centralcomm":
        evidence = parsed.evidence if isinstance(parsed.evidence, dict) else {}
        if not (evidence.get("provenance") or {}).get("fields"):
            parsed = stamp_centralcomm(parsed)
    else:
        parsed = ensure_provenance(parsed)
    stack = None
    if not format_key:
        from .components import ARCHETYPE_FORMAT

        format_key = ARCHETYPE_FORMAT.get(archetype or parsed.archetype or "brand") or "iab-billboard"
    if format_key:
        if layer_count in (None, "") and parsed.elements:
            layer_count = layer_count_from_elements(parsed.elements)
        parsed, stack = adapt_system(
            parsed,
            format_key,
            layer_count or MIN_LAYERS,
            swaps=swaps,
            archetype=archetype,
        )
    parsed.specimen_html = render_specimen(parsed, standalone=False, stack=stack)
    data = dump_system(parsed)
    data["table_html"] = table_html(parsed)
    data["tailwind"] = tailwind_theme(parsed)
    if parsed.scope == "campaign":
        data["specimen_url"] = specimen_campaign_path(
            parsed.id.replace("dsa-campaign-", "") if parsed.id else CENTRALCOMM_CAMPAIGN_SLUG,
            format_key,
            layer_count,
        )
    else:
        data["specimen_url"] = specimen_path(parsed.client_id, format_key, layer_count)
    data["iab_formats"] = list_iab_formats()
    data["layers"] = {
        "min": MIN_LAYERS,
        "max": MAX_LAYERS,
        "count": int((stack or {}).get("layer_count") or MIN_LAYERS),
    }
    data["elements"] = list(parsed.elements or [])
    data["creative_line"] = parsed.creative_line or ""
    data["token_groups"] = [
        {
            "id": key,
            "label": label,
            "tokens": [
                {"id": token_id, "value": (parsed.tokens or {}).get(token_id, "")}
                for token_id in ids
            ],
        }
        for key, label, ids in TOKEN_GROUPS
    ]
    data["intents"] = [
        {"id": "contrast", "label": "Contraste", "hint": "Tinta e leitura a 4.5:1."},
        {"id": "type", "label": "Tipo", "hint": "Peso e tracking de peça."},
        {"id": "cta", "label": "CTA", "hint": "Miolo, canto e elevação do botão."},
        {"id": "compact", "label": "Compacto", "hint": "Menos ar, título fechado."},
        {"id": "airy", "label": "Arejado", "hint": "Mais margem e botão largo."},
    ]
    data["backgrounds"] = list(parsed.backgrounds or [])
    data["archetype"] = parsed.archetype
    data["rules"] = parsed.rules or {}
    data["dna"] = parsed.dna or {}
    data["tracks"] = list(parsed.tracks or [])
    data["catalog"] = catalog_for(parsed, client_id=parsed.client_id)
    data["iab_formats"] = data["catalog"]["iab_formats"]
    data["components"] = data["catalog"]["components"]
    data["archetypes"] = data["catalog"]["archetypes"]
    data["flow"] = data["catalog"]["flow"]
    data["loop"] = data["catalog"]["loop"]
    from .provenance import summarize_for_payload

    data["provenance"] = summarize_for_payload(parsed)
    data["needs_confirmation"] = data["provenance"]["needs_confirmation"]
    data["identity"] = data["provenance"]["identity"]
    data["needs_input"] = list(parsed.needs_input or [])
    data["ad_copy_by_format"] = dict(parsed.ad_copy_by_format or {})
    if stack:
        data["adapt"] = stack
        data["adapt_conflicts"] = list(stack.get("conflicts") or [])
    from .runtime_policy import (
        MIGRATED_TASKS,
        POLICY_VERSION,
        UNMIGRATED_TASKS,
        preset_context_for,
    )
    from .skills import skill_bundle

    preset_context = preset_context_for(parsed)
    task = "preset" if parsed.source == "tailwind-centralcomm" else "brand"
    data["skill_context"] = skill_bundle(task, preset_context=preset_context)
    data["runtime_context"] = {
        "profile": "ads-runtime-payload",
        "policy_version": POLICY_VERSION,
        "preset_context": preset_context,
        "migrated": list(MIGRATED_TASKS),
        "unmigrated": list(UNMIGRATED_TASKS),
        "skill_applied": False,
    }
    from .validate import attach_validation_payload

    payload = attach_validation_payload(data, parsed, report=report)
    if isinstance(storage, dict):
        payload["storage"] = storage
    return payload


def specimen_path(client_id, format_key=None, layer_count=None):
    slug = client_id if client_id not in (None, "") else CENTRALCOMM_SLUG
    path = f"/lab/design-system/marca/{slug}"
    return _with_query(path, format_key, layer_count)


def specimen_campaign_path(campaign_id, format_key=None, layer_count=None):
    slug = campaign_id if campaign_id not in (None, "") else CENTRALCOMM_CAMPAIGN_SLUG
    path = f"/lab/design-system/campanha/{slug}"
    return _with_query(path, format_key, layer_count)


def _with_query(path, format_key, layer_count):
    query = []
    if format_key:
        query.append(f"format={format_key}")
    if layer_count:
        query.append(f"layers={layer_count}")
    return f"{path}?{'&'.join(query)}" if query else path


def is_preset_id(client_id):
    from .centralcomm import is_house_context_id

    return is_house_context_id(client_id)


def read_preset():
    from .provenance import stamp_centralcomm

    return payload_for(stamp_centralcomm(centralcomm_preset(status="approved")))


def read_campaign_preset():
    system, _elements = ensure_campaign_design_system(
        centralcomm_preset(status="approved"),
        centralcomm_campaign_brief(),
    )
    system.status = "approved"
    return payload_for(system, format_key="iab-billboard")


def materialize_client(client, existing=None):
    return ensure_brand_design_system(client, existing=existing)


def run_refine(
    system,
    *,
    attempts=4,
    text_callable=None,
    reference_urls=None,
    client=None,
    client_id=None,
    intent=None,
):
    refined, reports = refine_design_system(
        system,
        attempts=attempts,
        text_callable=text_callable,
        reference_urls=reference_urls,
        client=client,
        client_id=client_id,
        intent=intent,
    )
    return refined, reports


def run_improve(system, intent, *, client=None, client_id=None):
    if str(intent or "").strip().lower() not in IMPROVE_INTENTS:
        raise ValueError("Escolha o que melhorar: contraste, tipo, CTA, compacto ou arejado.")
    return improve_system(system, intent, client=client, client_id=client_id)


def run_patch(system, tokens=None, ad_copy=None, dna=None, archetype=None):
    return patch_system(system, tokens=tokens, ad_copy=ad_copy, dna=dna, archetype=archetype)


def run_loop(system, *, text_callable=None, reference_urls=None, client=None, client_id=None):
    return advance_loop(
        system,
        text_callable=text_callable,
        reference_urls=reference_urls,
        client=client,
        client_id=client_id,
    )


def mark_approved(system):
    data = dump_system(system)
    data["status"] = "approved"
    return parse_system(data)
