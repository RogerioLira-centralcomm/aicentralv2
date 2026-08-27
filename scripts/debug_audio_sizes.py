"""Compara duração declarada vs tamanho dos arquivos de áudio."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

STATIC = Path(__file__).resolve().parent.parent / 'aicentralv2' / 'static'


def resolve_local(rel):
    if not rel:
        return None
    rel = str(rel).lstrip('/')
    if rel.startswith('static/'):
        rel = rel[len('static/'):]
    return STATIC / rel


def main():
    cfg = dict(
        dbname=os.getenv('DB_NAME', 'aicentral_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
    )
    with psycopg.connect(**cfg) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, direcao, texto, created_at, provider_payload
                FROM whatsapp_mensagens
                WHERE texto ILIKE '%udio%'
                ORDER BY id DESC LIMIT 15
            ''')
            rows = cur.fetchall()

    for row in rows:
        msg_id, direcao, texto, created_at, payload = row
        payload = payload or {}
        media = payload.get('_media') or {}
        seconds = media.get('seconds')
        local = media.get('local_url')
        path = resolve_local(local)
        size = path.stat().st_size if path and path.exists() else None
        print(
            f'id={msg_id} {direcao} at={created_at} seconds={seconds} '
            f'size={size} path={local!r} exists={bool(path and path.exists())}'
        )

if __name__ == '__main__':
    main()
