"""
Backfill seguro dos campos monetários de cadu_pi.

Por padrão roda em dry-run. Use --apply para gravar as alterações.
"""

import argparse
import os
from decimal import Decimal

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


load_dotenv()


MONETARY_COLUMNS = (
    "vr_bruto_pi",
    "vr_cms_agencia",
    "vr_cms_parc_com",
    "vr_liquido_pi",
    "vr_liquido_pr_pi",
    "vr_platafor_max_pi",
    "total_platafor_max_pi",
)


def get_db_config():
    return {
        "dbname": os.getenv("DB_NAME", "aicentral_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "row_factory": dict_row,
    }


def is_blank(value):
    return value is None or str(value).strip() == ""


def to_float(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def format_real_br(value):
    if value is None or value == "":
        return None
    cents = int(round(float(value) * 100))
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    reais, centavos = divmod(cents, 100)
    reais_fmt = format(reais, ",").replace(",", ".")
    return f"R$ {sign}{reais_fmt},{centavos:02d}"


def existing_value(pi, column):
    return None if is_blank(pi.get(column)) else pi.get(column)


def fetch_affected_pis(cursor, only_id=None):
    where_blank = " OR ".join(f"NULLIF(TRIM({col}), '') IS NULL" for col in MONETARY_COLUMNS)
    params = []
    where = f"({where_blank})"
    if only_id:
        where += " AND id_pi = %s"
        params.append(only_id)

    cursor.execute(
        f"""
        SELECT id_pi, cotacao_id, perc_cms_agencia, perc_cms_parc_reg,
               {", ".join(MONETARY_COLUMNS)}
        FROM cadu_pi
        WHERE {where}
        ORDER BY id_pi
        """,
        params,
    )
    return cursor.fetchall()


def fetch_cotacao_source(cursor, cotacao_id):
    if not cotacao_id:
        return {}

    cursor.execute(
        """
        SELECT c.valor_total_proposta,
               ag.percentual AS agencia_percentual,
               parc.percentual AS parceiro_percentual
        FROM cadu_cotacoes c
        LEFT JOIN tbl_cliente ag ON c.agencia_id = ag.id_cliente
        LEFT JOIN tbl_cliente parc ON c.id_parceiro = parc.id_cliente
        WHERE c.id = %s
        """,
        (cotacao_id,),
    )
    cotacao = cursor.fetchone() or {}

    cursor.execute(
        """
        SELECT investimento_bruto, investimento_liquido, valor_total
        FROM cadu_cotacao_linhas
        WHERE cotacao_id = %s
          AND COALESCE(is_deleted, FALSE) = FALSE
          AND COALESCE(is_subtotal, FALSE) = FALSE
          AND COALESCE(is_header, FALSE) = FALSE
        """,
        (cotacao_id,),
    )
    linhas = cursor.fetchall()

    bruto = to_float(cotacao.get("valor_total_proposta"))
    if bruto <= 0 and linhas:
        bruto = sum(to_float(l.get("investimento_bruto") or l.get("valor_total")) for l in linhas)

    liquido = 0.0
    if linhas:
        liquido = sum(to_float(l.get("investimento_liquido")) for l in linhas)
    if liquido <= 0:
        liquido = bruto

    return {
        "valor_bruto": bruto,
        "valor_liquido": liquido,
        "perc_agencia": to_float(cotacao.get("agencia_percentual")),
        "perc_parceiro": to_float(cotacao.get("parceiro_percentual")),
    }


def fetch_campaign_total(cursor, id_pi):
    cursor.execute(
        """
        SELECT valor_plataforma
        FROM cadu_pi_campanha
        WHERE id_pi = %s
        """,
        (id_pi,),
    )
    return sum(to_float(row.get("valor_plataforma")) for row in cursor.fetchall())


def build_updates(cursor, pi):
    cotacao = fetch_cotacao_source(cursor, pi.get("cotacao_id"))
    campanha_total = fetch_campaign_total(cursor, pi["id_pi"])

    bruto = cotacao.get("valor_bruto") or to_float(existing_value(pi, "vr_bruto_pi"))
    liquido = cotacao.get("valor_liquido") or to_float(existing_value(pi, "vr_liquido_pi"))
    if liquido <= 0:
        liquido = bruto

    perc_agencia = cotacao.get("perc_agencia") or to_float(pi.get("perc_cms_agencia"))
    perc_parceiro = cotacao.get("perc_parceiro") or to_float(pi.get("perc_cms_parc_reg"))
    comissao_agencia = to_float(existing_value(pi, "vr_cms_agencia"))
    if comissao_agencia <= 0 and bruto > 0 and perc_agencia > 0:
        comissao_agencia = round(bruto * perc_agencia / 100, 2)

    comissao_parceiro = to_float(existing_value(pi, "vr_cms_parc_com"))
    if comissao_parceiro <= 0 and liquido > 0 and perc_parceiro > 0:
        comissao_parceiro = round(liquido * perc_parceiro / 100, 2)

    liquido_pr = to_float(existing_value(pi, "vr_liquido_pr_pi"))
    if liquido_pr <= 0 and liquido > 0:
        liquido_pr = round(liquido - comissao_parceiro, 2)

    plataforma_max = to_float(existing_value(pi, "vr_platafor_max_pi"))
    if plataforma_max <= 0:
        base_plataforma = liquido_pr if comissao_parceiro > 0 else liquido
        plataforma_max = round(base_plataforma * 0.3, 2) if base_plataforma > 0 else campanha_total

    total_plataforma = to_float(existing_value(pi, "total_platafor_max_pi"))
    if total_plataforma <= 0:
        total_plataforma = plataforma_max or campanha_total

    if bruto > 0:
        candidates = {
            "vr_bruto_pi": bruto,
            "vr_cms_agencia": comissao_agencia,
            "vr_cms_parc_com": comissao_parceiro,
            "vr_liquido_pi": liquido,
            "vr_liquido_pr_pi": liquido_pr,
            "vr_platafor_max_pi": plataforma_max,
            "total_platafor_max_pi": total_plataforma,
        }
    elif campanha_total > 0:
        candidates = {
            "vr_platafor_max_pi": campanha_total,
            "total_platafor_max_pi": campanha_total,
        }
    else:
        return {}

    updates = {}
    for column, value in candidates.items():
        if is_blank(pi.get(column)) and value is not None and value >= 0:
            updates[column] = format_real_br(value)
    return updates


def apply_updates(cursor, id_pi, updates):
    if not updates:
        return
    assignments = ", ".join(f"{column} = %s" for column in updates)
    params = list(updates.values()) + [id_pi]
    cursor.execute(
        f"""
        UPDATE cadu_pi
        SET {assignments},
            updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
        WHERE id_pi = %s
        """,
        params,
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill de campos monetarios vazios em cadu_pi")
    parser.add_argument("--apply", action="store_true", help="grava as alteracoes no banco")
    parser.add_argument("--id-pi", type=int, help="limita o backfill a um PI especifico")
    args = parser.parse_args()

    conn = psycopg.connect(**get_db_config())
    try:
        with conn.cursor() as cursor:
            pis = fetch_affected_pis(cursor, args.id_pi)
            print(f"PIs afetados encontrados: {len(pis)}")
            changed = 0
            for pi in pis:
                updates = build_updates(cursor, pi)
                if not updates:
                    print(f"PI {pi['id_pi']}: sem fonte suficiente para preencher")
                    continue
                changed += 1
                before = {column: pi.get(column) for column in updates}
                print(f"PI {pi['id_pi']}: {before} -> {updates}")
                if args.apply:
                    apply_updates(cursor, pi["id_pi"], updates)

            if args.apply:
                conn.commit()
                print(f"OK: {changed} PI(s) atualizados.")
            else:
                conn.rollback()
                print(f"DRY-RUN: {changed} PI(s) seriam atualizados. Use --apply para gravar.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
