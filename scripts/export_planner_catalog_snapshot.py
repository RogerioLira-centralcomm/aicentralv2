"""Exporta o estado editorial dos Portais e dos Canais do Planner para um JSON portátil (chaves por domínio e slug, nunca por id).

Uso (no banco onde o trabalho foi feito):  python scripts/export_planner_catalog_snapshot.py docs/planner-catalog-snapshot.json
Depois, no banco de produção:             python scripts/apply_planner_catalog_snapshot.py docs/planner-catalog-snapshot.json [--apply]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')
from aicentralv2 import create_app  # noqa: E402
from aicentralv2.cadu_family import repository  # noqa: E402

PORTAL_FIELDS = ('active', 'featured_rank', 'description', 'site_sections', 'ad_formats', 'signals_checked_at', 'popularity_rank', 'popularity_source',
                 'popularity_checked_at', 'traffic_tier', 'demographics', 'estimates_updated_at', 'ads_txt_status', 'ads_txt_records', 'ads_txt_checked_at',
                 'programmatic_status', 'programmatic_signals', 'programmatic_checked_at', 'site_title', 'favicon_url')
CHANNEL_FIELDS = ('descricao', 'categoria', 'alcance', 'usuarios_unicos', 'formatos_resumo', 'diferenciais', 'medicao', 'produtos',
                  'fontes_metricas', 'perfil_audiencia', 'melhor_uso')
CHANNELS = ('uber', 'ifood', '99', 'amazon-ads', 'logan', 'serasa', 'interativos')


def main(target):
    with create_app().app_context():
        portals = repository.rows('SELECT to_jsonb(p) AS data FROM cadu_planner_portals p ORDER BY id')
        prints = {}
        for row in repository.rows("SELECT portal_id, kind, file_path, source_url, captured_at FROM cadu_planner_portal_prints WHERE status = 'aprovado'"):
            prints.setdefault(row['portal_id'], []).append({'kind': row['kind'], 'file_path': row['file_path'], 'source_url': row['source_url'],
                                                           'captured_at': row['captured_at'].isoformat() if row['captured_at'] else None})
        out_portals = []
        for row in portals:
            data = row['data']
            item = {'domain': data['domain'], 'source_id': data['id']}
            item.update({field: data.get(field) for field in PORTAL_FIELDS if field in data})
            item['prints'] = prints.get(data['id'], [])
            out_portals.append(item)
        channels = []
        for row in repository.rows('SELECT to_jsonb(c) AS data FROM cadu_canais c ORDER BY id'):
            data = row['data']
            if str(data['slug']) in CHANNELS or str(data.get('nome')) in ('Serasa Data (DMP)', 'Interativos', 'Amazon Ads / Marketplace'):
                channels.append({'slug': data['slug'], **{field: data.get(field) for field in CHANNEL_FIELDS if field in data}})
    Path(target).write_text(json.dumps({'portals': out_portals, 'channels': channels}, ensure_ascii=False, indent=1, default=str))
    print(f'{len(out_portals)} portais, {len(channels)} canais, {sum(len(p["prints"]) for p in out_portals)} prints -> {target}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'planner-catalog-snapshot.json')
