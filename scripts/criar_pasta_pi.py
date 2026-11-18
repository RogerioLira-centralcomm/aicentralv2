#!/usr/bin/env python3
"""Cria pastas locais de um PI (mesmo fluxo do botão Gerar pastas)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app, db
from aicentralv2.config import DevelopmentConfig
from aicentralv2.services.pi_make_webhooks import PiMakeWebhookError, gerar_pastas_drive_pi
from aicentralv2.services.pi_local_storage import pi_storage_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id-pi", type=int, help="ID do PI existente")
    parser.add_argument("--codigo", help="Código PI (só simulação em disco, sem gravar no banco)")
    parser.add_argument("--simular", action="store_true", help="Não usa banco; só cria pastas no disco")
    args = parser.parse_args()

    app = create_app(DevelopmentConfig)

    with app.app_context():
        if args.simular or args.codigo:
            from unittest.mock import patch

            from aicentralv2.services.pi_local_storage import gerar_pastas_local_pi

            codigo = (args.codigo or "PI_SIMULADO_DEV").strip()
            id_pi = args.id_pi if args.id_pi is not None else 888888
            pi = {"id_pi": id_pi, "codigo_pi_cc": codigo}
            with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True):
                pastas = gerar_pastas_local_pi(pi, strict=False)
            base = pi_storage_dir(pi)
            print(f"Pasta criada (simulação): {base}")
            for name in ("principal", "financeiro", "pecas", "assinados"):
                print(f"  - {base / name}")
            print("URLs (se app estiver no ar):")
            print(" ", pastas.get("googled_pi_princ"))
            return 0

        id_pi = args.id_pi
        if not id_pi:
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_pi FROM cadu_pi
                    WHERE codigo_pi_cc IS NOT NULL AND trim(codigo_pi_cc) <> ''
                      AND (googled_pi_princ IS NULL OR trim(googled_pi_princ) = '')
                    ORDER BY id_pi DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
            if not row:
                print("Nenhum PI sem pasta encontrado. Use --simular --codigo PI123456")
                return 1
            id_pi = int(row["id_pi"])

        pi = db.obter_cadu_pi_por_id(id_pi)
        if not pi:
            print(f"PI {id_pi} não encontrado")
            return 1
        if pi.get("googled_pi_princ"):
            print(f"PI {id_pi} já tem pasta: {pi['googled_pi_princ']}")
            return 1
        if not pi.get("codigo_pi_cc"):
            print("PI sem codigo_pi_cc")
            return 1

        try:
            pastas = gerar_pastas_drive_pi(pi, strict=True)
        except PiMakeWebhookError as exc:
            print(f"Erro: {exc}")
            return 1

        base = pi_storage_dir(pi)
        print(f"Pastas criadas para PI {id_pi} ({pi['codigo_pi_cc']})")
        print(f"Disco: {base}")
        print(f"Principal: {pastas.get('googled_pi_princ')}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())