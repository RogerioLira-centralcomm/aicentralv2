from aicentralv2.cadu_radar import lab_types, prompts


def test_v16_prompt_formats_with_the_runtime_fields():
    messages = prompts.messages('angles', '1.6', today='2026-10-08', payload='{}')
    assert 'CATÁLOGO' in messages[0]['content'] and messages[1]['content'] == '{}'


def test_validate_keeps_only_catalog_channels_and_supported_angles():
    buzz = [{'id': 'B1'}]
    catalog = [{'ref': 'C1', 'id': 10, 'name': 'Globoplay', 'category': 'CTV'}]
    raw = [
        {'tipo': 'midia', 'titulo': 'A', 'buzz': ['B1'], 'objetivo': 'awareness',
         'canais': [{'id': 'C1', 'formato': 'vídeo 30s', 'por_que': 'audiência'}, {'id': 'C9'}]},
        {'tipo': 'conteudo', 'titulo': 'B', 'buzz': ['B7']},
        {'tipo': 'outro', 'titulo': 'C', 'buzz': ['B1'], 'objetivo': 'fama'},
    ]
    kept = lab_types.validate(raw, buzz, catalog)
    assert [item['titulo'] for item in kept] == ['A', 'C']
    assert kept[0]['canais'] == [{'id': 10, 'name': 'Globoplay', 'formato': 'vídeo 30s', 'por_que': 'audiência'}]
    assert kept[0]['canais_invalidos'] == ['C9'] and kept[0]['objetivo'] == 'awareness'
    assert kept[1]['tipo'] is None and kept[1]['objetivo'] is None
