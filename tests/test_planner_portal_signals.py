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
