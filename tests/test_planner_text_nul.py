from aicentralv2.cadu_planner import plans


def test_briefing_and_labels_drop_nul_that_postgres_rejects():
    briefing = plans._clean_briefing({'notes': 'Escolher um está\x00dio', 'budget': 0})
    assert briefing == {'notes': 'Escolher um estádio', 'budget': '0'}
    assert plans._clean_label('Marca\x00 X') == 'Marca X'
