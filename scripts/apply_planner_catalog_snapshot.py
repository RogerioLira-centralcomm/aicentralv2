"""Aplica no banco atual o snapshot editorial dos Portais e Canais do Planner (gerado por export_planner_catalog_snapshot.py).

Chaves por domínio (portais) e slug (canais), nunca por id. Sem --apply é só simulação (nada é gravado).
Uso: python scripts/apply_planner_catalog_snapshot.py docs/planner-catalog-snapshot.json [--apply] [--remap-files]

Regras: portal nunca é reativado (só desativado); descrição só dos portais com perfil curado; leituras (estimativas, formatos, ads.txt)
só entram se o snapshot for mais novo que o dado do banco; prints aprovados são registrados a partir dos arquivos já no repositório.
Se os ids dos portais forem diferentes entre os bancos, as pastas static/images/portais/{thumbs,prints} (nomeadas por id) precisam ser
renomeadas: use --remap-files (copia pelos ids do banco atual, depois remove os nomes de origem que não servem mais).
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')
from psycopg.types.json import Json  # noqa: E402

from aicentralv2 import create_app  # noqa: E402
from aicentralv2.cadu_family import repository  # noqa: E402
from aicentralv2.db import get_db  # noqa: E402

STATIC = ROOT / 'aicentralv2' / 'static'
JSON_COLUMNS = {'site_sections', 'ad_formats', 'demographics', 'programmatic_signals', 'formatos_resumo', 'diferenciais', 'medicao', 'produtos', 'fontes_metricas'}
REQUIRED = ('popularity_rank', 'traffic_tier', 'demographics', 'ad_formats', 'site_sections', 'signals_checked_at')
# (timestamp column, fields it dates): a group is only written when the snapshot is newer.
GROUPS = (('estimates_updated_at', ('popularity_rank', 'popularity_source', 'popularity_checked_at', 'traffic_tier', 'demographics', 'estimates_updated_at')),
          ('signals_checked_at', ('ad_formats', 'signals_checked_at')),
          ('ads_txt_checked_at', ('ads_txt_status', 'ads_txt_records', 'ads_txt_checked_at', 'programmatic_status', 'programmatic_signals', 'programmatic_checked_at')))


def value_for(column, value):
    return Json(value) if column in JSON_COLUMNS and value is not None else value


def newer(snapshot_value, current):
    if not snapshot_value:
        return False
    if not current:
        return True
    return datetime.fromisoformat(str(snapshot_value).replace('Z', '+00:00')) > (current if isinstance(current, datetime) else datetime.fromisoformat(str(current)))


def update(cur, table, key_column, key, values, apply):
    if not values:
        return
    if apply:
        sets = ', '.join(f'{column} = %s' for column in values)
        cur.execute(f'UPDATE {table} SET {sets} WHERE {key_column} = %s', [value_for(column, value) for column, value in values.items()] + [key])


def main(path, apply, remap_files):
    snapshot = json.loads(Path(path).read_text())
    with create_app().app_context():
        columns = {row['column_name'] for row in repository.rows("SELECT column_name FROM information_schema.columns WHERE table_name = 'cadu_planner_portals'")}
        missing = [name for name in REQUIRED if name not in columns]
        if missing:
            raise SystemExit(f'Faltam colunas ({", ".join(missing)}): rode as migrações do ORDER.txt antes.')
        from aicentralv2.cadu_planner.portal_profiles import PROFILES
        from aicentralv2.cadu_planner.portals import TOP_PROFILES
        curated = set(PROFILES) | set(TOP_PROFILES)
        by_domain = {row['domain']: row for row in repository.rows('SELECT * FROM cadu_planner_portals')}
        conn = get_db()
        counts = {'portais_ausentes': 0, 'desativados': 0, 'ids_iguais': 0, 'ids_diferentes': 0, 'grupos_atualizados': 0, 'descricoes': 0, 'prints': 0, 'prints_sem_arquivo': 0}
        absent, id_map = [], {}
        with conn.cursor() as cur:
            for item in snapshot['portals']:
                current = by_domain.get(item['domain'])
                if not current:
                    counts['portais_ausentes'] += 1
                    absent.append(item['domain'])
                    continue
                id_map[item['source_id']] = current['id']
                counts['ids_iguais' if current['id'] == item['source_id'] else 'ids_diferentes'] += 1
                if item.get('active') is False and current.get('active'):
                    update(cur, 'cadu_planner_portals', 'id', current['id'], {'active': False, 'featured_rank': None}, apply)
                    counts['desativados'] += 1
                    continue
                if not current.get('active'):
                    continue
                simple = {}
                if item.get('featured_rank') != current.get('featured_rank') and item.get('featured_rank') is not None:
                    simple['featured_rank'] = item['featured_rank']
                if item['domain'] in curated and item.get('description') and item['description'] != current.get('description'):
                    simple['description'] = item['description']
                    counts['descricoes'] += 1
                if item.get('site_sections') and item['domain'] in curated:
                    simple['site_sections'] = item['site_sections']
                for column in ('site_title', 'favicon_url'):
                    if item.get(column) and not current.get(column):
                        simple[column] = item[column]
                update(cur, 'cadu_planner_portals', 'id', current['id'], simple, apply)
                for stamp, fields in GROUPS:
                    if newer(item.get(stamp), current.get(stamp)):
                        update(cur, 'cadu_planner_portals', 'id', current['id'], {field: item.get(field) for field in fields if field in columns}, apply)
                        counts['grupos_atualizados'] += 1
            for item in snapshot['portals']:
                prod_id = id_map.get(item['source_id'])
                for shot in item.get('prints', []) if prod_id else []:
                    source = STATIC / shot['file_path']
                    if remap_files and prod_id != item['source_id']:
                        continue  # re-registered below, after the files were remapped
                    if not source.exists():
                        counts['prints_sem_arquivo'] += 1
                        continue
                    counts['prints'] += 1
                    if apply:
                        cur.execute("""INSERT INTO cadu_planner_portal_prints (portal_id, kind, file_path, source_url, status, captured_at)
                                       VALUES (%s, %s, %s, %s, 'aprovado', %s) ON CONFLICT (portal_id, kind, file_path) DO NOTHING""",
                                    (prod_id, shot['kind'], shot['file_path'], shot['source_url'], shot['captured_at']))
            for channel in snapshot['channels']:
                current = (repository.rows('SELECT id FROM cadu_canais WHERE slug = %s', (channel['slug'],)) or [None])[0]
                if not current:
                    print('canal ausente:', channel['slug'])
                    continue
                update(cur, 'cadu_canais', 'id', current['id'], {key: value for key, value in channel.items() if key != 'slug'}, apply)
                print('canal', channel['slug'], 'ok' if apply else '(simulação)')
        if apply:
            conn.commit()
        if counts['ids_diferentes'] and not remap_files:
            print('ATENÇÃO: há portais com id diferente entre os bancos. As miniaturas e prints (nomeados por id) podem aparecer no portal errado; rode com --remap-files.')
        if remap_files and counts['ids_diferentes']:
            remap(snapshot, id_map, apply, conn)
        print(json.dumps(counts, ensure_ascii=False), '(gravado)' if apply else '(simulação)')
        if absent:
            print('portais do snapshot ausentes neste banco (primeiros 15):', absent[:15])


def remap(snapshot, id_map, apply, conn):
    """thumbs/{id}.webp and prints/{id}/ are named by id: rebuild them under this database's ids (read everything first, then write)."""
    thumbs_dir = STATIC / 'images' / 'portais' / 'thumbs'
    staged_thumbs = {id_map[item['source_id']]: (thumbs_dir / f"{item['source_id']}.webp").read_bytes()
                     for item in snapshot['portals'] if item['source_id'] in id_map and (thumbs_dir / f"{item['source_id']}.webp").exists()}
    staged_prints = []
    for item in snapshot['portals']:
        prod_id = id_map.get(item['source_id'])
        for shot in item.get('prints', []) if prod_id else []:
            source = STATIC / shot['file_path']
            if source.exists():
                staged_prints.append((prod_id, shot, source.read_bytes()))
    print(f'remapeamento: {len(staged_thumbs)} miniaturas e {len(staged_prints)} prints')
    if not apply:
        return
    for item in snapshot['portals']:
        (thumbs_dir / f"{item['source_id']}.webp").unlink(missing_ok=True)
        shutil.rmtree(STATIC / 'images' / 'portais' / 'prints' / str(item['source_id']), ignore_errors=True)
    for prod_id, data in staged_thumbs.items():
        (thumbs_dir / f'{prod_id}.webp').write_bytes(data)
    with conn.cursor() as cur:
        for prod_id, shot, data in staged_prints:
            relative = f"images/portais/prints/{prod_id}/{Path(shot['file_path']).name}"
            target = STATIC / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            cur.execute("""INSERT INTO cadu_planner_portal_prints (portal_id, kind, file_path, source_url, status, captured_at)
                           VALUES (%s, %s, %s, %s, 'aprovado', %s) ON CONFLICT (portal_id, kind, file_path) DO NOTHING""",
                        (prod_id, shot['kind'], relative, shot['source_url'], shot['captured_at']))
    conn.commit()


if __name__ == '__main__':
    arguments = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    if not arguments:
        raise SystemExit(__doc__)
    main(arguments[0], '--apply' in sys.argv, '--remap-files' in sys.argv)
