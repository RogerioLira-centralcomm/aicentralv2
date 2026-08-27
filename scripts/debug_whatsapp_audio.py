"""Diagnóstico de mensagens de áudio WhatsApp."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import psycopg

from aicentralv2.services.wasender_service import detectar_midia_mensagem

load_dotenv(Path(__file__).resolve().parent.parent / '.env')


def main():
    cfg = dict(
        dbname=os.getenv('DB_NAME', 'aicentral_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
    )
    ids = [39, 38, 36, 34, 31]
    with psycopg.connect(**cfg) as conn:
        with conn.cursor() as cur:
            for mid in (39, 38):
                cur.execute(
                    'SELECT id, direcao, texto, provider_payload, created_at FROM whatsapp_mensagens WHERE id=%s',
                    (mid,),
                )
                row = cur.fetchone()
                if not row:
                    continue
                msg_id, direcao, texto, payload, created_at = row
                payload = payload or {}
                media = payload.get('_media')
                md = payload.get('_message_data')
                print(f'--- id={msg_id} dir={direcao} at={created_at} texto={texto!r}')
                if isinstance(media, dict):
                    print(f'  _media.type={media.get("type")} local={media.get("local_url")!r}')
                    print(f'  _media.url={(media.get("url") or "")[:100]!r}')
                else:
                    print('  _media: None')
                if isinstance(md, dict):
                    t, info = detectar_midia_mensagem(md)
                    print(f'  detect={t} ptt={info.get("ptt") if info else None}')
                else:
                    print('  _message_data: None')
                print(f'  payload keys: {list(payload.keys())[:15]}')
                data = payload.get('data')
                if isinstance(data, dict):
                    msgs = data.get('messages')
                    if isinstance(msgs, dict):
                        mb = msgs.get('messageBody')
                        mk = (msgs.get('message') or {}).keys() if isinstance(msgs.get('message'), dict) else None
                        print(f'  data.messages.messageBody={mb!r} message keys={list(mk) if mk else None}')
                    else:
                        print(f'  data keys: {list(data.keys())[:12]}')
                        msg = data.get('message')
                        if isinstance(msg, dict):
                            print(f'  data.message keys: {list(msg.keys())[:8]}')


if __name__ == '__main__':
    main()
