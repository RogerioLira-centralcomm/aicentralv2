"""Base de fontes do Radar: nível de confiança por domínio e selo da oportunidade.

O nível vem de ``data/sources_v1.json`` (curadoria da equipe) e de regras fixas:
domínios de governo (.gov.br, .leg.br, .jus.br, .mp.br) são fonte primária, o
site oficial da marca também, e domínio desconhecido conta como C. Tudo aqui é
determinístico; o modelo nunca decide se uma fonte é confiável.
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

DATA = Path(__file__).with_name('data') / 'sources_v1.json'
PRIMARY_SUFFIXES = ('.gov.br', '.leg.br', '.jus.br', '.mp.br')
SECOND_LEVEL = {'com.br', 'org.br', 'net.br', 'gov.br', 'leg.br', 'jus.br', 'mp.br', 'edu.br', 'co.uk', 'com.ar'}
PRESS_GROUPS = ('nacional', 'mercado_midia', 'regional')

UF_NAMES = {
    'AC': 'acre', 'AL': 'alagoas', 'AP': 'amapa', 'AM': 'amazonas', 'BA': 'bahia', 'CE': 'ceara',
    'DF': 'distrito federal', 'ES': 'espirito santo', 'GO': 'goias', 'MA': 'maranhao', 'MT': 'mato grosso',
    'MS': 'mato grosso do sul', 'MG': 'minas gerais', 'PA': 'para', 'PB': 'paraiba', 'PR': 'parana',
    'PE': 'pernambuco', 'PI': 'piaui', 'RJ': 'rio de janeiro', 'RN': 'rio grande do norte',
    'RS': 'rio grande do sul', 'RO': 'rondonia', 'RR': 'roraima', 'SC': 'santa catarina', 'SP': 'sao paulo',
    'SE': 'sergipe', 'TO': 'tocantins'}
CAPITALS = {
    'belo horizonte': 'MG', 'porto alegre': 'RS', 'curitiba': 'PR', 'florianopolis': 'SC', 'vitoria': 'ES',
    'recife': 'PE', 'salvador': 'BA', 'fortaleza': 'CE', 'goiania': 'GO', 'brasilia': 'DF', 'manaus': 'AM',
    'belem': 'PA', 'natal': 'RN', 'joao pessoa': 'PB', 'sao luis': 'MA', 'teresina': 'PI',
    'campo grande': 'MS', 'cuiaba': 'MT', 'bh': 'MG', 'poa': 'RS'}


def _plain(text):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(text or '').casefold()) if not unicodedata.combining(ch))


def host(url):
    value = str(url or '').strip()
    if '//' not in value:
        value = 'https://' + value
    name = (urlparse(value).hostname or '').casefold()
    return name[4:] if name.startswith('www.') else name


def root(domain):
    """Domínio registrável (aproximação de grupo de mídia): g1.globo.com → globo.com."""
    parts = host(domain).split('.')
    keep = 3 if len(parts) >= 3 and '.'.join(parts[-2:]) in SECOND_LEVEL else 2
    return '.'.join(parts[-keep:])


@lru_cache(maxsize=1)
def catalog():
    data = json.loads(DATA.read_text(encoding='utf-8'))
    return {item['domain']: item for item in data['sources']}


def lookup(url, brand_site=''):
    """``{domain, name, group, tier, primary}`` para uma URL."""
    domain = host(url)
    if not domain:
        return {'domain': '', 'name': '', 'group': 'desconhecido', 'tier': 'C', 'primary': False}
    if brand_site and root(domain) == root(brand_site):
        return {'domain': domain, 'name': 'Site da marca', 'group': 'oficial', 'tier': 'A', 'primary': True}
    if domain.endswith(PRIMARY_SUFFIXES) or f'.{domain}' in PRIMARY_SUFFIXES:
        return {'domain': domain, 'name': domain, 'group': 'governo', 'tier': 'A', 'primary': True}
    known = catalog()
    probe = domain
    while probe:
        if probe in known:
            item = known[probe]
            return {'domain': domain, 'name': item['name'], 'group': item['group'], 'tier': item['tier'],
                    'primary': item['group'] == 'governo', 'uf': item.get('uf')}
        probe = probe.split('.', 1)[1] if '.' in probe else ''
    return {'domain': domain, 'name': domain, 'group': 'desconhecido', 'tier': 'C', 'primary': False}


def place_ufs(places):
    """UFs citadas nas praças ('Belo Horizonte, SP' → {'MG', 'SP'})."""
    found = set()
    for raw in str(places or '').replace(';', ',').split(','):
        text = _plain(raw).strip()
        if not text:
            continue
        if text.upper() in UF_NAMES:
            found.add(text.upper())
        found.update(uf for name, uf in CAPITALS.items() if name in text)
        found.update(uf for uf, name in UF_NAMES.items() if name == text)
    return found


def press_domains(places='', groups=PRESS_GROUPS, tiers=('A', 'B'), limit=30):
    """Veículos da base para a descoberta na imprensa: nacionais e de mercado + regionais das praças."""
    ufs = place_ufs(places)
    chosen = []
    for item in catalog().values():
        if item['group'] not in groups or item['tier'] not in tiers:
            continue
        if item['group'] == 'regional' and item.get('uf') not in ufs:
            continue
        chosen.append(item)
    # Regionais das praças primeiro: são as que o modelo sozinho menos encontra.
    chosen.sort(key=lambda item: (item['group'] != 'regional', item['tier'], item['domain']))
    return [item['domain'] for item in chosen[:limit]]


def confidence(source_urls, brand_site='', corroborated_by_both_flows=False, contradicted=False):
    """Selo da oportunidade: alta, media ou baixa (plano v2, "Bases e confiabilidade")."""
    looked = [lookup(url, brand_site) for url in source_urls if url]
    strong = [item for item in looked if item['tier'] in ('A', 'B')]
    independent = {root(item['domain']) for item in strong}
    if contradicted:
        return 'baixa' if not strong else 'media'
    if any(item['primary'] for item in looked) or len(independent) >= 2:
        return 'alta'
    if strong or corroborated_by_both_flows:
        return 'media'
    return 'baixa'
