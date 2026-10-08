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


def test_breakdown_by_type_keeps_legacy_fields():
    from aicentralv2.cadu_radar import angle_types
    media = angle_types.breakdown({'tipo': 'midia', 'objetivo': 'awareness', 'publico': 'p', 'pracas': 'MG', 'periodo': {'inicio': '2026-10-08', 'fim': '2026-11-01'},
                                   'mensagem': 'm', 'canais': [{'id': 5, 'name': 'Globoplay', 'formato': 'vídeo', 'por_que': 'x'}]})
    assert media['type'] == 'midia' and media['media'][0]['id'] == 5 and media['channels'] == ['Globoplay'] and media['formats'] == ['vídeo']
    content = angle_types.breakdown({'tipo': 'conteudo', 'tema': 't', 'formatos': ['artigo'], 'tom': 'leve'})
    assert content['content'] == {'theme': 't', 'message': None, 'formats': ['artigo'], 'tone': 'leve'} and content['formats'] == ['artigo']
    intel = angle_types.breakdown({'tipo': 'inteligencia', 'impacto': 'i', 'observar': 'o'})
    assert intel['impact'] == 'i' and intel['watch'] == 'o' and intel['channels'] == []


def test_period_must_be_valid_and_ordered():
    from aicentralv2.cadu_radar import angle_types
    assert angle_types._period({'inicio': '2026-10-08', 'fim': '2026-10-01'}) == {}
    assert angle_types._period({'inicio': '2026-02-30', 'fim': '2026-03-01'}) == {}
    assert angle_types._period({'inicio': '2026-10-08', 'fim': '2026-10-31'}) == {'inicio': '2026-10-08', 'fim': '2026-10-31'}


def test_chat_prompt_carries_theme_formats_and_sources():
    from aicentralv2.cadu_radar import angle_types
    text = angle_types.chat_prompt({'title': 'Guia da reta final', 'thesis': 'Preparar o corredor.', 'score_breakdown': {
        'why_now': 'São Silvestre abriu inscrições', 'content': {'theme': 'preparação', 'formats': ['artigo', 'carrossel'], 'tone': 'motivador'},
        'buzz': [{'assunto': 'Inscrições abertas', 'veiculo': 'CBN', 'data': '2026-09-25', 'url': 'https://cbn.globo.com/x'}]}},
        brand='Nike', focus='corrida de rua')
    assert text.startswith('Produza o conteúdo desta pauta para Nike, vinda do Radar sobre corrida de rua.')
    assert 'Formatos: artigo, carrossel' in text and 'Tom: motivador' in text and 'https://cbn.globo.com/x' in text


def test_media_angle_becomes_a_filled_plan_payload():
    from aicentralv2.cadu_radar import repository
    item = {'id': 'o1', 'title': 'Reta final', 'thesis': 'Estar presente.', 'geo_scores': [], 'quadrant': None, 'brand_ref': 'b1', 'project_ref': 'p1',
            'score_breakdown': {'type': 'midia', 'objective': 'awareness', 'audience': 'Corredores', 'message': 'Chegue pronto',
                                'places': 'São Paulo', 'period': {'inicio': '2026-10-08', 'fim': '2026-12-31'}, 'why_now': 'Inscrições abertas',
                                'media': [{'id': 5, 'name': 'Globoplay', 'formato': 'vídeo 15s', 'por_que': 'tela grande'}],
                                'buzz': [{'assunto': 'Inscrições', 'veiculo': 'CBN', 'data': '2026-09-25', 'url': 'https://cbn/x'}]}}
    payload = repository.plan_payload(item)
    assert payload['objective'] == 'awareness' and payload['project_ref'] == 'p1'
    assert payload['briefing']['period'] == '08/10/2026 a 31/12/2026' and payload['briefing']['geography'] == 'São Paulo'
    notes = payload['briefing']['notes']
    assert 'Público: Corredores' in notes and '- Globoplay (vídeo 15s): tela grande' in notes and 'https://cbn/x' in notes


def test_legacy_angle_keeps_the_old_plan_payload():
    from aicentralv2.cadu_radar import repository
    item = {'id': 'o2', 'title': 'Ideia', 'thesis': 't', 'geo_scores': [{'place': 'MG'}], 'quadrant': None, 'brand_ref': None, 'project_ref': None,
            'score_breakdown': {'formats': ['carrossel'], 'channels': ['Instagram']}}
    payload = repository.plan_payload(item)
    assert payload['objective'] == 'consideracao' and payload['briefing']['geography'] == 'MG' and 'period' not in payload['briefing']
    assert 'Canais sugeridos pelo Radar: Instagram' in payload['briefing']['notes']
