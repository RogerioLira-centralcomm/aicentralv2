"""Describe observed edge traffic without confusing missing data with zero."""


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
}
NODE_PLATFORMS = {'facebook': 'meta', 'instagram': 'meta', 'dv360': 'google', 'organic_search': 'organic',
                  'organic_social': 'social', 'communication': 'email'}
SEARCH_HOSTS = ('google.', 'bing.', 'duckduckgo.', 'yahoo.', 'ecosia.', 'yandex.')
SOCIAL_HOSTS = ('facebook.', 'instagram.', 'linkedin.', 't.co', 'twitter.', 'x.com', 'tiktok.', 'youtube.', 'pinterest.', 'lnkd.in')
PLATFORM_LABELS = {'direct': 'Acesso direto', 'organic': 'Busca orgânica', 'social': 'Redes sociais', 'referral': 'Outros sites',
                   'google': 'Google Ads', 'meta': 'Meta Ads', 'tiktok': 'TikTok Ads', 'linkedin': 'LinkedIn Ads',
                   'youtube': 'YouTube', 'email': 'E-mail', 'whatsapp': 'WhatsApp', 'sms': 'SMS', 'campaign': 'Outras campanhas'}


def origin_platform(origin):
    """Platform of a session origin encoded as 'utm:<source>' or 'ref:<host>'; no origin means direct access."""
    if not origin:
        return 'direct'
    kind, _, value = str(origin).partition(':')
    if kind == 'utm':
        return next((platform for platform, aliases in PLATFORM_ALIASES.items() if value in aliases), 'campaign')
    if any(token in value for token in SEARCH_HOSTS):
        return 'organic'
    if any(token in value for token in SOCIAL_HOSTS):
        return 'social'
    return 'referral'


def node_platform(node):
    platform = node.get('source') or str(node.get('kind') or '').partition('.')[2]
    return NODE_PLATFORMS.get(platform, platform)


def apply_session_bounds(config, nodes, edges, bounds, measured_ids):
    """Fill entrances/exits per page and observed traffic for source nodes, from per-session first/last page rows."""
    if not bounds:
        return
    entrances, exits, by_platform, landing = {}, {}, {}, {}
    for row in bounds:
        sessions = int(row['sessions'] or 0)
        platform = origin_platform(row.get('origin'))
        entrances[row['first_node']] = entrances.get(row['first_node'], 0) + sessions
        exits[row['last_node']] = exits.get(row['last_node'], 0) + sessions
        by_platform[platform] = by_platform.get(platform, 0) + sessions
        landing[(platform, row['first_node'])] = landing.get((platform, row['first_node']), 0) + sessions
    config_nodes = {node.get('id'): node for node in config.get('nodes', []) if isinstance(node, dict)}
    for item in nodes:
        if item['id'] in measured_ids:
            item['entrances'] = entrances.get(item['id'], 0)
            item['exits'] = exits.get(item['id'], 0)
        elif (config_nodes.get(item['id']) or {}).get('type') == 'source':
            item['sessions'] = by_platform.get(node_platform(config_nodes[item['id']]), 0)
            item['estimated_from'] = 'origin'
    totals = {item['id']: item.get('sessions') for item in nodes}
    for edge in edges:
        source = config_nodes.get(edge['from']) or {}
        if source.get('type') != 'source' or edge['to'] not in measured_ids:
            continue
        sessions = landing.get((node_platform(source), edge['to']), 0)
        denominator = totals.get(edge['from']) or 0
        edge['sessions'] = sessions
        edge['rate'] = round(100 * sessions / denominator, 1) if denominator else None
        edge['observation'] = {'status': 'measured' if denominator else 'no_origin', 'sessions': sessions,
                               'rate': edge['rate'], 'denominator': denominator}


def origin_summary(bounds):
    totals = {}
    for row in bounds or []:
        platform = origin_platform(row.get('origin'))
        totals[platform] = totals.get(platform, 0) + int(row['sessions'] or 0)
    return [{'platform': platform, 'label': PLATFORM_LABELS.get(platform, platform), 'sessions': sessions}
            for platform, sessions in sorted(totals.items(), key=lambda item: -item[1])]
