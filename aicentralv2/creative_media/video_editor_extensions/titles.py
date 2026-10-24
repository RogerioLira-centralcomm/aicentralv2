"""Texto de título na posição do playhead."""

POSITIONS = {'top': .15, 'center': .5, 'bottom': .82}


def add_title(context, params):
    if not params['text'].strip():
        raise ValueError('Escreva o texto.')
    command = {'op': 'add_text', 'args': {
        'text': params['text'], 'start': params['playhead_seconds'], 'duration': params['duration'],
        'x': .5, 'y': POSITIONS[params['position']], 'size': params['size'], 'color': params['color'] or '#ffffff',
        'background': '#000000' if params['style'] == 'box' else '', 'bold': params['style'] != 'plain'}}
    return [command], f'Título adicionado em {params["playhead_seconds"]:.1f} s.'
