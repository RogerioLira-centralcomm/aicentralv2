"""Safe campaign draft generated from an import; never auto-creates a campaign."""
from .import_recognition import recognize_platform


def campaign_draft(item):
    source = recognize_platform(item.get('supplier'), item.get('original_name'))
    name = str(item.get('original_name') or '').rsplit('.', 1)[0].replace('_', ' ').strip()
    return {
        'campaign_name': name[:200],
        'platform': '' if source['platform'] == 'Não identificado' else source['platform'],
        'start_date': item.get('period_start').isoformat() if item.get('period_start') else '',
        'end_date': item.get('period_end').isoformat() if item.get('period_end') else '',
        'supplier': str(item.get('supplier') or '')[:200],
        'requires_confirmation': ['project_ref', 'objective', 'goals'],
    }
