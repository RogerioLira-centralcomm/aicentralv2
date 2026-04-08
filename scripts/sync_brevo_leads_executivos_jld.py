#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincroniza no Brevo os e-mails de leads (cadu_leads) e de contatos de lead (cadu_lead_contatos)
cuja carteira é João, Luísa ou Demétrius (cadu_leads.id_executivo → nome do executivo).

Mesmo fluxo da API: contato na lista "[Executivo] - Leads" e removido da lista 21 (usuários ativos).

- Idempotente: pode rodar várias vezes (updateEnabled no Brevo).
- BREVO_API_KEY: variável de ambiente ou linha no .env na raiz (UTF-8/BOM, aspas).

Uso (raiz do repo):
  python scripts/sync_brevo_leads_executivos_jld.py
  python scripts/sync_brevo_leads_executivos_jld.py --dry-run
  python scripts/sync_brevo_leads_executivos_jld.py --sleep 0.1
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


# E-mail do próprio lead + e-mails de cadu_lead_contatos (carteira = id_executivo)
SQL_LEADS_FONTES = """
    SELECT * FROM (
        SELECT
            LOWER(TRIM(l.email)) AS email_norm,
            TRIM(l.email) AS email,
            TRIM(COALESCE(l.nome, '')) AS nome,
            TRIM(COALESCE(l.telefone, '')) AS telefone,
            TRIM(COALESCE(l.empresa, '')) AS empresa,
            vend.nome_completo AS executivo_nome,
            'lead' AS origem,
            l.id::text AS origem_ref
        FROM cadu_leads l
        INNER JOIN tbl_contato_cliente vend ON l.id_executivo = vend.id_contato_cliente
        WHERE l.email IS NOT NULL
          AND TRIM(l.email) <> ''
          AND l.id_executivo IS NOT NULL
          AND vend.nome_completo IS NOT NULL
          AND TRIM(vend.nome_completo) <> ''

        UNION ALL

        SELECT
            LOWER(TRIM(lc.email)) AS email_norm,
            TRIM(lc.email) AS email,
            TRIM(COALESCE(lc.nome, '')) AS nome,
            TRIM(COALESCE(lc.telefone, '')) AS telefone,
            TRIM(COALESCE(l.empresa, '')) AS empresa,
            vend.nome_completo AS executivo_nome,
            'lead_contato' AS origem,
            lc.id::text AS origem_ref
        FROM cadu_lead_contatos lc
        INNER JOIN cadu_leads l ON lc.id_lead = l.id
        INNER JOIN tbl_contato_cliente vend ON l.id_executivo = vend.id_contato_cliente
        WHERE lc.email IS NOT NULL
          AND TRIM(lc.email) <> ''
          AND l.id_executivo IS NOT NULL
          AND vend.nome_completo IS NOT NULL
          AND TRIM(vend.nome_completo) <> ''
    ) AS u
    ORDER BY email_norm, origem, origem_ref
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza leads J/L/D no Brevo (segmento Leads).")
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
            cur.execute(SQL_LEADS_FONTES)
            rows = cur.fetchall()

    filtrados_exec = []
    for row in rows:
        chave = brevo_primeiro_nome_normalizado(row.get("executivo_nome"))
        if chave in CHAVES_EXECUTIVOS_ALVO:
            filtrados_exec.append(row)

    # Um registro por e-mail (primeira linha na ordenação vence)
    por_email = {}
    for row in filtrados_exec:
        k = row["email_norm"]
        if k not in por_email:
            por_email[k] = row
    alvo = list(por_email.values())

    print(f"Linhas brutas (lead + contatos com executivo e e-mail): {len(rows)}")
    print(f"Após filtro João / Luísa / Demétrius: {len(filtrados_exec)}")
    print(f"E-mails únicos a sincronizar: {len(alvo)}")

    if args.dry_run:
        for r in alvo[:25]:
            print(
                f"  [dry-run] email={r['email']} nome={r['nome']!r} "
                f"exec={r['executivo_nome']!r} origem={r['origem']}/{r['origem_ref']}"
            )
        if len(alvo) > 25:
            print(f"  ... e mais {len(alvo) - 25} e-mails.")
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
        nome = (row.get("nome") or "").strip()
        empresa = (row.get("empresa") or "").strip()
        exec_nome = (row.get("executivo_nome") or "").strip()
        tel = (row.get("telefone") or "").strip()

        try:
            res = brevo_sincronizar_contato_lista_executivo(
                email=email,
                nome=nome or None,
                segmento="leads",
                nome_executivo=exec_nome,
                api_key=brevo_key,
                atributos={
                    "NOME": nome,
                    "EMPRESA": empresa,
                    "TELEFONE": tel,
                },
            )
            if res.get("success"):
                ok += 1
            else:
                fail += 1
                print(f"FALHA email={email}: {res.get('error', res)}")
        except Exception as e:
            fail += 1
            print(f"ERRO email={email}: {e}")

        if args.sleep > 0 and i < len(alvo):
            time.sleep(args.sleep)

        if i % 50 == 0:
            print(f"Progresso: {i}/{len(alvo)} (ok={ok}, falha={fail})")

    print(f"Concluído: sucesso={ok}, falha={fail}, total={len(alvo)}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
