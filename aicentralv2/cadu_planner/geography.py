"""Praças escritas à mão ('Sp, RJ, BH') → nomes por extenso para o plano final.

Determinístico: siglas de estado e de cidades comuns viram o nome; o resto mantém o que a
pessoa escreveu, só com a capitalização arrumada. Nada é acrescentado nem descartado.
"""
from __future__ import annotations

import re
import unicodedata

STATES = {
    'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas', 'ba': 'Bahia', 'ce': 'Ceará',
    'df': 'Distrito Federal', 'es': 'Espírito Santo', 'go': 'Goiás', 'ma': 'Maranhão', 'mt': 'Mato Grosso',
    'ms': 'Mato Grosso do Sul', 'mg': 'Minas Gerais', 'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná',
    'pe': 'Pernambuco', 'pi': 'Piauí', 'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte',
    'rs': 'Rio Grande do Sul', 'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina', 'sp': 'São Paulo',
    'se': 'Sergipe', 'to': 'Tocantins',
}
CITIES = {
    'bh': 'Belo Horizonte', 'bhz': 'Belo Horizonte', 'poa': 'Porto Alegre', 'bsb': 'Brasília', 'cwb': 'Curitiba',
    'rec': 'Recife', 'ssa': 'Salvador', 'for': 'Fortaleza', 'fln': 'Florianópolis', 'floripa': 'Florianópolis',
    'sampa': 'São Paulo', 'rio': 'Rio de Janeiro', 'abc': 'ABC Paulista', 'grande sp': 'Grande São Paulo',
    'grande sao paulo': 'Grande São Paulo', 'sao paulo': 'São Paulo', 'rio de janeiro': 'Rio de Janeiro',
    'belo horizonte': 'Belo Horizonte', 'brasilia': 'Brasília', 'brasil': 'Brasil', 'nacional': 'Brasil',
}
_SMALL = {'de', 'do', 'da', 'dos', 'das', 'e'}
_SPLIT = re.compile(r'\s*(?:[,;/\n|]|\s+e\s+)\s*', re.I)


def _fold(value):
    return unicodedata.normalize('NFD', value).encode('ascii', 'ignore').decode().lower().strip(' .')


def _title(value):
    words = value.split()
    # Dentro de uma frase, só a sigla em maiúsculas vira estado ('interior de MG'); 'se', 'to' e 'pa' são palavras.
    return ' '.join(STATES[word.lower()] if len(word) == 2 and word.isupper() and word.lower() in STATES else
                    word if word.isupper() and len(word) > 3 else
                    (word.lower() if index and word.lower() in _SMALL else word[:1].upper() + word[1:].lower())
                    for index, word in enumerate(words))


def places(text):
    """['São Paulo', 'Rio de Janeiro', 'Belo Horizonte'] a partir de 'Sp, RJ, BH'."""
    out = []
    for part in _SPLIT.split(str(text or '')):
        part = part.strip(' .-')
        if not part:
            continue
        key = _fold(part)
        name = CITIES.get(key) or STATES.get(key) or _title(part)
        if name not in out:
            out.append(name)
    return out


def normalize(text):
    """'Sp, RJ, BH' → 'São Paulo, Rio de Janeiro e Belo Horizonte'."""
    names = places(text)
    if len(names) < 2:
        return names[0] if names else ''
    return ', '.join(names[:-1]) + ' e ' + names[-1]
