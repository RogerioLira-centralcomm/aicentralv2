#!/usr/bin/env python3
"""Importa o catálogo HTML da CentralComm para ``cadu_formatos``.

O HTML em português é a fonte editorial: descrição, mercados aplicáveis,
segmentos criativos, imagem e galeria ficam preservados em ``dados_extras``.
Execute a migration ``add_cadu_interactive_creative_categories.sql`` antes.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path('/Users/apololira/Downloads/centralcomm/html-slides-pt')


def clean(value: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', value))).strip()


def attr(markup: str, name: str) -> str:
    match = re.search(rf'\b{name}=["\']([^"\']*)["\']', markup, re.I)
    return html.unescape(match.group(1)).strip() if match else ''


def category_for(labels: list[str]) -> str:
    values = {label.casefold() for label in labels}
    if values & {'jogável', 'gamificação'}:
        return 'Gamificação'
    if 'geração de leads' in values:
        return 'Geração de leads'
    if 'exposição de produto' in values:
        return 'Descoberta de produto'
    if 'narrativa' in values:
        return 'Narrativa de marca'
    if 'foco na marca' in values:
        return 'Awareness de marca'
    return 'Experiência interativa'


def purpose_for(labels: list[str]) -> str:
    values = {label.casefold() for label in labels}
    if values & {'exposição de produto', 'geração de leads', 'interatividade', 'jogável', 'gamificação'}:
        return 'Conversão'
    return 'Alcance'


def slug_for(name: str) -> str:
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    normalized = re.sub(r'[^a-z0-9]+', '-', normalized.casefold()).strip('-')
    return f'interativo-{normalized}'


def parse_catalog(source: Path) -> list[dict]:
    overview = (source / 'creative-format-overview.html').read_text(encoding='utf-8')
    articles = re.findall(r'<article class="format-card">(.*?)</article>', overview, re.S | re.I)
    records = []
    for article in articles:
        name_match = re.search(r'<h2>(.*?)</h2>', article, re.S | re.I)
        description_match = re.search(r'<p class="description">(.*?)</p>', article, re.S | re.I)
        vertical_match = re.search(r'<p class="vertical-line">(.*?)</p>', article, re.S | re.I)
        chips_match = re.search(r'<div class="chips">(.*?)</div>', article, re.S | re.I)
        gallery_match = re.search(r'<a class="card-link"([^>]*)>', article, re.S | re.I)
        image_match = re.search(r'<img([^>]*)>', article, re.S | re.I)
        detail_match = re.search(r'<a class="format-card-target"([^>]*)>', article, re.S | re.I)
        if not (name_match and description_match and vertical_match):
            continue
        labels = [clean(item) for item in re.findall(r'<span>(.*?)</span>', chips_match.group(1), re.S | re.I)] if chips_match else []
        markets = [part.strip() for part in clean(vertical_match.group(1)).split(',') if part.strip()]
        detail_name = attr(detail_match.group(1), 'href') if detail_match else ''
        detail = (source / detail_name).read_text(encoding='utf-8') if detail_name else ''
        examples = re.findall(
            r'<a[^>]*class=["\'][^"\']*example-pill[^"\']*["\'][^>]*href=["\']([^"\']+)',
            detail, re.S | re.I,
        )
        gallery_url = attr(gallery_match.group(1), 'href') if gallery_match else ''
        records.append({
            'name': clean(name_match.group(1)),
            'description': clean(description_match.group(1)),
            'creative_category': category_for(labels),
            'purpose': purpose_for(labels),
            'segments': labels,
            'markets': markets,
            'image_url': attr(image_match.group(1), 'src') if image_match else '',
            # O parceiro entrega o criativo em uma página isolada e responsiva.
            # Mantemos o endereço original, sem proxy nem redirecionamento.
            'creative_url': html.unescape(examples[0]) if examples else gallery_url,
            'gallery_url': gallery_url,
        })
    if not records:
        raise RuntimeError('Nenhum formato foi encontrado no catálogo HTML.')
    return records


def import_records(records: list[dict]) -> tuple[int, int]:
    from dotenv import load_dotenv
    import psycopg
    from psycopg.rows import dict_row

    load_dotenv(ROOT / '.env')
    created = updated = 0
    with psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'aicentralv2'), user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''), row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            for position, item in enumerate(records, start=1):
                extras = json.dumps({
                    'fonte_catalogo': 'centralcomm/html-slides-pt',
                    'segmentos_aplicaveis': item['segments'],
                    'mercados_aplicaveis': item['markets'],
                    'objetivo_comercial': item['purpose'],
                    'imagem_referencia': item['image_url'],
                    'creative_url': item['creative_url'],
                    'gallery_url': item['gallery_url'],
                }, ensure_ascii=False)
                cur.execute('''SELECT id FROM cadu_formatos
                                WHERE LOWER(nome) = LOWER(%s) AND is_interativo = TRUE
                                ORDER BY id LIMIT 1''', (item['name'],))
                existing = cur.fetchone()
                if existing:
                    cur.execute('''UPDATE cadu_formatos
                                      SET descricao = %s, categoria_criativa = %s,
                                          plataforma_slug = 'interativos', tipo = 'display_interativo',
                                          dimensoes = 'IAB desktop e mobile (conforme briefing)',
                                          formatos_arquivo = 'JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável',
                                          dados_extras = COALESCE(dados_extras, '{}'::jsonb) || %s::jsonb,
                                          is_active = TRUE, is_interativo = TRUE
                                    WHERE id = %s''',
                                (item['description'], item['creative_category'], extras, existing['id']))
                    updated += 1
                else:
                    cur.execute('''INSERT INTO cadu_formatos
                                        (slug, nome, descricao, categoria_criativa, plataforma_slug, tipo,
                                         dimensoes, formatos_arquivo, dados_extras, is_active, is_interativo, ordem)
                                    VALUES (%s, %s, %s, %s, 'interativos', 'display_interativo', %s, %s,
                                            %s::jsonb, TRUE, TRUE, %s)''',
                                (slug_for(item['name']), item['name'], item['description'], item['creative_category'],
                                 'IAB desktop e mobile (conforme briefing)',
                                 'JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável', extras, 900 + position))
                    created += 1
        conn.commit()
    return created, updated


def audit_records() -> list[dict]:
    from dotenv import load_dotenv
    import psycopg
    from psycopg.rows import dict_row

    load_dotenv(ROOT / '.env')
    with psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'aicentralv2'), user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''), row_factory=dict_row,
    ) as conn, conn.cursor() as cur:
        cur.execute('''SELECT id, slug, nome, descricao, tipo, plataforma_slug,
                              categoria_criativa, is_interativo, dados_extras
                         FROM cadu_formatos
                        ORDER BY is_interativo DESC, nome''')
        return list(cur.fetchall())


def purpose_for_record(record: dict) -> str:
    conversion_types = {'automated', 'conversational', 'ecommerce', 'lead-gen', 'search'}
    conversion_categories = {
        'descoberta', 'descoberta de produto', 'exploração', 'gamificação',
        'geração de leads', 'participação',
    }
    if str(record.get('tipo') or '').strip().casefold() in conversion_types:
        return 'Conversão'
    if record.get('is_interativo') and str(record.get('categoria_criativa') or '').strip().casefold() in conversion_categories:
        return 'Conversão'
    return 'Alcance'


def classify_base() -> tuple[int, int]:
    """Classifica o catálogo legado sem inventar mercados ou segmentos."""
    from dotenv import load_dotenv
    import psycopg
    from psycopg.rows import dict_row

    load_dotenv(ROOT / '.env')
    changed = unchanged = 0
    with psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'aicentralv2'), user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''), row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id, tipo, categoria_criativa, is_interativo,
                                  dados_extras ->> 'objetivo_comercial' AS purpose
                             FROM cadu_formatos
                            WHERE is_active = TRUE''')
            for record in cur.fetchall():
                purpose = purpose_for_record(record)
                if record['purpose'] == purpose:
                    unchanged += 1
                    continue
                cur.execute('''UPDATE cadu_formatos
                                  SET dados_extras = COALESCE(dados_extras, '{}'::jsonb)
                                                     || %s::jsonb
                                WHERE id = %s''',
                            (json.dumps({'objetivo_comercial': purpose}), record['id']))
                changed += 1
        conn.commit()
    return changed, unchanged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--classify-base', action='store_true')
    args = parser.parse_args()
    if args.audit:
        print(json.dumps(audit_records(), ensure_ascii=False, indent=2, default=str))
        return
    if args.classify_base:
        changed, unchanged = classify_base()
        print(f'Classificação do catálogo: {changed} atualizados, {unchanged} já classificados.')
        return
    records = parse_catalog(args.source)
    if args.dry_run:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    created, updated = import_records(records)
    print(f'Catálogo CentralComm importado: {created} criados, {updated} atualizados.')


if __name__ == '__main__':
    main()
