"""Leads v3: e-mail do passo enviado pela Brevo em nome do executivo, com assinatura em modelo e medição.

O executivo revisa o texto e envia com um clique. Remetente e reply-to são o e-mail dele (o domínio
centralcomm.media está autenticado na Brevo), então a resposta cai na caixa dele. Abertura e clique
chegam pelo webhook da Brevo e viram eventos do lead. Abertura por proxy (Apple Mail Privacy Protection
e afins abrem o e-mail sozinhos) fica contada à parte e não vale como abertura real.
"""

from __future__ import annotations

import html
import logging
import os
import re
from datetime import datetime

from . import leads_v3_cadencias as cadencias
from .leads_v3_mensagens import DISPOSITIVOS
from .leads_v3_prospeccao import ProspeccaoError

DOMINIOS_REMETENTE = tuple(d.strip().lower() for d in os.getenv("LEADS_V3_SENDER_DOMAINS", "centralcomm.media").split(",")
                           if d.strip())
# Proteção da reputação do domínio: e-mails de prospecção por executivo por dia.
LIMITE_DIARIO = int(os.getenv("LEADS_V3_EMAIL_DAILY_LIMIT", "60"))
EMPRESA = "CentralComm"
SITE = os.getenv("LEADS_V3_SIGNATURE_SITE", "https://centralcomm.media")
logger = logging.getLogger(__name__)

_RODAPE_RE = re.compile(r"\n+(" + "|".join(re.escape(v) for v in DISPOSITIVOS.values() if v) + r")\s*$")
_URL_RE = re.compile(r"https?://[^\s<>()\"']+[^\s<>()\"'.,;:!?]")
_LINKEDIN_RE = re.compile(r"^https://([a-z]{2,3}\.)?linkedin\.com/", re.I)

# Fonte comum do corpo e da assinatura: parece e-mail escrito à mão, não peça de marketing.
_FONTE = "font-family:Arial,Helvetica,sans-serif;"


def _sem_esquema(url):
    return re.sub(r"^https?://(www\.)?", "", url or "").rstrip("/")


def _tel_href(telefone):
    digitos = re.sub(r"[^\d+]", "", telefone or "")
    if digitos and not digitos.startswith("+"):
        digitos = "+55" + digitos.lstrip("0") if len(digitos) <= 11 else "+" + digitos
    return f"tel:{digitos}" if digitos else ""


def _assinatura_simples(dados):
    """Nome em negrito, cargo · empresa e uma linha de contato. Sem imagem: não cai em Promoções."""
    nome, cargo = dados.get("nome") or "", dados.get("cargo") or ""
    telefone, linkedin = dados.get("telefone") or "", dados.get("linkedin_url") or ""
    linha2 = " · ".join(p for p in (cargo, EMPRESA) if p)
    contato_txt = [p for p in (telefone, linkedin, _sem_esquema(SITE)) if p]
    texto = "\n".join(p for p in (nome, linha2, " · ".join(contato_txt)) if p)

    esc = html.escape
    links = []
    if telefone:
        links.append(f'<a href="{esc(_tel_href(telefone))}" style="color:#555;text-decoration:none">{esc(telefone)}</a>')
    if linkedin:
        links.append(f'<a href="{esc(linkedin)}" style="color:#555">LinkedIn</a>')
    links.append(f'<a href="{esc(SITE)}" style="color:#555">{esc(_sem_esquema(SITE))}</a>')
    partes = []
    if nome:
        partes.append(f'<strong style="color:#222">{esc(nome)}</strong>')
    if linha2:
        partes.append(esc(linha2))
    partes.append(" · ".join(links))
    html_ = f'<div style="{_FONTE}font-size:13px;line-height:1.5;color:#555;margin-top:12px">' + "<br>".join(partes) + "</div>"
    return texto, html_


# Os próximos modelos entram aqui; a preferência do executivo só guarda a chave.
MODELOS_ASSINATURA = {
    "simples": {"rotulo": "Simples", "montar": _assinatura_simples},
}


def normalizar_preferencias(payload):
    """Campos da assinatura vindos da tela. Erros viram ProspeccaoError (mensagem para o executivo)."""
    modelo = payload.get("modelo_assinatura") or "simples"
    if modelo not in MODELOS_ASSINATURA:
        raise ProspeccaoError("Modelo de assinatura inválido.")
    linkedin = str(payload.get("linkedin_url") or "").strip()
    if linkedin and not linkedin.lower().startswith("http"):
        linkedin = "https://" + linkedin
    if linkedin and not _LINKEDIN_RE.match(linkedin):
        raise ProspeccaoError("O LinkedIn precisa ser um link do linkedin.com.")
    return {
        "modelo_assinatura": modelo,
        "nome_assinatura": str(payload.get("nome_assinatura") or "").strip()[:120] or None,
        "cargo": str(payload.get("cargo") or "").strip()[:120] or None,
        "telefone": str(payload.get("telefone") or "").strip()[:40] or None,
        "linkedin_url": linkedin[:300] or None,
    }


def assinatura(prefs, *, nome_usuario=None):
    """(texto, html) do bloco de assinatura do executivo, no modelo que ele escolheu."""
    prefs = prefs or {}
    modelo = MODELOS_ASSINATURA.get(prefs.get("modelo_assinatura") or "simples", MODELOS_ASSINATURA["simples"])
    return modelo["montar"]({"nome": prefs.get("nome_assinatura") or nome_usuario, "cargo": prefs.get("cargo"),
                             "telefone": prefs.get("telefone"), "linkedin_url": prefs.get("linkedin_url")})


def _paragrafos_html(texto):
    """Texto puro → parágrafos HTML; links viram <a> (é por eles que a Brevo mede o clique)."""
    def linha(trecho):
        partes, inicio = [], 0
        for m in _URL_RE.finditer(trecho):
            partes.append(html.escape(trecho[inicio:m.start()]))
            url = html.escape(m.group(0))
            partes.append(f'<a href="{url}">{url}</a>')
            inicio = m.end()
        partes.append(html.escape(trecho[inicio:]))
        return "".join(partes)

    blocos = [b.strip("\n") for b in re.split(r"\n\s*\n", texto.strip()) if b.strip()]
    return "".join(f'<p style="margin:0 0 12px">{"<br>".join(linha(l) for l in b.split(chr(10)))}</p>' for b in blocos)


def montar_email(texto, prefs, *, nome_usuario=None):
    """Corpo revisado (com o fecho) + bloco de assinatura + 'Enviado do meu…' no fim. Devolve (html, texto)."""
    corpo = (texto or "").strip()
    match = _RODAPE_RE.search(corpo)
    rodape = match.group(1) if match else ""
    if match:
        corpo = corpo[:match.start()].rstrip()
    assin_txt, assin_html = assinatura(prefs, nome_usuario=nome_usuario)
    texto_final = "\n\n".join(p for p in (corpo, assin_txt, rodape) if p)
    html_final = (f'<div style="{_FONTE}font-size:14px;line-height:1.5;color:#222">{_paragrafos_html(corpo)}{assin_html}'
                  + (f'<p style="margin:16px 0 0;color:#888;font-size:13px">{html.escape(rodape)}</p>' if rodape else "")
                  + "</div>")
    return html_final, texto_final


def validar_remetente(email):
    email = str(email or "").strip().lower()
    dominio = email.rsplit("@", 1)[-1] if "@" in email else ""
    if dominio not in DOMINIOS_REMETENTE:
        raise ProspeccaoError(f"O envio pela Brevo sai do seu e-mail de login, que precisa ser @{DOMINIOS_REMETENTE[0]}. "
                              "Use 'Abrir no Gmail' por enquanto.")
    return email


def enviados_hoje(cursor, usuario_id, *, agora=None):
    agora = agora or datetime.now()
    cursor.execute(
        """
        SELECT COUNT(*) AS n FROM cadu_lead_mensagem_eventos
         WHERE evento = 'enviado' AND provedor = 'brevo' AND payload ->> 'id_usuario' = %s AND ocorreu_em >= %s
        """,
        [str(usuario_id), agora.replace(hour=0, minute=0, second=0, microsecond=0)],
    )
    return int((cursor.fetchone() or {}).get("n") or 0)


def enviar_passo(cursor, inscricao_id, *, assunto, texto, passo, usuario, prefs, enviar_fn, id_gancho=None, agora=None):
    """Envia o e-mail do passo atual e marca o passo como feito, na mesma transação.

    `usuario` = {id, nome, email} do executivo logado. `passo` é o passo que a tela mostrava: se a
    cadência já andou (clique duplo, outra aba), nada é enviado. `enviar_fn(**kwargs)` é o
    BrevoService.enviar_email (injetado para teste). A inscrição fica travada durante o envio.
    """
    assunto = str(assunto or "").strip()[:200]
    texto = str(texto or "").strip()
    if not assunto:
        raise ProspeccaoError("Escreva o assunto antes de enviar.")
    if not texto:
        raise ProspeccaoError("Escreva a mensagem antes de enviar.")
    remetente = validar_remetente(usuario.get("email"))
    cursor.execute(
        """
        SELECT i.id, i.id_lead, i.id_contato, i.status, i.passo_atual, cad.passos -> i.passo_atual AS passo,
               c.nome AS contato_nome, c.email, c.email_status
          FROM cadu_lead_cadencia_inscricoes i
          JOIN cadu_lead_cadencias cad ON cad.id = i.id_cadencia
          JOIN cadu_lead_contatos c ON c.id = i.id_contato
         WHERE i.id = %s
           FOR UPDATE OF i
        """,
        [inscricao_id],
    )
    insc = cursor.fetchone()
    if not insc:
        raise ProspeccaoError("Cadência não encontrada.")
    if insc["status"] != "ativa" or insc["passo_atual"] != passo:
        raise ProspeccaoError("Este passo já foi feito ou a cadência mudou. Atualize a tela.")
    if (insc["passo"] or {}).get("canal") != "email":
        raise ProspeccaoError("Este passo não é de e-mail.")
    destino = str(insc["email"] or "").strip()
    if not destino:
        raise ProspeccaoError("Esta pessoa não tem e-mail.")
    if insc["email_status"] == "invalido":
        raise ProspeccaoError("O e-mail desta pessoa está marcado como inválido.")
    cursor.execute("SELECT 1 FROM cadu_lead_optout WHERE canal = 'email' AND valor = %s", [destino.lower()])
    if cursor.fetchone():
        raise ProspeccaoError("Esta pessoa pediu para não receber e-mails.")
    if enviados_hoje(cursor, usuario["id"], agora=agora) >= LIMITE_DIARIO:
        raise ProspeccaoError(f"Você chegou ao limite de {LIMITE_DIARIO} e-mails por dia pela Brevo. Amanhã libera.")

    corpo_html, corpo_txt = montar_email(texto, prefs, nome_usuario=usuario.get("nome"))
    nome_remetente = (prefs or {}).get("nome_assinatura") or usuario.get("nome") or remetente
    resultado = enviar_fn(
        to_email=destino, to_name=insc["contato_nome"] or "", subject=assunto, html_content=corpo_html,
        text_content=corpo_txt, reply_to={"name": nome_remetente, "email": remetente}, tags=["leads-v3"],
        sender={"name": nome_remetente, "email": remetente},
    )
    if not resultado.get("success") or not resultado.get("messageId"):
        raise ProspeccaoError(resultado.get("user_message") or "A Brevo não aceitou o envio. Tente de novo em instantes.")

    try:
        cursor.execute(
            """
            INSERT INTO cadu_lead_mensagem_eventos (id_lead, id_contato, id_inscricao, canal, direcao, evento,
                                                    provedor, provedor_message_id, payload)
            VALUES (%s, %s, %s, 'email', 'saida', 'enviado', 'brevo', %s, %s)
            """,
            [insc["id_lead"], insc["id_contato"], inscricao_id, resultado["messageId"],
             cadencias._json({"id_usuario": str(usuario["id"]), "assunto": assunto, "passo": passo, "remetente": remetente,
                              **({"id_gancho": id_gancho} if id_gancho else {})})],
        )
        estado = cadencias.avancar(cursor, inscricao_id, "feito", usuario_id=usuario["id"], usuario_nome=usuario.get("nome"),
                                   nota=f"enviado pela Brevo: {assunto}", agora=agora, id_gancho=id_gancho)
    except Exception:
        # O e-mail já saiu: sem o registro, abertura e clique não chegam ao lead. Fica o id para conciliar.
        logger.error("leads-v3: e-mail enviado (messageId=%s, inscrição %s) sem registro no lead.",
                     resultado["messageId"], inscricao_id)
        raise
    return {**estado, "message_id": resultado["messageId"], "texto": corpo_txt}


# ─────────────────────────────────────────────────────
# Eventos do webhook da Brevo
# ─────────────────────────────────────────────────────
# O webhook da conta assina uniqueOpened/uniqueProxyOpen (primeira abertura); se um dia assinar também
# opened/proxyOpen (cada abertura), somar_evento casa a primeira de cada tipo para não contar em dobro.
EVENTOS_BREVO = {
    "delivered": "entregue", "opened": "aberto", "unique_opened": "aberto", "proxy_open": "aberto",
    "unique_proxy_open": "aberto", "click": "clicado", "hard_bounce": "bounce", "soft_bounce": "bounce",
    "blocked": "bounce", "invalid_email": "bounce", "invalid": "bounce", "spam": "optout", "unsubscribed": "optout",
    "error": "falhou",
}
_BOUNCE_DEFINITIVO = {"hard_bounce", "invalid_email", "invalid"}


def nome_evento(valor):
    """'uniqueOpened' / 'unique_opened' / 'Opened' → 'unique_opened' / 'opened'."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "_", str(valor or "").strip()).lower().replace(" ", "_")


def somar_evento(evento, atual, *, nome, quando, url=None, motivo=None):
    """Payload acumulado do evento (uma linha por e-mail e tipo de evento)."""
    novo = dict(atual or {})
    if evento == "aberto":
        chave = "proxy" if nome in ("proxy_open", "unique_proxy_open") else "reais"
        pendente = f"{chave}_unico_pendente"  # a primeira abertura veio pelo unique_* e o opened dela ainda não
        vezes = int(novo.get(chave) or 0)
        if nome.startswith("unique_"):
            if vezes:
                return novo  # o opened da primeira abertura já contou
            novo[chave], novo[pendente] = 1, True
        elif novo.pop(pendente, False):
            pass  # este opened é a mesma primeira abertura que o unique_* já contou
        else:
            novo[chave] = vezes + 1
        if chave == "reais":
            novo["primeira_real"] = novo.get("primeira_real") or quando
            novo["ultima_real"] = quando
        return novo
    novo["vezes"] = int(novo.get("vezes") or 0) + 1
    novo["ultimo_em"] = quando
    if evento == "clicado" and url:
        novo["urls"] = (list(dict.fromkeys([*(novo.get("urls") or []), url])))[-10:]
    if nome:
        novo["tipo"] = nome
    if motivo:
        novo["motivo"] = str(motivo)[:300]
    return novo


def aplicar_evento_brevo(cursor, evento_brevo, *, agora=None):
    """Grava o evento no lead se o message-id for de um e-mail do Leads v3. Devolve True se gravou."""
    nome = nome_evento(evento_brevo.get("event"))
    evento = EVENTOS_BREVO.get(nome)
    message_id = str(evento_brevo.get("message-id") or evento_brevo.get("messageId") or "").strip()
    if not evento or not message_id:
        return False
    cursor.execute(
        """
        SELECT id_lead, id_contato, id_inscricao FROM cadu_lead_mensagem_eventos
         WHERE provedor = 'brevo' AND provedor_message_id = %s AND evento = 'enviado'
        """,
        [message_id],
    )
    envio = cursor.fetchone()
    if not envio:
        return False
    cursor.execute(
        """
        INSERT INTO cadu_lead_mensagem_eventos (id_lead, id_contato, id_inscricao, canal, direcao, evento,
                                                provedor, provedor_message_id, payload)
        VALUES (%s, %s, %s, 'email', 'saida', %s, 'brevo', %s, '{}'::jsonb)
        ON CONFLICT (provedor, provedor_message_id, evento) WHERE provedor_message_id IS NOT NULL DO NOTHING
        """,
        [envio["id_lead"], envio["id_contato"], envio["id_inscricao"], evento, message_id],
    )
    cursor.execute(
        """
        SELECT id, payload FROM cadu_lead_mensagem_eventos
         WHERE provedor = 'brevo' AND provedor_message_id = %s AND evento = %s
           FOR UPDATE
        """,
        [message_id, evento],
    )
    linha = cursor.fetchone()
    quando = (agora or datetime.now()).strftime("%Y-%m-%dT%H:%M")
    payload = somar_evento(evento, linha["payload"], nome=nome, quando=quando, url=evento_brevo.get("link"),
                           motivo=evento_brevo.get("reason"))
    cursor.execute("UPDATE cadu_lead_mensagem_eventos SET payload = %s WHERE id = %s", [cadencias._json(payload), linha["id"]])

    if evento == "optout" and envio["id_contato"]:
        _parar_por_optout(cursor, envio, nome)
    elif evento == "bounce" and nome in _BOUNCE_DEFINITIVO and envio["id_contato"]:
        _parar_por_bounce(cursor, envio)
    return True


def _parar_cadencias(cursor, contato_id, status, motivo):
    cursor.execute(
        """
        UPDATE cadu_lead_cadencia_inscricoes SET status = %s, proxima_em = NULL, motivo_parada = %s
         WHERE id_contato = %s AND status IN ('ativa', 'pausada')
        """,
        [status, motivo, contato_id],
    )


def _parar_por_optout(cursor, envio, nome):
    cursor.execute("SELECT nome, email FROM cadu_lead_contatos WHERE id = %s", [envio["id_contato"]])
    contato = cursor.fetchone() or {}
    if contato.get("email"):
        cursor.execute(
            """
            INSERT INTO cadu_lead_optout (canal, valor, motivo, origem) VALUES ('email', %s, %s, 'brevo')
            ON CONFLICT (canal, valor) DO NOTHING
            """,
            [str(contato["email"]).strip().lower(), "marcou como spam" if nome == "spam" else "descadastro"],
        )
    motivo = "Marcou o e-mail como spam" if nome == "spam" else "Pediu para não receber e-mails"
    _parar_cadencias(cursor, envio["id_contato"], "cancelada", motivo)
    cadencias._atividade(cursor, envio["id_lead"], "nota", f"{motivo} — {contato.get('nome') or 'contato'} (Brevo); cadência encerrada.",
                         envio["id_contato"], None, None)


def _parar_por_bounce(cursor, envio):
    cursor.execute("UPDATE cadu_lead_contatos SET email_status = 'invalido' WHERE id = %s", [envio["id_contato"]])
    _parar_cadencias(cursor, envio["id_contato"], "pausada", "E-mail voltou (endereço não existe)")
    cadencias._atividade(cursor, envio["id_lead"], "nota", "E-mail voltou: endereço não existe. Cadência pausada; ache outro e-mail.",
                         envio["id_contato"], None, None)
