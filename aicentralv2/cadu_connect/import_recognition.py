"""Conservative source classification; never binds a campaign automatically."""
import re

PLATFORMS = (
    ('Meta Ads', ('meta ads', 'facebook ads', 'instagram ads', 'ads manager')),
    ('Google Ads', ('google ads', 'adwords', 'googleads')),
    ('Looker Studio', ('looker studio', 'datastudio', 'data studio')),
    ('Google Drive', ('google drive', 'drive.google.com', 'sheets.google', 'google sheets')),
    ('TikTok Ads', ('tiktok ads', 'tiktokads')),
)


def recognize_platform(*values):
    text = ' '.join(str(value or '').casefold() for value in values)
    text = re.sub(r'[_\-.]+', ' ', text)
    matches = [label for label, aliases in PLATFORMS if any(alias in text for alias in aliases)]
    return {'platform': matches[0] if len(matches) == 1 else 'Não identificado',
            'confidence': 'high' if len(matches) == 1 else 'low'}
