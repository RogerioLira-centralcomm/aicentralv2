"""Cria cadu_estrategias (se faltar) e insere as estratégias-semente que ainda não existem.

Reexecutável: compara por slug; em estratégia existente só acrescenta campos que faltam,
nunca sobrescreve o que foi editado no admin.
Uso: python migrations/run_seed_cadu_estrategias.py [--dry-run]
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from aicentralv2.estrategias import semente  # noqa: E402

COLUNAS = ("slug", "nome", "objetivo", "resumo", "verba_minima")


def main(dry_run: bool = False) -> None:
    ddl = (ROOT / "migrations" / "add_cadu_estrategias.sql").read_text(encoding="utf-8")
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            cur.execute("SELECT slug FROM cadu_estrategias")
            existentes = {r[0] for r in cur.fetchall()}
            novas = [e for e in semente.lista() if e["slug"] not in existentes]
            completadas = 0
            for ordem, e in enumerate(semente.lista(), start=1):
                dados = {k: v for k, v in e.items() if k not in COLUNAS}
                if e["slug"] in existentes:
                    # Campos novos da semente entram por baixo; o que o admin editou fica por cima.
                    cur.execute("UPDATE cadu_estrategias SET dados = %s::jsonb || dados "
                                "WHERE slug = %s AND NOT (dados ?& %s)", (Json(dados), e["slug"], list(dados)))
                    completadas += cur.rowcount
                    continue
                cur.execute(
                    "INSERT INTO cadu_estrategias (slug, nome, objetivo, resumo, verba_minima, ordem, dados) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (slug) DO NOTHING",
                    (e["slug"], e["nome"], e["objetivo"], e["resumo"], e["verba_minima"], ordem * 10, Json(dados)),
                )
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    print(f"cadu_estrategias: {len(novas)} nova(s), {len(existentes)} já existia(m), {completadas} completada(s) "
          f"com campos novos{' (dry-run, nada gravado)' if dry_run else ''}.")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
