from aicentralv2.creative_brand_analysis import _text


def test_text_keeps_plain_strings():
    assert _text('  Energia  ', 50) == 'Energia'
    assert _text(None, 50) is None


def test_text_unwraps_evidence_object():
    assert _text({'value': 'Resumo', 'source_url': 'https://x'}, 50) == 'Resumo'


def test_text_joins_evidence_list_without_python_repr():
    result = _text([{'value': 'Primeiro.', 'source_url': 'https://a', 'confidence': 0.9},
                    {'value': 'Segundo.', 'excerpt': '## X'}, 'Terceiro.'], 200)
    assert result == 'Primeiro. Segundo. Terceiro.'
    assert '{' not in result and "'value'" not in result


def test_text_respects_limit():
    assert _text([{'value': 'abcdef'}], 3) == 'abc'
