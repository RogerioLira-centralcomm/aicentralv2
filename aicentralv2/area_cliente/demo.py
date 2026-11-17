"""Modo demonstração do hub: dados fictícios para a conta da Centralcomm (cliente 174), para gravar vídeos e testar telas.

Nada aqui lê nem grava o banco de produção. Os PIs e campanhas de exemplo são montados em memória, no mesmo formato que
``dados.py`` devolve, e valem **só** para o cliente definido em ``HUB_DEMO_CLIENTE_ID`` (padrão 174; ``0`` desliga). Como não
existem no banco, relatórios, cotações e PIs reais do CentralX não enxergam nada disto.

Os envios (PI, cotação e briefing) são simulados na sessão do navegador: a leitura "demora" alguns segundos e devolve um
resultado de exemplo, o envio ao executivo só muda a tela. Nenhuma linha é criada, nenhum e-mail sai.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid as uuidlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, session

CLIENTE_PADRAO = 174
BASE_ID = 900_000_000                 # ids dos PIs de exemplo: longe de qualquer id real
ESPERA_LEITURA = 4                    # segundos da "leitura" simulada
CHAVE = "hub_demo"


def cliente_demo() -> int:
    try:
        return int(current_app.config.get("HUB_DEMO_CLIENTE_ID", CLIENTE_PADRAO))
    except (TypeError, ValueError):
        return 0


def ativo(cliente_id) -> bool:
    try:
        return bool(cliente_demo()) and int(cliente_id) == cliente_demo()
    except (TypeError, ValueError):
        return False


def eh_pi_demo(id_pi) -> bool:
    try:
        return BASE_ID < int(id_pi) <= BASE_ID + 20
    except (TypeError, ValueError):
        return False


def _tem_demo(ids) -> bool:
    return any(eh_pi_demo(i) for i in ids or [])


# ---------- PIs e campanhas ----------

def _milhar(n) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _campanha(n, id_pi, nome, plataforma, objetivo, inicio, fim, meta, pct, hoje):
    from . import dados, plataformas
    total = max((fim - inicio).days, 1)
    tempo = max(0, min(100, round(100 * (hoje - inicio).days / total)))
    encerrada = fim < hoje
    no_ar = not encerrada and inicio <= hoje
    ritmo = dados._ritmo(pct, tempo) if no_ar else ""
    atingido = meta * pct / 100
    return {
        "id": BASE_ID + n, "id_pi": id_pi, "nome": nome, "plataforma": plataforma, "objetivo": objetivo,
        "status": "Ativa" if no_ar else "Finalizada", "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "meta": float(meta), "meta_label": _milhar(meta), "atingido": float(atingido), "atingido_label": _milhar(atingido),
        "pct": pct, "tempo_pct": tempo if no_ar else None, "dias_restantes": (fim - hoje).days if no_ar else -1,
        "ritmo": ritmo, "dash_embed": "", "dash_abrir": "", "dash_compartilhado": False, "atual": False, "no_ar": no_ar,
        "responsavel": "Equipe Centralcomm", "plataforma_logo": plataformas.logo(plataforma),
        "plataforma_iniciais": plataformas.iniciais(plataforma),
    }


def _definicao(hoje: date) -> list[dict]:
    d = lambda dias: hoje + timedelta(days=dias)                                 # noqa: E731
    pis = [
        {"n": 1, "titulo": "Lançamento Coleção Verão", "codigo": "DEMO-001", "cliente": "Moda Solaris", "agencia": "Agência Fullgás", "status": ("Em andamento", 3), "ini": d(-20), "fim": d(25),
         "bruto": 180000, "notas": (1, 0),
         "camps": [("Alcance · Redes sociais", "Meta Ads", "Alcance", 3_200_000, 58), ("Conversão · Busca", "Google Ads", "Tráfego", 85_000, 42),
                   ("Vídeo · Lançamento", "YouTube", "Visualizações", 600_000, 22)]},
        {"n": 2, "titulo": "Black Friday Varejo", "codigo": "DEMO-002", "cliente": "Supermercados Horizonte", "agencia": "Estúdio Alvorada", "status": ("Em andamento", 3), "ini": d(-9), "fim": d(12),
         "bruto": 120000, "notas": (1, 0),
         "camps": [("Programática · Display", "DV360", "Impressões", 4_500_000, 49), ("Remarketing · Social", "Meta Ads", "Cliques", 60_000, 47)]},
        {"n": 3, "titulo": "Dia das Mães", "codigo": "DEMO-003", "cliente": "Joias Aurora", "agencia": "Agência Fullgás", "status": ("Finalizado", 5), "ini": d(-200), "fim": d(-170),
         "bruto": 95000, "notas": (2, 2),
         "camps": [("Presentes · Busca", "Google Ads", "Cliques", 70_000, 104), ("Emoção · Vídeo", "YouTube", "Visualizações", 500_000, 101)]},
        {"n": 4, "titulo": "Conta Premiada App", "codigo": "DEMO-004", "cliente": "Cooperativa Nova Aliança", "agencia": "Pulso Comunicação", "status": ("Finalizado", 5), "ini": d(-120), "fim": d(-92),
         "bruto": 150000, "notas": (3, 3),
         "camps": [("Instalações · App", "Meta Ads", "Instalações", 18_000, 103), ("Programática · App", "DV360", "Impressões", 6_000_000, 99)]},
        {"n": 5, "titulo": "Liquidação de Verão", "codigo": "DEMO-005", "cliente": "Moda Solaris", "agencia": "Estúdio Alvorada", "status": ("Finalizado", 5), "ini": d(-310), "fim": d(-280),
         "bruto": 80000, "notas": (1, 1),
         "camps": [("Alcance · Social", "Meta Ads", "Alcance", 2_000_000, 106)]},
    ]
    return pis


def _montar():
    from . import dados
    hoje = date.today()
    projetos, campanhas, pis = [], [], []
    for p in _definicao(hoje):
        id_pi = BASE_ID + p["n"]
        camps = [_campanha(p["n"] * 10 + i, id_pi, nome, plat, obj, p["ini"], p["fim"], meta, pct, hoje)
                 for i, (nome, plat, obj, meta, pct) in enumerate(p["camps"], 1)]
        status, status_id = p["status"]
        pcts = [c["pct"] for c in camps if c["pct"] is not None]
        total = max((p["fim"] - p["ini"]).days, 1)
        tempo = max(0, min(100, round(100 * (hoje - p["ini"]).days / total)))
        em_curso = p["fim"] >= hoje
        contraparte = {"rotulo": "Agência", "nome": p["agencia"]}
        proj = {
            "id": id_pi, "titulo": p["titulo"], "pi": p["codigo"], "cliente": p["cliente"], "contraparte": contraparte,
            "status": status, "status_id": status_id, "ativo": status_id in dados.SUB_STATUS_ATIVOS,
            "periodo": {"inicio": p["ini"].isoformat(), "fim": p["fim"].isoformat()}, "atualizado_em": (hoje - timedelta(days=2 if em_curso else 60)).isoformat(),
            "n_campanhas": len(camps), "plataformas": sorted({c["plataforma"] for c in camps}),
            "pct": round(sum(pcts) / len(pcts)) if pcts else None, "tempo_pct": tempo if em_curso else None,
            "dias_restantes": (p["fim"] - hoje).days if em_curso else -1, "campanhas": camps, "dash_pi": "",
        }
        proj["ritmo"] = dados._ritmo(proj["pct"], proj["tempo_pct"]) if em_curso else ""
        projetos.append(proj)
        campanhas += camps
        n_notas, n_pagas = p["notas"]
        bruto = float(p["bruto"])
        pis.append({
            "id": id_pi, "pi": p["codigo"], "titulo": p["titulo"], "status": status, "status_id": status_id, "periodo": proj["periodo"],
            "cliente": p["cliente"], "agencia": p["agencia"], "bruto": bruto, "comissao": None, "liquido": bruto, "n_notas": n_notas, "n_pagas": n_pagas,
            "atualizado_em": proj["atualizado_em"], "criado_em": (p["ini"] - timedelta(days=12)).isoformat(), "documentos": [],
            "contraparte": contraparte,
        })
    return projetos, campanhas, pis


def projetos(busca: str = "", id_pi=None) -> list[dict]:
    lista, _c, _p = _montar()
    if id_pi is not None:
        lista = [p for p in lista if p["id"] == int(id_pi)]
    termo = (busca or "").strip().lower()
    if termo:
        lista = [p for p in lista if termo in p["titulo"].lower() or termo in p["pi"].lower()]
    return lista


def campanhas(ids) -> list[dict]:
    wanted = {int(i) for i in ids or []}
    return [c for c in _montar()[1] if c["id_pi"] in wanted]


def pis(id_pi=None) -> list[dict]:
    lista = _montar()[2]
    return [p for p in lista if id_pi is None or p["id"] == int(id_pi)]


def notas(id_pi) -> list[dict]:
    """Notas no formato do banco (linhas) para ``pi_do_cliente``: uma por mês do PI."""
    alvo = next((p for p in pis(id_pi)), None)
    if not alvo:
        return []
    hoje = date.today()
    ini = date.fromisoformat(alvo["periodo"]["inicio"])
    saida = []
    for i in range(alvo["n_notas"]):
        emissao = ini + timedelta(days=10 + 30 * i)
        pago = i < alvo["n_pagas"]
        valor = alvo["bruto"] / max(alvo["n_notas"], 1)
        saida.append({"numero_nota": f"{4100 + alvo['id'] % 100 + i}", "data_emissao": emissao, "valor": valor, "valor_liquido": valor,
                      "mes_ref_comp": f"{emissao:%m/%Y}", "data_pag_prevista": emissao + timedelta(days=30),
                      "data_pag_realizado": emissao + timedelta(days=28) if pago else None,
                      "status": "Pagamento realizado" if pago else "NF emitida"})
    return [n for n in saida if n["data_emissao"] <= hoje]


def etapas(id_pi) -> list[dict]:
    alvo = next((p for p in pis(id_pi)), None)
    if not alvo:
        return []
    ini = date.fromisoformat(alvo["periodo"]["inicio"])
    base = [("dados_validados", -8), ("campanhas_configuradas", -4), ("materiais_recebidos", -2), ("campanha_iniciada", 0)]
    if alvo["status_id"] == 5:
        fim = date.fromisoformat(alvo["periodo"]["fim"])
        return [{"etapa": e, "concluida_em": datetime.combine(ini + timedelta(days=o), datetime.min.time())} for e, o in base] + \
               [{"etapa": "fechamento_comunicado", "concluida_em": datetime.combine(fim + timedelta(days=2), datetime.min.time())},
                {"etapa": "enviado_financeiro", "concluida_em": datetime.combine(fim + timedelta(days=5), datetime.min.time())}]
    return [{"etapa": e, "concluida_em": datetime.combine(ini + timedelta(days=o), datetime.min.time())} for e, o in base
            if ini + timedelta(days=o) <= date.today()]


def atividades(ids_pi, por_id, limite=6) -> list[dict]:
    from . import dados
    saida = []
    for id_pi in ids_pi:
        if not eh_pi_demo(id_pi):
            continue
        for e in etapas(id_pi):
            saida.append({"titulo": dados.ETAPAS_CLIENTE.get(e["etapa"], "Atualização da operação"),
                          "projeto": (por_id.get(id_pi) or {}).get("titulo") or f"PI #{id_pi}", "projeto_id": id_pi, "em": e["concluida_em"]})
    return sorted(saida, key=lambda a: a["em"], reverse=True)[:limite]


# ---------- briefings enviados e histórico ----------

def _loja() -> dict:
    loja = session.get(CHAVE)
    if not isinstance(loja, dict):
        loja = session[CHAVE] = {"pi": {}, "cotacao": {}, "briefings": []}
    return loja


def briefings_enviados() -> list[dict]:
    """Briefings de exemplo mais os que foram "enviados" nesta sessão de demonstração."""
    hoje = date.today()
    fixos = [("Coleção de verão 2027", "Vender a nova coleção pelo site e nas lojas de BH.", "Em planejamento", "success", 9),
             ("Lançamento do app", "Gerar instalações de app com foco em Android.", "Enviado · em análise", "brand", 3)]
    def texto(t, o):
        return (f"## Objetivo\n{o}\n\n## Público\nMulheres 25-44, classes B e C, interessadas em moda e compras online.\n\n"
                "## Praças\nBelo Horizonte; Contagem; Betim\n\n## Período\nDezembro a janeiro\n\n## Verba prevista\nR$ 50 a 150 mil\n\n"
                "## Canais de interesse\nRedes sociais, Busca")
    saida = [{"id": 900_100 + i, "titulo": t, "objetivo": o, "status": s, "tom": tom, "autor": "Equipe Centralcomm", "texto": texto(t, o),
              "em": (hoje - timedelta(days=dias)).strftime("%d/%m/%Y")} for i, (t, o, s, tom, dias) in enumerate(fixos)]
    nossos = [{"id": 900_200 + i, "titulo": b["titulo"], "objetivo": b["objetivo"], "status": "Enviado · em análise", "tom": "brand",
               "autor": "Equipe Centralcomm", "texto": texto(b["titulo"], b["objetivo"]), "em": hoje.strftime("%d/%m/%Y")} for i, b in enumerate(_loja()["briefings"])]
    return list(reversed(nossos)) + saida


def historico_briefing() -> list[dict]:
    """Itens para "Repetir um PI antigo", no formato de ``briefing.historico``."""
    saida = []
    for p in pis():
        proj = next(x for x in projetos() if x["id"] == p["id"])
        saida.append({
            "id": f"pi:{p['id']}", "fonte": "PI", "titulo": p["titulo"], "quando": p["periodo"]["inicio"][5:7] + "/" + p["periodo"]["inicio"][:4],
            "objetivo": "Aumentar a presença da marca e gerar vendas no período.", "objetivo_tipo": "marca", "kpi": "Alcance",
            "plataformas": proj["plataformas"], "canais": ["social", "busca"], "pracas": ["Belo Horizonte", "Contagem", "Betim"],
            "publico": "Mulheres 25-44, classes B e C, interesse em moda e compras online", "dias": 30,
            "inicio_iso": p["periodo"]["inicio"], "fim_iso": p["periodo"]["fim"],
        })
    return saida[:5]


def registrar_briefing(valores: dict) -> int:
    loja = _loja()
    loja["briefings"] = (loja["briefings"] + [{"titulo": valores.get("titulo") or "Briefing", "objetivo": valores.get("objetivo") or ""}])[-5:]
    session.modified = True
    return 900_200 + len(loja["briefings"]) - 1


# ---------- envios simulados (PI e cotação) ----------

LEITURA_PI = {
    "numero_pi": "DEMO-0451", "cliente": {"razao_social": "CLIENTE EXEMPLO S.A."}, "agencia": {"razao_social": "AGÊNCIA EXEMPLO LTDA"},
    "campanha": "CAMPANHA DE VERÃO 2027", "produto": "VAREJO", "periodo_texto": "DEZEMBRO/2026", "totais": {"bruto": "R$ 60.000,00"},
    "linhas": [{"plataforma": "Meta Ads", "praca": "Belo Horizonte", "formato": "Carrossel"}, {"plataforma": "Google Ads", "praca": "Contagem", "formato": "Pesquisa"},
               {"plataforma": "YouTube", "praca": "Betim", "formato": "Vídeo 15s"}, {"plataforma": "DV360", "praca": "MG", "formato": "Display"}],
}

LEITURA_COTACAO = {
    "titulo": "Campanha de verão 2027", "objetivo": "Vender a nova coleção de verão pelo site e nas lojas de Belo Horizonte.",
    "publico": "Mulheres 25-44, classes B e C, interessadas em moda e viagens.", "pracas": ["Belo Horizonte", "Contagem", "Betim"],
    "inicio": (date.today() + timedelta(days=20)).isoformat(), "fim": (date.today() + timedelta(days=50)).isoformat(), "verba": "", "canais": ["social", "busca"],
    "formatos": ["Carrossel", "Story"], "pecas": "", "resumo": "Material pede uma campanha de verão com foco em BH e região.",
    "faltou": ["verba prevista", "situação das peças"], "avisos": [],
}


def novo_envio(tipo: str, nomes: list[str]) -> str:
    """Registra um envio simulado (``pi`` ou ``cotacao``) e devolve o uuid de demonstração."""
    loja = _loja()
    novo = f"demo-{uuidlib.uuid4().hex[:10]}"
    loja[tipo][novo] = {"uuid": novo, "nomes": nomes[:5], "em": time.time(), "enviado_em": None, "mensagem": ""}
    if len(loja[tipo]) > 5:
        loja[tipo].pop(next(iter(loja[tipo])))
    session.modified = True
    return novo


def envio(tipo: str, uuid) -> dict | None:
    return _loja()[tipo].get(str(uuid)) if str(uuid).startswith("demo-") else None


def envios(tipo: str) -> list[dict]:
    return list(reversed(list(_loja()[tipo].values())))


def lendo(registro: dict) -> bool:
    return not registro.get("enviado_em") and time.time() - registro["em"] < ESPERA_LEITURA


def marcar_enviado(tipo: str, uuid, mensagem: str = "") -> bool:
    registro = envio(tipo, uuid)
    if not registro or registro.get("enviado_em"):
        return False
    if (estado_pi(registro) != "pronto") if tipo == "pi" else lendo(registro):
        return False
    registro["enviado_em"], registro["mensagem"] = time.time(), (mensagem or "")[:1000]
    session.modified = True
    return True


def quando(ts) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ---------- PI de demonstração: o PDF enviado é lido de verdade, só que fora do banco ----------
# O resultado (o resumo que o cliente vê) vai para um arquivo temporário em instance/hub_demo; nenhuma linha é criada.
EXECUTAR_EM_SEGUNDO_PLANO = True      # os testes trocam por False para ler na hora
LIMITE_LEITURA_PI = 180               # segundos até desistir de uma leitura sem resposta


def _pasta() -> Path:
    base = current_app.config.get("HUB_DEMO_DIR") or os.path.join(current_app.instance_path, "hub_demo")
    pasta = Path(base)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _arquivo(uuid_envio: str, ext: str) -> Path:
    seguro = "".join(c for c in str(uuid_envio) if c.isalnum() or c == "-")
    return _pasta() / f"{seguro}.{ext}"


def _limpar_antigos(horas: int = 24) -> None:
    """Apaga os PDFs e resultados temporários da demonstração com mais de um dia (a pasta não cresce sem fim)."""
    limite = time.time() - horas * 3600
    for f in _pasta().glob("demo-*"):
        try:
            if f.stat().st_mtime < limite:
                f.unlink()
        except OSError:
            pass


def guardar_pdf(uuid_envio: str, conteudo: bytes) -> None:
    _limpar_antigos()
    _arquivo(uuid_envio, "pdf").write_bytes(conteudo)


def _ler_agora(uuid_envio: str, nome: str) -> None:
    from ..pi_entrada import hub, leitor
    try:
        leitura = leitor.ler(_arquivo(uuid_envio, "pdf").read_bytes(), nome)
        resumo = hub.resumo_para_cliente(leitura.pi)
        saida = {"resumo": resumo, "numero_pi": resumo.get("numero_pi") or ""}
    except leitor.LeituraErro as exc:
        saida = {"erro": str(exc)}
    except Exception:
        current_app.logger.warning("Leitura do PI de demonstração falhou.", exc_info=True)
        saida = {"erro": "Não foi possível ler o PDF neste momento. Tente novamente."}
    _arquivo(uuid_envio, "json").write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")


def iniciar_leitura_pi(uuid_envio: str, nome: str) -> None:
    if not EXECUTAR_EM_SEGUNDO_PLANO:
        return _ler_agora(uuid_envio, nome)
    app = current_app._get_current_object()

    def tarefa():
        with app.app_context():
            _ler_agora(uuid_envio, nome)
    threading.Thread(target=tarefa, name=f"demo-pi-{uuid_envio[-6:]}", daemon=True).start()


def resultado_pi(uuid_envio: str) -> dict | None:
    caminho = _arquivo(uuid_envio, "json")
    try:
        return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None
    except (OSError, ValueError):
        return None


def estado_pi(registro: dict) -> str:
    """lendo, erro, pronto ou enviado, para o PI de demonstração."""
    if registro.get("enviado_em"):
        return "enviado"
    res = resultado_pi(registro["uuid"])
    if res is None:
        return "erro" if time.time() - registro["em"] > LIMITE_LEITURA_PI else "lendo"
    return "erro" if res.get("erro") else "pronto"
