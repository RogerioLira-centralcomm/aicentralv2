#!/usr/bin/env python3
"""
Cria pastas de teste no SERVIDOR Linux (via SSH), como o app fará em produção.

Requisitos no .env do dev:
  PI_UPLOAD_ROOT=/var/www/aicentralv2/instance/uploads/pi
  PI_UPLOAD_REMOTE_SSH=usuario@servidor   (chave SSH sem senha interativa)

Uso:
  python scripts/criar_pasta_pi_dev_servidor.py
  python scripts/criar_pasta_pi_dev_servidor.py --codigo PI_DEV_SERVIDOR --id-pi 999998
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from aicentralv2 import create_app
    from aicentralv2.config import DevelopmentConfig
    from aicentralv2.services import pi_storage_ssh
    from aicentralv2.services.pi_local_storage import (
        PiLocalStorageError,
        gerar_pastas_local_pi,
        listar_arquivos_secao,
        pi_storage_dir_posix,
        salvar_upload,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--codigo", default="PI_DEV_SERVIDOR")
    parser.add_argument("--id-pi", type=int, default=999998)
    args = parser.parse_args()

    if not pi_storage_ssh.remote_storage_enabled():
        print(
            "ERRO: configure no .env do dev:\n"
            "  PI_UPLOAD_ROOT=/var/www/aicentralv2/instance/uploads/pi\n"
            "  PI_UPLOAD_REMOTE_SSH=usuario@ip-do-servidor\n"
            "Teste o SSH antes: ssh usuario@servidor 'ls -la /var/www/aicentralv2/instance/uploads/pi'",
            file=sys.stderr,
        )
        return 2

    app = create_app(DevelopmentConfig)
    pi = {"id_pi": args.id_pi, "codigo_pi_cc": args.codigo}

    class Buf2:
        filename = "criado-do-dev.txt"

        def save(self, dest):
            Path(dest).write_text(
                "Teste criado do dev via SSH para /var/www/.../uploads/pi\n",
                encoding="utf-8",
            )

    with app.app_context():
        try:
            with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True):
                result = gerar_pastas_local_pi(pi, strict=False)
            salvo = salvar_upload(pi, "principal", Buf2())
            lista = listar_arquivos_secao(pi, "principal")
        except PiLocalStorageError as exc:
            print(f"FALHA: {exc}", file=sys.stderr)
            return 1

    base = pi_storage_dir_posix(pi)
    print("OK — pastas criadas no SERVIDOR Linux:")
    print(f"  {base}/")
    for s in ("principal", "financeiro", "pecas", "assinados"):
        print(f"  {base}/{s}/")
    print(f"Arquivo enviado: {salvo.get('path')}")
    print(f"Listagem principal: {[x['name'] for x in lista]}")
    print(f"storage_path: {result.get('storage_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())