#!/usr/bin/env python3
"""Exporta o catálogo de canais da CentralX para a referência da skill."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app  # noqa: E402
from aicentralv2.crm_v3_canais import listar_canais  # noqa: E402


OUTPUT = Path(__file__).resolve().parents[1] / "references" / "channels.csv"
FIELDS = (
    "snapshot_at", "slug", "nome", "categoria", "tipo", "alcance",
    "viewability", "investimento_minimo", "descricao", "formatos",
    "segmentacoes", "diferenciais",
)


def export(output: Path = OUTPUT) -> int:
    app = create_app()
    with app.app_context():
        channels = listar_canais()
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for channel in channels:
            writer.writerow({
                "snapshot_at": stamp,
                "slug": channel.get("slug", ""),
                "nome": channel.get("nome", ""),
                "categoria": channel.get("categoria", ""),
                "tipo": channel.get("tipo", ""),
                "alcance": channel.get("alcance", ""),
                "viewability": channel.get("viewability", ""),
                "investimento_minimo": channel.get("investimento_minimo", ""),
                "descricao": channel.get("descricao", ""),
                "formatos": json.dumps(channel.get("formatos") or [], ensure_ascii=False, separators=(",", ":")),
                "segmentacoes": json.dumps(channel.get("segmentacoes") or [], ensure_ascii=False, separators=(",", ":")),
                "diferenciais": json.dumps(channel.get("diferenciais") or [], ensure_ascii=False, separators=(",", ":")),
            })
    return len(channels)


if __name__ == "__main__":
    count = export()
    print(f"Exportados {count} canais para {OUTPUT}")
