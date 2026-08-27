"""Diagnóstico rápido de mensagens WhatsApp com mídia."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parent.parent / '.env')


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
            cur.execute(
                'SELECT id, texto, provider_payload FROM whatsapp_mensagens ORDER BY id DESC LIMIT 20'
            )
            rows = cur.fetchall()

    for row in rows:
        msg_id, texto, payload = row
        payload = payload or {}
        raw = json.dumps(payload, ensure_ascii=False)
        flags = []
        if '_media' in raw:
            flags.append('_media')
        if 'videoMessage' in raw:
            flags.append('videoMessage')
        if 'gifPlayback' in raw:
            flags.append('gifPlayback')
        if 'imageMessage' in raw:
            flags.append('imageMessage')
        if '_message_data' in raw:
            flags.append('_message_data')
        print(f"id={msg_id} texto={ascii(texto)} flags={flags}")


if __name__ == '__main__':
    main()
