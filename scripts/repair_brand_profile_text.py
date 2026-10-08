"""Repara campos de texto de cx_clients.brand_profile gravados como repr de lista/objeto de evidências.

Antes, a auditoria salvava `str([{'value': ..., 'source_url': ...}])` em brand_summary e campos irmãos.
Padrão: só mostra o que mudaria. Com --apply grava e guarda o valor antigo em --backup.

    .venv/bin/python scripts/repair_brand_profile_text.py            # simulação
    .venv/bin/python scripts/repair_brand_profile_text.py --apply    # grava
"""
import argparse
import ast
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.types.json import Jsonb

from aicentralv2.creative_brand_analysis import _plain_text
from aicentralv2.db import get_db_config

FIELDS = ('brand_summary', 'tone_of_voice', 'positioning', 'target_audience', 'creative_guidelines')


def parse(text):
    """Lê JSON ou repr do Python; devolve None quando não é uma estrutura."""
    for loader in (json.loads, ast.literal_eval):
        try:
            value = loader(text)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            continue
        if isinstance(value, (list, dict)):
            return value
    return None


def repaired(value):
    if not isinstance(value, str) or not value.lstrip().startswith(('[{', '{')):
        return None
    structure = parse(value.strip())
    if structure is None:
        return None
    clean = _plain_text(structure)
    return clean if clean and clean != value else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', default=str(ROOT / 'tmp' / f'brand_profile_text_backup_{datetime.now():%Y%m%d_%H%M%S}.json'))
    args = parser.parse_args()
    changes = []
    with psycopg.connect(**get_db_config()) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, name, brand_profile FROM cx_clients WHERE brand_profile IS NOT NULL')
            for row in cursor.fetchall():
                profile = row['brand_profile'] or {}
                fixes = {field: repaired(profile.get(field)) for field in FIELDS}
                fixes = {field: new for field, new in fixes.items() if new}
                if fixes:
                    changes.append({'id': row['id'], 'name': row['name'],
                                    'before': {field: profile[field] for field in fixes}, 'after': fixes})
            print(f'{len(changes)} marcas com texto a reparar')
            for item in changes:
                print(f"- {item['id']} {item['name']}: {', '.join(item['after'])}")
                for field, new in item['after'].items():
                    print(f'    {field}: {new[:110]}')
            if not args.apply or not changes:
                return
            Path(args.backup).parent.mkdir(parents=True, exist_ok=True)
            Path(args.backup).write_text(json.dumps(changes, ensure_ascii=False, indent=1, default=str))
            for item in changes:
                cursor.execute('''UPDATE cx_clients SET brand_profile = brand_profile || %s WHERE id = %s''',
                               (Jsonb(item['after']), item['id']))
        conn.commit()
    print(f'{len(changes)} marcas atualizadas; backup em {args.backup}')


if __name__ == '__main__':
    main()
