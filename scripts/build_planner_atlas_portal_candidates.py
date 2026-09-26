"""Build a review-only CSV of portal candidates from the Atlas da Notícia API.

This script does not write to the Planner database. All rows are explicitly
marked pending editorial validation and contain no audience estimates/rankings.
"""
import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


API = 'https://api.atlas.jor.br/api/v1'
API_DOCS = 'https://atlas.jor.br/api/documentacao-da-api/'
STATES = ('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO').split()
FIELDS = ('id', 'nome_veiculo', 'segmento', 'cidade', 'estado', 'regiao', 'ativo',
          'media_channels', 'business_models', 'features')
CSV_FIELDS = ('name', 'domain', 'category', 'description', 'audience_estimate',
              'audience_period', 'audience_source_url', 'audience_checked_at',
              'public_attributes', 'featured_rank')
USER_AGENT = 'CaduPlannerResearch/1.0 (public-source dataset preparation)'


def get_json(path, token=None):
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = Request(f'{API}{path}', headers=headers)
    with urlopen(request, timeout=60) as response:
        body = response.read(50_000_001)
    if len(body) > 50_000_000:
        raise RuntimeError('Atlas API response exceeded 50 MB safety limit.')
    return json.loads(body)


def normalize_site(value):
    value = str(value or '').strip()
    if not value:
        return None
    parsed = urlparse(value if '://' in value else 'https://' + value)
    host = (parsed.hostname or '').lower().rstrip('.')
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {'http', 'https'} or not host:
        return None
    if parsed.username or parsed.password or port not in (None, 80, 443):
        return None
    if host.startswith('www.'):
        host = host[4:]
    try:
        host = host.encode('idna').decode('ascii')
    except UnicodeError:
        return None
    if not re.fullmatch(r'[a-z0-9.-]{1,255}', host) or '..' in host:
        return None
    return host, parsed.geturl()


def get_site_channel(row):
    channels = row.get('media_channels') or []
    candidates = []
    if isinstance(channels, list):
        for item in channels:
            channel = item.get('channel') or {}
            if str(channel.get('name') or '').strip().lower() != 'site':
                continue
            site = normalize_site(item.get('link'))
            if site:
                candidates.append(site)
    if not candidates:
        return None
    # The Atlas 'Site' channel is the primary directory evidence; prefer HTTPS
    # if multiple website entries were recorded for one outlet.
    return sorted(candidates, key=lambda item: (item[1].startswith('https://'), item[0]), reverse=True)[0]


def relation_names(values):
    if not isinstance(values, list):
        return []
    return sorted({str(item.get('name')).strip() for item in values
                   if isinstance(item, dict) and item.get('name')})


def allocate_quotas(counts, limit):
    quotas = {key: 0 for key in counts}
    remaining = min(limit, sum(counts.values()))
    while remaining:
        available = {key: count - quotas[key] for key, count in counts.items()
                     if count > quotas[key]}
        total = sum(available.values())
        if not total:
            break
        shares = {key: remaining * count / total for key, count in available.items()}
        additions = {key: min(available[key], math.floor(share))
                     for key, share in shares.items()}
        placed = sum(additions.values())
        for key, amount in additions.items():
            quotas[key] += amount
        remaining -= placed
        if remaining:
            order = sorted((key for key in available if quotas[key] < counts[key]),
                           key=lambda key: (-(shares[key] - math.floor(shares[key])), key))
            for key in order[:remaining]:
                quotas[key] += 1
                remaining -= 1
    return quotas


def candidate_score(candidate):
    # Completeness/transparency signal only; this is not an audience estimate,
    # editorial-quality score or a ranking of the 200 leading publishers.
    return (candidate['verified_criteria'], candidate['https'],
            len(candidate['business_models']), len(candidate['features']))


def build_candidates(limit):
    if not 600 <= limit <= 1500:
        raise ValueError('--limit precisa estar entre 600 e 1500.')
    token = get_json('/auth/dummy-jwt').get('access_token')
    if not token:
        raise RuntimeError('Atlas API did not return a public dummy JWT.')

    verified = get_json('/media/verified')
    verified_by_id = {str(item['id']): item for item in verified if item.get('id') is not None}
    params = [('estado[]', state) for state in STATES]
    params += [('ativo', '1'), ('segmento', 'Online')]
    params += [('field[]', field) for field in FIELDS]
    rows = get_json('/data/analytic?' + urlencode(params), token)
    if not isinstance(rows, list):
        raise RuntimeError('Unexpected Atlas analytic response.')

    unique = {}
    for row in rows:
        if row.get('ativo') not in (1, '1', True) or str(row.get('segmento') or '').strip().lower() != 'online':
            continue
        site = get_site_channel(row)
        if not site or not row.get('nome_veiculo') or not row.get('estado'):
            continue
        domain, site_url = site
        verified_item = verified_by_id.get(str(row.get('id')), {})
        criteria = []
        for key, value in verified_item.items():
            if key.endswith('_url') and value and verified_item.get(key[:-4]) == 'sim':
                criteria.append({'criterio': key[:-4], 'url': value})
        candidate = {
            'name': str(row['nome_veiculo']).strip()[:180], 'domain': domain,
            'site_url': site_url, 'city': str(row.get('cidade') or '').strip(),
            'state': str(row.get('estado') or '').strip().upper(),
            'region': str(row.get('regiao') or '').strip(),
            'business_models': relation_names(row.get('business_models')),
            'features': relation_names(row.get('features')),
            'verified_criteria': int(verified_item.get('criterios') or 0),
            'criteria_evidence': criteria,
            'atlas_id': row.get('id'),
            'https': site_url.startswith('https://'),
        }
        current = unique.get(domain)
        if current is None or candidate_score(candidate) > candidate_score(current):
            unique[domain] = candidate

    by_state = {}
    for candidate in unique.values():
        by_state.setdefault(candidate['state'], []).append(candidate)
    quotas = allocate_quotas({state: len(values) for state, values in by_state.items()}, limit)
    selected = []
    for state in sorted(by_state):
        candidates = sorted(by_state[state], key=lambda item: (
            tuple(-part for part in candidate_score(item)), item['name'].casefold(), item['domain']))
        selected.extend(candidates[:quotas[state]])
    return selected, {'online_active_records': len(rows), 'unique_websites': len(unique),
                      'selected': len(selected), 'verified': sum(bool(x['verified_criteria']) for x in selected),
                      'state_quotas': quotas}


def write_csv(candidates, output):
    observed_at = datetime.now(timezone.utc).isoformat()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8-sig', newline='') as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            attributes = [
                {'atributo': 'status_curadoria', 'valor': 'pendente_validacao_editorial'},
                {'atributo': 'fonte_cadastro', 'valor': 'Atlas da Notícia — API pública',
                 'source_url': API_DOCS},
                {'atributo': 'atlas_media_id', 'valor': candidate['atlas_id']},
                {'atributo': 'segmento_atlas', 'valor': 'Online'},
                {'atributo': 'localizacao', 'valor': ' · '.join(filter(None, (
                    candidate['city'], candidate['state'], candidate['region']))),
                 'source_url': API_DOCS},
                {'atributo': 'canal_site_atlas', 'valor': candidate['site_url'],
                 'source_url': API_DOCS},
                {'atributo': 'https_anunciado_pelo_veiculo', 'valor': candidate['https']},
                {'atributo': 'domain_status', 'valor': 'candidato_pendente_de_crawl_e_revisao'},
                {'atributo': 'coletado_em', 'valor': observed_at},
            ]
            if candidate['business_models']:
                attributes.append({'atributo': 'modelos_de_negocio_declarados',
                                   'valor': candidate['business_models'],
                                   'source_url': API_DOCS})
            if candidate['features']:
                attributes.append({'atributo': 'caracteristicas_declaradas',
                                   'valor': candidate['features'],
                                   'source_url': API_DOCS})
            if candidate['verified_criteria']:
                attributes.append({'atributo': 'criterios_de_transparencia_atlas',
                                   'valor': candidate['verified_criteria'],
                                   'source_url': API + '/media/verified'})
                attributes.extend({'atributo': item['criterio'], 'valor': 'sim',
                                   'source_url': item['url']}
                                  for item in candidate['criteria_evidence'])
            region = candidate['region'] or 'Região não informada'
            description = (f"Veículo do segmento online no Atlas da Notícia; "
                           f"localização: {candidate['city']}, {candidate['state']}. "
                           'Candidato pendente de validação de domínio e curadoria.')
            writer.writerow({
                'name': candidate['name'], 'domain': candidate['domain'],
                'category': f'Jornalismo online · {region}', 'description': description,
                'audience_estimate': '', 'audience_period': '', 'audience_source_url': '',
                'audience_checked_at': '', 'public_attributes': json.dumps(
                    attributes, ensure_ascii=False, separators=(',', ':')),
                'featured_rank': '',
            })
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--output', default='tmp/planner-portais-atlas-candidatos.csv')
    args = parser.parse_args()
    candidates, summary = build_candidates(args.limit)
    output = write_csv(candidates, args.output)
    print(json.dumps({**summary, 'output': str(output)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
