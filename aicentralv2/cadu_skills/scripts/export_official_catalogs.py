#!/usr/bin/env python3
"""Exporta canais, audiências e formatos para a família oficial Cadu Skills."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app  # noqa: E402
from aicentralv2.creative_format_registry import FORMATS  # noqa: E402
from aicentralv2.crm_v3_canais import listar_canais  # noqa: E402


SKILLS_ROOT = Path(__file__).resolve().parents[1]
MEDIA_REFS = SKILLS_ROOT / "media-planning" / "references"
DESTINATIONS = {
    "channels.csv": (
        MEDIA_REFS,
        SKILLS_ROOT / "channel-intelligence" / "references",
        SKILLS_ROOT / "audience-intelligence" / "references",
        SKILLS_ROOT / "format-intelligence" / "references",
    ),
    "audiences.csv": (
        MEDIA_REFS,
        SKILLS_ROOT / "channel-intelligence" / "references",
        SKILLS_ROOT / "audience-intelligence" / "references",
    ),
    "formats.csv": (
        MEDIA_REFS,
        SKILLS_ROOT / "channel-intelligence" / "references",
        SKILLS_ROOT / "format-intelligence" / "references",
    ),
}

CHANNEL_FIELDS = (
    "snapshot_at", "slug", "nome", "categoria", "tipo", "alcance", "viewability",
    "investimento_minimo", "descricao", "segmentacoes", "diferenciais",
    "audience_slugs", "audience_names", "audience_count",
)
AUDIENCE_FIELDS = (
    "snapshot_at", "id", "slug", "nome", "canonical_name", "titulo_chamativo",
    "plataforma", "fonte", "categoria", "subcategoria", "catalog_role", "market_scope",
    "primary_market", "primary_submarket", "related_markets", "b2b_b2c_orientation",
    "signal_types", "funnel_stages", "available_channels", "geographic_scope",
    "activation_restrictions", "descricao", "descricao_curta", "descricao_comercial",
    "caso_uso_principal", "insights_planejamento", "diferenciais_competitivos",
    "perfil_socioeconomico", "tags", "momentos_chave", "interesses_correlatos",
    "publico_estimado", "publico_numero", "tamanho", "demografia", "dispositivos",
    "propensao_compra", "sazonalidade",
    "curation_status", "classification_confidence", "data_quality_status", "data_origin",
    "source_reference", "source_observed_at", "data_valid_until", "methodology_note",
    "is_estimated", "verification_candidate", "verification_gaps", "measurements",
)
FORMAT_FIELDS = (
    "snapshot_at", "source", "channel_slug", "channel_name", "channel_type", "format_key",
    "name", "label", "width", "height", "duration", "family", "kind", "best_for",
    "devices", "channels", "placement_zones", "viewer_types", "required_elements",
    "optional_elements", "forbidden_elements", "safe_areas", "aliases", "commercial_notes",
)


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(type(value).__name__)


def _json(value) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _list(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return [text]
        return list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
    return [value]


def _audiences_from_db():
    from aicentralv2.db import get_db

    with get_db().cursor() as cursor:
        cursor.execute(
            """
            SELECT to_jsonb(a) AS audience,
                   COALESCE(p.nome, NULLIF(TRIM(a.fonte), '')) AS plataforma_nome,
                   cat.nome AS categoria_nome, sub.nome AS subcategoria_nome,
                   COALESCE(to_jsonb(tax), '{}'::jsonb) AS taxonomy,
                   COALESCE((
                       SELECT jsonb_agg(to_jsonb(m) ORDER BY m.period_end DESC NULLS LAST, m.id)
                         FROM cadu_audience_measurements m WHERE m.audience_id = a.id
                   ), '[]'::jsonb) AS measurements,
                   COALESCE((
                       SELECT jsonb_agg(jsonb_build_object(
                           'slug', rel.market_slug, 'name', market.nome,
                           'relation_type', rel.relation_type
                       ) ORDER BY rel.relation_type, market.ordem_exibicao)
                         FROM cadu_audience_market_relations rel
                         JOIN cadu_taxonomy_markets market ON market.slug = rel.market_slug
                        WHERE rel.audience_id = a.id
                   ), '[]'::jsonb) AS related_markets
              FROM cadu_audiencias a
         LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
         LEFT JOIN cadu_categorias cat ON cat.id = a.categoria_id
         LEFT JOIN cadu_subcategorias sub ON sub.id = a.subcategoria_id
         LEFT JOIN cadu_audience_taxonomy tax ON tax.audience_id = a.id
             WHERE a.is_active IS TRUE
          ORDER BY a.nome
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def _audiences_from_snapshot(path: Path):
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            audience = dict(row)
            rows.append({
                "audience": audience,
                "plataforma_nome": row.get("plataforma") or row.get("fonte") or "",
                "categoria_nome": row.get("categoria") or "",
                "subcategoria_nome": row.get("subcategoria") or "",
                "taxonomy": {},
                "measurements": [],
                "related_markets": [],
            })
    return rows


def _audience_rows(raw_rows, stamp):
    out = []
    for wrapper in raw_rows:
        a = wrapper.get("audience") or {}
        tax = wrapper.get("taxonomy") or {}
        demografia = {key: a.get(key) for key in (
            "demografia_homens", "demografia_mulheres", "idade_18_24", "idade_25_34",
            "idade_35_44", "idade_45_mais",
        ) if a.get(key) not in (None, "")}
        dispositivos = {key.removeprefix("dispositivo_"): a.get(key) for key in (
            "dispositivo_mobile", "dispositivo_desktop", "dispositivo_tablet",
        ) if a.get(key) not in (None, "")}
        available_channels = _list(tax.get("available_channels"))
        verification_gaps = []
        for field, label in (
            (tax.get("data_origin"), "origem"),
            (tax.get("source_reference"), "fonte de evidência"),
            (tax.get("source_observed_at"), "data de observação"),
            (tax.get("data_valid_until"), "validade"),
            (tax.get("methodology_note"), "metodologia"),
            (available_channels, "canais de ativação explícitos"),
        ):
            if not field:
                verification_gaps.append(label)
        if tax.get("is_estimated") is True:
            verification_gaps.append("dado marcado como estimado")
        out.append({
            "snapshot_at": stamp,
            "id": a.get("id", ""), "slug": a.get("slug", ""), "nome": a.get("nome", ""),
            "canonical_name": tax.get("canonical_name", ""), "titulo_chamativo": a.get("titulo_chamativo", ""),
            "plataforma": wrapper.get("plataforma_nome") or "", "fonte": a.get("fonte", ""),
            "categoria": wrapper.get("categoria_nome") or "", "subcategoria": wrapper.get("subcategoria_nome") or "",
            "catalog_role": tax.get("catalog_role", "conceito de audiência"), "market_scope": tax.get("market_scope", ""),
            "primary_market": tax.get("primary_market_slug", ""), "primary_submarket": tax.get("primary_submarket", ""),
            "related_markets": _json(wrapper.get("related_markets") or []),
            "b2b_b2c_orientation": tax.get("b2b_b2c_orientation", ""),
            "signal_types": _json(_list(tax.get("signal_types"))), "funnel_stages": _json(_list(tax.get("funnel_stages"))),
            "available_channels": _json(available_channels),
            "geographic_scope": _json(_list(tax.get("geographic_scope"))),
            "activation_restrictions": _json(_list(tax.get("activation_restrictions"))),
            "descricao": a.get("descricao", ""), "descricao_curta": a.get("descricao_curta", ""),
            "descricao_comercial": a.get("descricao_comercial", ""), "caso_uso_principal": a.get("caso_uso_principal", ""),
            "insights_planejamento": a.get("insights_planejamento", ""),
            "diferenciais_competitivos": a.get("diferenciais_competitivos", ""),
            "perfil_socioeconomico": a.get("perfil_socioeconomico", ""), "tags": _json(_list(a.get("tags"))),
            "momentos_chave": _json(_list(a.get("momentos_chave"))),
            "interesses_correlatos": _json(_list(a.get("interesses_correlatos"))),
            "publico_estimado": a.get("publico_estimado", ""), "publico_numero": a.get("publico_numero", ""),
            "tamanho": a.get("tamanho", ""), "demografia": _json(demografia), "dispositivos": _json(dispositivos),
            "propensao_compra": a.get("propensao_compra", ""), "sazonalidade": a.get("sazonalidade", ""),
            "curation_status": tax.get("curation_status", "unclassified"),
            "classification_confidence": tax.get("classification_confidence", ""),
            "data_quality_status": tax.get("data_quality_status", "unverified"), "data_origin": tax.get("data_origin", ""),
            "source_reference": tax.get("source_reference", ""), "source_observed_at": tax.get("source_observed_at", ""),
            "data_valid_until": tax.get("data_valid_until", ""), "methodology_note": tax.get("methodology_note", ""),
            "is_estimated": tax.get("is_estimated", ""),
            "verification_candidate": not verification_gaps,
            "verification_gaps": _json(verification_gaps),
            "measurements": _json(wrapper.get("measurements") or []),
        })
    return out


def _norm(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _match_channel(value, channel):
    needle = _norm(value)
    exact = {_norm(channel.get("slug")), _norm(channel.get("nome")), _norm(channel.get("tipo"))}
    candidates = {_norm(channel.get("slug")), _norm(channel.get("nome"))}
    aliases = {
        "experian portal": {"serasa", "serasa experian"},
        "g1": {"g1 globo com", "globo com"},
        "spotify": {"spotify ads"},
        "prime video": {"amazon prime video"},
    }
    for key in tuple(candidates):
        candidates.update(aliases.get(key, set()))
    return bool(needle and (needle in exact or any(
        (len(candidate) > 2 and candidate in needle) or (len(needle) > 2 and needle in candidate)
        for candidate in candidates if candidate
    )))


def _channel_rows(channels, audiences, stamp):
    out = []
    for channel in channels:
        matches = []
        for audience in audiences:
            linked = _list(audience.get("available_channels"))
            linked.append(audience.get("plataforma") or audience.get("fonte"))
            if any(_match_channel(value, channel) for value in linked):
                matches.append(audience)
        out.append({
            "snapshot_at": stamp, "slug": channel.get("slug", ""), "nome": channel.get("nome", ""),
            "categoria": channel.get("categoria", ""), "tipo": channel.get("tipo", ""),
            "alcance": channel.get("alcance", ""), "viewability": channel.get("viewability", ""),
            "investimento_minimo": channel.get("investimento_minimo", ""), "descricao": channel.get("descricao", ""),
            "segmentacoes": _json(channel.get("segmentacoes") or []), "diferenciais": _json(channel.get("diferenciais") or []),
            "audience_slugs": _json([item.get("slug") for item in matches if item.get("slug")]),
            "audience_names": _json([item.get("nome") for item in matches if item.get("nome")]),
            "audience_count": len(matches),
        })
    return out


def _format_rows(channels, stamp):
    rows = []
    for channel in channels:
        for fmt in channel.get("formatos") or []:
            item = fmt if isinstance(fmt, dict) else {"nome": str(fmt)}
            rows.append({
                "snapshot_at": stamp, "source": "channel_catalog", "channel_slug": channel.get("slug", ""),
                "channel_name": channel.get("nome", ""), "channel_type": channel.get("tipo", ""),
                "format_key": item.get("chave", ""), "name": item.get("nome", ""), "label": item.get("label", ""),
                "width": item.get("w", ""), "height": item.get("h", ""), "duration": item.get("duracao", ""),
                "family": "", "kind": "", "best_for": item.get("melhor_para", ""),
                "devices": _json(item.get("dispositivos") or []), "channels": _json([channel.get("tipo") or channel.get("slug")]),
                "placement_zones": "[]", "viewer_types": "[]", "required_elements": "[]",
                "optional_elements": "[]", "forbidden_elements": "[]", "safe_areas": "{}", "aliases": "[]",
                "commercial_notes": _json({key: item.get(key) for key in ("taxa", "tempo", "extra") if item.get(key)}),
            })
    for fmt in FORMATS:
        rows.append({
            "snapshot_at": stamp, "source": "creative_registry", "channel_slug": "", "channel_name": "",
            "channel_type": "", "format_key": fmt.get("format_key", ""), "name": fmt.get("label", ""),
            "label": fmt.get("label", ""), "width": fmt.get("width", ""), "height": fmt.get("height", ""),
            "duration": fmt.get("duration", ""), "family": fmt.get("family", ""), "kind": fmt.get("kind", ""),
            "best_for": "", "devices": _json(fmt.get("devices") or []), "channels": _json(fmt.get("channels") or []),
            "placement_zones": _json(fmt.get("placement_zones") or []), "viewer_types": _json(fmt.get("viewer_types") or []),
            "required_elements": _json(fmt.get("required_elements") or []),
            "optional_elements": _json(fmt.get("optional_elements") or []),
            "forbidden_elements": _json(fmt.get("forbidden_elements") or []), "safe_areas": _json(fmt.get("safe_areas") or {}),
            "aliases": _json(fmt.get("aliases") or []), "commercial_notes": "{}",
        })
    return rows


def _write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def export(*, offline_audiences: Optional[Path] = None):
    app = create_app()
    with app.app_context():
        channels = listar_canais()
        raw_audiences = _audiences_from_snapshot(offline_audiences) if offline_audiences else _audiences_from_db()
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    audiences = _audience_rows(raw_audiences, stamp)
    datasets = {
        "channels.csv": (CHANNEL_FIELDS, _channel_rows(channels, audiences, stamp)),
        "audiences.csv": (AUDIENCE_FIELDS, audiences),
        "formats.csv": (FORMAT_FIELDS, _format_rows(channels, stamp)),
    }
    for name, (fields, rows) in datasets.items():
        primary = DESTINATIONS[name][0] / name
        _write(primary, fields, rows)
        for destination in DESTINATIONS[name][1:]:
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(primary, destination / name)
    return {name: len(rows) for name, (_, rows) in datasets.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-audiences", type=Path, help="Snapshot CSV usado somente quando o banco não está acessível.")
    args = parser.parse_args()
    counts = export(offline_audiences=args.offline_audiences)
    print(" · ".join(f"{name}: {count}" for name, count in counts.items()))
