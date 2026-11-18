#!/usr/bin/env python3
"""Teste rápido de pastas locais do PI (sem API / sem login).

Uso (na raiz do projeto, com venv ativo):
  python scripts/test_pi_pasta_dev.py
  python scripts/test_pi_pasta_dev.py --codigo PI999TEST --id-pi 0
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app
from aicentralv2.config import DevelopmentConfig
from aicentralv2.services.pi_local_storage import (
    gerar_pastas_local_pi,
    listar_arquivos_secao,
    pi_storage_dir,
    pi_upload_root,
    resolve_arquivo,
    salvar_upload,
)


class _FakeUpload:
    def __init__(self, name: str, data: bytes):
        self.filename = name
        self._data = data

    def save(self, dest):
        Path(dest).write_bytes(self._data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa leitura/escrita nas pastas locais do PI.")
    parser.add_argument("--codigo", default="PI_DEV_TEST", help="codigo_pi_cc de teste")
    parser.add_argument("--id-pi", type=int, default=1, help="id_pi fictício (só path no disco)")
    args = parser.parse_args()

    app = create_app(DevelopmentConfig)

    with app.app_context():
        root = pi_upload_root()
        writable = root.exists() and os.access(root, os.W_OK)
        print(f"PI_UPLOAD_ROOT efetivo: {root}")
        print(f"Existe e é gravável: {writable}")

        pi = {"id_pi": args.id_pi, "codigo_pi_cc": args.codigo}

        try:
            with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True):
                urls = gerar_pastas_local_pi(pi, strict=False)
        except Exception as exc:
            print(f"FALHA ao criar pastas: {exc}")
            return 1

        base = pi_storage_dir(pi)
        print(f"Pasta do PI: {base}")

        probe = b"teste-pi-pasta-dev\n"
        fake = _FakeUpload("acesso-dev.txt", probe)
        try:
            salvo = salvar_upload(pi, "principal", fake)
            path = resolve_arquivo(pi, "principal", salvo["name"])
            back = path.read_bytes()
        except Exception as exc:
            print(f"FALHA no upload/leitura: {exc}")
            return 1

        if back != probe:
            print("FALHA: conteúdo lido diferente do gravado.")
            return 1

        lista = listar_arquivos_secao(pi, "principal")
        print(f"Arquivos em principal/: {[x['name'] for x in lista]}")

        print("\nURLs (com app rodando e login):")
        for key in ("googled_pi_princ", "googled_pi_financ", "googled_pi_pecas", "googled_pi_arq_ass"):
            print(f"  {key}: {urls.get(key, '')}")

        print("\nOK — disco e pastas locais funcionando.")
        print("No browser: python run.py, login, abra a URL principal ou 'Gerar pastas' num PI real.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())