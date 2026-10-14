from aicentralv2.cadu_planner.geography import normalize


def test_handwritten_places_become_full_names():
    assert normalize('Sp, RJ, BH') == 'São Paulo, Rio de Janeiro e Belo Horizonte'
    assert normalize('Sp, RJ, MG') == 'São Paulo, Rio de Janeiro e Minas Gerais'
    assert normalize('SP/RJ') == 'São Paulo e Rio de Janeiro'
    assert normalize('grande sp e interior de MG') == 'Grande São Paulo e Interior de Minas Gerais'
    assert normalize('São Paulo, Rio de Janeiro e Belo Horizonte') == 'São Paulo, Rio de Janeiro e Belo Horizonte'
    assert normalize('') == ''
