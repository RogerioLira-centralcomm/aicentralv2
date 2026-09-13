"""Garante colunas da ficha e grava segmentações/formatos em cadu_canais."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2 import config  # noqa: E402,F401
from aicentralv2.crm_v3_canais import sincronizar_canais_db  # noqa: E402


if __name__ == "__main__":
    resultado = sincronizar_canais_db()
    print(
        f"Canais sincronizados: {resultado['updated']} atualizados, "
        f"{resultado['inserted']} inseridos"
    )
