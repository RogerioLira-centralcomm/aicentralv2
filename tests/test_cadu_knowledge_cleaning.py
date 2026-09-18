from aicentralv2.cadu_skills.knowledge import clean_rag_content


def test_clean_rag_content_is_deterministic_and_preserves_rag_structure():
    raw = '\ufeff# Título\r\n\r\n\r\n**Pergunta:**   \r\n\r\nResposta.   \r\n'
    assert clean_rag_content(raw) == '# Título\n\n**Pergunta:**\n\nResposta.'


def test_clean_rag_content_does_not_rewrite_content():
    raw = '# Marketing de Premissa\n\nFatos conduzem a uma conclusão lógica.\n\n| Termo | Definição |\n|---|---|'
    assert clean_rag_content(raw) == raw
