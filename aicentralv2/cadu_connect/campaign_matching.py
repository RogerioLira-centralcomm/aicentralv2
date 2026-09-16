"""Explainable import-to-campaign matching. It never makes the final decision."""
import re


def _key(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).strip()


def candidates(extracted, reports):
    """Return ordered, explainable candidates; ambiguous names stay unresolved."""
    platform = _key(extracted.get('platform'))
    external_id = str(extracted.get('external_campaign_id') or '').strip()
    name = _key(extracted.get('campaign_name'))
    result = []
    for report in reports:
        doc = report.get('document') or {}
        score, reasons = 0, []
        if external_id and external_id == str(doc.get('external_campaign_id') or '').strip():
            score, reasons = 100, ['ID da campanha coincide']
            if platform and platform == _key(doc.get('platform')):
                reasons.append('plataforma coincide')
        elif platform and name and platform == _key(doc.get('platform')) and name == _key(report.get('campaign_name')):
            score, reasons = 70, ['nome e plataforma coincidem']
        elif name and name == _key(report.get('campaign_name')):
            score, reasons = 45, ['nome coincide; plataforma precisa de confirmação']
        if score:
            result.append({'report_id': report['id'], 'campaign_name': report['campaign_name'],
                           'score': score, 'reasons': reasons})
    result.sort(key=lambda item: item['score'], reverse=True)
    if len(result) > 1 and result[0]['score'] == result[1]['score']:
        for item in result: item['ambiguous'] = True
    return result


def recommendation(extracted, reports):
    found = candidates(extracted, reports)
    if len(found) == 1 and found[0]['score'] == 100:
        return {'action': 'update_existing', 'candidate': found[0], 'candidates': found}
    return {'action': 'confirm_match' if found else 'create_or_hold', 'candidate': None, 'candidates': found}
