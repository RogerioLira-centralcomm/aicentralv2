"""Public popularity and estimated profile of catalog portals.

What is measured: the rank of the domain in the Tranco list (public, research-grade, aggregates several
traffic panels). What is estimated, and always labelled so: the size tier derived from that rank, and the
demographic lean derived from the editorial category and region. No visit counts are invented here.
"""
import csv
import io
import re
import zipfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen

TRANCO_URL = 'https://tranco-list.eu/top-1m.csv.zip'
TRANCO_SOURCE = 'tranco'
TRANCO_PARENT_SOURCE = 'tranco_parent'
SECOND_LEVEL = {'com', 'org', 'net', 'gov', 'edu', 'jus', 'mil'}
# rank ceiling -> tier; a rank inherited from the parent domain is one tier lower (a section is smaller than its site).
TIERS = ((10_000, 'grande'), (100_000, 'medio'), (1_000_000, 'pequeno'))
# A section of a giant site (g1 inside globo.com) is still big; only smaller parents pass a tier down.
TOP_PARENT_RANK = 1_000
ORDER = ('grande', 'medio', 'pequeno', 'nicho')

# category keyword -> (gender lean, dominant age band, social class); lean is measured against a 50/50 base.
PROFILES = (
    ('esporte', ('masculino', '25-44', 'BC')),
    ('automotivo', ('masculino', '25-54', 'BC')),
    ('tecnologia', ('masculino', '18-34', 'BC')),
    ('economia', ('masculino', '25-54', 'AB')),
    ('mulher', ('feminino', '25-44', 'BC')),
    ('saúde', ('feminino', '25-54', 'BC')),
    ('entretenimento', ('feminino', '18-34', 'BC')),
    ('música', ('equilibrado', '18-34', 'BC')),
    ('viagem', ('equilibrado', '25-54', 'AB')),
    ('ciência', ('equilibrado', '18-34', 'BC')),
)
DEFAULT_PROFILE = ('equilibrado', '25-54', 'BC')
REGIONS = {'Norte': 'Norte', 'Nordeste': 'Nordeste', 'Sudeste': 'Sudeste', 'Sul': 'Sul', 'Centro-Oeste': 'Centro-Oeste'}


def registrable(domain):
    """'g1.globo.com' -> 'globo.com'; 'x.com.br' keeps three labels."""
    labels = str(domain or '').lower().strip('.').split('.')
    if len(labels) <= 2:
        return '.'.join(labels)
    keep = 3 if len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL else 2
    return '.'.join(labels[-keep:])


def load_tranco(path=None, timeout=120):
    """{domain: rank}. Read from a local zip/csv path when given, otherwise downloaded once from tranco-list.eu."""
    if path:
        raw = open(path, 'rb').read()
    else:
        with urlopen(Request(TRANCO_URL, headers={'User-Agent': 'CaduPlannerCatalogBot/1.0'}), timeout=timeout) as response:
            raw = response.read()
    if raw[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            raw = archive.read(archive.namelist()[0])
    ranks = {}
    for row in csv.reader(io.StringIO(raw.decode('utf-8', 'replace'))):
        if len(row) >= 2 and row[0].isdigit():
            ranks[row[1].strip().lower()] = int(row[0])
    return ranks


def popularity(domain, ranks):
    """(rank, source) for the domain itself, else for its registrable parent, else (None, None)."""
    domain = str(domain or '').lower().strip('.')
    if domain in ranks:
        return ranks[domain], TRANCO_SOURCE
    parent = registrable(domain)
    if parent != domain and parent in ranks:
        return ranks[parent], TRANCO_PARENT_SOURCE
    return None, None


def traffic_tier(rank, source):
    tier = next((name for ceiling, name in TIERS if rank and rank <= ceiling), 'nicho')
    if source == TRANCO_PARENT_SOURCE and tier != 'nicho' and rank > TOP_PARENT_RANK:
        tier = ORDER[min(ORDER.index(tier) + 1, len(ORDER) - 1)]
    return tier


def demographics(category, uf=None, scope=None):
    """Estimated lean from the editorial category; regional news carries the region instead of a topic."""
    text = str(category or '').lower()
    region = next((value for key, value in REGIONS.items() if key.lower() in text), None)
    gender, age, social = next((profile for key, profile in PROFILES if key in text), DEFAULT_PROFILE)
    return {'genero': gender, 'idade_dominante': age, 'classe': social, 'regiao': region, 'uf': uf or None,
            'base': 'categoria editorial' if any(key in text for key, _ in PROFILES) else 'perfil geral de notícias',
            'confianca': 'baixa', 'estimado': True}


def estimate(portal, ranks):
    rank, source = popularity(portal['domain'], ranks)
    return {'popularity_rank': rank, 'popularity_source': source, 'traffic_tier': traffic_tier(rank, source),
            'demographics': demographics(portal.get('category'), portal.get('uf'), portal.get('scope'))}


def save_estimates(portal_id, values):
    from psycopg.types.json import Json
    from ..db import get_db
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_planner_portals
                              SET popularity_rank = %s, popularity_source = %s, traffic_tier = %s, demographics = %s,
                                  popularity_checked_at = %s, estimates_updated_at = %s
                            WHERE id = %s''',
                        (values['popularity_rank'], values['popularity_source'], values['traffic_tier'],
                         Json(values['demographics']), datetime.now(timezone.utc), datetime.now(timezone.utc), portal_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
