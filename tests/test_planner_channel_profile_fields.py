from aicentralv2.cadu_planner import catalog, channels


def _channel():
    return {'id': 7, 'slug': 'spotify', 'name': 'Spotify', 'categoria': 'Streaming', 'descricao': 'Áudio.',
            'alcance': '+56M usuários BR', 'perfil_audiencia': 'Plataforma massiva de streaming.', 'melhor_uso': 'Alcance em áudio.',
            'fontes_metricas': {'perfil': {'pesquisado_em': '2026-10-06'}},
            'investimento_minimo': 'não pode sair', 'prazo_entrega': 'interno', 'integracao': 'interno'}


def _stub(monkeypatch):
    monkeypatch.setattr(channels, 'detail', lambda _id: _channel())
    monkeypatch.setattr(channels, 'related_media', lambda _c: ([], []))
    monkeypatch.setattr(channels, 'activation_concepts', lambda _c: [])
    monkeypatch.setattr(channels, 'formats', lambda _c: [])
    monkeypatch.setattr(channels, 'news', lambda _id: [])
    monkeypatch.setattr(channels, 'related', lambda _c, limit=6: [{'id': 8, 'name': 'Deezer'}])
    monkeypatch.setattr(catalog, 'channel_roles', lambda _c: [])
    monkeypatch.setattr(catalog, 'channel_audiences', lambda _c: [])


def test_channel_profile_exposes_public_summary_and_related_but_not_internal_fields(monkeypatch):
    _stub(monkeypatch)
    profile = catalog.channel_profile(7)
    assert profile['perfil_audiencia'] == 'Plataforma massiva de streaming.'
    assert profile['melhor_uso'] == 'Alcance em áudio.'
    assert profile['fontes_metricas']['perfil']['pesquisado_em'] == '2026-10-06'
    assert profile['related'] == [{'id': 8, 'name': 'Deezer'}]
    for hidden in ('investimento_minimo', 'prazo_entrega', 'integracao'):
        assert hidden not in profile


def test_related_skips_hidden_categories(monkeypatch):
    called = []
    monkeypatch.setattr(channels, '_rows', lambda *a, **k: called.append(a) or [])
    assert channels.related({'id': 1, 'categoria': 'Portais'}) == []
    assert not called
