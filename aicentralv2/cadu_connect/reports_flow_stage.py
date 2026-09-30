"""Conservative stage coordinates for editable flow documents."""

STAGES = ('source', 'entry', 'exploration', 'intent', 'conversion', 'support')


def normalize_stage_position(node):
    item = dict(node)
    stage = item.get('stage')
    if item.get('type') == 'source':
        stage = 'source'
    elif item.get('type') == 'page' and stage == 'source':
        stage = 'entry' if item.get('isEntry') or item.get('path') == '/' else 'exploration'
    if stage in STAGES:
        item['stage'] = stage
        item['x'] = 80 + STAGES.index(stage) * 320
    return item
