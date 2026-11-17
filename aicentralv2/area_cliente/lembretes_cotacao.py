"""Lembretes do prazo de 24 h dos briefings de cotação: aviso ao executivo com 12 h restantes, ao gestor com 4 h e marca de atraso.

Roda em timer (a cada 15 minutos): ``python -m aicentralv2.area_cliente.lembretes_cotacao``. Cada lembrete sai uma vez, anotado em
``cadu_briefings.lembretes``. Briefing que já saiu de ``pendente`` (a equipe respondeu) ganha ``respondido_em`` e para de avisar.
O gestor vem de ``HUB_GESTOR_EMAIL`` (um ou mais e-mails separados por vírgula); sem ele, só o executivo é avisado.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
AVISOS = (("12h", timedelta(hours=12), "executivo"), ("4h", timedelta(hours=4), "gestor"))


def decidir(prazo: datetime, agora: datetime, feitos: dict | None) -> list[str]:
    """Lembretes devidos agora, do mais urgente ao menos. ``feitos`` é o que já saiu (chave -> horário)."""
    feitos = feitos or {}
    devidos = []
    if agora > prazo and "atraso" not in feitos:
        devidos.append("atraso")
    for chave, margem, _quem in reversed(AVISOS):
        if prazo - agora <= margem and agora <= prazo and chave not in feitos:
            devidos.append(chave)
    if agora > prazo:
        # já vencido: os avisos antecipados que nunca saíram não fazem mais sentido
        devidos = [d for d in devidos if d == "atraso"]
    return devidos[:1]


def _db():
    from .. import db
    return db


def pendentes() -> list[dict]:
    conn = _db().get_db()
    try:
        with conn.cursor() as c:
            c.execute("""SELECT b.id, b.titulo, b.status, b.prazo_resposta_em, b.lembretes, b.email_destinatario, b.responsavel_centralcomm,
                                b.cliente, b.responsavel
                           FROM cadu_briefings b
                          WHERE b.modo = 'cotacao' AND b.prazo_resposta_em IS NOT NULL AND b.respondido_em IS NULL AND b.deleted_at IS NULL""")
            return [dict(r) for r in c.fetchall()]
    except Exception:
        conn.rollback()
        raise


def _gravar(id_briefing: int, *, lembretes: dict | None = None, respondido: bool = False) -> None:
    conn = _db().get_db()
    try:
        with conn.cursor() as c:
            if respondido:
                c.execute("UPDATE cadu_briefings SET respondido_em = NOW() WHERE id = %s AND respondido_em IS NULL", (id_briefing,))
            if lembretes is not None:
                c.execute("UPDATE cadu_briefings SET lembretes = %s::jsonb WHERE id = %s", (json.dumps(lembretes), id_briefing))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def processar(agora: datetime | None = None, *, enviar=None) -> dict:
    """Varre os briefings de cotação em aberto. ``enviar(briefing, chave, destinatarios)`` troca o envio (testes)."""
    agora = agora or datetime.now(timezone.utc)
    enviar = enviar or _enviar_padrao
    saida = {"avisos": 0, "respondidos": 0}
    for b in pendentes():
        if b["status"] != "pendente":
            _gravar(b["id"], respondido=True)
            saida["respondidos"] += 1
            continue
        feitos = b.get("lembretes") or {}
        devidos = decidir(b["prazo_resposta_em"], agora, feitos)
        for chave in devidos:
            alvo = "gestor" if chave == "4h" else "executivo"
            destinatarios = _destinatarios(b, alvo, atraso=chave == "atraso")
            if destinatarios and enviar(b, chave, destinatarios):
                feitos = {**feitos, chave: agora.isoformat()}
                _gravar(b["id"], lembretes=feitos)
                saida["avisos"] += 1
    return saida


def _destinatarios(b: dict, alvo: str, atraso: bool = False) -> list[str]:
    gestores = [e.strip() for e in os.getenv("HUB_GESTOR_EMAIL", "").split(",") if e.strip()]
    executivo = [b["email_destinatario"]] if b.get("email_destinatario") else []
    if alvo == "gestor":
        return gestores
    return executivo + (gestores if atraso else [])


def _enviar_padrao(b: dict, chave: str, destinatarios: list[str]) -> bool:
    from ..product_domains import product_url
    from . import emails
    prazo = b["prazo_resposta_em"].astimezone(emails.FUSO)
    texto = {"12h": "faltam 12 horas", "4h": "faltam 4 horas", "atraso": "o prazo venceu"}[chave]
    ctx = {"titulo": b["titulo"], "cliente": b.get("cliente") or "", "prazo": prazo.strftime("%d/%m às %H:%M"), "situacao": texto,
           "atraso": chave == "atraso", "link_briefings": product_url("centralx", f"/briefings?busca={b['id']}"), "executivo": None,
           "primeiro_nome": "equipe"}
    ok = False
    for email in destinatarios:
        ok = emails._enviar("briefing-prazo", email, "Equipe Centralcomm", f"Cotação de {b.get('cliente') or 'cliente'}: {texto} ({b['titulo']})", ctx) or ok
    return ok


if __name__ == "__main__":                                                           # pragma: no cover
    from .. import create_app
    app = create_app()
    with app.app_context():
        print(processar())
