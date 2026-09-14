"""Estimativas determinísticas — o LLM não calcula volume."""

from __future__ import annotations

from .helpers import as_dict, as_list, text
from .pace import format_money


def calculate_estimates(snapshot: dict) -> dict:
    params = as_dict((snapshot or {}).get("media_params"))
    mix = as_list((snapshot or {}).get("mix"))
    channels = []
    available = False
    for item in mix:
        channel = as_dict(item)
        key = text(channel.get("id"))
        spec = as_dict(params.get(key) or params.get("default"))
        amount = _number(channel.get("amount"))
        row = {
            "id": key,
            "label": text(channel.get("label") or key),
            "amount": amount,
            "amount_label": channel.get("amount_label") or format_money(int(amount or 0)),
            "status": "not_available",
            "scenarios": [],
        }
        if amount and (spec.get("cpm") or spec.get("cpc")):
            row["scenarios"] = _channel_scenarios(amount, spec)
            row["status"] = "system_calculated"
            available = True
        channels.append(row)
    missing = []
    if not available:
        missing = ["CPM por canal", "frequência esperada", "CPC ou CTR", "taxa de conversão, quando aplicável"]
    return {
        "status": "available" if available else "not_available",
        "channels": channels,
        "assumptions": [text(item) for item in as_list(params.get("assumptions")) if text(item)],
        "warnings": [] if available else [
            "Estimativa ainda não disponível. Informe ou aprove CPM, frequência, CPC/CTR ou conversão."
        ],
        "missing": missing,
    }


def _channel_scenarios(amount: float, spec: dict) -> list[dict]:
    cpm = _number(spec.get("cpm"))
    freq = _number(spec.get("frequency") or spec.get("frequencia")) or 3
    cpc = _number(spec.get("cpc"))
    conv = _number(spec.get("conversion_rate") or spec.get("conversao"))
    rows = []
    if cpm:
        for name, cpm_factor, freq_factor in (
            ("conservador", 1.15, 1.1),
            ("referencia", 1.0, 1.0),
            ("potencial", 0.85, 0.9),
        ):
            used_cpm = cpm * cpm_factor
            used_freq = max(1.0, freq * freq_factor)
            impressions = (amount / used_cpm) * 1000
            reach = impressions / used_freq
            rows.append({
                "scenario": name,
                "cpm": round(used_cpm, 2),
                "frequency": round(used_freq, 2),
                "impressions": int(impressions),
                "reach": int(reach),
                "origin": "system_calculated",
            })
    if cpc:
        clicks = amount / cpc
        conversions = clicks * conv if conv else None
        rows.append({
            "scenario": "performance",
            "cpc": cpc,
            "clicks": int(clicks),
            "conversions": int(conversions) if conversions is not None else None,
            "cpa": round(amount / conversions, 2) if conversions else None,
            "origin": "system_calculated",
        })
    return rows


def format_estimates_for_prompt(estimates: dict) -> str:
    data = as_dict(estimates)
    if data.get("status") != "available":
        missing = ", ".join(as_list(data.get("missing")) or ["CPM", "frequência", "CPC"])
        return (
            "Estimativa ainda não disponível.\n"
            "Para calcular alcance e acessos, informe ou aprove: " + missing + "."
        )
    lines = ["Estimativas calculadas em Python (não recalcule):"]
    for channel in as_list(data.get("channels")):
        item = as_dict(channel)
        if item.get("status") != "system_calculated":
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
                lines.append(f"  performance: {row.get('clicks')} cliques (CPC {row.get('cpc')})")
    return "\n".join(lines)


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
