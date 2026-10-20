"""Estimativas de impacto: o modelo sugere as taxas, o Python calcula, o executivo revisa.

O modelo nunca calcula volume. Ele propõe CPM, CPC, CTR e frequência de referência
por canal (``suggest_media_params``); o executivo pode alterar qualquer valor e marcar a
estimativa como revisada; ``calculate_estimates`` transforma verba e taxas em impressões,
alcance e cliques. Cada número carrega a origem: estimativa do modelo ou valor do executivo.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..cadu_planner.benchmarks import impressions as _impressions, reach as _reach
from .catalog import CHANNEL_CATALOG
from .helpers import as_dict, as_list, text
from .pace import format_money

# Taxas aceitas por parâmetro; fora disso o valor é descartado (digitação ou resposta absurda).
RATE_LIMITS = {
    "cpm": (1.0, 400.0),
    "cpc": (0.05, 60.0),
    "ctr": (0.02, 10.0),
    "frequencia": (1.0, 15.0),
    "conversao": (0.05, 40.0),
}
RATE_LABELS = {"cpm": "CPM", "cpc": "CPC", "ctr": "CTR", "frequencia": "Frequência", "conversao": "Conversão"}

# Indicador que o cliente costuma sugerir: rótulo, unidade e sentido (custo: menor é melhor).
INDICATORS = {
    "cpm": {"label": "CPM", "unit": "brl", "kind": "cost"},
    "cpc": {"label": "CPC", "unit": "brl", "kind": "cost"},
    "cpv": {"label": "CPV", "unit": "brl", "kind": "cost"},
    "cpa": {"label": "CPA", "unit": "brl", "kind": "cost"},
    "ctr": {"label": "CTR", "unit": "pct", "kind": "volume"},
    "impressoes": {"label": "Impressões", "unit": "count", "kind": "volume"},
    "alcance": {"label": "Alcance", "unit": "count", "kind": "volume"},
    "cliques": {"label": "Cliques", "unit": "count", "kind": "volume"},
    "visitas": {"label": "Visitas ao site", "unit": "count", "kind": "volume"},
}
# O modelo não sugere taxas para OOH e Places (rede e operação vêm depois); valores
# informados pelo executivo para eles continuam valendo.
SKIP_GROUPS = {"ooh", "places"}

ORIGIN_MODEL = "modelo"
ORIGIN_EXECUTIVE = "executivo"

SUGGEST_PROMPT = """Você é analista de mídia digital no Brasil. Estime taxas de referência para cada canal de uma campanha.
Essas taxas alimentam uma estimativa de impacto que o executivo vai revisar, por isso devem ser realistas e prudentes.

Para cada canal devolva, em reais e em percentual:
- cpm: custo por mil impressões (R$)
- cpc: custo por clique (R$)
- ctr: taxa de cliques (%)
- frequencia: impressões por pessoa no período
- conversao: taxa de conversão do clique (%), só se o objetivo pedir leads ou vendas; senão null
- racional: uma frase curta com o motivo (formato, público, praça, objetivo)

Regras:
- Use o formato e a tática do canal: interativos em portais têm CPM maior e CTR maior que display comum; remarketing e DCO têm CTR mais alto e CPM maior por audiência qualificada; vídeo e CTV têm CPM maior e CTR menor.
- O recorte de classes AB e as praças de capital encarecem o CPM; considere isso quando vier no contexto.
- Não invente dados do anunciante. Sem base melhor, dê o valor típico de mercado e marque confianca baixa.
- Não estime OOH nem Places.
- Responda apenas JSON: {"canais": {"<id>": {"cpm": 0, "cpc": 0, "ctr": 0, "frequencia": 0, "conversao": null, "racional": "", "confianca": "alta|media|baixa"}}, "premissas": [""]}
"""


def _number(value) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace("R$", "").replace("%", "").replace(" ", "")
    raw = raw.replace(".", "").replace(",", ".") if raw.count(",") == 1 and raw.count(".") > 1 else raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def estimable(channel_id: str) -> bool:
    return (CHANNEL_CATALOG.get(channel_id) or {}).get("group") not in SKIP_GROUPS


def normalize_rates(raw) -> dict:
    """Taxas de um canal dentro dos limites; o que não passa sai em vez de virar número falso."""
    row = as_dict(raw)
    out: dict = {}
    for key, (low, high) in RATE_LIMITS.items():
        source = row.get(key)
        if key == "frequencia" and source in (None, ""):
            source = row.get("frequency")
        if key == "conversao" and source in (None, ""):
            source = row.get("conversion_rate")
        value = _number(source)
        if low <= value <= high:
            out[key] = round(value, 2)
    if text(row.get("racional")):
        out["racional"] = text(row.get("racional"))[:220]
    if text(row.get("confianca")).lower() in {"alta", "media", "baixa"}:
        out["confianca"] = text(row.get("confianca")).lower()
    # Valor sem origem foi digitado por alguém; só o que o modelo sugeriu vem marcado como "modelo".
    out["origem"] = ORIGIN_MODEL if text(row.get("origem")).lower() == ORIGIN_MODEL else ORIGIN_EXECUTIVE
    return out


def normalize_indicator(raw) -> dict:
    row = as_dict(raw)
    metric = text(row.get("metrica") or row.get("metric")).lower().replace("í", "i").replace("ç", "c").replace("õ", "o")
    if metric not in INDICATORS:
        return {}
    meta = _number(row.get("meta") if "meta" in row else row.get("target"))
    return {
        "metrica": metric,
        "meta": round(meta, 2) if meta > 0 else None,
        "origem": text(row.get("origem")) or "cliente",
    }


def normalize_media_params(raw, channel_ids=None) -> dict:
    """Estrutura canônica de ``media_params``. Aceita o formato antigo (taxas soltas por canal)."""
    data = as_dict(raw)
    channels_in = as_dict(data.get("canais")) or {
        key: value for key, value in data.items()
        if isinstance(value, dict) and (key == "default" or key in CHANNEL_CATALOG)
    }
    wanted = [text(key) for key in as_list(channel_ids)] if channel_ids is not None else list(channels_in)
    channels = {}
    for key in wanted:
        if key == "default":
            continue
        rates = normalize_rates(channels_in.get(key) or channels_in.get("default"))
        if any(name in rates for name in RATE_LIMITS):
            channels[key] = rates
    return {
        "canais": channels,
        "indicador": normalize_indicator(data.get("indicador")),
        "origem": ORIGIN_EXECUTIVE if text(data.get("origem")).lower() == ORIGIN_EXECUTIVE else ORIGIN_MODEL,
        "revisado": bool(data.get("revisado")) and bool(channels),
        "revisado_em": text(data.get("revisado_em")),
        "gerado_em": text(data.get("gerado_em")),
        "premissas": [text(item)[:200] for item in as_list(data.get("premissas")) if text(item)][:6],
        "chave": text(data.get("chave")),
    }


def params_key(snapshot: dict) -> str:
    """O que a sugestão do modelo leva em conta: canais, objetivo, praça, público e táticas."""
    import hashlib
    import json

    snap = as_dict(snapshot)
    payload = {
        "canais": [text(as_dict(row).get("id")) for row in as_list(snap.get("mix")) if estimable(text(as_dict(row).get("id")))],
        "objetivo": text(as_dict(snap.get("objective")).get("id")),
        "praca": as_dict(snap.get("geography")),
        "publico": as_list(snap.get("audiences")),
        "taticas": [(text(as_dict(t).get("tipo")), text(as_dict(t).get("segmento"))) for t in as_list(snap.get("taticas"))],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]


def suggest_media_params(snapshot: dict, existing=None, *, force: bool = False) -> dict:
    """Pede ao modelo as taxas dos canais que ainda não têm valor. Valores do executivo nunca são trocados."""
    from .ai import chat_json

    snap = as_dict(snapshot)
    rows = [as_dict(row) for row in as_list(snap.get("mix")) if estimable(text(as_dict(row).get("id")))]
    ids = [text(row.get("id")) for row in rows]
    current = normalize_media_params(existing, ids)
    keep = {
        key: value for key, value in current["canais"].items()
        if value.get("origem") == ORIGIN_EXECUTIVE or (not force and key in current["canais"])
    }
    missing = [row for row in rows if text(row.get("id")) not in keep]
    if not missing:
        return {**current, "canais": keep}
    context = {
        "objetivo": text(as_dict(snap.get("objective")).get("label") or as_dict(snap.get("objective")).get("id")),
        "praca": text(as_dict(snap.get("geography")).get("praca")) + " " + text(as_dict(snap.get("geography")).get("detail")),
        "publico": as_list(snap.get("audiences")),
        "periodo": text(as_dict(snap.get("period")).get("raw")),
        "kpis": as_list(snap.get("kpis")),
        "indicador_do_cliente": current["indicador"] or as_dict(snap.get("indicador_cliente")),
        "taticas": [
            {"tipo": text(as_dict(t).get("tipo")), "canais": as_list(as_dict(t).get("canais")),
             "formatos": as_list(as_dict(t).get("formatos")), "recorte_de_portais": text(as_dict(t).get("segmento"))}
            for t in as_list(snap.get("taticas"))
        ],
        "canais": [
            {"id": text(row.get("id")), "nome": text(row.get("label")), "grupo": text((CHANNEL_CATALOG.get(text(row.get("id"))) or {}).get("group")),
             "descricao": text(row.get("desc")), "tatica": text(row.get("tatica")), "percentual": row.get("pct")}
            for row in missing
        ],
    }
    import json

    parsed = as_dict(chat_json(
        SUGGEST_PROMPT,
        "Contexto da campanha:\n" + json.dumps(context, ensure_ascii=False, default=str),
        role="extract",
        max_tokens=2500,
    ))
    suggested = {}
    for key, value in as_dict(parsed.get("canais")).items():
        if text(key) in {text(row.get("id")) for row in missing}:
            rates = normalize_rates({**as_dict(value), "origem": ORIGIN_MODEL})
            if rates.get("cpm") and rates.get("ctr"):
                # CPC = CPM / (CTR x 10): as três taxas só fecham entre si se o CPC vier das outras duas.
                derived = round(rates["cpm"] / (rates["ctr"] * 10), 2)
                if RATE_LIMITS["cpc"][0] <= derived <= RATE_LIMITS["cpc"][1]:
                    rates["cpc"] = derived
            if any(name in rates for name in RATE_LIMITS):
                suggested[text(key)] = rates
    return {
        "canais": {**keep, **suggested},
        "indicador": current["indicador"],
        "origem": ORIGIN_MODEL if not keep else current["origem"],
        "revisado": False,
        "revisado_em": "",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "premissas": [text(item)[:200] for item in as_list(parsed.get("premissas")) if text(item)][:6],
        "chave": params_key(snap),
    }


def _spec(params: dict, key: str) -> dict:
    channels = as_dict(params.get("canais"))
    return as_dict(channels.get(key) or channels.get("default") or params.get(key) or params.get("default"))


def calculate_estimates(snapshot: dict) -> dict:
    snap = as_dict(snapshot)
    params = as_dict(snap.get("media_params"))
    mix = as_list(snap.get("mix"))
    channels = []
    available = False
    for item in mix:
        channel = as_dict(item)
        key = text(channel.get("id"))
        spec = normalize_rates(_spec(params, key))
        amount = _number(channel.get("amount"))
        row = {
            "id": key,
            "label": text(channel.get("label") or key),
            "amount": amount,
            "amount_label": channel.get("amount_label") or format_money(int(amount or 0)),
            "status": "not_available",
            "scenarios": [],
            "rates": {name: spec[name] for name in RATE_LIMITS if name in spec},
            "origem": spec.get("origem", ""),
            "racional": spec.get("racional", ""),
        }
        if amount and (spec.get("cpm") or spec.get("cpc")):
            row["scenarios"] = _channel_scenarios(amount, spec)
            row["status"] = "executive_reviewed" if spec.get("origem") == ORIGIN_EXECUTIVE else "model_estimate"
            available = True
        channels.append(row)
    ready = [row for row in channels if row["status"] != "not_available"]
    totals = _totals(ready)
    reviewed = bool(params.get("revisado"))
    indicator = _indicator(normalize_indicator(params.get("indicador") or snap.get("indicador_cliente")), ready, totals)
    missing = []
    if not available:
        missing = ["CPM por canal", "frequência esperada", "CPC ou CTR", "taxa de conversão, quando aplicável"]
    return {
        "status": "available" if available else "not_available",
        "origin": "executive_reviewed" if (available and reviewed) else ("model_estimate" if available else ""),
        "reviewed": reviewed and available,
        "reviewed_at": text(params.get("revisado_em")),
        "channels": channels,
        "totals": totals,
        "indicator": indicator,
        "assumptions": [text(item) for item in as_list(params.get("premissas") or params.get("assumptions")) if text(item)],
        "warnings": [] if available else [
            "Estimativa ainda não disponível. Gere com o modelo ou informe CPM, frequência, CPC/CTR ou conversão."
        ],
        "missing": missing,
    }


def _channel_scenarios(amount: float, spec: dict) -> list[dict]:
    cpm = _number(spec.get("cpm"))
    freq = _number(spec.get("frequencia") or spec.get("frequency")) or 3
    cpc = _number(spec.get("cpc"))
    ctr = _number(spec.get("ctr"))
    conv = _number(spec.get("conversao") or spec.get("conversion_rate"))
    rows = []
    if cpm:
        for name, cpm_factor, freq_factor in (
            ("conservador", 1.15, 1.1),
            ("referencia", 1.0, 1.0),
            ("potencial", 0.85, 0.9),
        ):
            used_cpm = cpm * cpm_factor
            used_freq = max(1.0, freq * freq_factor)
            impressions = _impressions(amount, used_cpm)
            reach = _reach(impressions, used_freq)
            row = {
                "scenario": name,
                "cpm": round(used_cpm, 2),
                "frequency": round(used_freq, 2),
                "impressions": int(impressions),
                "reach": int(reach),
                "origin": "system_calculated",
            }
            if ctr and not cpc:
                row["clicks"] = int(impressions * ctr / 100)
            rows.append(row)
    if cpc:
        clicks = amount / cpc
        conversions = clicks * conv / 100 if conv else None
        rows.append({
            "scenario": "performance",
            "cpc": cpc,
            "clicks": int(clicks),
            "conversions": int(conversions) if conversions is not None else None,
            "cpa": round(amount / conversions, 2) if conversions else None,
            "origin": "system_calculated",
        })
    return rows


def _reference(row: dict, scenario: str = "referencia") -> dict:
    return next((as_dict(s) for s in as_list(row.get("scenarios")) if as_dict(s).get("scenario") == scenario), {})


def _totals(ready: list[dict]) -> dict:
    """Totais que somam sem enganar: impressões e cliques somam; alcance entre canais se sobrepõe."""
    invested = sum(row["amount"] for row in ready)
    out = {"invested": int(invested), "invested_label": format_money(int(invested)), "impressions": None, "clicks": None, "reach_sum": None}
    impressions = [_reference(row).get("impressions") for row in ready]
    if any(impressions):
        out["impressions"] = int(sum(value or 0 for value in impressions))
        out["reach_sum"] = int(sum(_reference(row).get("reach") or 0 for row in ready))
    clicks = 0
    for row in ready:
        clicks += (_reference(row).get("clicks") or _reference(row, "performance").get("clicks") or 0)
    out["clicks"] = int(clicks) or None
    low = [_reference(row, "conservador").get("impressions") for row in ready]
    high = [_reference(row, "potencial").get("impressions") for row in ready]
    if any(low) and any(high):
        out["impressions_low"] = int(sum(v or 0 for v in low))
        out["impressions_high"] = int(sum(v or 0 for v in high))
    if out["impressions"] and out["clicks"]:
        out["ctr"] = round(out["clicks"] / out["impressions"] * 100, 2)
    if out["clicks"] and invested:
        out["cpc"] = round(invested / out["clicks"], 2)
    if out["impressions"] and invested:
        out["cpm"] = round(invested / out["impressions"] * 1000, 2)
    return out


def _indicator(indicator: dict, ready: list[dict], totals: dict) -> dict:
    """Compara o indicador sugerido pelo cliente com o que a estimativa entrega."""
    if not indicator:
        return {}
    metric = indicator["metrica"]
    spec = INDICATORS[metric]
    estimated = {
        "cpm": totals.get("cpm"), "cpc": totals.get("cpc"), "ctr": totals.get("ctr"),
        "impressoes": totals.get("impressions"), "alcance": totals.get("reach_sum"),
        "cliques": totals.get("clicks"), "visitas": totals.get("clicks"),
    }.get(metric)
    if metric in {"cpv", "cpa"}:
        spends = sum(row["amount"] for row in ready if _reference(row, "performance").get("conversions"))
        conv = sum(_reference(row, "performance").get("conversions") or 0 for row in ready)
        estimated = round(spends / conv, 2) if conv and metric == "cpa" else None
    target = indicator.get("meta")
    status = "sem_estimativa"
    if estimated is not None and target:
        better = estimated <= target if spec["kind"] == "cost" else estimated >= target
        status = "dentro" if better else ("acima" if spec["kind"] == "cost" else "abaixo")
    elif estimated is not None:
        status = "sem_meta"
    return {
        "metrica": metric, "rotulo": spec["label"], "unidade": spec["unit"], "tipo": spec["kind"],
        "meta": target, "estimado": estimated, "status": status, "origem": indicator.get("origem", "cliente"),
        "nota": "soma por canal; pode haver sobreposição de pessoas" if metric == "alcance" else "",
    }


def short_count(value) -> str:
    """1.250.000 -> '1,3 mi'; 24.000 -> '24 mil'."""
    number = _number(value)
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " mi"
    if number >= 1_000:
        return f"{round(number / 1_000):,}".replace(",", ".") + " mil"
    return str(int(number))


def brl(value, digits: int = 2) -> str:
    """1.5 -> 'R$ 1,50'."""
    number = _number(value)
    text_value = f"{number:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text_value}"


def public_view(estimates: dict) -> dict:
    """Estimativa pronta para a página pública: números formatados, origem e comparação com o indicador."""
    data = as_dict(estimates)
    if data.get("status") != "available":
        return {}
    rows = []
    for channel in as_list(data.get("channels")):
        item = as_dict(channel)
        if item.get("status") == "not_available":
            continue
        ref = _reference(item)
        perf = _reference(item, "performance")
        clicks = ref.get("clicks") or perf.get("clicks")
        rows.append({
            "label": text(item.get("label")),
            "invested": text(item.get("amount_label")),
            "cpm": brl(as_dict(item.get("rates")).get("cpm") or ref.get("cpm")) if (as_dict(item.get("rates")).get("cpm") or ref.get("cpm")) else "",
            "cpc": brl(perf.get("cpc") or as_dict(item.get("rates")).get("cpc")) if (perf.get("cpc") or as_dict(item.get("rates")).get("cpc")) else "",
            "impressions": short_count(ref.get("impressions")) if ref.get("impressions") else "",
            "reach": short_count(ref.get("reach")) if ref.get("reach") else "",
            "clicks": short_count(clicks) if clicks else "",
            "reviewed": item.get("status") == "executive_reviewed",
        })
    totals = as_dict(data.get("totals"))
    cards = []
    if totals.get("impressions"):
        span = ""
        if totals.get("impressions_low") and totals.get("impressions_high"):
            span = f"entre {short_count(totals['impressions_low'])} e {short_count(totals['impressions_high'])}"
        cards.append({"label": "Impressões", "value": short_count(totals["impressions"]), "note": span})
    if totals.get("clicks"):
        cards.append({"label": "Cliques", "value": short_count(totals["clicks"]), "note": f"CTR {str(totals['ctr']).replace('.', ',')}%" if totals.get("ctr") else ""})
    if totals.get("cpm"):
        cards.append({"label": "CPM médio", "value": brl(totals["cpm"]), "note": ""})
    if totals.get("cpc"):
        cards.append({"label": "CPC médio", "value": brl(totals["cpc"]), "note": ""})
    indicator = as_dict(data.get("indicator"))
    indicator_view = {}
    if indicator.get("metrica"):
        def fmt_value(value):
            if value in (None, ""):
                return ""
            if indicator.get("unidade") == "brl":
                return brl(value)
            if indicator.get("unidade") == "pct":
                return f"{str(value).replace('.', ',')}%"
            return short_count(value)

        indicator_view = {
            "label": indicator.get("rotulo"), "target": fmt_value(indicator.get("meta")), "estimated": fmt_value(indicator.get("estimado")),
            "status": indicator.get("status"), "note": text(indicator.get("nota")),
            "status_label": {"dentro": "Dentro da meta", "acima": "Acima da meta", "abaixo": "Abaixo da meta",
                             "sem_meta": "Sem meta definida", "sem_estimativa": "Sem estimativa para este indicador"}.get(indicator.get("status"), ""),
        }
    return {
        "origin": data.get("origin"),
        "origin_label": ORIGIN_LABELS.get(data.get("origin"), "Estimativa"),
        "reviewed": bool(data.get("reviewed")),
        "headline": headline(data),
        "cards": cards,
        "rows": rows,
        "indicator": indicator_view,
        "assumptions": [text(item) for item in as_list(data.get("assumptions")) if text(item)][:4],
        "reach_note": "O alcance é por canal e não soma: as mesmas pessoas podem ser impactadas por mais de um canal.",
    }


def headline(estimates: dict) -> str:
    """Uma frase para a página: origem, volume e investimento. Os detalhes ficam na seção de impacto."""
    data = as_dict(estimates)
    if data.get("status") != "available":
        return ""
    totals = as_dict(data.get("totals"))
    if not totals.get("impressions"):
        return ""
    parts = [f"cerca de {short_count(totals['impressions'])} de impressões"]
    if totals.get("clicks"):
        parts.append(f"{short_count(totals['clicks'])} de cliques")
    origin = ORIGIN_LABELS.get(data.get("origin"), "Estimativa")
    return f"{origin}: {' e '.join(parts)} com {totals.get('invested_label')} investidos."


ORIGIN_LABELS = {
    "model_estimate": "Estimativa do modelo, a validar pelo executivo",
    "executive_reviewed": "Estimativa revisada pelo executivo",
}


def format_estimates_for_prompt(estimates: dict) -> str:
    data = as_dict(estimates)
    if data.get("status") != "available":
        missing = ", ".join(as_list(data.get("missing")) or ["CPM", "frequência", "CPC"])
        return (
            "Estimativa ainda não disponível.\n"
            "Para calcular alcance e acessos, informe ou aprove: " + missing + "."
        )
    lines = [f"{ORIGIN_LABELS.get(data.get('origin'), 'Estimativa')} (calculada em Python; não recalcule):"]
    for channel in as_list(data.get("channels")):
        item = as_dict(channel)
        if item.get("status") == "not_available":
            continue
        lines.append(f"- {item.get('label')}: {item.get('amount_label')}")
        for scenario in as_list(item.get("scenarios")):
            row = as_dict(scenario)
            if row.get("impressions"):
                lines.append(
                    f"  {row.get('scenario')}: {row.get('impressions')} impr. / alcance {row.get('reach')} "
                    f"(CPM {row.get('cpm')}, freq {row.get('frequency')})"
                )
            if row.get("clicks"):
                lines.append(f"  {row.get('scenario')}: {row.get('clicks')} cliques" + (f" (CPC {row.get('cpc')})" if row.get("cpc") else ""))
    totals = as_dict(data.get("totals"))
    if totals.get("impressions"):
        lines.append(f"Total de referência: {totals['impressions']} impressões" + (f", {totals['clicks']} cliques" if totals.get("clicks") else "") + ".")
    indicator = as_dict(data.get("indicator"))
    if indicator.get("metrica"):
        lines.append(
            f"Indicador do cliente: {indicator.get('rotulo')} meta {indicator.get('meta')} · estimado {indicator.get('estimado')} · {indicator.get('status')}."
        )
    return "\n".join(lines)
