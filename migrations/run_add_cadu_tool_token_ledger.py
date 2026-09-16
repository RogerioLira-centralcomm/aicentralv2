#!/usr/bin/env python3
"""Aplica o ledger de créditos/tokens das ferramentas CADU."""
from pathlib import Path

from aicentralv2.db import get_db


def main():
    sql = Path(__file__).with_name("add_cadu_tool_token_ledger.sql").read_text(encoding="utf-8")
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
        print("OK cadu_credits_extras + cadu_tools_token_usage")
    except Exception:
        conn.rollback()
        raise


if __name__ == "__main__":
    main()
