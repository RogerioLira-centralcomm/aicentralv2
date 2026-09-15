#!/usr/bin/env python3
"""Adiciona o esqueleto comercial e demográfico da ficha de planejamento.

Os perfis são hipóteses de planejamento. Não substituem fonte de mobilidade,
IBGE ou dado de renda: esses campos ficam marcados como ``to_validate``.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

PROFILES = {
    "aeroporto": {
        "audience": ["Viajantes a lazer e a trabalho", "Acompanhantes e embarque", "Entorno de acesso"],
        "objective": "Cobertura de viagem com continuidade até o celular.",
        "channels": ["Display em apps", "Vídeo vertical", "Portais de viagem", "Retargeting de 7 e 15 dias"],
        "models": ["Alcance", "Consideração", "Recorrência"],
        "weekly": [62, 70, 77, 80, 83, 100, 74],
    },
    "shopping": {
        "audience": ["Consumidores de varejo e serviços", "Famílias e lazer", "Entorno qualificado"],
        "objective": "Presença de marca antes, durante e depois da visita.",
        "channels": ["Display em apps", "Vídeo vertical", "Portais locais", "Retargeting de 7 e 15 dias"],
        "models": ["Alcance", "Tráfego", "Recorrência"],
        "weekly": [86, 58, 60, 64, 72, 91, 100],
    },
    "evento": {
        "audience": ["Público de lazer e cultura", "Visitantes do entorno", "Fluxo de fim de semana"],
        "objective": "Concentrar presença no dia do evento e prolongar a consideração.",
        "channels": ["Display em apps", "Vídeo vertical", "Portais locais", "Retargeting de 7 e 15 dias"],
        "models": ["Alcance", "Pico de evento", "Recorrência"],
        "weekly": [86, 52, 55, 58, 63, 82, 100],
    },
}


def connect():
    return psycopg.connect(
        host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], row_factory=dict_row,
    )


def enrich(payload: dict, place_type: str) -> dict:
    profile = PROFILES.get(place_type, PROFILES["evento"])
    payload = dict(payload or {})
    existing = list(payload.get("target_audience") or [])
    payload["target_audience"] = list(dict.fromkeys(existing + profile["audience"]))[:4]
    point = (payload.get("points") or [{}])[0]
    if point:
        point["target_audience"] = list(dict.fromkeys(list(point.get("target_audience") or []) + profile["audience"]))[:4]
    payload["planning"] = {
        "objective": profile["objective"],
        "channels": profile["channels"],
        "models": profile["models"],
        "source_status": "to_validate",
        "note": "Hipótese inicial de planejamento; validar segmentação, inventário e verba com a mesa.",
    }
    payload.setdefault("income", {"label": "", "source_status": "to_validate"})
    payload["income"].setdefault("note", "Aguardando recorte de renda com fonte declarada.")
    weekly = dict(payload.get("weekly_movement") or {})
    if not any(value is not None for value in weekly.get("values") or []):
        weekly["values"] = profile["weekly"]
        weekly["source_status"] = "to_validate"
        weekly["note"] = "Curva-base de planejamento; substituir por fonte de mobilidade antes da contratação."
    payload["weekly_movement"] = weekly
    return payload


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, place_type, payload FROM cx_places")
        rows = cur.fetchall()
        for row in rows:
            cur.execute(
                "UPDATE cx_places SET payload=%s, updated_at=now() WHERE id=%s",
                (Json(enrich(row["payload"], row["place_type"])), row["id"]),
            )
    print(f"{len(rows)} Places com planejamento e demografia pendente de fonte.")


if __name__ == "__main__":
    main()
