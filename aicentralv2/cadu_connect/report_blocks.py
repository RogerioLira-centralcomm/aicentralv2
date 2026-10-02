"""Report document blocks: order, titles and visibility of what a report shows (inside and on the public link).

Built-in blocks read data (results, funnel, campaigns) or the classic fields (objective, goals, notes);
text blocks carry their own text. Documents without blocks get the default order.
"""
import re

DATA_BLOCKS = {'results': 'Resultados', 'funnel': 'Da mídia à conversão', 'campaigns': 'Campanhas'}
FIELD_BLOCKS = {'objective': 'Objetivo', 'goals': 'Metas', 'notes': 'Contexto de gestão'}
TEXT_TYPES = {'text': 'Texto', 'recommendations': 'Recomendações', 'next_steps': 'Próximos passos'}
BUILTIN = {**DATA_BLOCKS, **FIELD_BLOCKS}
MAX_BLOCKS = 30
MAX_TEXT = 8000


def default_blocks(document=None):
    document = document if isinstance(document, dict) else {}
    flow = document.get('scope') == 'flow'
    return [{'id': key, 'type': key, 'title': title, 'hidden': key == 'funnel' and not flow}
            for key, title in BUILTIN.items()]


def blocks_of(document):
    """Blocks to render: the saved ones, plus any built-in block a saved list predates (appended hidden)."""
    document = document if isinstance(document, dict) else {}
    saved = document.get('blocks')
    if not isinstance(saved, list) or not saved:
        return default_blocks(document)
    present = {block.get('type') for block in saved if isinstance(block, dict)}
    missing = [{**block, 'hidden': True} for block in default_blocks(document) if block['type'] not in present]
    return [block for block in saved if isinstance(block, dict)] + missing


def validate_blocks(value):
    """Clean list of blocks or ValueError. Built-ins appear once; text blocks need an id of their own."""
    if not isinstance(value, list) or not value or len(value) > MAX_BLOCKS:
        raise ValueError(f'Envie de 1 a {MAX_BLOCKS} blocos.')
    clean, ids, builtins = [], set(), set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Bloco inválido.')
        kind = item.get('type')
        if kind not in BUILTIN and kind not in TEXT_TYPES:
            raise ValueError('Tipo de bloco inválido.')
        block_id = kind if kind in BUILTIN else str(item.get('id') or '')
        if not re.fullmatch(r'[a-z0-9-]{1,40}', block_id) or block_id in ids:
            raise ValueError('Identificador de bloco inválido ou repetido.')
        if kind in BUILTIN:
            if kind in builtins:
                raise ValueError('Bloco repetido.')
            builtins.add(kind)
        title = ' '.join(str(item.get('title') or '').split())[:120] or BUILTIN.get(kind) or TEXT_TYPES[kind]
        hidden = item.get('hidden', False)
        if not isinstance(hidden, bool):
            raise ValueError('Visibilidade inválida.')
        block = {'id': block_id, 'type': kind, 'title': title, 'hidden': hidden}
        if kind in TEXT_TYPES:
            text = item.get('text') or ''
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                raise ValueError(f'O texto de cada bloco tem até {MAX_TEXT} caracteres.')
            block['text'] = text.strip()
        ids.add(block_id)
        clean.append(block)
    return clean


def version_changes(before, after):
    """What changed between two documents, per field and per block, for the version comparison."""
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    changes = []
    for field, label in (('objective', 'Objetivo'), ('goals', 'Metas'), ('management_notes', 'Contexto de gestão'),
                         ('start_date', 'Início'), ('end_date', 'Fim')):
        if (before.get(field) or '') != (after.get(field) or ''):
            changes.append({'kind': 'field', 'label': label, 'before': before.get(field) or '', 'after': after.get(field) or ''})
    old = {block['id']: block for block in blocks_of(before)}
    new = {block['id']: block for block in blocks_of(after)}
    for block_id, block in new.items():
        prior = old.get(block_id)
        if not prior:
            changes.append({'kind': 'added', 'label': block['title'], 'before': '', 'after': block.get('text', '')})
        elif prior.get('text', '') != block.get('text', '') or prior['title'] != block['title']:
            changes.append({'kind': 'block', 'label': block['title'], 'before': prior.get('text', '') or prior['title'],
                            'after': block.get('text', '') or block['title']})
        elif prior.get('hidden') != block.get('hidden'):
            changes.append({'kind': 'visibility', 'label': block['title'], 'before': 'oculto' if prior.get('hidden') else 'visível',
                            'after': 'oculto' if block.get('hidden') else 'visível'})
    for block_id, block in old.items():
        if block_id not in new:
            changes.append({'kind': 'removed', 'label': block['title'], 'before': block.get('text', ''), 'after': ''})
    if [block['id'] for block in blocks_of(before)] != [block['id'] for block in blocks_of(after)] and not any(
            change['kind'] in ('added', 'removed') for change in changes):
        changes.append({'kind': 'order', 'label': 'Ordem dos blocos', 'before': '', 'after': ''})
    return changes
