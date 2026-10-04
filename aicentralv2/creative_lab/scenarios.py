"""Test scenarios: data, not code. Each one isolates one variable and says what it should reveal.

References point at approved Workspace brand assets (``asset_id``) so every scenario runs on the
brand's own material. A scenario runs on every model, one generation at a time; the grid compares the
same scenario across models, so nothing is repeated with a different name.
"""

from __future__ import annotations

V1 = "v1 · briefing livre"
V2 = "v2 · briefing estruturado"
V3 = "v3 · pipeline do Studio"

SCENARIOS = [
    {
        "key": "marca-so-texto", "group": V1,
        "title": "Marca só por texto",
        "task": "generate", "brand_id": 25, "aspect_ratio": "1:1", "quality": "standard",
        "objective": "paid social ad",
        "instruction": "Anúncio institucional da Centralcomm para redes sociais: fundo escuro, sensação de tecnologia de mídia, headline grande e um botão.",
        "must_include_text": ["Mídia que chega.", "Fale com a gente"],
        "references": [], "logo_mode": "composer",
        "variable": "Sem nenhuma imagem: só a auditoria da marca em texto (paleta, diretriz, proibidos).",
        "hypothesis": "Mede quanto da identidade o modelo reconstrói a partir do texto auditado e se o PT-BR sai exato (acento, ponto final).",
    },
    {
        "key": "logo-nativo", "group": V1,
        "title": "Logo como referência nativa",
        "task": "generate", "brand_id": 31, "aspect_ratio": "3:4", "quality": "standard",
        "objective": "institutional social post",
        "instruction": "Post institucional da Cemig divulgando o autoatendimento Cemig Atende Web, com celular em destaque e a marca no topo.",
        "must_include_text": ["Sua conta de luz na palma da mão"],
        "references": [{"asset_id": 265, "role": "LOGO", "label": "Logo Cemig"}], "logo_mode": "native",
        "variable": "O logo vai para o modelo como imagem (não é aplicado depois pelo Composer).",
        "hypothesis": "Revela quem copia o logo fielmente e quem redesenha — decide se o Composer continua obrigatório por modelo.",
    },
    {
        "key": "produto-packshot", "group": V1,
        "title": "Produto + logo depois",
        "task": "generate", "brand_id": 7, "aspect_ratio": "3:4", "quality": "standard",
        "objective": "product ad",
        "instruction": "Anúncio do tênis R-Broox da Reserva em calçada urbana ao entardecer, o tênis é o herói da peça.",
        "must_include_text": ["Pisa leve."],
        "references": [{"asset_id": 26, "role": "PRODUCT", "label": "Tênis R-Broox"},
                       {"asset_id": 29, "role": "LOGO", "label": "Logo Reserva"}], "logo_mode": "composer",
        "variable": "Uma referência de produto; o logo é aplicado pelo Composer depois.",
        "hypothesis": "Fidelidade de produto (forma, cores, 'R' lateral) com uma única referência.",
    },
    {
        "key": "pessoa-produto", "group": V1,
        "title": "Pessoa + produto",
        "task": "generate", "brand_id": 4, "aspect_ratio": "3:4", "quality": "standard",
        "objective": "jewelry campaign ad",
        "instruction": "Campanha Vivara: a modelo da referência usando o colar de ouro da referência, luz suave de estúdio, fundo neutro quente.",
        "must_include_text": ["Brilho que é seu"],
        "references": [{"asset_id": 176, "role": "PERSON", "label": "Modelo Vivara", "has_person": True},
                       {"asset_id": 177, "role": "PRODUCT", "label": "Colar de ouro"},
                       {"asset_id": 6, "role": "LOGO", "label": "Logo Vivara"}], "logo_mode": "composer",
        "variable": "Duas referências nativas (pessoa e produto); quem aceita só 1 converte o produto em texto.",
        "hypothesis": "Identidade da pessoa × fidelidade do produto quando competem; expõe o limite de referências do Recraft.",
    },
    {
        "key": "editar-texto", "group": V1,
        "title": "Editar só o texto",
        "task": "edit", "brand_id": 7, "aspect_ratio": "3:4", "quality": "standard",
        "objective": "edit an existing ad",
        "instruction": "Trocar a oferta de 20% para 30%. Nada mais muda.",
        "must_include_text": ["Boas vindas", "com 30% OFF"],
        "preserve": ["the person (face, hair, clothes, pose)", "layout and typography style", "background", "every other text"],
        "alter": "Change the offer text '20%OFF' to '30%OFF' in the same typeface, size and position.",
        "references": [{"asset_id": 194, "role": "BASE", "label": "Peça Boas-vindas 20%", "has_person": True}], "logo_mode": "none",
        "variable": "Edição cirúrgica de um número numa peça real com pessoa.",
        "hypothesis": "Caso do Trocr: o modelo troca só o número ou redesenha a peça inteira?",
    },
    {
        "key": "editar-cenario", "group": V1,
        "title": "Editar o cenário",
        "task": "edit", "brand_id": 7, "aspect_ratio": "3:4", "quality": "standard",
        "objective": "edit an existing ad",
        "instruction": "Levar o modelo para uma rua de São Paulo à noite, com luzes de neon desfocadas; pessoa e roupa idênticas.",
        "must_include_text": [],
        "preserve": ["the person's identity, face, skin tone and pose", "the knitted t-shirt, its color and texture", "framing of the person"],
        "alter": "Replace the background with a blurred São Paulo street at night with soft neon bokeh. Remove the words 'TONS TERROSOS'.",
        "references": [{"asset_id": 196, "role": "BASE", "label": "Modelo tons terrosos", "has_person": True}], "logo_mode": "none",
        "variable": "Edição ampla (fundo) preservando identidade.",
        "hypothesis": "Preservação de identidade com mudança grande de luz — onde modelos 'trocam' o rosto.",
    },
    {
        "key": "estilo-referencia", "group": V1,
        "title": "Estilo de outra peça",
        "task": "generate", "brand_id": 25, "aspect_ratio": "16:9", "quality": "standard",
        "objective": "connected TV ad frame",
        "instruction": "Frame de anúncio para CTV da Centralcomm sobre mídia programática, no mesmo estilo visual da referência (escuro, verde neon, pessoa em destaque).",
        "must_include_text": ["Sua mídia, em todas as telas."],
        "references": [{"asset_id": 217, "role": "STYLE", "label": "Site Centralcomm (estilo)", "has_person": True},
                       {"asset_id": 197, "role": "LOGO", "label": "Símbolo Centralcomm"}], "logo_mode": "composer",
        "variable": "Referência de estilo (não de conteúdo) + ratio 16:9.",
        "hypothesis": "Quem copia a peça em vez de herdar o estilo; quem ignora a referência.",
    },
    {
        "key": "v2-cemig-whatsapp", "group": V2,
        "title": "Cemig no WhatsApp · desdobramento",
        "task": "generate", "brand_id": 31, "quality": "standard", "objective": "service awareness ad",
        "formats": ["feed-1x1", "story-9x16", "wide-16x9", "iab-300x250", "iab-300x600"],
        "instruction": "", "references": [], "logo_mode": "composer",
        "brief": {
            "archetype": "recorte-chamada", "audience": "Clientes residenciais da Cemig que perdem tempo com atendimento",
            "offer": "Atendimento da Cemig pelo WhatsApp (2ª via, religação, falta de energia)",
            "copy": {"kicker": "CEMIG ATENDE", "headline": "Sua conta de luz", "highlight": "NO WHATSAPP",
                     "support": "2ª via, religação e falta de energia sem sair de casa.", "cta": "Chame agora"},
            "casting": ["Mulher negra de 35 anos, cabelo cacheado preso, camiseta lisa verde-clara, sentada no sofá segurando o celular, sorriso tranquilo, olhando para a câmera"],
            "devices": ["cápsulas arredondadas em verde-lima como marcadores", "faixa inferior verde-escura com a marca"],
        },
        "variable": "Mesmo briefing estruturado em 5 formatos (feed, story, 16:9, 300×250, 300×600).",
        "hypothesis": "Quem diagrama por formato (zonas, herói, assinatura) e quem só estica a mesma imagem; quanto o recorte para IAB destrói.",
    },
    {
        "key": "v2-centralcomm-ritmo", "group": V2,
        "title": "Centralcomm · ritmo tipográfico",
        "task": "generate", "brand_id": 25, "quality": "standard", "objective": "agency positioning ad",
        "formats": ["feed-1x1", "story-9x16", "iab-300x250"],
        "instruction": "", "references": [], "logo_mode": "composer",
        "brief": {
            "archetype": "tipografico-faixa", "audience": "Diretores de marketing que contratam mídia em várias frentes",
            "copy": {"headline": "PROGRAMÁTICA. CTV. PERFORMANCE. PUBLISHERS.", "highlight": "UMA OPERAÇÃO SÓ.",
                     "tagline": "Centralcomm. Mídia que chega."},
            "casting": [], "devices": ["linhas curtas empilhadas alternando branco e verde neon", "aba sólida amarela no canto superior esquerdo"],
        },
        "variable": "Peça só tipográfica (aprendida de Gov. Minas e Uhuru) — sem foto para o modelo enfeitar.",
        "hypothesis": "Sem cena, sobra só diagramação e texto: mede tipografia pura e respeito à paleta.",
    },
    {
        "key": "v2-reserva-semana-cliente", "group": V2,
        "title": "Reserva · foto em faixa + oferta",
        "task": "generate", "brand_id": 7, "quality": "standard", "objective": "retail offer display ad",
        "formats": ["feed-4x5", "iab-300x250"],
        "instruction": "",
        "references": [{"asset_id": 196, "role": "PERSON", "label": "Modelo Reserva", "has_person": True},
                       {"asset_id": 29, "role": "LOGO", "label": "Logo Reserva"}], "logo_mode": "composer",
        "brief": {
            "archetype": "foto-faixa-bloco", "audience": "Clientes da Reserva na semana do cliente",
            "offer": "Semana do Cliente: +20% extra em todo o outlet com cupom (copy da peça real da marca)",
            "copy": {"kicker": "SEMANA DO CLIENTE", "headline": "Outlet com", "highlight": "+20% EXTRA",
                     "support": "Use o cupom DIADOCLIENTE.", "cta": "COMPRAR AGORA"},
            "casting": ["O modelo da referência, mesma roupa, recortado do peito para cima, olhando para a câmera"],
            "devices": ["corte reto entre a faixa de foto e o bloco preto", "botão retangular branco com texto preto"],
        },
        "variable": "Arquétipo MaxMilhas (foto em faixa + bloco) com a pessoa real da marca.",
        "hypothesis": "Pessoa de referência + oferta herói + bloco chapado: identidade × hierarquia.",
    },
    {
        "key": "v2-vivara-story", "group": V2,
        "title": "Vivara · story com recorte e produto",
        "task": "generate", "brand_id": 4, "quality": "standard", "objective": "jewelry story ad",
        "formats": ["story-9x16"],
        "instruction": "",
        "references": [{"asset_id": 176, "role": "PERSON", "label": "Modelo Vivara", "has_person": True},
                       {"asset_id": 177, "role": "PRODUCT", "label": "Colar de ouro"},
                       {"asset_id": 6, "role": "LOGO", "label": "Logo Vivara"}], "logo_mode": "composer",
        "brief": {
            "archetype": "recorte-chamada", "audience": "Mulheres 25–45 que presenteiam a si mesmas",
            "copy": {"kicker": "VIVARA", "headline": "Brilho que é seu", "support": "Colares em ouro para todos os dias.",
                     "cta": "Descubra na loja"},
            "casting": ["A modelo da referência usando o colar da referência, ombros à mostra, luz suave, olhando para a câmera"],
            "devices": ["fundo chapado bege-rosado da marca", "fio dourado fino como divisor"],
        },
        "variable": "Story (zonas de UI) + 2 referências que competem (pessoa e produto).",
        "hypothesis": "Zonas seguras do story e fidelidade de produto quando o elenco também vem de referência.",
    },
    {
        "key": "v2-reformatar-vertical-horizontal", "group": V2,
        "title": "Reformatar: vertical → horizontal",
        "task": "edit", "brand_id": 5, "quality": "standard", "objective": "format adaptation",
        "formats": ["wide-16x9"],
        "instruction": "Adaptar a peça vertical da Rede D'Or para 16:9 sem perder texto, pessoa nem assinatura.",
        "references": [{"asset_id": 13, "role": "BASE", "label": "Rede D'Or · vaga (vertical)", "has_person": True}],
        "logo_mode": "none",
        "brief": {"copy": {"headline": "Seu talento pode fazer parte do cuidado que transforma vidas",
                           "support": "Conheça as oportunidades de carreira na Rede D'Or"}},
        "variable": "Peça real vertical → 16:9: o modelo precisa estender o fundo e reposicionar o texto.",
        "hypothesis": "Desdobramento por edição: quem mantém texto e rosto e quem redesenha a peça.",
    },
    {
        "key": "v2-reformatar-horizontal-vertical", "group": V2,
        "title": "Reformatar: horizontal → vertical",
        "task": "edit", "brand_id": 7, "quality": "standard", "objective": "format adaptation",
        "formats": ["story-9x16"],
        "instruction": "Adaptar o banner horizontal da Reserva para story 9:16.",
        "references": [{"asset_id": 189, "role": "BASE", "label": "Reserva · banner outlet (horizontal)", "has_person": True}],
        "logo_mode": "none",
        "brief": {"copy": {"headline": "+20% extra", "support": "EM TODO O OUTLET"}},
        "variable": "Peça real horizontal → story: o texto sai do lado e vai para cima/baixo da pessoa.",
        "hypothesis": "O caso mais difícil do desdobramento: o canvas muda de orientação.",
    },
    {
        "key": "v2-reformatar-quadrado-vertical", "group": V2,
        "title": "Reformatar: quadrado → story e 300×600",
        "task": "edit", "brand_id": 5, "quality": "standard", "objective": "format adaptation",
        "formats": ["story-9x16", "iab-300x600"],
        "instruction": "Adaptar a peça 1:1 da Rede D'Or para story e half-page.",
        "references": [{"asset_id": 14, "role": "BASE", "label": "Rede D'Or · como se candidatar (1:1)", "has_person": True}],
        "logo_mode": "none",
        "brief": {"copy": {"headline": "Entenda como se candidatar a vagas na Rede D'Or"}},
        "variable": "Uma peça quadrada vira dois formatos altos.",
        "hypothesis": "Consistência entre formatos derivados da mesma base.",
    },
]


# -- v3: the Studio's own pipeline (director, composition mask, logo, fit) with real brand assets ----------------------
#
# Every v3 scenario carries what the Studio really receives from a brand: approved reference photos (person, product
# or style) AND the official logo, applied afterwards by code. A test without references or logo says nothing about
# the Studio, so those older scenarios (v1/v2) stay only as history. The mockup is the variable: the same briefing
# with the composition mask sent as an image, and without it.

MOCKUP_LABEL = {"image": "mockup como imagem", "text": "mockup só em texto", "none": "sem mockup"}
MOCKUP_VARIABLE = {
    "image": "O Studio como está hoje: a máscara de composição vai ao modelo como imagem e o contrato de zonas entra no prompt.",
    "text": "As mesmas zonas, só descritas em palavras.",
    "none": "Linha de base: o mesmo diretor, as mesmas referências e o logo por código, mas sem máscara; o modelo compõe sozinho.",
}
MOCKUP_HYPOTHESIS = {
    "image": "Com as referências reais, quanto da identidade (rosto, produto, paleta) e da zona do logo cada modelo preserva.",
    "text": "Se a descrição em texto basta quando o modelo não aceita a imagem da máscara.",
    "none": "O ganho real da máscara: a diferença desta linha para a de mockup como imagem.",
}


def _v3(stem, brand_label, family, formats, modes, *, learning, **fields):
    items = []
    for mode in modes:
        items.append({
            "task": "generate", "quality": "standard", "logo_mode": "composer", **fields,
            "key": f"v3-{stem}-{mode}", "group": f"{V3} · {brand_label}",
            "title": f"{brand_label} · {MOCKUP_LABEL[mode]}", "formats": formats,
            "pipeline": "studio", "mockup": {"mode": mode, "family": family},
            "variable": f"{learning} {MOCKUP_VARIABLE[mode]}", "hypothesis": MOCKUP_HYPOTHESIS[mode],
        })
    return items


V3_SCENARIOS = [
    *_v3(
        "vivara-pessoa-colar", "Vivara", "foto-texto-base", ["feed-4x5", "story-9x16", "iab-300x600"], ("image", "none"),
        learning="Pessoa e produto reais competem pela atenção do modelo.",
        brand_id=4, objective="jewelry campaign ad",
        instruction=("Anúncio de joia da Vivara. A modelo da referência (rosto, cabelo e tom de pele idênticos) usa o colar de ouro da referência "
                     "(forma, comprimento e acabamento idênticos), em luz suave de estúdio sobre fundo chapado bege-rosado. "
                     "Só o texto da copy, escrito exatamente; o logo oficial é aplicado depois, então nenhuma marca é desenhada."),
        references=[{"asset_id": 176, "role": "PERSON", "label": "Modelo Vivara", "has_person": True},
                    {"asset_id": 177, "role": "PRODUCT", "label": "Colar de ouro"},
                    {"asset_id": 6, "role": "LOGO", "label": "Logo Vivara"}],
        brief={
            "archetype": "recorte-chamada", "audience": "Mulheres de 25 a 45 anos que presenteiam a si mesmas",
            "copy": {"kicker": "VIVARA", "headline": "Brilho que é seu", "support": "Colares em ouro para todos os dias.", "cta": "Descubra na loja"},
            "casting": ["A modelo da referência, ombros à mostra, o colar da referência em primeiro plano e legível, olhando para a câmera, expressão serena"],
            "devices": ["fundo chapado bege-rosado da marca", "fio dourado fino separando a chamada", "área limpa no canto para o logo"],
        },
    ),
    *_v3(
        "reserva-tenis-heroi", "Reserva · tênis", "produto-destaque", ["feed-4x5", "story-9x16", "iab-300x250"], ("image", "none"),
        learning="Uma única referência de produto precisa sair idêntica (forma, cores, o R lateral).",
        brand_id=7, objective="product ad",
        instruction=("Anúncio do tênis R-Broox da Reserva. O tênis da referência é o herói da peça, idêntico ao original (forma, cores, solado e o R lateral), "
                     "numa calçada urbana ao entardecer, sem pessoas. Headline e botão com o texto exato da copy; o logo oficial é aplicado depois."),
        references=[{"asset_id": 26, "role": "PRODUCT", "label": "Tênis R-Broox"},
                    {"asset_id": 29, "role": "LOGO", "label": "Logo Reserva"}],
        brief={
            "archetype": "recorte-chamada", "audience": "Clientes da Reserva que procuram tênis para o dia a dia na cidade",
            "copy": {"headline": "Pisa leve.", "support": "Tênis R-Broox", "cta": "Ver na loja"},
            "casting": [],
            "devices": ["tênis grande em primeiro plano, ocupando o terço central", "calçada em desfoque suave ao fundo", "área limpa no canto para o logo"],
        },
    ),
    *_v3(
        "reserva-semana-cliente", "Reserva · oferta", "split", ["feed-4x5", "iab-300x250"], ("image", "none"),
        learning="Pessoa real da marca + oferta como herói + bloco chapado: identidade contra hierarquia.",
        brand_id=7, objective="retail offer display ad",
        instruction=("Peça de varejo da Reserva para a Semana do Cliente. O modelo da referência (mesmo rosto, roupa e pose), recortado do peito para cima, "
                     "ocupa a faixa de foto; ao lado, um bloco preto chapado traz a oferta. O número +20% EXTRA é o herói. Texto exato; o logo é aplicado depois."),
        references=[{"asset_id": 196, "role": "PERSON", "label": "Modelo Reserva", "has_person": True},
                    {"asset_id": 29, "role": "LOGO", "label": "Logo Reserva"}],
        brief={
            "archetype": "foto-faixa-bloco", "audience": "Clientes da Reserva na Semana do Cliente",
            "offer": "Semana do Cliente: +20% extra em todo o outlet com o cupom DIADOCLIENTE (copy da peça real da marca)",
            "copy": {"kicker": "SEMANA DO CLIENTE", "headline": "Outlet com", "highlight": "+20% EXTRA", "support": "Use o cupom DIADOCLIENTE.", "cta": "COMPRAR AGORA"},
            "casting": ["O modelo da referência, mesma roupa, recortado do peito para cima, olhando para a câmera"],
            "devices": ["corte reto entre a faixa de foto e o bloco preto", "botão retangular branco com texto preto", "área limpa no canto para o logo"],
        },
    ),
    *_v3(
        "centralcomm-estilo-site", "Centralcomm", "foto-texto-base", ["feed-1x1", "story-9x16", "iab-300x250"], ("image", "none"),
        learning="A referência é de estilo (escuro, verde neon, pessoa em destaque), não de conteúdo: o modelo herda a linguagem sem copiar a peça.",
        brand_id=25, objective="agency positioning ad",
        instruction=("Anúncio de posicionamento da Centralcomm, na mesma linguagem visual da referência de estilo (fundo escuro, verde neon, pessoa em destaque), "
                     "sem copiar a peça nem o texto dela. Headline e assinatura exatas; o logo oficial é aplicado depois."),
        references=[{"asset_id": 217, "role": "STYLE", "label": "Site Centralcomm (estilo)", "has_person": True},
                    {"asset_id": 197, "role": "LOGO", "label": "Símbolo Centralcomm"}],
        brief={
            "archetype": "ritmo-tipografico", "audience": "Diretores de marketing que contratam mídia em várias frentes",
            "copy": {"headline": "Sua mídia, em todas as telas.", "tagline": "Centralcomm. Mídia que chega.", "cta": "Fale com a gente"},
            "casting": ["Uma pessoa em destaque no estilo da referência, sem repetir a mesma pose nem o mesmo enquadramento"],
            "devices": ["linhas curtas empilhadas alternando branco e verde neon", "aba sólida amarela no canto superior esquerdo", "área limpa no canto para o logo"],
        },
    ),
    *_v3(
        "cemig-atende-web", "Cemig", "foto-texto-base", ["feed-1x1", "story-9x16", "iab-300x250"], ("image", "none"),
        learning="Marca com pouco material (logo e captura do site): o que o modelo faz com uma única referência de estilo.",
        brand_id=31, objective="service awareness ad",
        instruction=("Post de serviço da Cemig divulgando o autoatendimento Cemig Atende Web: um celular em destaque mostrando a conta de luz, "
                     "na linguagem visual da referência de estilo (a captura do site da Cemig). Texto exato; o logo oficial é aplicado depois."),
        references=[{"asset_id": 270, "role": "STYLE", "label": "Site Cemig (estilo)"},
                    {"asset_id": 265, "role": "LOGO", "label": "Logo Cemig"}],
        brief={
            "archetype": "recorte-chamada", "audience": "Clientes residenciais da Cemig que perdem tempo com atendimento",
            "copy": {"kicker": "CEMIG ATENDE WEB", "headline": "Sua conta de luz", "highlight": "NA PALMA DA MÃO", "cta": "Acesse agora"},
            "casting": [],
            "devices": ["celular grande em primeiro plano com a conta de luz na tela, sem números inventados", "cores da marca em campos chapados", "área limpa no canto para o logo"],
        },
    ),
]

SCENARIOS.extend(V3_SCENARIOS)


def scenarios(include_reserved: bool = True) -> list[dict]:
    return [item for item in SCENARIOS if include_reserved or not item.get("reserved")]


def scenario(key: str) -> dict:
    for item in SCENARIOS:
        if item["key"] == key:
            return item
    raise KeyError(f"Cenário desconhecido: {key}")
