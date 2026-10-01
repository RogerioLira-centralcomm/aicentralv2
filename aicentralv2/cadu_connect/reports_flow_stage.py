"""Stage labels for editable flow documents. Positions are free: the stage never forces a column."""

STAGES = ('source', 'entry', 'exploration', 'intent', 'conversion', 'support')


def normalize_stage(node):
    item = dict(node)
    stage = item.get('stage')
    if item.get('type') == 'source':
        stage = 'source'
    elif item.get('type') == 'page' and stage == 'source':
        stage = 'entry' if item.get('isEntry') or item.get('path') == '/' else 'exploration'
    if stage in STAGES:
        item['stage'] = stage
    return item
