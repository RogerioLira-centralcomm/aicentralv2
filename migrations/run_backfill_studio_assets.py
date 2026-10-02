#!/usr/bin/env python3
"""Copia imagens do Criar e clipes do Vídeo já gerados para a biblioteca única (cx_studio_assets).

Idempotente: usa a mesma chave (client_id, 'studio_create', request_id) que o
registro em tempo real. Sem --apply apenas lista o que seria gravado.
"""
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from aicentralv2.creative_media.public import asset_url  # noqa: E402
from aicentralv2.creative_media.studio_history import StudioCreationHistory  # noqa: E402


def main(apply=False):
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT g.request_id, g.client_id, g.user_id, g.project_id::text AS project_id,
                       g.result->>'image_url' AS image_url,
                       COALESCE(g.result->>'title', 'Imagem criada no Studio') AS title,
                       COALESCE(g.result->>'aspect_ratio', '') AS aspect_ratio
                  FROM cx_studio_image_generations g
                 WHERE g.status='completed' AND g.deleted_at IS NULL
                   AND COALESCE(g.result->>'image_url', '') <> ''
                   AND NOT EXISTS (
                       SELECT 1 FROM cx_studio_assets a
                        WHERE a.client_id=g.client_id AND a.source_type='studio_create'
                          AND a.source_id=g.request_id AND a.deleted_at IS NULL)
              ORDER BY g.created_at
            """)
            rows = cursor.fetchall()
            cursor.execute("""
                SELECT j.public_id, j.client_id, j.user_id,
                       m.public_id AS master_id, p.public_id AS poster_id,
                       COALESCE(j.plan_json->>'duration', '') AS duration
                  FROM cx_media_jobs j
                  JOIN cx_media_assets m ON m.job_id=j.id AND m.kind='master'
             LEFT JOIN cx_media_assets p ON p.job_id=j.id AND p.kind='poster'
                 WHERE j.status='ready' AND j.client_id IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM cx_studio_assets a
                        WHERE a.client_id=j.client_id AND a.source_type='studio_video'
                          AND a.source_id=j.public_id AND a.deleted_at IS NULL)
              ORDER BY j.created_at
            """)
            videos = cursor.fetchall()
        print(f"{len(rows)} imagem(ns) do Criar fora da biblioteca única.")
        for row in rows:
            print(f"  client={row['client_id']} project={row['project_id'] or '-'} {row['image_url']}")
        print(f"{len(videos)} clipe(s) do Vídeo fora da biblioteca única.")
        for row in videos:
            print(f"  client={row['client_id']} job={row['public_id']}")
        if not apply:
            print("Simulação. Rode com --apply para gravar.")
            return
        history = StudioCreationHistory(conn)
        for row in rows:
            history.register_asset(
                row["client_id"], row["user_id"], row["project_id"] or "", "image", "studio_create",
                row["request_id"], row["title"], row["image_url"],
                {"aspect_ratio": row["aspect_ratio"], "backfill": True},
            )
        for row in videos:
            history.register_asset(
                row["client_id"], row["user_id"], "", "video", "studio_video", row["public_id"],
                "Clipe do Studio", asset_url(row["master_id"]),
                {"poster_url": asset_url(row["poster_id"]), "duration": row["duration"], "backfill": True},
            )
        print(f"{len(rows) + len(videos)} registro(s) gravado(s).")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
