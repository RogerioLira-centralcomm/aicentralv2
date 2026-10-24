"""Legendas a partir da fala de uma mídia do projeto, com o Whisper local do worker."""


def auto_captions(context, params):
    from ..studio_tasks import transcribe
    timeline = context['timeline']
    if not isinstance(timeline, dict):
        raise ValueError('Abra o editor neste projeto antes de gerar legendas.')
    asset_id = params['asset']
    link = context['links'].get(asset_id)
    if not link or link['type'] not in {'video', 'audio'}:
        raise ValueError('Escolha um vídeo ou áudio do projeto.')
    placements = [element for scene in timeline['scenes'] for track in [*scene['tracks']['overlay'], scene['tracks']['main'], *scene['tracks']['audio']]
                  for element in track['elements'] if element.get('mediaId') == asset_id]
    if not placements:
        raise ValueError('Coloque essa mídia na timeline antes de legendar.')
    path, _, _ = context['resolve'](link['ref'])
    speech = transcribe(path)
    position = {'top': .15, 'center': .5, 'bottom': .82}[params['position']]
    commands = []
    for element in placements:
        start, trim = element['startTime'] / 120_000, element['trimStart'] / 120_000
        end = start + element['duration'] / 120_000
        for caption in speech['captions']:
            at = start + caption['start'] - trim
            until = min(end, start + caption['end'] - trim)
            if until <= start or at >= end:
                continue
            commands.append({'op': 'add_text', 'args': {
                'text': caption['text'], 'start': max(start, at), 'duration': until - max(start, at), 'x': .5, 'y': position,
                'size': params['size'], 'color': '#ffffff', 'background': '#000000' if params['style'] == 'box' else '', 'bold': True,
                'name': 'Legenda'}})
    if not commands:
        raise ValueError('Nenhuma fala reconhecida no trecho usado.')
    # Todas as legendas na mesma faixa: a primeira cria, as demais reutilizam a faixa anterior.
    for command in commands[1:]:
        command['args']['track_id'] = '@previous'
    return commands, f'{len(commands)} legendas ({speech.get("language") or "idioma detectado"}).'
