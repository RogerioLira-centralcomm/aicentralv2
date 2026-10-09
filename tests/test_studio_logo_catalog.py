"""Logos oficiais de terceiros citados no pedido: nome completo vence apelido, ordem do pedido, sem host genérico."""
from aicentralv2.creative_media import logo_catalog as lc

ENTRIES = [
    {'name': 'UOL', 'names': lc._names({'name': 'UOL', 'domain': 'uol.com.br'}), 'path': ''},
    {'name': 'Exame', 'names': lc._names({'name': 'Exame', 'domain': 'exame.com'}), 'path': ''},
    {'name': 'Valor Econômico', 'names': lc._names({'name': 'Valor Econômico', 'domain': 'valor.globo.com'}), 'path': ''},
    {'name': 'VALOR.COM.BR', 'names': lc._names({'name': 'VALOR.COM.BR', 'domain': 'valor.com.br'}), 'path': ''},
    {'name': 'Blog qualquer', 'names': lc._names({'name': 'Blog qualquer', 'domain': 'google.com'}), 'path': ''},
    {'name': 'Google DV360', 'names': lc._names({'name': 'Google DV360', 'slug': 'google-dv360'}, first_word=True), 'path': ''},
]


def test_mentioned_follows_brief_order_one_per_name():
    found = [entry['name'] for entry in lc.mentioned('Páginas de Valor, Exame e UOL', ENTRIES)]
    assert found == ['Valor Econômico', 'Exame', 'UOL']


def test_generic_host_is_not_a_name_and_first_word_works_for_channels():
    found = [entry['name'] for entry in lc.mentioned('logos do Google e do YouTube', ENTRIES)]
    assert found == ['Google DV360']


def test_nothing_mentioned():
    assert lc.mentioned('smartphone e painel DOOH', ENTRIES) == []
    assert lc.references('', 2) == [] and lc.references('UOL', 0) == []
