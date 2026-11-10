"""
Sincronia dos contatos do Leads v3 e do CRM v3 com as listas da Brevo (pasta Contatos).

Em vez de chamar a Brevo em cada um dos caminhos que gravam contato (são dezenas:
formulário, Apollo, busca na web, importação, conversão...), a sincronia compara o
banco com a Brevo e acerta só a diferença:

- Contato de cliente ativo  -> lista 21 + "[Executivo] - Clientes".
- Contato de lead em aberto -> "[Executivo] - Leads" (lead que virou cliente sai daqui).
- E-mail que é de cliente e de lead ao mesmo tempo conta como cliente.
- Quem pediu descadastro (cadu_lead_optout) não entra.
- Executivo sem lista mapeada (ex.: usuários de teste) não leva nenhum contato à Brevo.
- E-mail em leads de executivos diferentes fica com quem cadastrou primeiro (regra estável).
- As listas de executivo espelham o banco: sai delas quem virou cliente, trocou de executivo,
  foi desqualificado, pediu descadastro, foi apagado ou teve o e-mail corrigido.
- Nunca apaga contato da Brevo, não tira ninguém da 21 nem e-mail interno (@centralcomm) de lista.
- Contato que já existe na Brevo só ganha a lista; nome, empresa e telefone de lá não mudam.

`agendar_sincronia()` roda em segundo plano depois das gravações no Leads v3 e no CRM v3,
no máximo uma vez a cada INTERVALO_MINIMO segundos, e só consulta a Brevo quando o retrato
do banco mudou (ou a cada CONFERENCIA_BREVO segundos, para pegar mudanças feitas na Brevo).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

import requests

from .brevo_service import (
    BREVO_API_URL,
    BREVO_LISTAS_CONTATOS_VENDEDOR,
    LISTA_USUARIOS_ATIVOS,
    BrevoService,
    brevo_primeiro_nome_normalizado,
)

logger = logging.getLogger(__name__)

DOMINIOS_INTERNOS = ("centralcomm.media", "centralcomm.com.br")
STATUS_LEAD_FORA = ("nao_qualificado", "fechado_ganho")
INTERVALO_MINIMO = 120  # segundos entre duas sincronias automáticas
CONFERENCIA_BREVO = 1800  # mesmo sem mudança no banco, confere a Brevo a cada 30 min

LISTAS_EXECUTIVO: Set[int] = {
    lid for listas in BREVO_LISTAS_CONTATOS_VENDEDOR.values() for lid in listas.values()
}


@dataclass
class Desejado:
    email: str
    nome: str
    segmento: str  # 'clientes' | 'leads'
    executivo: Optional[str]
    empresa: str = ""
    telefone: str = ""

    @property
    def lista_executivo(self) -> Optional[int]:
        chave = brevo_primeiro_nome_normalizado(self.executivo)
        listas = BREVO_LISTAS_CONTATOS_VENDEDOR.get(chave or "")
        return listas[self.segmento] if listas else None

    @property
    def listas(self) -> List[int]:
        alvo = [LISTA_USUARIOS_ATIVOS] if self.segmento == "clientes" else []
        if self.lista_executivo is not None:
            alvo.append(self.lista_executivo)
        return alvo


@dataclass
class Plano:
    incluir: List[Dict[str, Any]] = field(default_factory=list)  # {desejado, listas}
    remover: Dict[int, List[str]] = field(default_factory=dict)  # lista -> e-mails
    sem_lista: Dict[str, int] = field(default_factory=dict)  # executivo -> qtd
    optout: int = 0

    def resumo(self) -> Dict[str, Any]:
        por_lista: Dict[int, int] = {}
        for item in self.incluir:
            for lid in item["listas"]:
                por_lista[lid] = por_lista.get(lid, 0) + 1
        return {
            "contatos_a_incluir": len(self.incluir),
            "entradas_por_lista": dict(sorted(por_lista.items())),
            "saidas_por_lista": {k: len(v) for k, v in sorted(self.remover.items())},
            "sem_lista_na_brevo": dict(self.sem_lista),
            "descadastrados_ignorados": self.optout,
        }


def _interno(email: str) -> bool:
    return email.rsplit("@", 1)[-1] in DOMINIOS_INTERNOS


def coletar_desejado(cursor) -> tuple[Dict[str, Desejado], int]:
    """Lê do banco onde cada e-mail deveria estar. Devolve (por e-mail, qtd de descadastrados)."""
    cursor.execute("SELECT LOWER(TRIM(valor)) AS email FROM cadu_lead_optout WHERE canal = 'email'")
    optout = {r["email"] for r in cursor.fetchall() if r["email"]}

    # Executivos (e quem é executivo de algum lead) não entram como contato.
    cursor.execute(
        """
        SELECT vendas_central_comm AS id FROM tbl_cliente WHERE vendas_central_comm IS NOT NULL
        UNION SELECT id_executivo FROM cadu_leads WHERE id_executivo IS NOT NULL
        """
    )
    executivos = {r["id"] for r in cursor.fetchall()}

    desejado: Dict[str, Desejado] = {}
    ignorados: Set[str] = set()

    cursor.execute(
        """
        SELECT ct.id_contato_cliente AS id, LOWER(TRIM(ct.email)) AS email, ct.nome_completo AS nome,
               ct.telefone, COALESCE(cl.nome_fantasia, cl.razao_social, '') AS empresa,
               ex.nome_completo AS executivo
          FROM tbl_contato_cliente ct
          JOIN tbl_cliente cl ON cl.id_cliente = ct.pk_id_tbl_cliente
          LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = cl.vendas_central_comm
         WHERE COALESCE(TRIM(ct.email), '') <> ''
           AND COALESCE(ct.status, TRUE) AND COALESCE(cl.status, TRUE)
           AND COALESCE(ct.user_type, 'client') = 'client'
         ORDER BY ct.id_contato_cliente
        """
    )
    for r in cursor.fetchall():
        email = r["email"]
        if r["id"] in executivos or _interno(email) or "@" not in email:
            continue
        if email in optout:
            ignorados.add(email)
            continue
        desejado.setdefault(email, Desejado(email, (r["nome"] or "").strip(), "clientes", r["executivo"],
                                            r["empresa"] or "", r["telefone"] or ""))

    cursor.execute(
        """
        SELECT LOWER(TRIM(ct.email)) AS email, ct.nome, ct.telefone, COALESCE(l.empresa, '') AS empresa,
               ex.nome_completo AS executivo
          FROM cadu_lead_contatos ct
          JOIN cadu_leads l ON l.id = ct.id_lead
          LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = l.id_executivo
         WHERE COALESCE(TRIM(ct.email), '') <> ''
           AND l.convertido_cliente_id IS NULL
           AND COALESCE(l.status, '') <> ALL(%s)
         ORDER BY ct.id  -- o mesmo e-mail em dois leads fica com o primeiro cadastro
        """,
        [list(STATUS_LEAD_FORA)],
    )
    for r in cursor.fetchall():
        email = r["email"]
        if _interno(email) or "@" not in email or "*" in email:
            continue
        if email in optout:
            ignorados.add(email)
            continue
        desejado.setdefault(email, Desejado(email, (r["nome"] or "").strip(), "leads", r["executivo"],
                                            r["empresa"] or "", r["telefone"] or ""))
    return desejado, len(ignorados)


def assinatura(desejado: Dict[str, Desejado]) -> int:
    """Retrato do que o banco quer na Brevo; igual ao anterior = nada a fazer."""
    return hash(frozenset((d.email, tuple(d.listas)) for d in desejado.values()))


def membros_da_lista(service: BrevoService, lista_id: int) -> Set[str]:
    emails: Set[str] = set()
    offset = 0
    while True:
        resp = requests.get(
            f"{BREVO_API_URL}/contacts/lists/{lista_id}/contacts",
            headers=service._headers,
            params={"limit": 500, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        contatos = resp.json().get("contacts") or []
        emails.update((c.get("email") or "").strip().lower() for c in contatos)
        if len(contatos) < 500:
            return emails
        offset += 500


def montar_plano(desejado: Dict[str, Desejado], membros: Dict[int, Set[str]], optout: int = 0) -> Plano:
    plano = Plano(optout=optout)
    for d in desejado.values():
        if d.lista_executivo is None:
            chave = (d.executivo or "(sem executivo)").split()[0] if d.executivo else "(sem executivo)"
            plano.sem_lista[chave] = plano.sem_lista.get(chave, 0) + 1
            continue  # executivo sem lista na Brevo (ex.: usuário de teste): não importa nada
        faltam = [lid for lid in d.listas if d.email not in membros.get(lid, set())]
        if faltam:
            plano.incluir.append({"desejado": d, "listas": faltam})
    # As listas de executivo espelham o banco: quem não deveria estar nela sai (só dela).
    for lid in sorted(LISTAS_EXECUTIVO):
        for email in sorted(membros.get(lid, set())):
            d = desejado.get(email)
            if _interno(email):
                continue  # equipe pode estar na lista para receber cópia das campanhas
            if d is None or lid not in d.listas:
                plano.remover.setdefault(lid, []).append(email)
    return plano


def aplicar_plano(service: BrevoService, plano: Plano, *, pausa: float = 0.12) -> Dict[str, Any]:
    ok, falhas = 0, []
    for item in plano.incluir:
        d: Desejado = item["desejado"]
        erro = _incluir(service, d, item["listas"])
        if erro is None:
            ok += 1
        else:
            falhas.append({"email": d.email, "erro": erro})
        time.sleep(pausa)
    removidos = 0
    for lid, emails in plano.remover.items():
        for i in range(0, len(emails), 150):
            lote = emails[i:i + 150]
            resp = requests.post(f"{BREVO_API_URL}/contacts/lists/{lid}/contacts/remove",
                                 headers=service._headers, json={"emails": lote}, timeout=30)
            if resp.status_code in (200, 201, 204):
                removidos += len(lote)
            else:
                falhas.append({"lista": lid, "erro": resp.text[:200]})
    return {"incluidos": ok, "removidos": removidos, "falhas": falhas}


def _incluir(service: BrevoService, d: Desejado, listas: List[int]) -> Optional[str]:
    """Cria o contato com nome/empresa/telefone; se já existe, só acrescenta as listas."""
    atributos = {k: v for k, v in {"NOME": d.nome, "EMPRESA": d.empresa, "TELEFONE": d.telefone}.items() if v}
    url = f"{BREVO_API_URL}/contacts"
    resp = requests.post(url, headers=service._headers, timeout=30,
                         json={"email": d.email, "attributes": atributos, "listIds": listas, "updateEnabled": False})
    if resp.status_code in (200, 201, 204):
        return None
    if resp.status_code == 400 and "duplicate" in resp.text.lower():
        resp = requests.post(url, headers=service._headers, timeout=30,
                             json={"email": d.email, "listIds": listas, "updateEnabled": True})
        if resp.status_code in (200, 201, 204):
            return None
    return f"{resp.status_code} {resp.text[:200]}"


def tamanhos_das_listas(service: BrevoService, listas: Iterable[int]) -> Dict[int, int]:
    out = {}
    for lid in listas:
        resp = requests.get(f"{BREVO_API_URL}/contacts/lists/{lid}", headers=service._headers, timeout=30)
        resp.raise_for_status()
        out[lid] = int(resp.json().get("uniqueSubscribers") or resp.json().get("totalSubscribers") or 0)
    return out


def sincronizar(cursor, service: Optional[BrevoService] = None, *, aplicar: bool = True,
                coletado: Optional[tuple] = None) -> Dict[str, Any]:
    service = service or BrevoService()
    if not service._api_key:
        return {"pulado": "sem chave da Brevo"}
    desejado, optout = coletado or coletar_desejado(cursor)
    listas = sorted(LISTAS_EXECUTIVO | {LISTA_USUARIOS_ATIVOS})
    membros = {lid: membros_da_lista(service, lid) for lid in listas}
    plano = montar_plano(desejado, membros, optout)
    resultado: Dict[str, Any] = {"contatos_no_banco": len(desejado), "plano": plano.resumo()}
    if aplicar and (plano.incluir or plano.remover):
        resultado["aplicado"] = aplicar_plano(service, plano)
    return resultado


# ---------------------------------------------------------------------------
# Disparo automático (depois de gravações no Leads v3 / CRM v3)
# ---------------------------------------------------------------------------

_trava = threading.Lock()
_estado = {"ultima": 0.0, "agendada": False, "assinatura": None, "brevo_em": 0.0}


def agendar_sincronia(app, executar: Optional[Callable[[], None]] = None) -> None:
    """Agenda uma sincronia em segundo plano, juntando várias gravações seguidas numa só."""
    with _trava:
        if _estado["agendada"]:
            return
        _estado["agendada"] = True
        espera = max(0.0, _estado["ultima"] + INTERVALO_MINIMO - time.time())

    def rodar():
        try:
            if executar:
                executar()
            else:
                import psycopg

                from .. import db as db_mod

                with app.app_context():
                    # Conexão própria e só de leitura: a thread não usa a conexão da requisição (g.db).
                    with psycopg.connect(**db_mod.get_db_config()) as conn:
                        conn.read_only = True
                        with conn.cursor() as cur:
                            coletado = coletar_desejado(cur)
                            sig = assinatura(coletado[0])
                            if sig == _estado["assinatura"] and time.time() - _estado["brevo_em"] < CONFERENCIA_BREVO:
                                return  # o banco não mudou: nada a levar à Brevo
                            res = sincronizar(cur, coletado=coletado)
                    if "pulado" not in res and not (res.get("aplicado") or {}).get("falhas"):
                        _estado["assinatura"], _estado["brevo_em"] = sig, time.time()
                    logger.info("Brevo (sincronia de contatos): %s", res)
        except Exception:
            logger.exception("Brevo (sincronia de contatos) falhou")
        finally:
            with _trava:
                _estado["ultima"] = time.time()
                _estado["agendada"] = False

    timer = threading.Timer(espera + 5, rodar)  # 5 s para a transação da requisição terminar
    timer.daemon = True
    timer.start()


def registrar_gatilho(bp) -> None:
    """Liga a sincronia automática às gravações bem-sucedidas de um blueprint."""
    from flask import current_app, request

    if getattr(bp, "_brevo_sync_ligado", False):  # create_app chamado de novo (testes)
        return
    bp._brevo_sync_ligado = True

    @bp.after_request
    def _brevo_sync_depois(resp):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and resp.status_code < 400:
            try:
                if current_app.config.get("BREVO_CONTATOS_SYNC", True) and not current_app.testing:
                    agendar_sincronia(current_app._get_current_object())
            except Exception:
                logger.exception("Brevo: não agendou a sincronia de contatos")
        return resp
