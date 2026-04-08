#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincroniza no Brevo contatos de clientes cujo cliente está com executivo João, Luísa ou Demétrius
(vendas_central_comm). Lista 21 + "[Executivo] - Clientes".

- Pode rodar várias vezes: a API Brevo atualiza contato/listas (updateEnabled), sem duplicar por e-mail.
- A chave vem de BREVO_API_KEY: variável de ambiente ou linha no .env na raiz do repositório
  (lida direto do arquivo se precisar, com UTF-8 e BOM).

Uso (raiz do repo):
  python scripts/sync_brevo_contatos_clientes_executivos_jld.py
  python scripts/sync_brevo_contatos_clientes_executivos_jld.py --dry-run
  python scripts/sync_brevo_contatos_clientes_executivos_jld.py --sleep 0.1
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv(ENV_FILE)
load_dotenv()

CHAVES_EXECUTIVOS_ALVO = frozenset({"joao", "luisa", "demetrius"})

_SQL = re.compile(r"^\s*BREVO_API_KEY\s*=", re.IGNORECASE)


def _resolver_brevo_api_key() -> str:
    """Ambiente primeiro; depois parse simples do .env (aspas, BOM)."""
    raw = (os.environ.get("BREVO_API_KEY") or "").strip()
    if raw:
        return raw.strip().strip('"').strip("'")
    if not os.path.isfile(ENV_FILE):
        return ""
    try:
        with open(ENV_FILE, encoding="utf-8-sig") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if _SQL.match(line):
                    _, _, val = line.partition("=")
                    return val.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


SQL_CONTATOS = """
    SELECT
        c.id_contato_cliente,
        c.email,
        c.nome_completo,
        c.telefone,
        c.user_type,
        COALESCE(cli.nome_fantasia, cli.razao_social, '') AS empresa,
        vend.nome_completo AS executivo_nome
    FROM tbl_contato_cliente c
    INNER JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
    INNER JOIN tbl_contato_cliente vend ON cli.vendas_central_comm = vend.id_contato_cliente
    WHERE c.status = true
      AND c.email IS NOT NULL
      AND TRIM(c.email) <> ''
      AND cli.vendas_central_comm IS NOT NULL
      AND cli.vendas_central_comm > 0
      AND vend.nome_completo IS NOT NULL
      AND TRIM(vend.nome_completo) <> ''
    ORDER BY c.id_contato_cliente
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza contatos de clientes J/L/D no Brevo.")
    parser.add_argument("--dry-run", action="store_true", help="Só contagem e amostra, sem API.")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        metavar="SEC",
        help="Pausa entre chamadas (ex.: 0.1).",
    )
    args = parser.parse_args()

    if os.path.isfile(ENV_FILE):
        load_dotenv(ENV_FILE, override=True)

    from aicentralv2 import create_app
    from aicentralv2.db import get_db
    from aicentralv2.services.brevo_service import (
        brevo_primeiro_nome_normalizado,
        brevo_sincronizar_contato_lista_executivo,
    )

    app = create_app()

    with app.app_context():
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(SQL_CONTATOS)
            rows = cur.fetchall()

    alvo = []
    for row in rows:
        chave = brevo_primeiro_nome_normalizado(row.get("executivo_nome"))
        if chave in CHAVES_EXECUTIVOS_ALVO:
            alvo.append(row)

    print(f"Total de contatos ativos com cliente vinculado a executivo: {len(rows)}")
    print(f"Filtrados (João / Luísa / Demétrius pelo pré-nome): {len(alvo)}")

    if args.dry_run:
        for r in alvo[:20]:
            print(
                f"  [dry-run] id={r['id_contato_cliente']} email={r['email']} "
                f"exec={r['executivo_nome']!r}"
            )
        if len(alvo) > 20:
            print(f"  ... e mais {len(alvo) - 20} registros.")
        return 0

    brevo_key = _resolver_brevo_api_key()
    if not brevo_key:
        print(
            "ERRO: BREVO_API_KEY não encontrada. "
            f"Defina no .env em {ENV_FILE} ou na variável de ambiente."
        )
        return 1

    ok = 0
    fail = 0
    for i, row in enumerate(alvo, 1):
        email = (row.get("email") or "").strip().lower()
        nome = (row.get("nome_completo") or "").strip()
        empresa = (row.get("empresa") or "").strip()
        exec_nome = (row.get("executivo_nome") or "").strip()
        ut = row.get("user_type") or "client"
        tel = (row.get("telefone") or "").strip()

        try:
            res = brevo_sincronizar_contato_lista_executivo(
                email=email,
                nome=nome or None,
                segmento="clientes",
                nome_executivo=exec_nome,
                api_key=brevo_key,
                atributos={
                    "NOME": nome,
                    "EMPRESA": empresa,
                    "TELEFONE": tel,
                    "TIPO_USUARIO": ut,
                },
            )
            if res.get("success"):
                ok += 1
            else:
                fail += 1
                print(
                    f"FALHA id={row['id_contato_cliente']} email={email}: {res.get('error', res)}"
                )
        except Exception as e:
            fail += 1
            print(f"ERRO id={row['id_contato_cliente']} email={email}: {e}")

        if args.sleep > 0 and i < len(alvo):
            time.sleep(args.sleep)

        if i % 50 == 0:
            print(f"Progresso: {i}/{len(alvo)} (ok={ok}, falha={fail})")

    print(f"Concluído: sucesso={ok}, falha={fail}, total={len(alvo)}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
