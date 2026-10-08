from aicentralv2.cadu_planner import portal_signals as ps

HTML = """
<header><nav><a href="/politica">Política</a><a href="/economia">Economia</a><a href="/esportes">Esportes</a>
<a href="/saude">Saúde</a><a href="https://outro.com/x">Fora do site</a><a href="/menu">Menu</a></nav></header>
<script>googletag.defineSlot('/1/top', [[970, 250], [728, 90]], 'div-top'); googletag.defineSlot('/1/side', [300, 250], 'div-side');
googletag.defineSlot('/1/mid', [[300, 250]], 'div-mid');</script>
<script src="https://cdn.taboola.com/x.js"></script><div class="publieditorial"></div>
"""


def test_ad_formats_reads_slot_sizes_and_markers():
    result = {item['format']: item for item in ps.ad_formats(HTML)}
    assert result['Billboard']['size'] == '970x250'
    assert result['Leaderboard']['size'] == '728x90'
    assert result['Retângulo médio']['count'] >= 2
    assert 'Nativo (recomendação)' in result and 'Branded content / publieditorial' in result


def test_ad_formats_empty_page_is_empty_list():
    assert ps.ad_formats('') == [] and ps.ad_formats('<p>sem anúncios</p>') == []


def test_menu_sections_keeps_same_site_links_only():
    assert ps.menu_sections(HTML, 'www.exemplo.com.br') == ['Política', 'Economia', 'Esportes', 'Saúde']


def test_attach_formats_links_observed_formats_to_the_iab_catalog(monkeypatch):
    from aicentralv2.cadu_family import repository
    from aicentralv2.cadu_planner import portals
    iab = [{'id': 1, 'slug': 'billboard-970x250', 'nome': 'Billboard (970x250)', 'tipo': 'display', 'dimensoes': '970x250 pixels'},
           {'id': 2, 'slug': 'pre-roll-vast', 'nome': 'Pre-Roll (VAST)', 'tipo': 'video', 'dimensoes': '1920x1080'},
           {'id': 3, 'slug': 'leaderboard-728x90', 'nome': 'Leaderboard (728x90)', 'tipo': 'display', 'dimensoes': '728x90 pixels'}]

    def fake_rows(sql, params=None):
        return iab if "'programatica_iab'" in sql else []
    monkeypatch.setattr(repository, 'rows', fake_rows)
    portal = {'domain': 'exemplo.com.br', 'ad_formats': [{'format': 'Billboard', 'size': '970x250', 'count': 3},
                                                         {'format': 'Vídeo in-stream (VAST/IMA)', 'size': None, 'count': 1},
                                                         {'format': 'Branded content / publieditorial', 'size': None, 'count': 1}]}
    groups = portals.attach_formats(portal)['formats']
    assert [item['label'] for item in groups['observed']] == ['Billboard', 'Vídeo in-stream (VAST/IMA)', 'Branded content / publieditorial']
    assert groups['observed'][0]['linked'] and groups['observed'][1]['linked'] and not groups['observed'][2]['linked']
    assert [item['slug'] for item in groups['market']] == ['leaderboard-728x90']  # what is already shown is not repeated
