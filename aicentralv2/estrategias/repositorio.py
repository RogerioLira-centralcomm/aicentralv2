"""Leitura e gravação das estratégias (tabela ``cadu_estrategias``).

Enquanto a migração não rodou, a leitura cai no catálogo-semente e o admin
avisa que falta a migração; gravar exige a tabela.
"""

from __future__ import annotations

import logging
from copy import deepcopy

import psycopg
from psycopg.types.json import Json

from . import catalogo, semente

log = logging.getLogger(__name__)

TABELA_AUSENTE = "A tabela cadu_estrategias ainda não existe: rode migrations/run_seed_cadu_estrategias.py."

_LIMITES = {"nome": 140, "resumo": 400, "descricao": 2000, "duracao": 120, "publico": 200, "cena": 400,
            "como_escala": 600, "texto": 300}


class EstrategiaInvalida(ValueError):
    pass


class TabelaAusente(RuntimeError):
    pass


def _conn():
    from ..db import get_db
    return get_db()


def _linha_para_estrategia(r: dict) -> dict:
    dados = deepcopy(r.get("dados") or {})
    dados.update({"id": r["id"], "slug": r["slug"], "nome": r["nome"], "objetivo": r["objetivo"],
                  "resumo": r.get("resumo") or "", "verba_minima": int(r["verba_minima"]), "ativo": bool(r["ativo"]),
                  "ordem": int(r["ordem"]), "atualizado_em": r.get("atualizado_em")})
    return dados


def _semente() -> list[dict]:
    saida = []
    for i, e in enumerate(semente.lista(), start=1):
        e.update({"id": i, "ativo": True, "ordem": i * 10, "atualizado_em": None})
        saida.append(e)
    return saida


def tabela_existe() -> bool:
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.cadu_estrategias') AS t")
        r = cur.fetchone()
    return bool(r and (r["t"] if isinstance(r, dict) else r[0]))


def listar(somente_ativas: bool = True) -> tuple[list[dict], bool]:
    """(estratégias, veio_do_banco). Sem a tabela, devolve a semente."""
    try:
        if not tabela_existe():
            return _semente(), False
        conn = _conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, slug, nome, objetivo, resumo, verba_minima, ativo, ordem, dados, atualizado_em "
                        "FROM cadu_estrategias" + (" WHERE ativo" if somente_ativas else "") + " ORDER BY ordem, nome")
            return [_linha_para_estrategia(r) for r in cur.fetchall()], True
    except psycopg.Error:
        log.exception("estrategias: falha ao listar; usando a semente")
        try:
            _conn().rollback()
        except Exception:
            pass
        return _semente(), False


def obter(estrategia_id: int, somente_ativas: bool = True) -> dict | None:
    todas, _ = listar(somente_ativas)
    return next((e for e in todas if e["id"] == int(estrategia_id)), None)


def obter_por_slug(slug: str, somente_ativas: bool = True) -> dict | None:
    todas, _ = listar(somente_ativas)
    return next((e for e in todas if e["slug"] == slug), None)


def obter_por_url(endereco: str, somente_ativas: bool = True) -> dict | None:
    """Pelo endereço público; aceita também o nome atual e o slug interno (quem chama redireciona)."""
    alvo = (endereco or "").strip().lower()
    if not alvo:
        return None
    todas, _ = listar(somente_ativas)
    return (next((e for e in todas if catalogo.url_slug(e) == alvo), None)
            or next((e for e in todas if catalogo.slug_url(e["nome"]) == alvo or e["slug"] == alvo), None))


# ---------- validação ----------

def _txt(valor, campo, obrigatorio=False, limite=None) -> str:
    texto = " ".join(str(valor or "").split())
    if obrigatorio and not texto:
        raise EstrategiaInvalida(f"Preencha {campo}.")
    lim = limite or _LIMITES.get(campo, _LIMITES["texto"])
    if len(texto) > lim:
        raise EstrategiaInvalida(f"{campo.capitalize()} passa de {lim} caracteres.")
    return texto


def _lista_txt(valores, campo, maximo=20) -> list[str]:
    if isinstance(valores, str):
        valores = valores.splitlines()
    saida = [_txt(v, campo) for v in (valores or [])]
    saida = [v for v in saida if v]
    if len(saida) > maximo:
        raise EstrategiaInvalida(f"Máximo de {maximo} itens em {campo}.")
    return saida


def _int(valor, campo, minimo=0, maximo=10_000_000) -> int:
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        raise EstrategiaInvalida(f"{campo.capitalize()} precisa ser um número.")
    if not minimo <= n <= maximo:
        raise EstrategiaInvalida(f"{campo.capitalize()} fora do intervalo ({minimo} a {maximo}).")
    return n


def normalizar(bruto: dict, slugs_validos: set[str]) -> dict:
    """Confere e limpa uma estratégia vinda do admin. Levanta EstrategiaInvalida."""
    if not isinstance(bruto, dict):
        raise EstrategiaInvalida("Dados da estratégia inválidos.")
    slug = _txt(bruto.get("slug"), "slug", True, 80).lower()
    if not catalogo.SLUG_RE.match(slug):
        raise EstrategiaInvalida("O slug só aceita letras minúsculas, números e hífen.")
    objetivo = str(bruto.get("objetivo") or "")
    if objetivo not in catalogo.OBJETIVOS:
        raise EstrategiaInvalida("Escolha um objetivo.")
    verba_minima = _int(bruto.get("verba_minima"), "verba mínima", catalogo.FAIXAS[0], catalogo.FAIXAS[-1])

    canais, vistos = [], set()
    for c in bruto.get("canais") or []:
        s = str((c or {}).get("slug") or "")
        if s not in slugs_validos and s not in catalogo.NOS_FLUXO:
            raise EstrategiaInvalida(f"Canal desconhecido: {s or '(vazio)'}.")
        if s in vistos:
            raise EstrategiaInvalida(f"Canal repetido: {s}.")
        vistos.add(s)
        no = s in catalogo.NOS_FLUXO
        papel = str(c.get("papel") or "")
        if not no and papel not in catalogo.PAPEIS:
            raise EstrategiaInvalida(f"Papel inválido em {s}.")
        minimo = c.get("minimo")
        canais.append({
            "slug": s, "papel": ("Dados" if s == "crm" else "Destino") if no else papel,
            "peso": 0 if no else _int(c.get("peso"), f"peso de {s}", 0, 100),
            "essencial": False if no else bool(c.get("essencial")),
            "minimo": 0 if no else (None if minimo in (None, "") else _int(minimo, f"mínimo de {s}", 0, 1_000_000)),
            "formatos": _lista_txt(c.get("formatos"), "formato", 12),
            "otimizacoes": _lista_txt(c.get("otimizacoes"), "otimização", 12),
            "nota": _txt(c.get("nota"), "nota"),
        })
    pagos = [c for c in canais if catalogo.recebe_verba(c)]
    if len(pagos) < 2:
        raise EstrategiaInvalida("Uma estratégia precisa de pelo menos 2 canais com peso.")
    na_minima = catalogo.divisao(canais, catalogo.faixa_inicial(verba_minima))["linhas"]
    if len(na_minima) < 2:
        raise EstrategiaInvalida("Na verba mínima só um canal recebe verba. Suba a verba mínima, "
                                 "marque canais como essenciais ou reduza os mínimos.")

    fluxo = []
    for e in bruto.get("fluxo") or []:
        nos = [n for n in (e or {}).get("nos") or [] if n in vistos]
        fluxo.append({"titulo": _txt(e.get("titulo"), "título da etapa", True, 60),
                      "descricao": _txt(e.get("descricao"), "descrição da etapa"), "nos": nos})
    if len(fluxo) < 2:
        raise EstrategiaInvalida("O fluxo precisa de pelo menos 2 etapas.")
    if len(fluxo) > 8:
        raise EstrategiaInvalida("O fluxo aceita até 8 etapas.")

    conv = bruto.get("conversao") or {}
    destino = str(conv.get("destino") or "")
    if destino not in catalogo.DESTINOS:
        raise EstrategiaInvalida("Escolha o destino da conversão.")
    rmk = bruto.get("remarketing") or {}
    lst = bruto.get("lista_clientes") or {}

    criativos = []
    for p in bruto.get("criativos") or []:
        if not (p or {}).get("peca"):
            continue
        criativos.append({"peca": _txt(p.get("peca"), "peça", True, 120), "specs": _txt(p.get("specs"), "especificação"),
                          "quantidade": _int(p.get("quantidade") or 1, "quantidade", 1, 50),
                          "canais": [s for s in p.get("canais") or [] if s in vistos]})
    kpis = []
    for k in bruto.get("kpis") or []:
        if not (k or {}).get("nome"):
            continue
        fonte = str(k.get("fonte") or "")
        kpis.append({"nome": _txt(k.get("nome"), "indicador", True, 120), "etapa": _txt(k.get("etapa"), "etapa", False, 60),
                     "fonte": fonte if fonte in catalogo.FONTES_KPI else "Plataforma",
                     "principal": bool(k.get("principal")), "como": _txt(k.get("como"), "como medir")})
    if not kpis:
        raise EstrategiaInvalida("Defina pelo menos um indicador.")
    efeitos = []
    for ef in bruto.get("efeitos") or []:
        if not (ef or {}).get("texto"):
            continue
        efeitos.append({"fase": _txt(ef.get("fase"), "fase", True, 40), "texto": _txt(ef.get("texto"), "efeito esperado", True, 400)})
    if len(efeitos) > 6:
        raise EstrategiaInvalida("Até 6 fases em O que esperar.")

    return {
        "slug": slug, "nome": _txt(bruto.get("nome"), "nome", True), "objetivo": objetivo,
        # Sugestão para a criação; salvar() decide o endereço final (mantém o atual na edição, evita repetido).
        "url_slug": catalogo.slug_url(bruto.get("nome")),
        "resumo": _txt(bruto.get("resumo"), "resumo", True), "verba_minima": verba_minima,
        "ativo": bool(bruto.get("ativo", True)), "ordem": _int(bruto.get("ordem") or 100, "ordem", 0, 10_000),
        "descricao": _txt(bruto.get("descricao"), "descricao"), "duracao": _txt(bruto.get("duracao"), "duracao"),
        "publico": _txt(bruto.get("publico"), "publico"), "cena": _txt(bruto.get("cena"), "cena"),
        "como_escala": _txt(bruto.get("como_escala"), "como_escala"),
        "canais": canais, "fluxo": fluxo,
        "conversao": {"destino": destino, "precisa_link": bool(conv.get("precisa_link")),
                      "descricao": _txt(conv.get("descricao"), "descrição da conversão"),
                      "eventos": _lista_txt(conv.get("eventos"), "evento", 10)},
        "remarketing": {"usa": bool(rmk.get("usa")), "publicos": _lista_txt(rmk.get("publicos"), "público", 10),
                        "janela_dias": _int(rmk.get("janela_dias") or 0, "janela", 0, 540),
                        "descricao": _txt(rmk.get("descricao"), "descrição do remarketing")},
        "lista_clientes": {"usa": bool(lst.get("usa")), "usos": _lista_txt(lst.get("usos"), "uso", 10),
                           "requisito": _txt(lst.get("requisito"), "requisito")},
        "criativos": criativos, "kpis": kpis, "efeitos": efeitos,
        "otimizacoes": _lista_txt(bruto.get("otimizacoes"), "otimização", 20),
    }


_COLUNAS = ("slug", "nome", "objetivo", "resumo", "verba_minima", "ativo", "ordem")


def _separar(e: dict) -> tuple[dict, dict]:
    colunas = {k: e[k] for k in _COLUNAS}
    dados = {k: v for k, v in e.items() if k not in _COLUNAS and k not in ("id", "atualizado_em")}
    return colunas, dados


def _endereco(e: dict, estrategia_id: int | None) -> str:
    """Endereço público a gravar. Na edição vale o que já estava no ar (o gravado ou, em linha
    antiga sem ele, o do nome anterior), para links compartilhados não quebrarem ao renomear.
    Endereço já usado por outra estratégia ganha sufixo (-2, -3...)."""
    todas, _ = listar(somente_ativas=False)
    atual = next((x for x in todas if estrategia_id and x["id"] == int(estrategia_id)), None)
    base = catalogo.url_slug(atual) if atual else (e.get("url_slug") or catalogo.slug_url(e.get("nome")))
    usados = {catalogo.url_slug(x) for x in todas if x is not atual}
    candidato, n = base, 2
    while candidato in usados:
        candidato, n = f"{base}-{n}", n + 1
    return candidato


def salvar(e: dict, estrategia_id: int | None, usuario_id: int | None) -> int:
    if not tabela_existe():
        raise TabelaAusente(TABELA_AUSENTE)
    e = dict(e, url_slug=_endereco(e, estrategia_id))
    colunas, dados = _separar(e)
    conn = _conn()
    try:
        with conn.cursor() as cur:
            if estrategia_id:
                cur.execute("""UPDATE cadu_estrategias SET slug=%s, nome=%s, objetivo=%s, resumo=%s, verba_minima=%s,
                               ativo=%s, ordem=%s, dados=%s, atualizado_em=now(), atualizado_por=%s WHERE id=%s RETURNING id""",
                            (*[colunas[k] for k in _COLUNAS], Json(dados), usuario_id, estrategia_id))
            else:
                cur.execute("""INSERT INTO cadu_estrategias (slug, nome, objetivo, resumo, verba_minima, ativo, ordem, dados,
                               atualizado_por) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                            (*[colunas[k] for k in _COLUNAS], Json(dados), usuario_id))
            r = cur.fetchone()
        conn.commit()
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        raise EstrategiaInvalida("Já existe uma estratégia com esse slug.")
    if not r:
        raise EstrategiaInvalida("Estratégia não encontrada.")
    return int(r["id"] if isinstance(r, dict) else r[0])


def alternar_ativo(estrategia_id: int, usuario_id: int | None) -> bool:
    if not tabela_existe():
        raise TabelaAusente(TABELA_AUSENTE)
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute("UPDATE cadu_estrategias SET ativo = NOT ativo, atualizado_em=now(), atualizado_por=%s "
                    "WHERE id=%s RETURNING ativo", (usuario_id, estrategia_id))
        r = cur.fetchone()
    conn.commit()
    return bool(r and (r["ativo"] if isinstance(r, dict) else r[0]))


# ---------- parâmetros da estimativa (benchmarks e conversões) ----------

def salvar_parametros(chave: str, valor: dict, usuario_id: int | None) -> None:
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.cadu_estrategias_parametros') AS t")
        r = cur.fetchone()
        if not (r and (r["t"] if isinstance(r, dict) else r[0])):
            raise TabelaAusente(TABELA_AUSENTE)
        cur.execute("""INSERT INTO cadu_estrategias_parametros (chave, valor, atualizado_por) VALUES (%s, %s, %s)
                       ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, atualizado_em = now(),
                       atualizado_por = EXCLUDED.atualizado_por""", (chave, Json(valor), usuario_id))
    conn.commit()
