#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backfill seguro dos campos financeiros de linhas de cotação.

Dry-run por padrão. Use --apply para gravar.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
load_dotenv()

from aicentralv2 import create_app, db  # noqa: E402
from aicentralv2.config import DevelopmentConfig, ProductionConfig  # noqa: E402


FINANCIAL_FIELDS = (
    "investimento_bruto",
    "investimento_liquido",
    "perc_margem_cc",
    "perc_tech_fee",
    "perc_com_vendas",
    "perc_pl_incentivos",
    "perc_impostos",
    "val_margem_cc",
    "val_tech_fee",
    "val_com_vendas",
    "val_pl_incentivos",
    "val_impostos",
)


def is_blank(value):
    return value is None or str(value).strip() == ""


def affected_cotacao_ids(cotacao_id=None, pi_id=None):
    if cotacao_id:
        return [cotacao_id]

    conn = db.get_db()
    with conn.cursor() as cursor:
        if pi_id:
            cursor.execute("SELECT cotacao_id FROM cadu_pi WHERE id_pi = %s", (pi_id,))
            row = cursor.fetchone()
            return [row["cotacao_id"]] if row and row.get("cotacao_id") else []

        blank_where = " OR ".join(f"{field} IS NULL" for field in FINANCIAL_FIELDS)
        cursor.execute(
            f"""
            SELECT DISTINCT cotacao_id
            FROM cadu_cotacao_linhas
            WHERE cotacao_id IS NOT NULL
              AND COALESCE(is_deleted, FALSE) = FALSE
              AND COALESCE(is_subtotal, FALSE) = FALSE
              AND COALESCE(is_header, FALSE) = FALSE
              AND ({blank_where})
            ORDER BY cotacao_id
            """
        )
        return [row["cotacao_id"] for row in cursor.fetchall()]


def financial_before(linha, updates):
    return {field: linha.get(field) for field in updates}


def build_updates(cotacao, linha, imposto_percentual):
    breakdown = db.calcular_breakdown_linha_cotacao(
        cotacao,
        linha,
        imposto_percentual=imposto_percentual,
    )
    candidates = {
        "volume_contratado": breakdown["volume_contratado"],
        "valor_unitario": breakdown["valor_unitario"],
        "valor_total": breakdown["valor_total"],
        "investimento_bruto": breakdown["investimento_bruto"],
        "valor_unitario_negociado": breakdown["valor_unitario_negociado"],
        "investimento_liquido": breakdown["investimento_liquido"],
        "perc_margem_cc": breakdown["perc_margem_cc"],
        "perc_tech_fee": breakdown["perc_tech_fee"],
        "perc_com_vendas": breakdown["perc_com_vendas"],
        "perc_pl_incentivos": breakdown["perc_pl_incentivos"],
        "perc_impostos": breakdown["perc_impostos"],
        "val_margem_cc": breakdown["val_margem_cc"],
        "val_tech_fee": breakdown["val_tech_fee"],
        "val_com_vendas": breakdown["val_com_vendas"],
        "val_pl_incentivos": breakdown["val_pl_incentivos"],
        "val_impostos": breakdown["val_impostos"],
        "fator_desconto": breakdown.get("fator_desconto"),
    }
    return {
        field: value
        for field, value in candidates.items()
        if field not in linha or is_blank(linha.get(field)) or field in {"investimento_bruto", "investimento_liquido", "valor_total"}
    }


def apply_updates(linha_id, updates):
    db.atualizar_linha_cotacao(linha_id, **updates)


def process_cotacao(cotacao_id, apply=False, imposto_percentual=15):
    cotacao = db.obter_cotacao_por_id(cotacao_id)
    if not cotacao:
        print(f"Cotacao {cotacao_id}: nao encontrada")
        return 0

    linhas = db.obter_linhas_cotacao(cotacao_id)
    changed = 0
    for linha in linhas or []:
        if linha.get("is_subtotal") or linha.get("is_header"):
            continue
        if not any(is_blank(linha.get(field)) for field in FINANCIAL_FIELDS):
            continue
        try:
            updates = build_updates(cotacao, linha, imposto_percentual)
        except Exception as err:
            print(f"Cotacao {cotacao_id} linha {linha.get('id')}: sem base suficiente ({err})")
            continue
        if not updates:
            continue
        changed += 1
        print(
            f"Cotacao {cotacao_id} linha {linha.get('id')}: "
            f"{financial_before(linha, updates)} -> {updates}"
        )
        if apply:
            apply_updates(linha["id"], updates)

    if apply and changed:
        total = db.calcular_valor_total_cotacao(cotacao_id)
        print(f"Cotacao {cotacao_id}: valor_total_proposta recalculado para {total}")
    return changed


def main():
    parser = argparse.ArgumentParser(description="Backfill de campos financeiros de cotações")
    parser.add_argument("--apply", action="store_true", help="grava as alterações no banco")
    parser.add_argument("--cotacao-id", type=int, help="limita a uma cotação")
    parser.add_argument("--pi-id", type=int, help="resolve a cotação a partir de um PI")
    parser.add_argument("--imposto-percentual", type=float, default=float(os.getenv("PI_IMPOSTO_PERCENTUAL", 15)))
    args = parser.parse_args()

    env = os.getenv("AICENTRAL_ENV") or os.getenv("FLASK_ENV") or "development"
    cfg = ProductionConfig if env.lower() == "production" else DevelopmentConfig
    app = create_app(cfg)
    with app.app_context():
        ids = affected_cotacao_ids(args.cotacao_id, args.pi_id)
        print(f"Cotacoes afetadas encontradas: {len(ids)}")
        total_changed = 0
        for cotacao_id in ids:
            total_changed += process_cotacao(
                cotacao_id,
                apply=args.apply,
                imposto_percentual=args.imposto_percentual,
            )

        if args.apply:
            print(f"OK: {total_changed} linha(s) atualizadas.")
        else:
            print(f"DRY-RUN: {total_changed} linha(s) seriam atualizadas. Use --apply para gravar.")


if __name__ == "__main__":
    main()
