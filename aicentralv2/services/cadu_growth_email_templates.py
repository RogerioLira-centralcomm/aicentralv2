"""Modelos de e-mail de adoção do Cadu e suíte segura de teste Brevo."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from typing import Any, Dict, Iterable, List, Tuple

from flask import current_app, has_request_context, render_template
from markupsafe import Markup, escape

from aicentralv2.services.brevo_service import get_brevo_product_service, product_email_brand


# Nunca aceitar o destinatário por formulário: a suíte é exclusiva de homologação.
BREVO_GROWTH_TEST_RECIPIENT = "apolo@centralcomm.media"
GROWTH_EMAIL_HEADER_IMAGE_URLS = {
    "workspace": "https://cadu.centralcomm.media/static/images/cadu/email/workspace-growth-v2.png",
    "studio": "https://cadu.centralcomm.media/static/images/cadu/email/studio-growth-v2.png",
    "connect": "https://cadu.centralcomm.media/static/images/cadu/email/connect-growth-v2.png",
    "skills": "https://cadu.centralcomm.media/static/images/cadu/email/skills-growth-v2.png",
    "planner": "https://cadu.centralcomm.media/static/images/cadu/email/planner-growth-v2.png",
}

GROWTH_EMAIL_MODELS: Dict[str, Dict[str, str]] = {
    "conversa-para-plano": {
        "label": "Conversas → planejamento completo",
        "product": "workspace",
        "subject": "Transforme a conversa de hoje em um plano que o time consegue executar",
        "title": "Transforme a conversa de hoje em um plano que o time consegue executar.",
        "description": "O contexto já existe. Agora ele pode virar uma decisão clara.",
        "cta_label": "Abrir Conversas",
        "cta_path": "/workspace/app/conversas",
        "default_body": "Você não precisa começar com uma planilha em branco. Uma boa conversa já reúne objetivo, público, praça, prazo, verba e restrições. O Cadu ajuda a separar **o que está confirmado, o que é premissa e o que ainda precisa de validação**.\n\nAbra o projeto em andamento, registre o briefing que você já tem e peça uma estrutura de decisão. Assim, o time reduz retrabalho e volta ao raciocínio original quando a campanha mudar.",
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
        "subject": "Defina o formato antes de pedir a próxima peça",
        "title": "Defina o formato antes de pedir a próxima peça.",
        "description": "A criação trabalha melhor quando a entrega já foi decidida.",
        "cta_label": "Ver Formatos",
        "cta_path": "/formatos",
        "default_body": "Antes de pedir uma peça, confirme **dispositivo, placement, dimensão ou duração, ativos e limitações técnicas**. Esse alinhamento evita que a criação descubra restrições quando já está produzindo.\n\nEm Formatos, encontre a entrega compatível com o canal prioritário e registre o que é obrigatório, preferencial ou proibido. A peça continua criativa, mas nasce pronta para o contexto em que será vista.",
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


def list_growth_email_model_choices() -> List[Tuple[str, str]]:
    return [(key, model["label"]) for key, model in GROWTH_EMAIL_MODELS.items()]


def _absolute_url(path: str) -> str:
    return f"{str(current_app.config.get('CADU_URL') or 'https://cadu.centralcomm.media').rstrip('/')}{path}"


def _format_body_html(text: str) -> Markup:
    """Aceita apenas markdown de negrito e parágrafos; todo o resto é escapado."""
    paragraphs = []
    for paragraph in str(text or "").strip().split("\n\n"):
        safe_text = str(escape(paragraph.strip()))
        safe_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe_text)
        if safe_text:
            paragraphs.append(f'<p style="margin:0 0 16px">{safe_text}</p>')
    return Markup("".join(paragraphs))


def build_growth_email(model_key: str, *, body: str | None = None) -> Dict[str, Any]:
    model = GROWTH_EMAIL_MODELS.get(model_key)
    if not model:
        raise KeyError(model_key)
    product = model["product"]
    return {
        "model_key": model_key,
        "model_label": model["label"],
        "subject": model["subject"],
        "template_name": "cadu-growth.html",
        "template_folder": "emails/externos",
        "product": product,
        "params": {
            "BRAND": product_email_brand(product),
            "HEADER_IMAGE_URL": GROWTH_EMAIL_HEADER_IMAGE_URLS[product],
            "TITLE": model["title"],
            "DESCRIPTION": model["description"],
            "BODY_HTML": _format_body_html(body or model["default_body"]),
            "CTA_LABEL": model["cta_label"],
            "CTA_URL": _absolute_url(model["cta_path"]),
        },
    }


def render_growth_email(model_key: str) -> str:
    cfg = build_growth_email(model_key)
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
    if model_keys is None:
        return list(GROWTH_EMAIL_MODELS)
    selected = list(dict.fromkeys(str(key) for key in model_keys if str(key) in GROWTH_EMAIL_MODELS))
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
