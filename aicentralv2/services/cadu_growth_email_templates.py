"""Modelos de e-mail de adoção do Cadu e suíte segura de teste Brevo."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from typing import Any, Dict, Iterable, List, Tuple

from flask import current_app, has_request_context, render_template
from markupsafe import Markup, escape

from aicentralv2.product_domains import product_url
from aicentralv2.services.brevo_service import email_asset_url, get_brevo_product_service, product_email_brand


# Nunca aceitar o destinatário por formulário: a suíte é exclusiva de homologação.
BREVO_GROWTH_TEST_RECIPIENT = "apolo@centralcomm.media"
GROWTH_EMAIL_BAND_URLS = {
    "workspace": "/static/images/cadu/email/bands/workspace-band-v2.png",
    "studio": "/static/images/cadu/email/bands/studio-band-v2.png",
    "connect": "/static/images/cadu/email/bands/connect-band-v2.png",
    "skills": "/static/images/cadu/email/bands/skills-band-v2.png",
    "planner": "/static/images/cadu/email/bands/planner-band-v2.png",
}

GROWTH_EMAIL_ILLUSTRATIONS_URL = "/static/emails/growth/"

GROWTH_EMAIL_MODELS: Dict[str, Dict[str, str]] = {
    "conversa-para-plano": {
        "label": "Conversas → planejamento completo",
        "product": "workspace",
        "subject": "Transforme a conversa de hoje em um plano que o time consegue executar",
        "title": "Transforme a conversa de hoje em um plano que o time consegue executar.",
        "description": "O contexto já existe. Agora ele pode virar uma decisão clara.",
        "cta_label": "Abrir Conversas",
        "cta_path": "/conversas",
        "default_body": "Você não precisa começar com uma planilha em branco. Uma boa conversa já reúne objetivo, público, praça, prazo, verba e restrições. O Cadu ajuda a separar **o que está confirmado, o que é premissa e o que ainda precisa de validação**.\n\nAbra o projeto em andamento, registre o briefing que você já tem e peça uma estrutura de decisão. Assim, o time reduz retrabalho e volta ao raciocínio original quando a campanha mudar.",
    },
    "dicas-de-uso": {
        "label": "Dicas de uso → hábitos que mantêm o projeto útil",
        "product": "workspace",
        "eyebrow": "Dica de uso",
        "illustration": "dicas-de-uso.png",
        "subject": "Três hábitos que deixam seus projetos no Cadu mais úteis",
        "title": "Três hábitos que deixam o Cadu mais útil a cada semana.",
        "description": "Pequenos registros hoje evitam recomeçar do zero amanhã.",
        "cta_label": "Ler o guia no portal",
        "cta_path": "/workspace/conteudos/briefing-vivo",
        "secondary_label": "Abrir meus projetos",
        "secondary_path": "/projetos",
        "default_body": "O Cadu trabalha melhor quando o projeto guarda o que o time já sabe. Três hábitos simples fazem diferença.\n\n**Registre o objetivo e as restrições.** Uma frase sobre o resultado esperado, o prazo e o que não pode mudar já orienta toda conversa, plano e peça.\n\n**Guarde as decisões da reunião.** Transforme a ata em decisões, dúvidas e responsáveis. Assim a próxima conversa não depende da memória de ninguém.\n\n**Salve a resposta que foi aprovada.** O que ficou decidido volta para o projeto e passa a ser referência para as próximas entregas.\n\nO guia no portal mostra o passo a passo com exemplos.",
    },
    "dicas-de-prompts": {
        "label": "Dicas de prompts → pedidos que geram respostas melhores",
        "product": "workspace",
        "eyebrow": "Dica de prompt",
        "illustration": "dicas-de-prompts.png",
        "subject": "Como pedir ao Cadu e receber uma resposta que dá para usar",
        "title": "Um bom pedido tem objetivo, público, formato e tom.",
        "description": "Quatro informações transformam um pedido genérico em uma resposta útil.",
        "cta_label": "Ver o guia de prompts",
        "cta_path": "/workspace/conteudos/dicas-de-prompts",
        "secondary_label": "Abrir Conversas",
        "secondary_path": "/conversas",
        "default_body": "A qualidade da resposta depende do pedido. Antes de enviar, confira se ele diz quatro coisas.\n\n**Objetivo:** o que a resposta precisa permitir que você faça. **Público:** para quem o resultado se destina. **Formato:** lista, tabela, roteiro, texto curto ou plano em etapas. **Tom:** direto, técnico, institucional ou leve.\n\nCompare: \"fale sobre o lançamento\" com \"resuma o lançamento em cinco tópicos para o cliente, em tom direto, destacando prazo e verba\". O segundo já nasce pronto para revisão.\n\nComo o Cadu conhece a marca e o projeto, você não precisa repetir o contexto: peça apenas o que falta. Quando a resposta ficar boa, salve no projeto.",
    },
    "planner-interativos": {
        "label": "Formatos e Interativos → peças que o público usa",
        "product": "planner",
        "eyebrow": "Planner",
        "illustration": "planner-interativos.png",
        "subject": "Formatos interativos: quiz, cube, 360 e outros nos grandes portais",
        "title": "Quando o anúncio vira experiência, o público participa.",
        "description": "No Planner, Formatos e Interativos mostram o que cada canal aceita antes de produzir.",
        "cta_label": "Ver os Interativos",
        "cta_path": "/interativos",
        "secondary_label": "Consultar todos os formatos",
        "secondary_path": "/formatos",
        "default_body": "Antes de produzir uma peça, vale saber o que o canal aceita. Em **Formatos**, o Planner mostra dimensões, duração e especificações de cada entrega, para a criação começar certa.\n\nNos grandes portais (g1, UOL, R7 e CNN), existem também os **Interativos**: hotspot, cartas, quiz, cube, raspadinha, 360, contagem regressiva e vídeo. Eles pedem uma ação do público e funcionam bem quando a campanha tem algo para explorar, comparar ou descobrir.\n\nComece pelo objetivo: se a meta é atenção e lembrança, um interativo pode cumprir esse papel melhor que um banner comum. **Disponibilidade e preço dependem de confirmação comercial.**",
    },
    "reengajamento": {
        "label": "Reengajamento → o que você ainda não testou",
        "product": "workspace",
        "eyebrow": "Para a sua próxima sessão",
        "illustration": "dicas-de-uso.png",
        "subject": "Um atalho para a sua próxima sessão no Cadu",
        "title": "O seu projeto continua pronto. Que tal testar algo novo?",
        "description": "Separamos o que você ainda não experimentou no Cadu.",
        "cta_label": "Abrir meu Workspace",
        "cta_path": "/app",
        "default_body": "A sua marca e o seu projeto continuam no Workspace, prontos para a próxima conversa, plano ou peça.\n\nSe quiser um ponto de partida, abra o projeto e peça ao Cadu **um resumo do que já foi decidido e do que falta**.",
    },
    "plugins-agentes": {
        "label": "Plugins → o Cadu dentro do seu assistente de IA",
        "product": "workspace",
        "eyebrow": "Integrações",
        "illustration": "plugins-agentes.png",
        "subject": "Use o Cadu dentro do assistente de IA que você já usa",
        "title": "Leve o contexto do Cadu para o assistente que você já usa.",
        "description": "Conecte ChatGPT, Claude, Cursor ou Codex ao seu projeto, com as permissões que você aprovar.",
        "cta_label": "Conectar meu assistente",
        "cta_path": "/integracoes",
        "secondary_label": "Entender como funciona",
        "secondary_path": "/workspace/conteudos/conectar-agente-de-ia",
        "default_body": "Se você já trabalha com um assistente de IA, não precisa copiar e colar o briefing a cada conversa. Conectado ao Cadu, ele lê o projeto e a marca e trabalha sobre o mesmo contexto do seu time.\n\nPor ele você pode **consultar projetos e marcas, enviar notas, links e arquivos, criar documentos e abrir uma sessão do Studio** já com o briefing preenchido.\n\nVocê decide o que liberar: a conexão só habilita os módulos e permissões que você aprovar, e ações que envolvem equipe ou tokens pedem a sua confirmação.\n\nA configuração fica em Integrações, na parte de agentes de IA.",
    },
    "planner-radar": {
        "label": "Planner Radar → oportunidades para o próximo plano",
        "product": "planner",
        "eyebrow": "Novo no Planner",
        "illustration": "planner-radar.png",
        "subject": "Novo: o Radar de Oportunidades do Planner",
        "title": "Novo no Planner: sinais do mercado para o seu próximo plano.",
        "description": "O Radar busca oportunidades ligadas à sua marca e mostra de onde veio cada uma.",
        "cta_label": "Abrir o Radar",
        "cta_path": "/radar",
        "secondary_label": "Ler o guia do Radar",
        "secondary_product": "workspace",
        "secondary_path": "/workspace/conteudos/radar-de-oportunidades",
        "default_body": "O Radar de Oportunidades procura, com base na marca e no projeto, notícias e sinais de mercado que podem virar pauta, mídia ou ação. Em vez de uma lista solta, ele organiza o resultado numa **matriz Orgânico × Pago** e mostra a fonte de cada oportunidade.\n\nPara usar: escolha a marca e o projeto na barra de contexto, descreva em uma frase o que você quer observar e inicie a busca. Quando uma oportunidade fizer sentido, **crie o planejamento a partir dela**.\n\nÉ uma ferramenta nova. Cada busca usa tokens do seu saldo (cerca de 15 mil), então vale começar por um tema claro. **Confira sempre a fonte e a data** antes de apresentar algo ao cliente.",
    },
    "studio-criar": {
        "label": "Studio Criar → anúncios e imagens com a marca",
        "product": "studio",
        "eyebrow": "Studio",
        "illustration": "studio-criar.png",
        "subject": "Crie anúncios e imagens com a identidade da sua marca",
        "title": "Crie anúncios e imagens que já nascem com a sua marca.",
        "description": "No Studio, o briefing e a identidade da marca entram no pedido antes de você escrever.",
        "cta_label": "Abrir o Studio",
        "cta_path": "/criar",
        "secondary_label": "Ver o guia de campanha",
        "secondary_product": "workspace",
        "secondary_path": "/workspace/conteudos/campanha-em-formatos",
        "default_body": "Em Criar, você escolhe o que quer produzir (uma imagem, um anúncio ou a edição de uma peça) e o Studio parte da marca e do projeto que você já cadastrou.\n\nPara **anúncios**, a marca é obrigatória: é ela que garante cores, tom e referências aprovadas. Descreva o objetivo, o público, o formato e o texto exato que a peça deve ter.\n\nDepois, ajuste o que for preciso sem refazer tudo: composição, enquadramento, cor e acabamento. Cada geração usa tokens do seu saldo, e você acompanha o consumo no extrato do Workspace.\n\nSe ainda não cadastrou a marca, comece por ela: o resultado melhora muito.",
    },
    "audiencias": {
        "label": "Audiências → seleção com propósito",
        "product": "planner",
        "subject": "Antes de escolher canais, entenda quem a campanha precisa alcançar",
        "title": "Antes de escolher canais, entenda quem a campanha precisa alcançar.",
        "description": "Audiência é uma decisão que sustenta o mix — não uma etapa de preenchimento.",
        "cta_label": "Explorar Audiências",
        "cta_path": "/audiencias",
        "default_body": "Antes de comparar públicos, responda três perguntas: **quem precisa ser alcançado, qual sinal sustenta essa escolha e qual papel essa pessoa tem na campanha**. Isso evita selecionar uma audiência apenas porque ela parece familiar.\n\nEm Audiências, comece pelo objetivo do projeto e conecte a escolha à praça e ao canal. Registre também o que depende de confirmação comercial. A recomendação fica mais clara para o cliente e mais simples de otimizar depois.",
    },
    "canais": {
        "label": "Canais → papel no mix",
        "product": "planner",
        "subject": "Cada canal precisa ter um papel claro no seu plano",
        "title": "Cada canal precisa ter um papel claro no seu plano.",
        "description": "Uma lista de canais não explica uma estratégia.",
        "cta_label": "Conhecer Canais",
        "cta_path": "/canais",
        "default_body": "Conhecer um canal não basta. A escolha começa quando você define se ele serve para **gerar descoberta, sustentar consideração, capturar intenção ou apoiar conversão**.\n\nEm Canais, compare apenas as opções que respondem ao objetivo atual do projeto. Registre público, formato principal, métrica, risco e o que precisa de confirmação. Isso transforma um mix habitual em uma decisão que o time consegue defender e ajustar.",
    },
    "places": {
        "label": "Places → praça e lugares específicos",
        "product": "planner",
        "subject": "Escolha os lugares onde a mensagem realmente ganha contexto",
        "title": "Escolha os lugares onde a mensagem realmente ganha contexto.",
        "description": "Praça é mais do que uma cidade escrita no briefing.",
        "cta_label": "Abrir Places",
        "cta_path": "/places",
        "default_body": "Quando o contexto físico importa, a praça não pode ser só o nome de uma cidade. Places ajuda a investigar onde a mensagem encontra a rotina do público — e por que aquele cenário fortalece a tese.\n\nExplore uma praça prioritária e relacione o lugar ao canal e ao momento de consumo. **Inventário, preço e viabilidade continuam sujeitos à confirmação comercial**. O ganho aqui é construir uma decisão mais contextual e menos genérica.",
    },
    "formatos": {
        "label": "Formatos → especificação de entrega",
        "product": "studio",
        "subject": "Antes de editar, defina onde e como o criativo precisa performar",
        "title": "Antes de editar, defina onde e como o criativo precisa performar.",
        "description": "Edição, vídeo e formato funcionam melhor quando respondem ao contexto certo.",
        "cta_label": "Ver Formatos",
        "cta_path": "/formatos",
        "default_body": "Antes de editar um vídeo ou adaptar uma imagem, confirme **placement, dimensão ou duração, ativos disponíveis e limitações técnicas**. Esse alinhamento evita que a edição descubra restrições tarde demais.\n\nEm Formatos, encontre a entrega compatível com o canal prioritário e registre o que é obrigatório, preferencial ou proibido. A análise do criativo fica mais útil quando compara peças feitas para o contexto em que serão vistas.",
    },
    "connect-reports": {
        "label": "Reports → reports que sustentam decisões",
        "product": "connect",
        "subject": "Um report útil mostra o que mudou e qual decisão vem depois",
        "title": "Um report útil mostra o que mudou e qual decisão vem depois.",
        "description": "Dados só viram gestão quando ganham contexto, leitura e próximo passo.",
        "cta_label": "Abrir Reports",
        "cta_path": "/",
        "default_body": "Um número isolado não explica uma campanha. Um bom report conecta **período, indicador, objetivo, contexto e a decisão que o time precisa tomar**. Assim, a conversa deixa de ser uma lista de métricas e passa a orientar a gestão.\n\nNo Reports, organize fontes autorizadas, revise os dados antes de usar e registre a leitura que acompanha cada mudança. O report fica pronto para o cliente entender o que aconteceu — e para o time saber o que fazer em seguida.",
    },
    "skills-conhecimento-reutilizavel": {
        "label": "Skills → conhecimento que o time reutiliza",
        "product": "skills",
        "subject": "Transforme uma boa orientação em conhecimento que o time consegue reutilizar",
        "title": "Transforme uma boa orientação em conhecimento que o time consegue reutilizar.",
        "description": "Exemplos, contexto e instruções certos evitam que cada projeto recomece do zero.",
        "cta_label": "Abrir Skills",
        "cta_path": "/skills/",
        "default_body": "Uma orientação útil não precisa ficar presa a uma conversa ou a uma pessoa. Quando você reúne **objetivo, contexto, exemplos aprovados e limites claros**, o time passa a aplicar o mesmo raciocínio com mais consistência.\n\nEm Skills, organize o que deve ser repetido: como analisar, qual referência usar, o que evitar e como revisar o resultado. A próxima pessoa começa com conhecimento confiável — e não apenas com uma página em branco.",
    },
    "smart-docs": {
        "label": "Smart Docs → decisão documentada",
        "product": "workspace",
        "subject": "Registre a decisão para o projeto não recomeçar do zero",
        "title": "Registre a decisão para o projeto não recomeçar do zero.",
        "description": "O que foi decidido precisa sobreviver à reunião.",
        "cta_label": "Abrir Smart Docs",
        "cta_path": "/smart-docs",
        "default_body": "Um plano só continua útil se o time encontra **a tese, as escolhas feitas, as premissas e as pendências** depois da reunião. Sem isso, cada ajuste parece um recomeço.\n\nEm Smart Docs, registre a decisão recente perto do projeto: público, canais, formatos, riscos e próximos passos. Quando o cliente pedir mudança ou outra pessoa entrar no trabalho, a lógica continua acessível.",
    },
}


def _visible_growth_models() -> Dict[str, Dict[str, Any]]:
    """Skills fora do lançamento: o modelo com CTA para Skills some da suíte."""
    from ..product_flags import skills_enabled
    if skills_enabled():
        return GROWTH_EMAIL_MODELS
    return {key: model for key, model in GROWTH_EMAIL_MODELS.items() if model["product"] != "skills"}


def list_growth_email_model_choices() -> List[Tuple[str, str]]:
    return [(key, model["label"]) for key, model in _visible_growth_models().items()]


def _absolute_url(product: str, path: str) -> str:
    return product_url(product, path)


def _format_body_html(text: str) -> Markup:
    """Aceita apenas markdown de negrito e parágrafos; todo o resto é escapado."""
    paragraphs = []
    for paragraph in str(text or "").strip().split("\n\n"):
        safe_text = str(escape(paragraph.strip()))
        safe_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe_text)
        if safe_text:
            paragraphs.append(f'<p style="margin:0 0 16px">{safe_text}</p>')
    return Markup("".join(paragraphs))


def build_growth_email(model_key: str, *, body: str | None = None, first_name: str | None = None,
                       unsubscribe_url: str | None = None) -> Dict[str, Any]:
    model = _visible_growth_models().get(model_key)
    if not model:
        raise KeyError(model_key)
    product = model["product"]
    text = body or model["default_body"]
    if first_name:
        text = f"Olá, {first_name}.\n\n{text}"
    return {
        "model_key": model_key,
        "model_label": model["label"],
        "subject": model["subject"],
        "template_name": "cadu-growth.html",
        "template_folder": "emails/externos",
        "product": product,
        "params": {
            "BRAND": product_email_brand(product),
            "BRAND_BAND_URL": email_asset_url(GROWTH_EMAIL_BAND_URLS[product]),
            "TITLE": model["title"],
            "DESCRIPTION": model["description"],
            "BODY_HTML": _format_body_html(text),
            "UNSUBSCRIBE_URL": unsubscribe_url or "",
            "CTA_LABEL": model["cta_label"],
            "CTA_URL": _absolute_url(product, model["cta_path"]),
            "EYEBROW": model.get("eyebrow", ""),
            "ILLUSTRATION_URL": email_asset_url(GROWTH_EMAIL_ILLUSTRATIONS_URL + model["illustration"]) if model.get("illustration") else "",
            "SECONDARY_LABEL": model.get("secondary_label", ""),
            "SECONDARY_URL": _absolute_url(model.get("secondary_product", product), model["secondary_path"]) if model.get("secondary_path") else "",
        },
    }


def render_growth_email(model_key: str, *, first_name: str | None = None,
                        unsubscribe_url: str | None = None) -> str:
    cfg = build_growth_email(model_key, first_name=first_name, unsubscribe_url=unsubscribe_url)
    template_name = f"{cfg['template_folder']}/{cfg['template_name']}"
    template_vars = {key.lower(): value for key, value in cfg["params"].items()}
    if has_request_context():
        return render_template(template_name, **template_vars)
    # A suíte também é executável pelo terminal/worker, onde os context
    # processors do ERP ainda esperam uma requisição Flask.
    with current_app.test_request_context("/teste-brevo/cadu-growth"):
        return render_template(template_name, **template_vars)


def _send_growth_test(app, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Envia HTML já renderizado dentro do contexto Flask do worker."""
    with app.app_context():
        return get_brevo_product_service(cfg["product"]).enviar_email(
            to_email=BREVO_GROWTH_TEST_RECIPIENT,
            to_name="Apolo",
            subject=f"[TESTE] {cfg['subject']}",
            html_content=cfg["html"],
        )


def _selected_model_keys(model_keys: Iterable[str] | None) -> List[str]:
    visible = _visible_growth_models()
    if model_keys is None:
        return list(visible)
    selected = list(dict.fromkeys(str(key) for key in model_keys if str(key) in visible))
    if not selected:
        raise ValueError("Selecione ao menos um modelo de e-mail válido.")
    return selected


def run_growth_email_test_suite(
    *, dry_run: bool = False, model_keys: Iterable[str] | None = None
) -> Dict[str, Any]:
    """Executa os modelos selecionados; cada resultado é independente para não travar a suíte."""
    results: List[Dict[str, Any]] = []
    prepared: List[Tuple[int, Dict[str, Any]]] = []
    selected_model_keys = _selected_model_keys(model_keys)
    for model_key in selected_model_keys:
        cfg = build_growth_email(model_key)
        try:
            preview_html = render_growth_email(model_key)
            result: Dict[str, Any] = {
                "model_key": model_key,
                "label": cfg["model_label"],
                "subject": cfg["subject"],
                "success": True,
                "dry_run": dry_run,
                "preview_html": preview_html,
            }
            cfg["html"] = preview_html
            prepared.append((len(results), cfg))
        except Exception as exc:  # cada modelo deve falhar isoladamente
            result = {"model_key": model_key, "label": cfg["model_label"], "success": False, "error": str(exc)}
        results.append(result)

    if not dry_run and prepared:
        app = current_app._get_current_object()
        # No máximo três conexões simultâneas: limita pressão na API e impede
        # que um timeout transforme a suíte inteira em uma fila de seis envios.
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="brevo-growth-test") as executor:
            futures = {executor.submit(_send_growth_test, app, cfg): index for index, cfg in prepared}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results[index].update(future.result())
                except Exception as exc:
                    results[index].update({"success": False, "error": str(exc)})
    return {
        "recipient": BREVO_GROWTH_TEST_RECIPIENT,
        "selected_model_keys": selected_model_keys,
        "dry_run": dry_run,
        "results": results,
        "success": all(item.get("success") for item in results),
        "sent": sum(1 for item in results if item.get("success") and not dry_run),
        "failed": sum(1 for item in results if not item.get("success")),
    }
