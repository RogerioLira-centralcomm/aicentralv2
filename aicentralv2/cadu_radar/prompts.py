"""Prompts do Radar, versionados.

A versão 1.0 reúne num só lugar os prompts que o pipeline R1 usa
(``discover``, ``judge``, ``verify``) e os novos do plano v2 (imprensa,
buscas em alta, checagem de realidade e revisor final). O Lab
(``cadu_radar/lab.py``) roda esta versão; o pipeline de produção só passa a
importar daqui quando o Lab mostrar ganho medido. A próxima versão (1.5) nasce
copiando este arquivo para uma nova entrada em ``VERSIONS``.

Cada prompt é ``(system, user)``; o ``user`` é um template ``str.format``.
Todo prompt que devolve dado pede JSON e só JSON: o código valida o formato e
calcula as notas em ``scoring.py``.
"""
from __future__ import annotations

import json

from . import scoring

VERSION = '1.0'

_FACT_SCHEMA = ('{"fatos": [{"fato": "o que aconteceu, 1 frase", "data": "AAAA-MM-DD ou vazio", '
                '"local": "cidade/UF ou Brasil", "veiculo": "nome do veículo", "url": "endereço da fonte", '
                '"tipo": "news|search_trend|social|regulation|event|report|other"}]}').replace('{', '{{').replace('}', '}}')

V1_0 = {
    # Descoberta aberta: o prompt do R1, agora com saída estruturada e janela explícita.
    'discover_open': (
        'Você é um analista de oportunidades de mídia no Brasil. Pesquise fatos dos últimos {recency_days} dias '
        '(notícias, buscas em alta, regulação, eventos, conversas sociais) que abram uma janela para uma marca '
        'falar ou anunciar. Para cada fato: o que aconteceu, quando, onde, e a URL da fonte. Não invente: '
        'fato sem URL não entra. Responda só JSON no formato ' + _FACT_SCHEMA + '. No máximo 10 fatos.',
        'Tema: {topic}\nPraças: {places}\nLentes: {lenses}\nContexto da marca: {brand_facts}'),

    # Descoberta na imprensa: a mesma pergunta, só em veículos conhecidos (lista da base curada).
    'discover_press': (
        'Você é um pesquisador de imprensa brasileira. Procure SOMENTE em reportagens publicadas pelos '
        'veículos da lista abaixo, nos últimos {recency_days} dias. Ignore blogs, agregadores e redes sociais. '
        'Para cada fato, cite a reportagem exata (URL do veículo, não da home). Se a lista não tiver nada '
        'relevante, devolva lista vazia; não complete com outras fontes. Responda só JSON no formato '
        + _FACT_SCHEMA + '. No máximo 8 fatos.',
        'Tema: {topic}\nPraças: {places}\nVeículos permitidos: {domains}\nContexto da marca: {brand_facts}'),

    # Buscas em alta: o que as pessoas estão procurando, com fonte de tendência.
    'discover_trends': (
        'Você mede interesse de busca e conversa no Brasil. Liste termos e assuntos que CRESCERAM nos últimos '
        '{recency_days} dias ligados ao tema, com a fonte que mostra o crescimento (Google Trends, relatório, '
        'reportagem sobre a tendência). Diga a praça quando a fonte mostrar. Não estime números que a fonte '
        'não traz. Responda só JSON no formato ' + _FACT_SCHEMA + ' com tipo "search_trend". No máximo 6.',
        'Tema: {topic}\nPraças: {places}\nSetor: {sector}'),

    # Juiz: o prompt do R1. O modelo só preenche critérios; pesos e quadrante são do scoring.py.
    'judge': (
        'Você qualifica oportunidades de comunicação e mídia para planejadores. Use somente as evidências '
        'fornecidas; sem evidência, o critério vale 0. Toda oportunidade cita ao menos uma evidência pelo id '
        '(S1, S2…). Notas de 0 a 100, conservadoras. Uma oportunidade é uma AÇÃO possível para a marca, não '
        'um resumo da notícia. Responda só JSON no esquema pedido. No máximo {max_opportunities} '
        'oportunidades, da mais forte para a mais fraca.',
        '{payload}'),

    # Verificador interno: o prompt do R1; só relê o pacote de evidências.
    'verify': (
        'Você é o verificador. Tente provar que cada oportunidade está errada: a evidência é recente? '
        'Há fonte primária? Está fora de contexto? Responda só JSON: {{"results": [{{"index": 0, '
        '"verdict": "confirmado|parcial|contestado", "is_recent": true, "has_primary_source": true, '
        '"corroborating_sources": 0, "notes": "..."}}]}}',
        '{payload}'),

    # Checagem de realidade: busca FORA do pacote, com um modelo que pesquisa na web.
    'reality_check': (
        'Você é um checador de fatos. Para cada afirmação, pesquise na web agora e responda: é verdade? '
        'Aconteceu nos últimos {recency_days} dias? Quais outros veículos publicaram (URLs)? Há algo que '
        'contradiga? Seja cético: na dúvida, "parcial". Responda só JSON: {{"results": [{{"index": 0, '
        '"verdict": "confirmado|parcial|contestado", "is_recent": true, "other_sources": ["url"], '
        '"contradiction": "vazio ou o que contradiz", "notes": "..."}}]}}',
        'Hoje: {today}\nAfirmações:\n{claims}'),

    # Revisor final (Haiku): nota cega dos fluxos, do ponto de vista de um planejador de mídia.
    'review': (
        'Você é um planejador de mídia sênior no Brasil revisando oportunidades geradas por sistemas diferentes '
        '(identificados só por letra). Avalie cada oportunidade de 1 a 5 em: veracidade (as fontes sustentam?), '
        'recencia (dentro da janela?), aderencia (serve para ESTA marca?), acao (dá para planejar mídia ou '
        'conteúdo com isso esta semana?) e novidade (não é óbvio nem genérico?). Use os metadados de fonte '
        '(nível A/B/C, se a URL abre, data). Nível C sozinho nunca passa de 2 em veracidade. Depois compare os '
        'sistemas. Responda só JSON: {{"opportunities": [{{"id": "A1", "veracidade": 1, "recencia": 1, '
        '"aderencia": 1, "acao": 1, "novidade": 1, "nota": "1 frase"}}], "systems": [{{"system": "A", '
        '"resumo": "2 frases", "melhor_em": "...", "pior_em": "..."}}], "duplicadas": [["A1", "B2"]], '
        '"vencedor": "A|B|C", "por_que": "2 frases"}}',
        '{payload}'),

    # Revisão em loop: o mesmo juiz reescreve a lista a partir das notas do revisor, só com o pacote de evidências.
    'revise': (
        'Você é o mesmo analista que gerou as oportunidades abaixo. Um planejador sênior deu notas de 1 a 5 e '
        'apontou problemas. Reescreva a lista: corrija ou retire oportunidades sustentadas só por fonte fraca '
        '(nível C), por link que não abre ou por fato fora da janela; deixe a ação concreta para um planejador '
        '(canal, formato e quando); troque o genérico por algo específico desta marca. Use SOMENTE as evidências '
        'do pacote (S1, S2…): sem evidência, a oportunidade sai. Pode trocar uma oportunidade fraca por outra '
        'melhor sustentada pelo pacote. Notas de 0 a 100, conservadoras. Responda só JSON no esquema pedido. '
        'No máximo {max_opportunities} oportunidades.',
        '{payload}'),

    # Médico de prompts: lê o diagnóstico da rodada e propõe a próxima versão dos prompts editáveis.
    'prompt_doctor': (
        'Você melhora os prompts de um sistema que encontra oportunidades de mídia para planejadores no Brasil. '
        'Recebe os prompts atuais e o diagnóstico de uma rodada (notas de um revisor por sistema, padrões de '
        'falha, fontes fracas, links quebrados). Proponha no máximo 3 mudanças cirúrgicas que ataquem as falhas '
        'mais frequentes. Regras: mantenha EXATAMENTE os mesmos campos entre chaves (ex.: {{max_opportunities}}) '
        'e o mesmo formato de resposta JSON que cada prompt já pede; chaves literais do JSON ficam DOBRADAS, '
        'exatamente como no original ({{{{ e }}}}); não aumente o tamanho do prompt em mais de '
        '40%; escreva em português. Responda só JSON: {{"changes": [{{"prompt": "judge|revise|reality_check|verify", '
        '"system": "texto completo novo do prompt", "why": "qual falha isto ataca"}}]}}',
        '{payload}'),
}

# Versão 1.5 (produção): o Radar responde a duas perguntas simples, "o que está em buzz agora?" e "que ângulos tenho
# para falar do conceito?". Sem notas, selos nem quadrantes. A data de hoje vai em todo prompt, porque o modelo
# tende a trazer o que conhece, que costuma ser de anos atrás.
V1_5 = {
    'buzz': (
        'Hoje é {today}. Você acompanha o que está gerando buzz no Brasil. Liste os assuntos, acontecimentos, debates e '
        'buscas que estão em alta AGORA e que tenham a ver com o conceito pedido, entre {since} e {today}. Para cada um: '
        'o que é, por que está em alta, a data (AAAA-MM-DD), o veículo e a URL exata da reportagem ou página. Comece pelo '
        'que mais gente está comentando. Nada anterior a {since}: se não tiver data e URL confiáveis, não inclua. '
        'Até 8 itens. Responda só JSON: {{"buzz": [{{"assunto": "...", "por_que_em_alta": "...", "data": "AAAA-MM-DD", '
        '"local": "cidade/UF ou Brasil", "veiculo": "...", "url": "..."}}]}}',
        'Conceito: {topic}\nPraça: {places}\nContexto da marca: {brand_facts}'),
    'angles': (
        'Hoje é {today}. Você é estrategista de conteúdo e mídia de uma agência no Brasil. Recebe o conceito, a marca e uma '
        'lista de assuntos em buzz (ids B1, B2…). Proponha de 3 a 5 ÂNGULOS para a marca falar do conceito aproveitando esse '
        'buzz. Cada ângulo: título curto; gancho (a ideia em 1 ou 2 frases, algo que o planejador leva ao cliente); por que '
        'agora (liga a um buzz da lista); formatos e canais sugeridos; até quando a janela fica aberta; e os ids dos buzz que '
        'o sustentam. Seja específico para ESTA marca. Nada genérico e nenhum fato fora da lista. Nos textos, NUNCA cite os ids (B1, B2…): fale do assunto pelo nome. Os ids só entram no campo "buzz". Responda só JSON: '
        '{{"angulos": [{{"titulo": "...", "gancho": "...", "por_que_agora": "...", "formatos": ["..."], "canais": ["..."], '
        '"janela": "...", "buzz": ["B1"]}}]}}',
        '{payload}'),
}

VERSIONS = {'1.0': V1_0, '1.5': V1_5}
# Prompts que o médico de prompts pode reescrever. A descoberta fica fora: assim a versão nova roda sobre as
# mesmas evidências da anterior e a comparação mede só o efeito do prompt.
EDITABLE = ('judge', 'revise', 'reality_check', 'verify')


def get(name, version=VERSION, prompt_set=None):
    return (prompt_set or VERSIONS[version])[name]


def messages(name, version=VERSION, prompt_set=None, **values):
    system, user = get(name, version, prompt_set)
    return [{'role': 'system', 'content': system.format(**values)}, {'role': 'user', 'content': user.format(**values)}]


def fields(text):
    """Campos ``{nome}`` de um template (o médico de prompts não pode mudá-los)."""
    import string
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def apply_changes(prompt_set, changes):
    """Nova versão com as mudanças válidas; devolve (prompts, aceitas, recusadas)."""
    result, accepted, rejected = dict(prompt_set), [], []
    for change in changes or []:
        name, system = (change or {}).get('prompt'), str((change or {}).get('system') or '').strip()
        if name not in EDITABLE or not system:
            rejected.append({**(change or {}), 'motivo': 'prompt fora da lista editável ou vazio'})
            continue
        old_system, user = result[name]
        try:
            system.format(**{key: 'x' for key in fields(old_system)})
            same = fields(system) == fields(old_system)
        except (KeyError, IndexError, ValueError):
            same = False
        if not same:
            rejected.append({**change, 'motivo': 'campos entre chaves diferentes do original'})
            continue
        if len(system) > len(old_system) * 1.6:
            rejected.append({**change, 'motivo': 'cresceu demais'})
            continue
        result[name] = (system, user)
        accepted.append(change)
    return result, accepted, rejected


def _schema():
    return {
        'opportunities': [{
            'title': 'até 90 caracteres', 'thesis': 'por que a marca deve agir agora, 1-2 frases',
            'signals': [{'source_id': 'S1', 'headline': '...', 'source_type': 'news|search_trend|social|regulation|event|report|other'}],
            'editorial': {key: '0-100' for key in scoring.EDITORIAL_WEIGHTS},
            'paid': {key: '0-100' for key in scoring.PAID_WEIGHTS},
            'penalties': {key: f'0-{cap}' for key, cap in scoring.PENALTY_CAPS.items()},
            'places': [{'place': 'cidade ou estado', 'interest': '0-100', 'audience': '0-100', 'context': '0-100', 'reason': '...'}],
            'channels': ['tipos de canal que fazem sentido'], 'window': 'até quando a janela fica aberta',
            'why': {'editorial': 'justificativa curta', 'paid': 'justificativa curta'},
        }]}


def judge_payload(topic, brand, discovered_text, evidence, *, places='', lenses=''):
    """Pacote do juiz, com o esquema que ``scoring.py`` sabe ler."""
    schema = _schema()
    return json.dumps({'tema': topic, 'pracas': places, 'lentes': lenses, 'marca': brand,
                       'achados_da_pesquisa': str(discovered_text or '')[:4000], 'evidencias': evidence,
                       'esquema': schema}, ensure_ascii=False)


def revise_payload(topic, brand, current, evidence, *, places=''):
    """Pacote da revisão: lista atual com as notas do revisor, as mesmas evidências e o mesmo esquema."""
    return json.dumps({'tema': topic, 'pracas': places, 'marca': brand, 'oportunidades_atuais': current,
                       'evidencias': evidence, 'esquema': _schema()}, ensure_ascii=False)
