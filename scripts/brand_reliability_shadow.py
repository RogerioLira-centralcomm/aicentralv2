#!/usr/bin/env python3
"""Export a golden-set template or evaluate latest brand snapshots read-only."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2.brand_reliability import evaluate_shadow  # noqa: E402


def _connect():
    load_dotenv(ROOT / '.env')
    return psycopg.connect(
        host=os.environ['DB_HOST'], port=os.getenv('DB_PORT', '5432'),
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
        password=os.getenv('DB_PASSWORD', ''), connect_timeout=10,
        row_factory=dict_row,
    )


def _latest_records(brand_ids: list[int] | None) -> list[dict]:
    params: list[object] = []
    where = ''
    if brand_ids:
        where = 'WHERE s.brand_id = ANY(%s)'
        params.append(brand_ids)
    query = f'''
        WITH latest AS (
            SELECT DISTINCT ON (s.brand_id) s.id, s.brand_id, s.job_id, s.decision
              FROM cadu_workspace_brand_profile_snapshots s
              {where}
             ORDER BY s.brand_id, s.created_at DESC, s.id DESC
        )
        SELECT f.brand_id, f.snapshot_id, l.job_id AS run_id, l.decision AS run_status,
               f.field_name, f.field_category, f.value, f.status, f.confidence,
               f.evidence_count, f.reason_code, f.pipeline_version,
               f.contract_version, f.score_version
          FROM latest l
          JOIN cadu_workspace_brand_identity_fields f ON f.snapshot_id = l.id
         ORDER BY f.brand_id, f.field_category, f.field_name
    '''
    with _connect() as conn, conn.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('template', 'evaluate'))
    parser.add_argument('--golden', type=Path, help='JSON de rótulos humanos para evaluate')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--brand-id', type=int, action='append', dest='brand_ids')
    args = parser.parse_args()
    records = _latest_records(args.brand_ids)
    if args.mode == 'template':
        payload = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'instructions': 'Revise expected_status e expected_value; não use a saída do pipeline como verdade sem validação humana.',
            'labels': [{
                'brand_id': row['brand_id'], 'field_name': row['field_name'],
                'field_category': row['field_category'], 'applicable': True, 'reviewed': False,
                'expected_status': None, 'expected_value': None,
                'candidate_status': row['status'], 'candidate_value': row['value'],
            } for row in records],
        }
    else:
        if not args.golden:
            parser.error('--golden é obrigatório no modo evaluate')
        golden = json.loads(args.golden.read_text(encoding='utf-8'))
        labels = golden.get('labels', golden) if isinstance(golden, dict) else golden
        payload = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'scope': {'brand_ids': args.brand_ids or 'latest_all'},
            **evaluate_shadow(records, labels),
        }
    _write_json(args.output, payload)
    print(f'{args.mode}: {len(records)} campos; relatório em {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
