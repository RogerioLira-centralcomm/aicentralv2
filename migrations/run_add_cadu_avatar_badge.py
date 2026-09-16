#!/usr/bin/env python3
"""Adiciona a preferência de selo de avatar do Cadu aos contatos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def main():
    sql = Path(__file__).with_name('add_cadu_avatar_badge.sql').read_text(encoding='utf-8')
    with psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'aicentralv2'), user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
    print('Preferência de selo de avatar Cadu pronta.')


if __name__ == '__main__':
    main()
