"""Campaign Snapshot — fonte única da verdade da geração."""

from __future__ import annotations

from datetime import datetime, timezone

from .catalog import CHANNEL_CATALOG, channel_label, objetivo_label
from .helpers import as_bool, as_dict, as_list, client_display_name, session_title, text
from .materials import normalize_references
from .mix import progress_calendar, should_progress
from .pace import budget_shares, campaign_pace, format_money
from .places_bridge import snapshot_places


def build_snapshot(row: dict, dados: dict | None = None) -> dict:
    dados = as_dict(dados if dados is not None else row.get("dados_detectados"))
    campanha = as_dict(dados.get("campanha"))
    brand = as_dict(dados.get("brand"))
    fonte = as_dict(dados.get("fonte"))
    refs = normalize_references(fonte.get("referencias") or dados.get("referencias"))
    canais = [key for key in as_list(campanha.get("canais") or dados.get("canais")) if key in CHANNEL_CATALOG]
    split = campanha.get("canais_verba") if isinstance(campanha.get("canais_verba"), dict) else {}
    shares = budget_shares(split) if split else {}
    mix = []
    for key in canais:
        mix.append({
            "id": key,
            "label": channel_label(key),
            "pct": shares.get(key),
            "amount": split.get(key),
            "amount_label": format_money(int(split.get(key) or 0)) if split.get(key) else "",
            "desc": (CHANNEL_CATALOG.get(key) or {}).get("desc", ""),
        })
    pace = campaign_pace(campanha)
    sources = []
    for item in refs:
        sources.append({
            "id": text(item.get("kind")) + ":" + text(item.get("label") or item.get("url") or item.get("name")),
            "kind": item.get("kind"),
            "label": item.get("label") or item.get("name") or item.get("url"),
            "papel": item.get("papel"),
            "notas": text(item.get("notas"))[:2000],
        })
    pending = as_list(as_dict(row.get("analise_ia")).get("falta_completar"))
    snapshot_id = f"campaign_{text(row.get('id') or row.get('session_token') or 'tmp')}_r{int(datetime.now(timezone.utc).timestamp())}"
    client_name = text(row.get("cliente") or dados.get("cliente") or campanha.get("cliente"))
    confidential = as_bool(dados.get("anunciante_confidencial"))
    return {
        "snapshot_id": snapshot_id,
        "client": {
            "name": client_name,
            "id": dados.get("cliente_id"),
            "agency": text(dados.get("agencia") or campanha.get("agencia")),
            "agency_id": dados.get("agencia_id"),
            "confidential": confidential,
            "display_name": client_display_name(confidential=confidential, name=client_name),
        },
        "campaign": {
            "name": session_title(row, dados),
            "id": row.get("session_token"),
        },
        "objective": {
            "id": text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo")),
            "label": objetivo_label(text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo"))),
            "text": text(dados.get("objetivo_texto")),
        },
        "audiences": [text(row.get("publico_alvo") or dados.get("publico"))] if text(row.get("publico_alvo") or dados.get("publico")) else [],
        "geography": {
            "praca": text(campanha.get("praca") or dados.get("praca")),
            "detail": text(campanha.get("praca_detalhe") or dados.get("praca_detalhe")),
        },
        "period": {"raw": text(row.get("prazo") or campanha.get("periodo") or dados.get("periodo"))},
        "budget": {
            "raw": text(row.get("budget") or campanha.get("verba") or dados.get("verba")),
            "base": text(campanha.get("verba_base") or dados.get("verba_base") or "total"),
        },
        "channels": canais,
        "mix": mix,
        "mix_method": text(as_dict(campanha.get("mix")).get("method")),
        "mix_progress": should_progress(pace.get("meses"), campanha.get("mix")),
        "calendar": progress_calendar(
            canais,
            text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo")),
            text(as_dict(campanha.get("mix")).get("method")),
            pace,
            campanha.get("mix"),
        ),
        "kpis": as_list(dados.get("kpis") or campanha.get("kpis")),
        "brand": {
            "name": text(brand.get("name")),
            "tone": text(brand.get("tone_of_voice")),
            "summary": text(brand.get("brand_summary")),
            "audience": text(brand.get("target_audience")),
            "products": brand.get("products_services"),
        },
        "places": snapshot_places(campanha.get("places") or dados.get("places")),
        "interativos": as_dict(campanha.get("interativos") or dados.get("interativos")),
        "restrictions": [text(dados.get("observacoes"))] if text(dados.get("observacoes")) else [],
        "sources": sources,
        "assumptions": [],
        "pending_decisions": [text(item) for item in pending if text(item)],
        "briefing": text(row.get("briefing_melhorado") or row.get("briefing_compilado")),
        "user_briefing": text(fonte.get("briefing") or row.get("input_text_original")),
        "pace": {
            "labels": pace.get("rotulos") or [],
            "keys": pace.get("chaves") or [],
            "allocation": pace.get("alocacao") or {},
            "how": text(pace.get("como")),
        },
        "media_params": as_dict(dados.get("media_params") or campanha.get("media_params")),
    }


def build_evidence(snapshot: dict) -> dict:
    sources = as_list((snapshot or {}).get("sources"))
    return {
        "snapshot_id": text((snapshot or {}).get("snapshot_id")),
        "source_count": len(sources),
        "sources": sources,
        "briefing": text((snapshot or {}).get("briefing")),
        "user_briefing": text((snapshot or {}).get("user_briefing")),
        "restrictions": as_list((snapshot or {}).get("restrictions")),
        "pending_decisions": as_list((snapshot or {}).get("pending_decisions")),
    }
