"""Describe observed edge traffic without confusing missing data with zero."""
import re
import unicodedata

# Session origins are encoded as 'utm:<source>|<campaign>' or 'ref:<host>'; older rows carry only 'utm:<source>'.
# Engine id -> (label, registrable domains). Matching is by domain suffix, not substring, so
# mail.google.com or a site that merely contains "bing." in its name are not search engines.
SEARCH_ENGINES = {
    'google': ('Google', ('google.com', 'google.com.br', 'google.pt', 'google.co.uk', 'google.es', 'google.de', 'google.fr', 'google.it', 'google.ca', 'google.com.ar', 'google.com.mx', 'google.cl', 'google.co')),
    'bing': ('Bing', ('bing.com',)),
    'yahoo': ('Yahoo', ('yahoo.com', 'search.yahoo.com', 'br.search.yahoo.com')),
    'duckduckgo': ('DuckDuckGo', ('duckduckgo.com',)),
    'ecosia': ('Ecosia', ('ecosia.org',)),
    'yandex': ('Yandex', ('yandex.ru', 'yandex.com')),
    'baidu': ('Baidu', ('baidu.com',)),
    'brave': ('Brave Search', ('search.brave.com',)),
}
SEARCH_ENGINE_IDS = tuple(SEARCH_ENGINES)
# AI assistants that send visitors (a link in an answer). ChatGPT adds utm_source=chatgpt.com itself; the others arrive by referrer.
# Checked before search engines: gemini.google.com is a Google domain but is not a search result.
AI_AGENTS = {
    'chatgpt': ('ChatGPT', ('chatgpt.com', 'chat.openai.com', 'openai.com'), {'chatgpt', 'openai'}),
    'gemini': ('Gemini', ('gemini.google.com', 'bard.google.com'), {'gemini', 'bard'}),
    'claude': ('Claude', ('claude.ai',), {'claude', 'anthropic'}),
}


def ai_agent_for(value):
    """AI agent id of a referrer host or utm_source value, or None."""
    value = str(value or '').lower().strip(' .').removeprefix('www.')
    for agent, (_, domains, names) in AI_AGENTS.items():
        if value in names or any(value == domain or value.endswith('.' + domain) for domain in domains):
            return agent
    return None

# Subdomains of an engine's domain that are not search results.
NOT_SEARCH = ('mail.', 'accounts.', 'docs.', 'drive.', 'maps.', 'play.', 'support.', 'news.', 'calendar.')


def search_engine_for_host(host):
    """Engine id of a referrer host, or None."""
    host = str(host or '').lower().strip('.')
    if not host or host.startswith(NOT_SEARCH):
        return None
    for engine, (_, domains) in SEARCH_ENGINES.items():
        for domain in domains:
            if host == domain or host.endswith('.' + domain):
                return engine
    return None


def parse_origin(origin):
    """(kind, source_or_host, campaign) of an encoded origin; kind is None for direct access."""
    if not origin:
        return None, '', ''
    kind, _, value = str(origin).partition(':')
    if kind == 'utm':
        source, _, campaign = value.partition('|')
        return 'utm', source.lower(), campaign.lower()
    return kind, value.lower(), ''


def search_engine_label(engine):
    return SEARCH_ENGINES.get(engine, (engine,))[0]


def utm_token(value):
    """Comparable form of a UTM value: 'Lançamento Out' and 'lancamento-out' are the same campaign."""
    text = unicodedata.normalize('NFD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9._]+', '-', text).strip('-')



def edge_observation(edge, measured_ids, node_totals, transition_totals, has_events):
    source, target = edge['from'], edge['to']
    if source not in measured_ids or target not in measured_ids:
        return {'status': 'unmeasured', 'sessions': None, 'rate': None, 'denominator': None}
    if not has_events:
        return {'status': 'no_data', 'sessions': None, 'rate': None, 'denominator': None}
    denominator = int(node_totals.get(source, {}).get('sessions') or 0)
    sessions = int(transition_totals.get((source, target), 0))
    return {'status': 'measured' if denominator else 'no_origin',
            'sessions': sessions, 'rate': round(100 * sessions / denominator, 1) if denominator else None,
            'denominator': denominator}


# Aliases accepted for each traffic platform a source node can represent.
PLATFORM_ALIASES = {
    'google': {'google', 'googleads', 'google_ads', 'adwords', 'gads', 'google-ads'},
    'meta': {'facebook', 'fb', 'meta', 'instagram', 'ig', 'facebook_ads', 'meta_ads'},
    'tiktok': {'tiktok', 'tiktok_ads'}, 'linkedin': {'linkedin', 'linkedin_ads', 'lnkd'},
    'youtube': {'youtube', 'yt'}, 'email': {'email', 'e-mail', 'newsletter', 'mailchimp', 'rdstation', 'hubspot'},
    'whatsapp': {'whatsapp', 'wa'}, 'sms': {'sms'},
    **{agent: {*names, *domains} for agent, (_, domains, names) in AI_AGENTS.items()},
}
NODE_PLATFORMS = {'facebook': 'meta', 'instagram': 'meta', 'dv360': 'google', 'organic_search': 'organic',
                  'organic_social': 'social', 'communication': 'email'}
SOCIAL_HOSTS = ('facebook.', 'instagram.', 'linkedin.', 't.co', 'twitter.', 'x.com', 'tiktok.', 'youtube.', 'pinterest.', 'lnkd.in')
PLATFORM_LABELS = {'direct': 'Acesso direto', 'organic': 'Busca orgânica', 'social': 'Redes sociais', 'referral': 'Outros sites',
                   'google': 'Google Ads', 'meta': 'Meta Ads', 'tiktok': 'TikTok Ads', 'linkedin': 'LinkedIn Ads',
                   'youtube': 'YouTube', 'email': 'E-mail', 'whatsapp': 'WhatsApp', 'sms': 'SMS', 'campaign': 'Outras campanhas',
                   **{agent: label for agent, (label, _, _) in AI_AGENTS.items()}}


def origin_platform(origin):
    """Platform of a session origin encoded as 'utm:<source>[|<campaign>]' or 'ref:<host>'; no origin means direct access."""
    kind, value, _ = parse_origin(origin)
    if kind is None:
        return 'direct'
    if kind == 'utm':
        return next((platform for platform, aliases in PLATFORM_ALIASES.items() if value in aliases), 'campaign')
    if ai_agent_for(value):
        return ai_agent_for(value)
    if search_engine_for_host(value):
        return 'organic'
    if any(token in value for token in SOCIAL_HOSTS):
        return 'social'
    return 'referral'


def node_platform(node):
    platform = node.get('source') or str(node.get('kind') or '').partition('.')[2]
    return NODE_PLATFORMS.get(platform, platform)


def node_search_engines(node):
    engines = node.get('search_engines')
    return set(engines) if isinstance(engines, list) and engines else None


def sources_by_platform(config_nodes):
    grouped = {}
    for node in config_nodes:
        if isinstance(node, dict) and node.get('type') == 'source':
            grouped.setdefault(node_platform(node), []).append(node)
    return grouped


def resolve_source(origin, candidates):
    """The drawn origin a session belongs to, or None when no single node can claim it.

    Two Instagram origins are told apart by the UTM fields the user set on each; a field left
    blank accepts any value. Search origins are told apart by the engines they cover.
    """
    if not candidates:
        return None
    kind, value, campaign = parse_origin(origin)
    if kind == 'ref' and search_engine_for_host(value):
        engine = search_engine_for_host(value)
        matches = [node for node in candidates if node_search_engines(node) is None or engine in node_search_engines(node)]
        return matches[0] if len(matches) == 1 else None
    if kind != 'utm':
        return candidates[0] if len(candidates) == 1 else None
    scored = []
    for node in candidates:
        utm = (node.get('media') or {}).get('utm') or {}
        explicit_source, explicit_campaign = utm_token(utm.get('source')), utm_token(utm.get('campaign'))
        if (explicit_source and explicit_source != utm_token(value)) or (explicit_campaign and explicit_campaign != utm_token(campaign)):
            continue
        score = bool(explicit_source) + bool(explicit_campaign) * 2 + (0.5 if str(node.get('source') or '').lower() == value else 0)
        scored.append((score, node))
    if not scored:
        return None
    best = max(score for score, _ in scored)
    winners = [node for score, node in scored if score == best]
    return winners[0] if len(winners) == 1 else None


def apply_session_bounds(config, nodes, edges, bounds, measured_ids):
    """Fill entrances/exits per page and observed traffic per source node, from per-session first/last page rows.

    Each session is credited to one source node at most; sessions of a drawn platform that no node can
    claim are returned as unattributed instead of being counted on every node of that platform.
    """
    if not bounds:
        return []
    config_nodes = {node.get('id'): node for node in config.get('nodes', []) if isinstance(node, dict)}
    grouped = sources_by_platform(config_nodes.values())
    entrances, exits, by_source, landing, engines, unattributed = {}, {}, {}, {}, {}, {}
    for row in bounds:
        sessions = int(row['sessions'] or 0)
        entrances[row['first_node']] = entrances.get(row['first_node'], 0) + sessions
        exits[row['last_node']] = exits.get(row['last_node'], 0) + sessions
        platform = origin_platform(row.get('origin'))
        if platform not in grouped:
            continue
        source = resolve_source(row.get('origin'), grouped[platform])
        if platform == 'organic':
            engine = search_engine_for_host(parse_origin(row.get('origin'))[1]) or 'other'
            bucket = engines.setdefault(source['id'] if source else None, {})
            bucket[engine] = bucket.get(engine, 0) + sessions
        if source is None:
            unattributed[platform] = unattributed.get(platform, 0) + sessions
            continue
        by_source[source['id']] = by_source.get(source['id'], 0) + sessions
        landing[(source['id'], row['first_node'])] = landing.get((source['id'], row['first_node']), 0) + sessions
    for item in nodes:
        if item['id'] in measured_ids:
            item['entrances'] = entrances.get(item['id'], 0)
            item['exits'] = exits.get(item['id'], 0)
        elif (config_nodes.get(item['id']) or {}).get('type') == 'source':
            item['sessions'] = by_source.get(item['id'], 0)
            item['estimated_from'] = 'origin'
            if item['id'] in engines:
                item['search_engines'] = [{'engine': engine, 'label': search_engine_label(engine) if engine != 'other' else 'Outros buscadores', 'sessions': count}
                                          for engine, count in sorted(engines[item['id']].items(), key=lambda pair: -pair[1])]
    totals = {item['id']: item.get('sessions') for item in nodes}
    for edge in edges:
        source = config_nodes.get(edge['from']) or {}
        if source.get('type') != 'source' or edge['to'] not in measured_ids:
            continue
        sessions = landing.get((edge['from'], edge['to']), 0)
        denominator = totals.get(edge['from']) or 0
        edge['sessions'] = sessions
        edge['rate'] = round(100 * sessions / denominator, 1) if denominator else None
        edge['observation'] = {'status': 'measured' if denominator else 'no_origin', 'sessions': sessions,
                               'rate': edge['rate'], 'denominator': denominator}
    unmatched_engines = engines.get(None, {})
    return [{'platform': platform, 'label': f"{PLATFORM_LABELS.get(platform, platform)} · sem origem identificada", 'sessions': count,
             **({'search_engines': [{'engine': engine, 'label': search_engine_label(engine) if engine != 'other' else 'Outros buscadores', 'sessions': value}
                                    for engine, value in sorted(unmatched_engines.items(), key=lambda pair: -pair[1])]} if platform == 'organic' else {})}
            for platform, count in sorted(unattributed.items(), key=lambda pair: -pair[1])]


def origin_summary(bounds):
    totals, engines = {}, {}
    for row in bounds or []:
        platform = origin_platform(row.get('origin'))
        sessions = int(row['sessions'] or 0)
        totals[platform] = totals.get(platform, 0) + sessions
        if platform == 'organic':
            engine = search_engine_for_host(parse_origin(row.get('origin'))[1]) or 'other'
            engines[engine] = engines.get(engine, 0) + sessions
    return [{'platform': platform, 'label': PLATFORM_LABELS.get(platform, platform), 'sessions': sessions,
             **({'search_engines': [{'engine': engine, 'label': search_engine_label(engine) if engine != 'other' else 'Outros buscadores', 'sessions': count}
                                    for engine, count in sorted(engines.items(), key=lambda pair: -pair[1])]} if platform == 'organic' else {})}
            for platform, sessions in sorted(totals.items(), key=lambda item: -item[1])]


def apply_engagement(nodes, active_rows, depth_row, measured_ids):
    """Average active time per page and pages per session; None means not measured, never zero."""
    by_node = {str(row['node_id']): row for row in active_rows or []}
    weighted, leaves = 0, 0
    for item in nodes:
        row = by_node.get(item['id'])
        if item['id'] in measured_ids and row:
            item['avg_active_ms'] = int(row['avg_active_ms'] or 0)
            weighted += int(row['avg_active_ms'] or 0) * int(row['leaves'] or 0)
            leaves += int(row['leaves'] or 0)
    pages = (depth_row or {}).get('pages_per_session')
    return {'avg_active_ms': round(weighted / leaves) if leaves else None,
            'pages_per_session': float(pages) if pages is not None else None}


def origin_landings(bounds, config):
    """Where each origin lands, flagged when no source node of the flow can claim it.

    The map only shows the sources someone planned; visitors also arrive direct, from other sites, from
    campaigns nobody drew, or with a UTM that matches none of the drawn origins of their channel.
    """
    grouped = sources_by_platform(config.get('nodes', []))
    totals, unclaimed_drawn = {}, set()
    for row in bounds or []:
        platform = origin_platform(row.get('origin'))
        claimed = resolve_source(row.get('origin'), grouped.get(platform)) is not None
        if not claimed and platform in grouped:
            unclaimed_drawn.add(platform)
        key = (platform, claimed, row['first_node'])
        totals[key] = totals.get(key, 0) + int(row['sessions'] or 0)
    return [{'platform': platform,
             'label': PLATFORM_LABELS.get(platform, platform) + (' · sem origem identificada' if platform in unclaimed_drawn and not claimed else ''),
             'node_id': node_id, 'sessions': sessions, 'drawn': claimed}
            for (platform, claimed, node_id), sessions in sorted(totals.items(), key=lambda item: -item[1])
            if node_id is not None]
