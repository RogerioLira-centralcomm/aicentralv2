"""E-mails da Área do Cliente (identidade Centralcomm, remetente Brevo "clientes").

Para o cliente: novo acesso (segurança), acesso liberado (com criação de senha
quando falta), nova senha, senha alterada e briefing recebido. Para a equipe:
pedido de acesso e novo briefing, sempre para o executivo da conta (ou a caixa
da equipe, quando o cliente não tem executivo).

O HTML é montado na requisição e o envio roda em segundo plano: login e briefing
não esperam o Brevo. Falha de envio só vai para o log.
"""

from __future__ import annotations

import logging
import secrets
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, render_template, request

logger = logging.getLogger(__name__)
FUSO = ZoneInfo("America/Sao_Paulo")
HORAS_CRIAR_SENHA = 72
MODELOS = ("novo-acesso", "acesso-liberado", "redefinir-senha", "senha-alterada",
           "pedido-acesso", "briefing-novo", "briefing-recebido")


def _url(path="/"):
    from ..product_domains import product_url
    return product_url("clientes", path)


def _agora_br() -> str:
    return datetime.now(FUSO).strftime("%d/%m/%Y às %H:%M")


def _primeiro(nome) -> str:
    partes = str(nome or "").split()
    return partes[0] if partes else "tudo bem"


def renderizar(modelo: str, **ctx) -> str:
    from ..services.brevo_service import product_email_brand
    return render_template(f"emails/area_cliente/{modelo}.html",
                           brand=product_email_brand("clientes"), area_url=_url("/"), **ctx)


def _enviar(modelo, para_email, para_nome, assunto, ctx, reply_to=None) -> bool:
    """Monta o HTML agora e entrega em segundo plano. Devolve False se não há destinatário."""
    if not para_email:
        return False
    html = renderizar(modelo, **ctx)
    app = current_app._get_current_object()
    if app.config.get("MAIL_DEBUG"):
        logger.info("Área do Cliente (MAIL_DEBUG): %s -> %s", assunto, para_email)
        return True
    from ..services.brevo_service import get_brevo_product_service
    servico = get_brevo_product_service("clientes")

    def entregar():
        with app.app_context():
            try:
                resultado = servico.enviar_email(to_email=para_email, to_name=para_nome or para_email,
                                                 subject=assunto, html_content=html, reply_to=reply_to,
                                                 tags=["area-cliente", modelo])
                if not (resultado or {}).get("success"):
                    logger.warning("E-mail %s não enviado para %s: %s", modelo, para_email, (resultado or {}).get("error"))
            except Exception:
                logger.warning("Falha ao enviar o e-mail %s", modelo, exc_info=True)

    threading.Thread(target=entregar, name=f"email-{modelo}", daemon=True).start()
    return True


def _executivo_do_cliente(cliente_id) -> dict:
    from .. import db
    from ..campanha_acompanhamento_publico import _whatsapp
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT cli.nome_fantasia, vend.nome_completo, vend.email, vend.telefone
                  FROM tbl_cliente cli
                  LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
                 WHERE cli.id_cliente = %s
                """,
                (cliente_id,),
            )
            row = cursor.fetchone() or {}
    except Exception:
        conn.rollback()
        raise
    return {"cliente": row.get("nome_fantasia") or "", "nome": row.get("nome_completo") or "",
            "email": row.get("email") or "", "whatsapp": _whatsapp(row.get("telefone"))}


def _reply_executivo(executivo):
    return {"name": executivo["nome"], "email": executivo["email"]} if executivo and executivo.get("email") else None


def _dispositivo(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    navegador = next((n for chave, n in (("edg", "Edge"), ("chrome", "Chrome"), ("firefox", "Firefox"), ("safari", "Safari")) if chave in ua), "Navegador")
    sistema = next((s for chave, s in (("iphone", "iPhone"), ("ipad", "iPad"), ("android", "Android"), ("mac os", "macOS"), ("windows", "Windows"), ("linux", "Linux")) if chave in ua), "")
    return f"{navegador} em {sistema}" if sistema else navegador


# ---------- Para o cliente ----------

def novo_acesso(usuario_login: dict) -> bool:
    """Aviso de segurança a cada login no host da Área do Cliente."""
    cliente_id = usuario_login.get("pk_id_tbl_cliente")
    executivo = _executivo_do_cliente(cliente_id) if cliente_id else {}
    ctx = {
        "primeiro_nome": _primeiro(usuario_login.get("nome_completo")), "email": usuario_login.get("email"),
        "cliente": executivo.get("cliente", ""), "quando": _agora_br(),
        "dispositivo": _dispositivo(request.headers.get("User-Agent", "")),
        "ip": request.headers.get("X-Real-IP") or request.remote_addr or "",
        "link_senha": _url("/forgot-password"), "executivo": executivo,
    }
    return _enviar("novo-acesso", usuario_login.get("email"), usuario_login.get("nome_completo"),
                   "Novo acesso à sua Área do Cliente", ctx, _reply_executivo(executivo))


def acesso_liberado(contato: dict) -> bool:
    """Ao ligar o acesso no CRM v3. Sem senha cadastrada, manda o link para criar uma."""
    from .. import db
    executivo = _executivo_do_cliente(contato.get("pk_id_tbl_cliente"))
    link_senha = ""
    if not contato.get("tem_senha"):
        token = secrets.token_urlsafe(32)
        if db.atualizar_reset_token(contato["email"], token, datetime.utcnow() + timedelta(hours=HORAS_CRIAR_SENHA)):
            link_senha = _url(f"/reset-password/{token}")
    ctx = {"primeiro_nome": _primeiro(contato.get("nome_completo")), "email": contato.get("email"),
           "cliente": executivo.get("cliente", ""), "link_senha": link_senha,
           "horas_validade": HORAS_CRIAR_SENHA, "executivo": executivo}
    return _enviar("acesso-liberado", contato.get("email"), contato.get("nome_completo"),
                   "Sua Área do Cliente Centralcomm está liberada", ctx, _reply_executivo(executivo))


def redefinir_senha(contato: dict, link_reset: str, minutos=60) -> bool:
    return _enviar("redefinir-senha", contato.get("email"), contato.get("nome_completo"), "Crie uma nova senha",
                   {"primeiro_nome": _primeiro(contato.get("nome_completo")), "link_reset": link_reset,
                    "minutos_validade": minutos, "executivo": None})


def senha_alterada(contato: dict) -> bool:
    return _enviar("senha-alterada", contato.get("email"), contato.get("nome_completo"), "Sua senha foi alterada",
                   {"primeiro_nome": _primeiro(contato.get("nome_completo")), "quando": _agora_br(),
                    "link_senha": _url("/forgot-password"), "executivo": None})


def _resumo_briefing(valores: dict) -> dict:
    from .briefing import CANAIS
    rotulos = dict(CANAIS)
    ini, fim = valores.get("inicio"), valores.get("fim")
    periodo = ""
    if ini or fim:
        periodo = f"{ini.strftime('%d/%m/%Y') if ini else 'a definir'} a {fim.strftime('%d/%m/%Y') if fim else 'a definir'}"
    itens = (valores.get("descobrir") or "").split("\n", 1)[1].replace("- ", "") if valores.get("descobrir") else ""
    from .briefing import qualidade, resumo
    secoes = [(r, t) for r, t in resumo(valores) if r not in ("Objetivo", "Mais detalhes")] if "objetivo_tipo" in valores else []
    return {"titulo": valores.get("titulo"), "objetivo": valores.get("objetivo"), "publico": valores.get("publico"),
            "periodo": periodo, "verba": valores.get("verba"), "descricao": valores.get("descricao"),
            "canais": ", ".join(rotulos[c] for c in valores.get("canais") or [] if c in rotulos),
            "itens_descobrir": itens, "secoes": secoes, "origem": valores.get("origem_rotulo") or "",
            "objetivo_completo": dict(resumo(valores)).get("Objetivo", valores.get("objetivo")) if secoes else valores.get("objetivo"),
            "qualidade": (valores.get("qualidade") or qualidade(valores)) if secoes else None}


def briefing_recebido(usuario: dict, valores: dict) -> bool:
    executivo = usuario.get("executivo") or {}
    ctx = {**_resumo_briefing(valores), "primeiro_nome": usuario.get("primeiro_nome"), "quando": _agora_br(),
           "link_briefing": _url("/briefing"), "executivo": executivo}
    return _enviar("briefing-recebido", usuario.get("email"), usuario.get("nome"),
                   f"Recebemos seu briefing: {valores.get('titulo')}", ctx, _reply_executivo(executivo))


# ---------- Para a equipe Centralcomm ----------

def _destino_equipe(executivo) -> tuple[str, str]:
    if executivo and executivo.get("email"):
        return executivo["email"], executivo["nome"]
    return current_app.config.get("AREA_CLIENTE_EMAIL_EQUIPE", ""), "Equipe Centralcomm"


def briefing_novo(usuario: dict, valores: dict, briefing_id: int) -> bool:
    from ..product_domains import product_url
    executivo = usuario.get("executivo") or {}
    para, nome = _destino_equipe(executivo)
    ctx = {**_resumo_briefing(valores), "nome": usuario.get("nome"), "email": usuario.get("email"),
           "cliente": usuario.get("cliente_nome"), "primeiro_nome_executivo": _primeiro(nome),
           "link_briefings": product_url("centralx", f"/briefings?busca={briefing_id}"), "executivo": None}
    reply = {"name": usuario.get("nome"), "email": usuario.get("email")} if usuario.get("email") else None
    return _enviar("briefing-novo", para, nome, f"Novo briefing de {usuario.get('cliente_nome')}: {valores.get('titulo')}", ctx, reply)


def pedido_acesso(usuario: dict) -> bool:
    from ..product_domains import product_url
    executivo = usuario.get("executivo") or {}
    para, nome = _destino_equipe(executivo)
    ctx = {"nome": usuario.get("nome"), "email": usuario.get("email"), "cliente": usuario.get("cliente_nome"),
           "quando": _agora_br(), "primeiro_nome_executivo": _primeiro(nome),
           "link_crm": product_url("centralx", f"/crm-v3?cliente={usuario.get('cliente_id')}"), "executivo": None}
    reply = {"name": usuario.get("nome"), "email": usuario.get("email")} if usuario.get("email") else None
    return _enviar("pedido-acesso", para, nome, f"{usuario.get('nome')} pediu acesso à Área do Cliente", ctx, reply)


# ---------- Prévias (sem envio) ----------

def previa(modelo: str) -> str:
    """HTML de um modelo com dados de exemplo, para revisar o layout."""
    executivo = {"nome": "João Figueiredo", "email": "joao@centralcomm.media", "whatsapp": "https://wa.me/5531999990000"}
    exemplo_briefing = {"titulo": "Lançamento da coleção de verão", "objetivo": "Gerar visitas às lojas de BH e vender pelo site.",
                        "publico": "Mulheres de 25 a 45 anos, Belo Horizonte e região", "periodo": "01/12/2026 a 15/01/2027",
                        "verba": "até R$ 50 mil", "canais": "Redes sociais, Busca", "itens_descobrir": "Canal: Spotify\nAudiência: Alta Renda",
                        "descricao": "Já temos as peças da campanha de inverno como referência.",
                        "secoes": [("Público", "Mulheres de 25 a 45 anos\nRecorte: Mulheres; idades 25-34, 35-44; classes A, B"),
                                   ("Praças", "Abrangência: Cidades\nBelo Horizonte - MG; Contagem - MG; Nova Lima - MG"),
                                   ("Período", "01/12/2026 a 15/01/2027\nDatas-chave: Black Friday, Natal"),
                                   ("Verba prevista", "R$ 20 a 50 mil"), ("Canais de interesse", "Redes sociais, Busca"),
                                   ("Materiais e mensuração", "Tenho as peças prontas\nSite/destino: loja.exemplo.com.br\nMensuração: Pixel da Meta, Google Analytics 4")],
                        "objetivo_completo": "Tipo: Vender pelo site ou app\nKPI principal: Vendas (meta: 300 pedidos)\nGerar visitas às lojas de BH e vender pelo site.",
                        "origem": "PI Coleção de inverno (05/2026)",
                        "qualidade": {"nota": 88, "pendencias": ["Informar a verba ou uma faixa."], "avisos": []}}
    ctx = {
        "novo-acesso": {"primeiro_nome": "Ana", "email": "ana@cliente.com.br", "cliente": "CLIENTE EXEMPLO", "quando": _agora_br(),
                        "dispositivo": "Chrome em macOS", "ip": "187.0.0.1", "link_senha": _url("/forgot-password"), "executivo": executivo},
        "acesso-liberado": {"primeiro_nome": "Ana", "email": "ana@cliente.com.br", "cliente": "CLIENTE EXEMPLO",
                            "link_senha": _url("/reset-password/exemplo"), "horas_validade": HORAS_CRIAR_SENHA, "executivo": executivo},
        "redefinir-senha": {"primeiro_nome": "Ana", "link_reset": _url("/reset-password/exemplo"), "minutos_validade": 60, "executivo": None},
        "senha-alterada": {"primeiro_nome": "Ana", "quando": _agora_br(), "link_senha": _url("/forgot-password"), "executivo": None},
        "pedido-acesso": {"nome": "Ana Souza", "email": "ana@cliente.com.br", "cliente": "CLIENTE EXEMPLO", "quando": _agora_br(),
                          "primeiro_nome_executivo": "João", "link_crm": "#", "executivo": None},
        "briefing-novo": {**exemplo_briefing, "nome": "Ana Souza", "email": "ana@cliente.com.br", "cliente": "CLIENTE EXEMPLO",
                          "primeiro_nome_executivo": "João", "link_briefings": "#", "executivo": None},
        "briefing-recebido": {**exemplo_briefing, "primeiro_nome": "Ana", "quando": _agora_br(), "link_briefing": _url("/briefing"),
                              "executivo": executivo},
    }[modelo]
    return renderizar(modelo, **ctx)
