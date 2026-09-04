"""CRM v3 — camada de repositório com Postgres.

Fase 3 do plano CRM v3 UX Overhaul. Expõe uma superfície idêntica ao
`CrmTestStore` (em memória) mas resolve tudo em `db.py` / Postgres.

Feature flag `USE_CRM_V3_STORE` (default agora é REAL):
- não setado / "real" / "db" / "0" / "false"  → repositório Postgres.
- "mock" / "memory" / "1" / "true"            → store em memória (fixture).

Fallback automático: se o import do módulo `db` falhar (falta libpq,
ambiente sem banco) ou a primeira chamada básica quebrar, o
`get_store()` volta para o store em memória — evita derrubar a UI em
dev/sandbox e continua servindo o CRM v3.

Escopo desta iteração
---------------------
O repositório implementa (Fase 3.2b completa):
- Clientes (list/get/create/update) via `db.obter_clientes_paginado`,
  `db.obter_cliente_por_id`, `db.criar_cliente`, `db.atualizar_cliente`.
- Contatos via `db.obter_contatos_por_cliente`, `db.criar_contato`,
  `db.atualizar_contato`.
- Agencias vinculadas via `db.listar_agencias_vinculadas_cliente`,
  `db.listar_clientes_vinculados_agencia`, `db.salvar_agencias_vinculadas_cliente`.
- Atividades (leitura + create/update/delete) em `sales_atividades` via
  `db.obter/criar/atualizar/excluir_atividade_cliente`.
- Objetivos (leitura + create/update/delete + conquistar) em
  `sales_objetivos_cliente` via `db.obter/criar/atualizar/conquistar/excluir_objetivo_cliente`.
- Notas (leitura + create; histórico é append-only, sem PATCH/DELETE,
  espelhando o CRM legado) em `sales_historico_cliente` via
  `db.listar_historico_cliente` e `db.criar_historico_cliente`.
- Cotações (leitura + create/update/delete) em `cadu_cotacoes` via
  `db.obter_cotacoes_cliente`, `db.criar_cotacao`, `db.atualizar_cotacao`,
  `db.deletar_cotacao` (soft delete).

`update_nota` e `delete_nota` retornam `(None, None)` / `(False, None)`
propositalmente para preservar o contrato *append-only* do histórico.
"""

from __future__ import annotations

import os
import re
from datetime import date as _date, datetime as _datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from .crm_v3_helpers import (
    filtrar_vinculos_colisao_lookup,
    uf_por_capital_operacao,
    texto_sem_markdown,
    titulo_atividade_lista,
)


def _db():
    """Import lazy do módulo db, para não falhar em ambientes sem libpq.

    Se o processo nunca ativar `USE_CRM_V3_STORE=0` o import nunca é executado.
    """
    from . import db as _real_db
    return _real_db


def _rollback_if_failed(reason: str = "") -> None:
    """Faz ROLLBACK na conexão do request quando a transação está morta.

    Contexto crítico (set/2026): `db.get_db()` cria a conexão com
    `autocommit=False`. Toda a request compartilha essa MESMA conexão
    dentro de uma transação implícita. Se qualquer query falha
    (schema divergente, coluna inexistente, deadlock, etc.), o
    Postgres coloca a transação em `aborted` e devolve
    `InFailedSqlTransaction` em TODAS as queries seguintes — até
    que um ROLLBACK explícito seja executado.

    Sem essa recuperação, um único cliente com dados inconsistentes
    derrubava toda a listagem: try/except no repo capturava, mas a
    próxima iteração recebia InFailedSqlTransaction e recaptura, etc.
    O log ficava cheio de InFailedSqlTransaction em cascata.

    Uso: chamar dentro do `except Exception` sempre que uma query do
    módulo `db` falhar em cima de uma transação compartilhada.
    """
    try:
        conn = _db().get_db()
        if conn and not getattr(conn, "closed", True):
            conn.rollback()
    except Exception:
        # Se o rollback falhou, a conexão está perdida — o `close_db`
        # do teardown_request vai limpar e o próximo request começa
        # do zero. Não há muito o que fazer aqui.
        pass


# =============================================================================
# Feature flag
# =============================================================================

# Valores explícitos que forçam MOCK. Note: `1`/`true`/`yes` foram
# removidos propositalmente em set/2026 porque a semântica anterior era
# "ativa o store novo (=mock)" — muita gente ainda tem essas variáveis
# setadas na produção esperando "ligar o banco real". Agora só valores
# obviamente ligados a memória contam.
_MOCK_TOKENS = frozenset({"mock", "memory", "in-memory", "fake", "fixture"})
_REAL_TOKENS = frozenset({"real", "db", "postgres", "postgresql", "prod"})


def _flag_raw() -> str:
    return (
        os.environ.get("USE_CRM_V3_STORE")
        or os.environ.get("CRM_V3_STORE")  # alias mais claro (set/2026)
        or ""
    ).strip().lower()


def use_repository() -> bool:
    """Retorna True se o CRM v3 deve usar o banco real (default)."""
    raw = _flag_raw()
    if raw in _MOCK_TOKENS:
        return False
    return True  # default + qualquer valor não reconhecido → real


# Diagnóstico do último `get_store()` — usado por /api/_debug/store para
# expor no painel qual modo o processo está servindo e por quê.
_LAST_DIAGNOSTIC: Dict[str, Any] = {
    "mode": "unknown",  # "real" | "mock"
    "reason": "not-initialized",
    "flag_env": "",
    "flag_recognized": None,
    "db_error": None,
    "at": None,
}


def store_diagnostic() -> Dict[str, Any]:
    """Retorna dict do último diagnóstico decidido pelo get_store()."""
    return dict(_LAST_DIAGNOSTIC)


# =============================================================================
# Helpers de mapeamento (row → dict compatível com CrmTestStore)
# =============================================================================

_CLASSIFICACOES = ("Prospecção", "Ativo", "Geladeira")


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Converte Decimal/str/int para float sem derrubar o GET do cliente."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _map_cliente(row: Dict[str, Any]) -> Dict[str, Any]:
    """Converte um registro de `tbl_cliente` para o formato usado pelo v3 UI."""
    if not row:
        return {}
    is_agencia = bool(row.get("agencia_key")) or (
        str(row.get("agencia_display") or "").strip().lower() in ("sim", "s")
    )
    tipo_display = row.get("tipo_cliente_display") or ""
    tipo_label = "Agência" if is_agencia else "Cliente final"
    classificacao = row.get("classificacao_cliente") or "Prospecção"
    if classificacao not in _CLASSIFICACOES:
        classificacao = "Prospecção"

    nome = row.get("nome_fantasia") or row.get("razao_social") or ""
    # UF de exibição: prefere a sigla oficial do JOIN (tbl_estado.sigla);
    # se ausente, tenta interpretar o campo bruto (`estado`) apenas quando
    # for uma string curta tipo "MG"/"SP".
    sigla_estado = (row.get("estado_sigla") or "").strip().upper()
    if not sigla_estado:
        raw_estado = row.get("estado")
        if isinstance(raw_estado, str) and len(raw_estado.strip()) <= 3:
            sigla_estado = raw_estado.strip().upper()
    endereco = {
        "cep": row.get("cep") or "",
        "uf": sigla_estado,
        # ID numérico do estado — útil para debug/consistência. O drawer
        # continua exibindo/enviando pela sigla; o backend resolve.
        "pk_id_aux_estado": row.get("pk_id_aux_estado") or None,
        "cidade": row.get("cidade") or "",
        "bairro": row.get("bairro") or "",
        "logradouro": row.get("logradouro") or "",
        "numero": row.get("numero") or "",
        "complemento": row.get("complemento") or "",
    }
    uf_capital = uf_por_capital_operacao(endereco["cidade"])
    if uf_capital:
        endereco["uf"] = uf_capital

    vinculos_src = row.get("agencias_vinculadas") or []
    lookup_ids = row.get("_agencia_lookup_ids")
    if lookup_ids is None:
        # tbl_agencia é lookup Sim/Não (ids 1/2 na base). Sem o id
        # explícito do lookup, ainda descartamos colisão clássica
        # quando existe outra agência no N:N.
        lookup_ids = {1, 2}
    vinculos_src = filtrar_vinculos_colisao_lookup(vinculos_src, lookup_ids)
    vinculos = []
    for v in vinculos_src:
        ag_id = v.get("id_agencia_cliente") or v.get("agencia_id") or ""
        # Não usar v["id_cliente"]: na tabela N:N esse campo (quando
        # existe) é o cliente-final, não a agência. Usá-lo como
        # fallback associava a agência errada (ex.: ADALA) em vários
        # clientes sem vínculo real.
        if not ag_id:
            continue
        if "agencia_key" in v or "agencia_display" in v:
            eh_agencia = v.get("agencia_key") is True or str(
                v.get("agencia_display") or ""
            ).strip().lower() in ("sim", "s")
            if not eh_agencia:
                continue
        vinculos.append({
            "agencia_id": str(ag_id),
            "is_principal": v.get("is_principal") is True or v.get("is_principal") == 1,
            "nome": (v.get("nome_fantasia") or v.get("razao_social") or v.get("nome") or "").strip(),
        })
    principal = next((v for v in vinculos if v.get("is_principal")), vinculos[0] if vinculos else None)

    def _fmt_iso(dt):
        return dt.isoformat() if hasattr(dt, "isoformat") else (dt or None)

    return {
        "id": str(row.get("id_cliente")),
        "nome": nome,
        "nome_fantasia": row.get("nome_fantasia") or nome,
        "razao_social": row.get("razao_social") or nome,
        "pessoa": row.get("pessoa") or "J",
        "cnpj": row.get("cnpj") or "",
        "inscricao_estadual": row.get("inscricao_estadual") or "",
        "inscricao_municipal": row.get("inscricao_municipal") or "",
        "tipo_label": tipo_label,
        "perfil": "agencia" if is_agencia else "direto",
        "is_agencia": is_agencia,
        "classificacao_cliente": classificacao,
        "classificacao": classificacao,
        "tipo": tipo_display or "",
        "categoria": tipo_display or "",
        "id_tipo_cliente": row.get("id_tipo_cliente"),
        "cidade": row.get("cidade") or "",
        "uf": endereco["uf"],
        "estado_nome": row.get("estado_nome") or "",
        "endereco": endereco,
        "bv_percentual": _safe_float(row.get("percentual")),
        "margem_cc": _safe_float(row.get("margem_cc")),
        "opera_midia": bool(row.get("opera_midia")),
        "demanda_dados": bool(row.get("demanda_dados")),
        "demanda_programatica_canais": bool(row.get("demanda_programatica_canais")),
        "observacoes_comerciais_adicionais": row.get("observacoes_comerciais_adicionais") or "",
        # Nota livre do executivo (tbl_cliente.nota_executivo_vendas) — pode
        # ser NULL em bases sem a coluna (SELECT já degrada para NULL).
        "nota_executivo": row.get("nota_executivo_vendas") or "",
        # Site do cliente (tbl_cliente.site_url) — usado no CRM v3 para
        # derivar o logo automaticamente via Clearbit. Ausente em bases
        # que ainda não rodaram `add_site_url_to_tbl_cliente.sql`.
        "site_url": row.get("site_url") or "",
        "responsavel": row.get("executivo_nome") or "",
        "responsavel_email": row.get("executivo_email") or "",
        # ID do executivo (vendas_central_comm) — usado por filtros
        # opcionais no frontend (data-executivo-id no <option>).
        "executivo_id": str(row.get("vendas_central_comm")) if row.get("vendas_central_comm") else "",
        "data_cadastro": _fmt_iso(row.get("data_cadastro")),
        "data_modificacao": _fmt_iso(row.get("data_modificacao")),
        "status": row.get("status") if row.get("status") is not None else True,
        "agencia_id": (principal["agencia_id"] if principal and not is_agencia else ""),
        # Nome só vem de tbl_cliente_agencia (vínculo real). Nunca de
        # pk_id_tbl_agencia, que é o lookup Sim/Não de "esta ficha é
        # agência" — JOIN por esse id apontava para outro cliente (ADALA).
        "agencia_nome": (principal.get("nome") or "") if principal and not is_agencia else "",
        "agencias_vinculadas": vinculos,
    }


def _stamp_atividade_badge(mapped: Dict[str, Any]) -> Dict[str, Any]:
    """Preenche badge / proxima_atividade a partir de metrics.

    Textos que o frontend (situacaoHtml) reconhece:
    Sem atividade, Concluída, N dia(s) atrasado, Hoje, Amanhã, Em N dias.
    """
    metrics = mapped.get("metrics") or {}
    proxima = metrics.get("proxima_atividade")
    mapped["proxima_atividade"] = proxima
    if not proxima:
        ultimo = metrics.get("ultimo_contato") or ""
        if ultimo and ultimo != "—":
            mapped["badge"] = "Concluída"
            mapped["badge_type"] = "success"
        else:
            mapped["badge"] = "Sem atividade"
            mapped["badge_type"] = "danger"
        return mapped
    dias = int(proxima.get("dias") or 0)
    if dias < 0:
        d_abs = abs(dias)
        mapped["badge"] = (
            f"{d_abs} dia atrasado" if d_abs == 1 else f"{d_abs} dias atrasado"
        )
        mapped["badge_type"] = "warning"
    elif dias == 0:
        mapped["badge"] = "Hoje"
        mapped["badge_type"] = "success"
    elif dias == 1:
        mapped["badge"] = "Amanhã"
        mapped["badge_type"] = "info"
    else:
        mapped["badge"] = f"Em {dias} dias"
        mapped["badge_type"] = "info"
    return mapped


class CrmV3Repository:
    """Superfície igual ao CrmTestStore, mas conectada ao Postgres."""

    # ---------------- Clientes ------------------------------------------------

    def reset(self) -> None:  # pragma: no cover — não faz sentido em produção
        raise NotImplementedError("reset() só existe no store em memória")

    def list_clientes(self) -> List[Dict[str, Any]]:
        # per_page alto: a UI já pagina em memória (8 por página) e faz o
        # filtro cliente-side por executivo/tipo/perfil/pill/busca. 1000 é
        # confortável para a base atual; se crescer, movemos a paginação
        # para server-side via query params.
        page = _db().obter_clientes_paginado(page=1, per_page=1000) or {}
        rows = page.get("clientes", []) or []
        ids_lote = [r.get("id_cliente") for r in rows if r.get("id_cliente") is not None]
        vinculos_lote = {}
        try:
            vinculos_lote = _db().listar_agencias_vinculadas_lote(ids_lote) or {}
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("aicentral.crm_v3").info(
                "lote agencias_vinculadas falhou: %s: %s", type(e).__name__, e,
            )
            _rollback_if_failed("agencias_vinculadas lote")
        items = []
        _metrics_default = {
            "faturamento": 0.0, "pipeline": 0.0,
            "cotacoes_abertas": 0, "cotacoes_aprovadas": 0,
            "contatos_total": 0, "tarefas_abertas": 0,
            "ultimo_contato": "—",
        }
        for row in rows:
            row = dict(row)
            cid = row.get("id_cliente")
            row["agencias_vinculadas"] = (
                vinculos_lote.get(cid) or vinculos_lote.get(str(cid)) or []
            )
            mapped = _map_cliente(row)
            # Blindagem (set/2026): se _metrics_for ou o LEFT JOIN de
            # agências vinculadas falharem para UM cliente específico
            # (ex.: id órfão, executivo inexistente, cotação com valor
            # NULL num row antigo), NÃO derrubamos toda a listagem — o
            # card renderiza sem métricas e o log registra o erro para
            # investigação depois. Antes qualquer erro aqui virava 500
            # na página inteira.
            try:
                mapped["metrics"] = self._metrics_for(mapped["id"])
            except Exception as e:  # noqa: BLE001
                import logging
                logging.getLogger("aicentral.crm_v3").warning(
                    "_metrics_for falhou para cliente %s: %s: %s",
                    mapped.get("id"), type(e).__name__, e,
                )
                # ROLLBACK crítico: se _metrics_for morreu por causa de
                # uma query com erro, TODAS as queries seguintes retornam
                # InFailedSqlTransaction até dar rollback. Sem essa
                # linha, o try/except abaixo (listar_clientes_vinculados_agencia)
                # e o próximo cliente da lista também falhariam em cascata.
                _rollback_if_failed("_metrics_for")
                mapped["metrics"] = dict(_metrics_default)
                mapped["metrics_error"] = f"{type(e).__name__}: {str(e)[:120]}"

            # Set/2026 — Badge estilo Pipedrive na lista de clientes.
            _stamp_atividade_badge(mapped)

            # Preencher clientes finais/ agência nome para o card
            if mapped["is_agencia"]:
                try:
                    filhos = _db().listar_clientes_vinculados_agencia(mapped["id"]) or []
                    mapped["clientes_finais_ids"] = [str(x["id_cliente"]) for x in filhos]
                    mapped["clientes_finais_count"] = len(filhos)
                    mapped["clientes_finais"] = [
                        {
                            "id": str(x["id_cliente"]),
                            "nome": x.get("nome_fantasia") or x.get("razao_social"),
                            "classificacao_cliente": x.get("classificacao_cliente"),
                        }
                        for x in filhos
                    ]
                except Exception as e:  # noqa: BLE001
                    import logging
                    logging.getLogger("aicentral.crm_v3").warning(
                        "listar_clientes_vinculados_agencia falhou para %s: %s: %s",
                        mapped.get("id"), type(e).__name__, e,
                    )
                    _rollback_if_failed("listar_clientes_vinculados_agencia")
                    mapped["clientes_finais_ids"] = []
                    mapped["clientes_finais_count"] = 0
                    mapped["clientes_finais"] = []
            items.append(mapped)

        # Enriquecer com logo canônico do `cliente_web_info` — set/2026.
        # Motivo: na lista de clientes (coluna 1 do CRM v3) queremos
        # mostrar a logo real do site (og:image scrapeado) em vez de
        # só as iniciais. Antes o frontend usava `state.webInfoCache`,
        # mas esse cache só era populado ao selecionar o cliente — na
        # lista sempre aparecia só iniciais.
        #
        # Estratégia: uma única query batch (IN(...)) que traz todos
        # os logos de uma vez, em vez de N chamadas separadas. O
        # `web_logo_url` fica direto no dict do cliente, sem depender
        # do webInfoCache.
        #
        # Silencioso em caso de erro: se `cliente_web_info` não existe
        # (base antiga sem migration) ou a query falha, seguimos sem
        # logo — o frontend cai no Clearbit como sempre.
        try:
            ids_int = []
            for m in items:
                try:
                    ids_int.append(int(m["id"]))
                except (ValueError, TypeError):
                    pass
            if ids_int:
                # Usa a conexão gerenciada pelo Flask (g.db) — NÃO
                # fechamos aqui, quem fecha é `close_db` no teardown.
                conn = _db().get_db()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id_cliente, logo_url, favicon_url, dominio "
                        "FROM cliente_web_info "
                        "WHERE id_cliente = ANY(%s) AND status = 'ok'",
                        (ids_int,),
                    )
                    rows = cur.fetchall()
                logos = {}
                for r in rows:
                    if isinstance(r, dict):
                        cid = r.get("id_cliente")
                        logo = r.get("logo_url")
                        dom = r.get("dominio")
                    else:
                        cid, logo, _fav, dom = r[0], r[1], r[2], r[3]
                    if cid is not None:
                        logos[str(cid)] = {"logo_url": logo, "dominio": dom}
                for m in items:
                    info = logos.get(str(m["id"]))
                    if info:
                        if info.get("logo_url"):
                            m["web_logo_url"] = info["logo_url"]
                        # Preenche site_url quando o cadastro estava
                        # vazio mas o scout descobriu o domínio real.
                        if info.get("dominio") and not m.get("site_url"):
                            m["site_url"] = info["dominio"]
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("aicentral.crm_v3").info(
                "enriquecimento web_logo_url falhou (base sem cliente_web_info?): %s: %s",
                type(e).__name__, e,
            )
            _rollback_if_failed("web_logo_url batch")

        return items

    def list_lookups(self) -> Dict[str, Any]:
        """Consolida todos os combos "de dominio" usados pela UI (drawers,
        modais, filtros) em UMA única chamada.

        Motivo (set/2026): o CRM v3 tinha vários `<option>` hardcoded
        (tipo Público/Privado, UF, executivos "Luisa Santana", "João Paulo"
        etc.) que não refletiam a base real. Um endpoint agregado evita
        N+1 chamadas e simplifica o cache no frontend.

        Retorna:
          - tipos_cliente : [{id, label}] via db.obter_tipos_cliente
          - estados       : [{id, sigla, nome}] via db.obter_estados
          - setores       : [{id, nome}] via db.obter_setores
          - cargos        : [{id, nome, setor_id}] via db.obter_cargos
          - executivos    : [{id, nome, email}] via db.obter_vendedores_centralcomm
          - plataformas   : [{id, nome}] via db.obter_plataformas_campanha
          - classificacoes: enum fixo (Prospecção/Ativo/Geladeira)
        """
        db = _db()

        def _safe(fn, default=None):
            try:
                return fn() or default or []
            except Exception:
                return default if default is not None else []

        tipos = [
            {"id": str(r.get("id_tipo_cliente")), "label": r.get("display") or ""}
            for r in _safe(db.obter_tipos_cliente)
            if r.get("id_tipo_cliente") is not None
        ]
        estados = [
            {
                "id": str(r.get("id_estado")),
                "sigla": (r.get("sigla") or "").strip(),
                "nome": r.get("descricao") or "",
            }
            for r in _safe(db.obter_estados)
            if r.get("id_estado") is not None
        ]
        setores = [
            {"id": str(r.get("id_setor")), "nome": r.get("display") or r.get("nome") or ""}
            for r in _safe(db.obter_setores)
            if r.get("id_setor") is not None
        ]
        cargos = [
            {
                "id": str(r.get("id_cargo")),
                "nome": r.get("display") or r.get("nome") or "",
                "setor_id": str(r.get("pk_id_tbl_setor")) if r.get("pk_id_tbl_setor") else "",
            }
            for r in _safe(db.obter_cargos)
            if r.get("id_cargo") is not None
        ]
        executivos = [
            {
                "id": str(r.get("id_contato_cliente")),
                "nome": r.get("nome_completo") or "",
                "email": r.get("email") or "",
                "foto_url": r.get("foto_url") or "",
            }
            for r in _safe(db.obter_vendedores_centralcomm)
            if r.get("id_contato_cliente") is not None
        ]
        plataformas = [
            {"id": str(r.get("id_plataforma_campanha")), "nome": r.get("display") or r.get("nome") or ""}
            for r in _safe(db.obter_plataformas_campanha)
            if r.get("id_plataforma_campanha") is not None
        ]

        return {
            "tipos_cliente": tipos,
            "estados": estados,
            "setores": setores,
            "cargos": cargos,
            "executivos": executivos,
            "plataformas": plataformas,
            "classificacoes": [
                {"id": "Prospecção", "nome": "Prospecção"},
                {"id": "Ativo", "nome": "Ativo"},
                {"id": "Geladeira", "nome": "Geladeira"},
            ],
        }

    def list_agencias(self) -> List[Dict[str, Any]]:
        """Retorna TODAS as agências reais da base (não só as que estão
        na página atual de clientes carregada no frontend).

        Motivo (set/2026): o drawer de editar cliente precisa exibir
        todas as agências disponíveis no dropdown "Vínculos com agência".
        Antes o frontend derivava a lista de `state.clientes` (paginado),
        o que fazia aparecer só 2–3 agências mesmo com a base tendo
        dezenas. Agora usamos `db.obter_clientes_agencias()`, que já é
        a fonte oficial usada pelas telas de agência do CRM legado.

        Retorna dicts no formato mínimo esperado pelo select:
          {"id": "<id_cliente>", "nome": "<nome_fantasia_ou_razao>"}
        """
        rows = _db().obter_clientes_agencias() or []
        out = []
        for r in rows:
            nome = (r.get("nome_fantasia") or r.get("razao_social") or "").strip()
            if not nome:
                continue
            out.append({"id": str(r["id_cliente"]), "nome": nome})
        return out

    def get_cliente(self, cliente_id: str) -> Optional[Dict[str, Any]]:
        row = _db().obter_cliente_por_id(cliente_id)
        if not row:
            return None
        mapped = _map_cliente(row)
        uf_capital = uf_por_capital_operacao(mapped.get("cidade"))
        sigla_db = (row.get("estado_sigla") or "").strip().upper()
        if not sigla_db:
            raw_estado = row.get("estado")
            if isinstance(raw_estado, str) and len(raw_estado.strip()) <= 3:
                sigla_db = raw_estado.strip().upper()
        if uf_capital and sigla_db != uf_capital:
            try:
                _db().atualizar_campos_cliente(cliente_id, {"uf": uf_capital})
            except Exception:  # noqa: BLE001 — a tela já mostra a sigla
                pass
            mapped["uf"] = uf_capital
            if isinstance(mapped.get("endereco"), dict):
                mapped["endereco"]["uf"] = uf_capital
        try:
            mapped["metrics"] = self._metrics_for(cliente_id)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("aicentral.crm_v3").warning(
                "_metrics_for (detalhe) falhou para cliente %s: %s: %s",
                cliente_id, type(e).__name__, e,
            )
            _rollback_if_failed("_metrics_for")
            mapped["metrics"] = {
                "faturamento": 0.0, "pipeline": 0.0,
                "cotacoes_abertas": 0, "cotacoes_aprovadas": 0,
                "contatos_total": 0, "tarefas_abertas": 0,
                "ultimo_contato": "—",
            }
        _stamp_atividade_badge(mapped)
        if mapped["is_agencia"]:
            try:
                filhos = _db().listar_clientes_vinculados_agencia(cliente_id) or []
                mapped["clientes_finais_ids"] = [str(x["id_cliente"]) for x in filhos]
                mapped["clientes_finais_count"] = len(filhos)
                mapped["clientes_finais"] = [
                    {
                        "id": str(x["id_cliente"]),
                        "nome": x.get("nome_fantasia") or x.get("razao_social"),
                        "classificacao_cliente": x.get("classificacao_cliente"),
                    }
                    for x in filhos
                ]
            except Exception as e:  # noqa: BLE001
                import logging
                logging.getLogger("aicentral.crm_v3").warning(
                    "listar_clientes_vinculados_agencia (detalhe) falhou para %s: %s: %s",
                    cliente_id, type(e).__name__, e,
                )
                _rollback_if_failed("listar_clientes_vinculados_agencia")
                mapped["clientes_finais_ids"] = []
                mapped["clientes_finais_count"] = 0
                mapped["clientes_finais"] = []
        return mapped

    def create_cliente(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria cliente real via `db.criar_cliente`.

        Não expõe TODOS os campos ainda (BV/margem/opera_midia ficam para
        Fase 3.2b via db.atualizar_cliente separado).
        """
        razao = str(data.get("razao_social") or data.get("nome") or "").strip()
        nome_fantasia = str(data.get("nome") or data.get("nome_fantasia") or razao).strip()
        if not razao:
            raise ValueError("razao_social é obrigatório")

        id_tipo_cliente = data.get("id_tipo_cliente") or None
        try:
            id_tipo_cliente_int = int(id_tipo_cliente) if id_tipo_cliente else None
        except (TypeError, ValueError):
            id_tipo_cliente_int = None

        new_id = _db().criar_cliente(
            razao_social=razao,
            nome_fantasia=nome_fantasia,
            id_tipo_cliente=id_tipo_cliente_int or 1,
            pessoa=data.get("pessoa") or "J",
            cnpj=data.get("cnpj") or None,
            inscricao_municipal=data.get("inscricao_municipal") or None,
            inscricao_estadual=data.get("inscricao_estadual") or None,
        )
        # Vínculos com agências (N:N)
        vinculos = data.get("agencias_vinculadas") or []
        agencia_ids = [v.get("agencia_id") for v in vinculos if v.get("agencia_id")]
        principal = next((v.get("agencia_id") for v in vinculos if v.get("is_principal")), None)
        if agencia_ids:
            _db().salvar_agencias_vinculadas_cliente(new_id, agencia_ids, principal)
        return self.get_cliente(new_id) or {}

    def update_cliente(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """PATCH parcial no cliente.

        Aceita qualquer subconjunto dos campos suportados pelo edit-in-place
        (ver `_CLIENTE_INLINE_EDITABLE` em `db.py`), incluindo o
        alias `nome` → `nome_fantasia`. Só chama `db.atualizar_campos_cliente`
        quando há campos válidos; assim, um PATCH que envia só
        `agencias_vinculadas` (sem tocar em outros campos) atualiza
        apenas os vínculos, sem gerar UPDATE ruidoso em tbl_cliente.
        """
        atual = _db().obter_cliente_por_id(cliente_id)
        if not atual:
            return None
        # Campos individuais → PATCH parcial (whitelist em db.py).
        try:
            _db().atualizar_campos_cliente(cliente_id, data)
        except Exception:
            # Se a assinatura antiga estiver em uso (raro), tenta o fallback
            # completo com merge — preserva estabilidade em bases legadas.
            _db().atualizar_cliente(
                id_cliente=cliente_id,
                razao_social=data.get("razao_social") or atual.get("razao_social"),
                nome_fantasia=data.get("nome") or data.get("nome_fantasia") or atual.get("nome_fantasia"),
                id_tipo_cliente=data.get("id_tipo_cliente") or atual.get("id_tipo_cliente"),
                pessoa=data.get("pessoa") or atual.get("pessoa") or "J",
                cnpj=data.get("cnpj") if "cnpj" in data else atual.get("cnpj"),
                inscricao_municipal=data.get("inscricao_municipal") if "inscricao_municipal" in data else atual.get("inscricao_municipal"),
                inscricao_estadual=data.get("inscricao_estadual") if "inscricao_estadual" in data else atual.get("inscricao_estadual"),
            )
        # Reconciliar vínculos, se enviados
        if "agencias_vinculadas" in data:
            vinculos = data.get("agencias_vinculadas") or []
            agencia_ids = [v.get("agencia_id") for v in vinculos if v.get("agencia_id")]
            principal = next((v.get("agencia_id") for v in vinculos if v.get("is_principal")), None)
            _db().salvar_agencias_vinculadas_cliente(cliente_id, agencia_ids, principal)
        return self.get_cliente(cliente_id)

    # ---------------- Contatos ------------------------------------------------

    def list_contatos(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        rows = _db().obter_contatos_por_cliente(cliente_id) or []
        return [self._map_contato(r) for r in rows]

    def create_contato(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        new_id = _db().criar_contato(
            nome_completo=data.get("nome") or "",
            email=data.get("email") or "",
            senha=data.get("senha"),
            pk_id_tbl_cliente=cliente_id,
            telefone=data.get("telefone"),
            id_centralx=data.get("id_centralx"),
            status=True,
            telefone_secundario=data.get("telefone_secundario"),
        )
        row = _db().obter_contato_por_id(new_id)
        return self._map_contato(row) if row else None

    def update_contato(self, contato_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        row = _db().obter_contato_por_id(contato_id)
        if not row:
            return None, None
        _db().atualizar_contato(
            contato_id=contato_id,
            nome_completo=data.get("nome") or row.get("nome_completo"),
            email=data.get("email") or row.get("email"),
            telefone=data.get("telefone") if "telefone" in data else row.get("telefone"),
            pk_id_tbl_cliente=row.get("pk_id_tbl_cliente"),
            telefone_secundario=data.get("telefone_secundario") if "telefone_secundario" in data else row.get("telefone_secundario"),
        )
        updated = _db().obter_contato_por_id(contato_id)
        return self._map_contato(updated), str(updated.get("pk_id_tbl_cliente")) if updated else None

    def _map_contato(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        nome = row.get("nome_completo") or ""
        parts = nome.split()
        avatar = (parts[0][:1] + (parts[1][:1] if len(parts) > 1 else "")).upper() if parts else "?"
        return {
            "id": str(row.get("id_contato_cliente") or row.get("id")),
            "nome": nome,
            "email": row.get("email") or "",
            "telefone": row.get("telefone") or "",
            "telefone_secundario": row.get("telefone_secundario") or "",
            "cargo": row.get("cargo") or "",
            "setor": row.get("setor") or "",
            "status": "Ativo" if row.get("status") else "Inativo",
            "principal": bool(row.get("principal")),
            "avatar": avatar,
        }

    # ---------------- Atividades / Objetivos / Notas / Cotações --------------
    # Fase 3.2b: leitura + writes reais em `sales_atividades`,
    # `sales_objetivos_cliente`, `sales_historico_cliente` e `cadu_cotacoes`.
    # Toda validação de campos obrigatórios acontece aqui (o mesmo contrato do
    # CrmTestStore) para preservar as respostas 400 esperadas pelo frontend.

    # -- utilitários privados -------------------------------------------------

    def _current_executivo_id(self) -> Optional[int]:
        """Retorna o `user_id` da sessão Flask (o executivo autor).

        Falha silenciosa fora de contexto de request (scripts/tests).
        """
        try:
            from flask import session  # import local para evitar side-effects
            uid = session.get("user_id")
            return int(uid) if uid else None
        except Exception:
            return None

    def _iso_date(self, value: Any) -> str:
        """Converte date/datetime/string para 'YYYY-MM-DD'. Falha silenciosa → ''."""
        if not value:
            return ""
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()[:10]
            except Exception:
                return str(value)[:10]
        s = str(value).strip()
        # Aceita 'YYYY-MM-DD' e 'DD/MM/YYYY'
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            return s[:10]
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return s

    def _validate_iso_date(self, value: Any, field: str = "data") -> Optional[str]:
        """Valida e normaliza data ISO. Retorna None quando vazio; ValueError se inválido."""
        if value in (None, ""):
            return None
        iso = self._iso_date(value)
        try:
            _datetime.strptime(iso, "%Y-%m-%d")
        except Exception:
            raise ValueError(f"{field} inválida (use YYYY-MM-DD)")
        return iso

    @staticmethod
    def _initials(name: str) -> str:
        parts = [p for p in str(name or "").split() if p]
        if not parts:
            return "?"
        return (parts[0][:1] + (parts[1][:1] if len(parts) > 1 else "")).upper()

    @staticmethod
    def _brl(v: float) -> str:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _metrics_for(self, cliente_id: str) -> Dict[str, Any]:
        """Métricas resumidas do cliente para o header do CRM v3.

        Não é a fonte da verdade final — o frontend recomputa a partir das
        listas carregadas (contatos, atividades, cotações) via
        `computeMetricas`. Este método é o fallback para renderização
        inicial e para casos em que a UI ainda não puxou relacionamentos.

        Cada fonte é isolada em try/except: se contatos falhar, ainda
        entregamos cotações; se cotações falhar, ainda entregamos
        atividades. Antes uma exceção em qualquer uma delas quebrava
        toda a listagem de clientes.
        """
        try:
            contatos = self.list_contatos(cliente_id) or []
        except Exception as e:
            _rollback_if_failed("list_contatos")
            import logging
            logging.getLogger("aicentral.crm_v3").warning(
                "list_contatos %s falhou: %s: %s", cliente_id, type(e).__name__, e
            )
            contatos = []
        try:
            cotacoes = _db().obter_cotacoes_cliente(cliente_id) or []
        except Exception as e:
            _rollback_if_failed("obter_cotacoes_cliente")
            import logging
            logging.getLogger("aicentral.crm_v3").warning(
                "obter_cotacoes_cliente %s falhou: %s: %s", cliente_id, type(e).__name__, e
            )
            cotacoes = []

        # Set/2026 — bug corrigido: `cadu_cotacoes.status` é FK numérica
        # para `cadu_cotacoes_status.id`. Antes comparávamos essa FK
        # (ex.: "3") diretamente contra strings tipo "aprovada", o que
        # NUNCA batia — todas as métricas caíam para 0/R$ 0,00 mesmo
        # quando o cliente tinha cotações reais.
        # Solução: derivar o slug canônico a partir de `status_descricao`
        # (valor textual vindo do LEFT JOIN, ex.: "Aprovada",
        # "Rascunho") e comparar via `COTACAO_STATUS_ALIASES`.
        from .crm_v3_data import COTACAO_STATUS_ALIASES

        def _slug(cot: Dict[str, Any]) -> str:
            raw = str(cot.get("status_descricao") or "").strip().casefold()
            if not raw:
                return ""
            return COTACAO_STATUS_ALIASES.get(raw) or raw.replace(" ", "-")

        STATUS_ABERTAS = {"rascunho", "enviada", "em-acompanhamento"}
        abertas = [c for c in cotacoes if _slug(c) in STATUS_ABERTAS]
        aprovadas = [c for c in cotacoes if _slug(c) == "aprovada"]

        def _sum(items):
            total = 0.0
            for c in items:
                try:
                    total += float(c.get("valor_total_proposta") or 0)
                except (TypeError, ValueError):
                    continue
            return total

        faturamento = _sum(aprovadas)
        pipeline = _sum(abertas)

        # Tarefas abertas + último contato baseado em atividades reais.
        tarefas_abertas = 0
        ultimo_contato = "—"
        # Próxima atividade pendente — alimenta o badge estilo Pipedrive
        # (bolinha amarela ! para atrasadas, verde ✓ para hoje/futuras)
        # que aparece no canto direito de cada card na coluna 1 do CRM v3.
        # Ver `situacaoHtml` no crm_v3.js — o frontend interpreta pelo
        # texto do badge; badge_type é redundante mas útil para debug.
        proxima_atividade = None
        try:
            atividades = _db().obter_atividades_cliente(cliente_id) or []
            tarefas_abertas = sum(
                1 for a in atividades
                if str(a.get("status") or "").casefold() != "concluida"
            )
            # Última atividade concluída (data_atividade).
            concluidas = sorted(
                [
                    a for a in atividades
                    if str(a.get("status") or "").casefold() == "concluida"
                    and a.get("data_atividade")
                ],
                key=lambda a: a.get("data_atividade"),
                reverse=True,
            )
            if concluidas:
                dt = concluidas[0].get("data_atividade")
                iso = self._iso_date(dt)
                if iso:
                    try:
                        d = _datetime.strptime(iso, "%Y-%m-%d").date()
                        diff = (_date.today() - d).days
                        ultimo_contato = (
                            "Hoje" if diff == 0 else
                            "Ontem" if diff == 1 else
                            f"{diff}d atrás"
                        )
                    except Exception:
                        ultimo_contato = iso

            # Próxima atividade pendente: percorre pendentes/em_andamento,
            # separa em atrasadas / hoje / futuras, e escolhe a mais
            # crítica na ordem (atrasada > hoje > futura mais próxima).
            hoje = _date.today()
            atrasadas: List[Dict[str, Any]] = []
            hoje_list: List[Dict[str, Any]] = []
            futuras: List[Dict[str, Any]] = []
            for a in atividades:
                if str(a.get("status") or "").casefold() == "concluida":
                    continue
                # data_prazo é a coluna nova (set/2026). Prioriza ela;
                # fallback para data_atividade em bases antigas.
                dt_alvo = a.get("data_prazo") or a.get("data_atividade")
                iso = self._iso_date(dt_alvo)
                if not iso:
                    continue
                try:
                    d = _datetime.strptime(iso, "%Y-%m-%d").date()
                except Exception:
                    continue
                diff = (d - hoje).days
                reg = {
                    "id": a.get("id"),
                    "data": iso,
                    "titulo": (a.get("titulo") or a.get("descricao") or "").strip()[:120],
                    "dias": diff,
                }
                if diff < 0:
                    atrasadas.append(reg)
                elif diff == 0:
                    hoje_list.append(reg)
                else:
                    futuras.append(reg)
            if atrasadas:
                # Mais atrasada = menor `dias` (mais negativo). O usuário
                # precisa ver a atividade mais crítica primeiro.
                proxima_atividade = min(atrasadas, key=lambda r: r["dias"])
            elif hoje_list:
                proxima_atividade = hoje_list[0]
            elif futuras:
                # Mais próxima = menor `dias` positivo.
                proxima_atividade = min(futuras, key=lambda r: r["dias"])
        except Exception as e:
            _rollback_if_failed("obter_atividades_cliente")
            import logging
            logging.getLogger("aicentral.crm_v3").warning(
                "obter_atividades_cliente %s falhou: %s: %s",
                cliente_id, type(e).__name__, e
            )

        return {
            "contatos": len(contatos),
            "oportunidades": len(abertas),
            "faturamento": self._brl(faturamento),
            "valor_pis": self._brl(pipeline),
            "tarefas_abertas": tarefas_abertas,
            "cotacoes_abertas": len(abertas),
            "ultimo_contato": ultimo_contato,
            # Próxima atividade pendente (ou None).
            # {id, data (ISO), titulo, dias (negativo=atrasada)}
            "proxima_atividade": proxima_atividade,
        }

    # ---------------- Atividades (sales_atividades) --------------------------

    def _map_atividade(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um registro de `sales_atividades` para o shape do v3 UI.

        - `data_atividade` → `data` (ISO YYYY-MM-DD).
        - `descricao` mantém o texto; `titulo` cai de volta para `descricao`
          quando ausente (colunas novas podem estar vazias em bases antigas).
        - `responsavel_nome` vira `responsavel` (apenas exibição). O
          `executivo_id` continua disponível para lógica futura.
        """
        if not row:
            return {}
        data_iso = self._iso_date(row.get("data_atividade"))
        titulo = titulo_atividade_lista(row.get("titulo"), row.get("descricao"))
        descricao = texto_sem_markdown(row.get("descricao") or "")
        # hora_atividade é opcional (coluna nova em set/2026). Retorna
        # string vazia quando a base não tem a coluna ou o registro
        # ficou sem hora — a UI só exibe hora quando não-vazia.
        hora_raw = row.get("hora_atividade")
        hora_str = ""
        if hora_raw is not None:
            try:
                # `psycopg` devolve `datetime.time`; `strftime` mantém
                # somente HH:MM (o input `type=time` do drawer é HH:MM).
                hora_str = hora_raw.strftime("%H:%M") if hasattr(hora_raw, "strftime") else str(hora_raw)[:5]
            except Exception:
                hora_str = str(hora_raw)[:5]
        return {
            "id": str(row.get("id")),
            "titulo": titulo,
            "descricao": descricao,
            "data": data_iso,
            "data_label": "",  # UI computa o rótulo (Hoje/Amanhã/etc.)
            "hora": hora_str,
            "prioridade": "Média",  # tabela não persiste prioridade
            "status": row.get("status") or "pendente",
            "tipo": row.get("tipo") or "atividade",
            "responsavel": row.get("responsavel_nome") or "",
            "responsavel_iniciais": self._initials(row.get("responsavel_nome") or ""),
            "responsavel_foto_url": (row.get("responsavel_foto_url") or "").strip(),
            "executivo_id": (
                str(row.get("executivo_id")) if row.get("executivo_id") is not None else ""
            ),
            "contato_id": (
                str(row.get("contato_id")) if row.get("contato_id") is not None else ""
            ),
            "contato_nome": row.get("contato_nome") or "",
            "data_prazo": self._iso_date(row.get("data_prazo")) or "",
            "created_at": self._iso_date(row.get("created_at")) or "",
        }

    def list_atividades(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        try:
            rows = _db().obter_atividades_cliente(cliente_id) or []
        except Exception:
            return []
        return [self._map_atividade(r) for r in rows]

    def create_atividade(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        titulo = texto_sem_markdown(data.get("titulo") or "").strip()
        descricao = texto_sem_markdown(data.get("descricao") or "").strip() or titulo
        if not descricao:
            raise ValueError("Título é obrigatório")
        data_iso = self._validate_iso_date(data.get("data"), "data")
        if not data_iso:
            # Fallback: hoje se o UI não enviar (composer inline pode omitir)
            data_iso = _date.today().isoformat()
        tipo = (data.get("tipo") or "atividade").strip() or "atividade"
        contato_raw = data.get("contato_id")
        contato_id = None
        if contato_raw not in (None, "", 0, "0"):
            try:
                contato_id = int(contato_raw)
            except (TypeError, ValueError):
                contato_id = None
        # Hora é opcional. Aceita "HH:MM" ou "HH:MM:SS". Vazio → None.
        hora_raw = (data.get("hora") or "").strip()
        hora_val = hora_raw or None
        row = _db().criar_atividade_cliente(
            cliente_id=cliente_id,
            executivo_id=self._current_executivo_id(),
            descricao=descricao,
            data_atividade=data_iso,
            contato_id=contato_id,
            tipo=tipo,
            titulo=titulo or None,
            data_prazo=self._validate_iso_date(data.get("data_prazo"), "data_prazo"),
            hora_atividade=hora_val,
        )
        if not row:
            return None
        detail = _db().obter_atividade_cliente_por_id(row["id"])
        return self._map_atividade(detail) if detail else None

    def update_atividade(self, atividade_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        # Mapeamento shape v3 → colunas do banco:
        payload: Dict[str, Any] = {}
        if "titulo" in data:
            titulo = texto_sem_markdown(data.get("titulo") or "").strip()
            payload["titulo"] = titulo or None
            # Quando o UI edita só o título, mantemos `descricao` sincronizada
            # (base legada usa descricao como texto principal).
            if titulo and "descricao" not in data:
                payload["descricao"] = titulo
        if "descricao" in data:
            payload["descricao"] = texto_sem_markdown(data.get("descricao") or "").strip()
        if "data" in data:
            payload["data_atividade"] = self._validate_iso_date(data.get("data"), "data")
        if "data_prazo" in data:
            payload["data_prazo"] = self._validate_iso_date(data.get("data_prazo"), "data_prazo")
        if "tipo" in data:
            payload["tipo"] = (data.get("tipo") or "atividade").strip() or "atividade"
        if "status" in data:
            status = (data.get("status") or "").strip()
            if status not in ("pendente", "em_andamento", "concluida"):
                raise ValueError("status inválido")
            payload["status"] = status
        if "contato_id" in data:
            payload["contato_id"] = data.get("contato_id")
        if "hora" in data:
            # Vazio → None (limpa a hora). Backend só persiste se a coluna
            # hora_atividade existir; caso contrário ignora silenciosamente.
            hora_raw = (data.get("hora") or "").strip()
            payload["hora_atividade"] = hora_raw or None
        if not payload:
            return None, None
        try:
            row = _db().atualizar_atividade_cliente(atividade_id, payload)
        except ValueError as e:
            raise
        if not row:
            return None, None
        detail = _db().obter_atividade_cliente_por_id(atividade_id)
        if not detail:
            return None, None
        return self._map_atividade(detail), str(detail.get("cliente_id"))

    def delete_atividade(self, atividade_id: str) -> Tuple[bool, Optional[str]]:
        # Precisamos do cliente_id antes do DELETE para o response payload.
        detail = _db().obter_atividade_cliente_por_id(atividade_id)
        if not detail:
            return False, None
        cliente_id = str(detail.get("cliente_id")) if detail.get("cliente_id") else None
        row = _db().excluir_atividade_cliente(atividade_id)
        return (row is not None), cliente_id

    # ---------------- Objetivos (sales_objetivos_cliente) --------------------

    def _map_objetivo(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """DB → shape v3. Mapeia `conquistado` → `concluido`, `data_prazo` → `prazo`."""
        if not row:
            return {}
        return {
            "id": str(row.get("id")),
            "texto": row.get("texto") or "",
            "prazo": self._iso_date(row.get("data_prazo")) or "",
            "concluido": bool(row.get("conquistado")),
            "data_conquista": self._iso_date(row.get("data_conquista")) or "",
            "created_at": self._iso_date(row.get("created_at")) or "",
        }

    def list_objetivos(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        try:
            rows = _db().obter_objetivos_cliente(cliente_id) or []
        except Exception:
            return []
        return [self._map_objetivo(r) for r in rows]

    def create_objetivo(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        texto = (data.get("texto") or "").strip()
        if not texto:
            raise ValueError("Texto é obrigatório")
        prazo = self._validate_iso_date(data.get("prazo") or data.get("data_prazo"), "prazo")
        row = _db().criar_objetivo_cliente(
            cliente_id=cliente_id,
            executivo_id=self._current_executivo_id(),
            texto=texto,
            data_prazo=prazo,
        )
        if not row:
            return None
        detail = _db().obter_objetivo_cliente_por_id(row["id"])
        return self._map_objetivo(detail) if detail else None

    def update_objetivo(self, objetivo_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        # Atualiza texto/prazo via um caminho, `concluido` via outro (a
        # coluna `conquistado` tem seu próprio update com data_conquista).
        detail_before = _db().obter_objetivo_cliente_por_id(objetivo_id)
        if not detail_before:
            return None, None

        # 1) update de texto/prazo
        payload: Dict[str, Any] = {}
        if "texto" in data:
            texto = (data.get("texto") or "").strip()
            if not texto:
                raise ValueError("Texto é obrigatório")
            payload["texto"] = texto
        if "prazo" in data or "data_prazo" in data:
            payload["data_prazo"] = self._validate_iso_date(
                data.get("prazo") or data.get("data_prazo"), "prazo"
            )
        if payload:
            _db().atualizar_objetivo_cliente(objetivo_id, payload)

        # 2) update de concluido (mapeia para conquistado)
        if "concluido" in data:
            concluido = data.get("concluido")
            if not isinstance(concluido, bool):
                raise ValueError("concluido deve ser booleano")
            _db().conquistar_objetivo_cliente(objetivo_id, concluido)

        detail = _db().obter_objetivo_cliente_por_id(objetivo_id)
        if not detail:
            return None, None
        return self._map_objetivo(detail), str(detail.get("cliente_id"))

    def delete_objetivo(self, objetivo_id: str) -> Tuple[bool, Optional[str]]:
        detail = _db().obter_objetivo_cliente_por_id(objetivo_id)
        if not detail:
            return False, None
        cliente_id = str(detail.get("cliente_id")) if detail.get("cliente_id") else None
        row = _db().excluir_objetivo_cliente(objetivo_id)
        return (row is not None), cliente_id

    def list_cotacoes(self, cliente_id: str, include_vinculados: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Cotações reais do cliente (tabela `cadu_cotacoes`).

        Consome `db.obter_cotacoes_cliente_com_vinculos` para incluir também
        cotações de clientes vinculados (agência ↔ clientes finais).
        Mapeia os campos para o formato usado pelo v3 UI, normalizando o
        status (aliases em `crm_v3_data`).

        Se `include_vinculados=False`, usa a função original sem vínculos.

        Set/2026: antes engolíamos qualquer exceção com `return []`, o que
        fazia o UI mostrar "Nenhuma cotação registrada" indistinguível de
        "não conseguimos falar com o banco". Agora logamos WARNING com o
        tipo de exceção e mensagem antes de degradar — se o usuário vê
        vazio no CRM mas sabe que existe cotação, o log em journalctl
        mostra o motivo real. Adicionamos também `_rollback_if_failed`
        para evitar cascata de InFailedSqlTransaction.
        """
        import logging
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        try:
            if include_vinculados:
                rows = _db().obter_cotacoes_cliente_com_vinculos(cliente_id) or []
            else:
                rows = _db().obter_cotacoes_cliente(cliente_id) or []
        except Exception as e:  # noqa: BLE001
            _rollback_if_failed("list_cotacoes")
            logging.getLogger("aicentral.crm_v3").warning(
                "list_cotacoes cliente=%s include_vinculados=%s falhou: %s: %s",
                cliente_id, include_vinculados, type(e).__name__, e,
            )
            return []
        logging.getLogger("aicentral.crm_v3").info(
            "list_cotacoes cliente=%s → %d cotações (com_vinculos=%s)",
            cliente_id, len(rows), include_vinculados,
        )
        return [self._map_cotacao(r) for r in rows]

    def _prepare_cotacao_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza o JSON do frontend v3 para os kwargs de `db.criar/atualizar_cotacao`.

        Regras:
        - `titulo` funciona como fallback de `nome_campanha`.
        - `valor_total` / `valor` (string BRL) → `valor_total_proposta` (float).
        - `status` (slug do v3) → label do banco via `COTACAO_STATUS`.
        - `plataformas` (lista) → string CSV em `plataforma_campanha`.
        - Datas: aceita YYYY-MM-DD ou DD/MM/YYYY.
        """
        from .crm_v3_data import COTACAO_STATUS, COTACAO_STATUS_ALIASES

        payload: Dict[str, Any] = {}
        titulo = (data.get("titulo") or "").strip()
        nome_campanha = (data.get("nome_campanha") or titulo).strip()
        if nome_campanha:
            payload["nome_campanha"] = nome_campanha
        if "objetivo" in data:
            payload["objetivo_campanha"] = (data.get("objetivo") or "").strip()
        if "periodo_inicio" in data:
            payload["periodo_inicio"] = self._validate_iso_date(
                data.get("periodo_inicio"), "periodo_inicio"
            )
        if "periodo_fim" in data:
            payload["periodo_fim"] = self._validate_iso_date(
                data.get("periodo_fim"), "periodo_fim"
            )
        # Validação cruzada de período
        if (
            payload.get("periodo_inicio")
            and payload.get("periodo_fim")
            and payload["periodo_fim"] < payload["periodo_inicio"]
        ):
            raise ValueError("Período final não pode ser anterior ao período inicial")
        if "status" in data or "status_canonico" in data:
            raw = str(data.get("status_canonico") or data.get("status") or "").strip()
            slug = COTACAO_STATUS_ALIASES.get(raw.casefold())
            if slug is None and raw:
                raise ValueError("Status de cotação inválido")
            if slug:
                payload["status"] = COTACAO_STATUS[slug]  # armazena label canônico
        if "numero_cotacao" in data and str(data.get("numero_cotacao") or "").strip():
            payload["numero_cotacao"] = str(data["numero_cotacao"]).strip()
        # Valor: aceita `valor_total` (número) ou `valor` (BRL string "R$ 1.234,56").
        if "valor_total" in data and data["valor_total"] not in (None, ""):
            try:
                payload["valor_total_proposta"] = float(data["valor_total"])
            except (TypeError, ValueError):
                raise ValueError("valor_total inválido")
        elif "valor" in data and data["valor"]:
            raw_val = str(data["valor"]).strip()
            # "R$ 1.234,56" → 1234.56
            cleaned = re.sub(r"[^\d,\.\-]", "", raw_val).replace(".", "").replace(",", ".")
            try:
                payload["valor_total_proposta"] = float(cleaned) if cleaned else 0.0
            except ValueError:
                raise ValueError("valor inválido")
        if "plataformas" in data:
            plats = data.get("plataformas") or []
            if isinstance(plats, str):
                plats = [p.strip() for p in plats.split(",") if p.strip()]
            elif isinstance(plats, (list, tuple)):
                plats = [str(p).strip() for p in plats if str(p).strip()]
            else:
                plats = []
            payload["plataforma_campanha"] = ", ".join(plats)
        return payload

    def create_cotacao(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        payload = self._prepare_cotacao_payload(data)
        nome = payload.pop("nome_campanha", None)
        periodo_inicio = payload.pop("periodo_inicio", None)
        if not nome:
            raise ValueError("Título é obrigatório")
        if not periodo_inicio:
            # UI do CRM v3 pode não pedir período; assumimos hoje como default
            # para satisfazer o NOT NULL de `cadu_cotacoes.periodo_inicio`.
            periodo_inicio = _date.today().isoformat()
        # Se status não veio, usa Rascunho (mesmo default do CRM legado).
        payload.setdefault("status", "Rascunho")
        # Assina o executivo responsável (mesma regra do form legado)
        responsavel = self._current_executivo_id()
        if responsavel:
            payload.setdefault("responsavel_comercial", responsavel)
        try:
            new_id, _numero = _db().criar_cotacao(
                client_id=cliente_id,
                nome_campanha=nome,
                periodo_inicio=periodo_inicio,
                **payload,
            )
        except TypeError:
            # Assinatura antiga (retorno único) — segurança extra.
            new_id = _db().criar_cotacao(
                client_id=cliente_id,
                nome_campanha=nome,
                periodo_inicio=periodo_inicio,
                **payload,
            )
        if not new_id:
            return None
        # Rebusca via `obter_cotacoes_cliente` para manter o mesmo shape
        # do `list_cotacoes` (evita divergência entre create e list).
        rows = _db().obter_cotacoes_cliente(cliente_id) or []
        row = next((r for r in rows if str(r.get("id")) == str(new_id)), None)
        return self._map_cotacao(row) if row else {"id": str(new_id)}

    def update_cotacao(self, cotacao_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        # `db.atualizar_cotacao` aceita kwargs; primeiro precisamos localizar
        # o cliente da cotação para devolver no payload de resposta.
        payload = self._prepare_cotacao_payload(data)
        if not payload:
            return None, None
        try:
            ok = _db().atualizar_cotacao(cotacao_id, **payload)
        except Exception:
            return None, None
        if not ok:
            return None, None
        # Busca a linha atualizada — precisa do client_id para popular a resposta.
        conn = _db().get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT client_id FROM cadu_cotacoes WHERE id = %s",
                (cotacao_id,),
            )
            row = cur.fetchone()
        if not row:
            return None, None
        cliente_id = str(row.get("client_id"))
        rows = _db().obter_cotacoes_cliente(cliente_id) or []
        detail = next((r for r in rows if str(r.get("id")) == str(cotacao_id)), None)
        return (self._map_cotacao(detail) if detail else {"id": str(cotacao_id)}), cliente_id

    def delete_cotacao(self, cotacao_id: str) -> Tuple[bool, Optional[str]]:
        # Descobre o cliente antes do soft-delete.
        conn = _db().get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT client_id FROM cadu_cotacoes WHERE id = %s",
                (cotacao_id,),
            )
            row = cur.fetchone()
        if not row:
            return False, None
        cliente_id = str(row.get("client_id")) if row.get("client_id") else None
        try:
            ok = _db().deletar_cotacao(cotacao_id, soft_delete=True)
        except Exception:
            return False, None
        return bool(ok), cliente_id

    def _map_cotacao(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um registro de `cadu_cotacoes` para o shape do v3 UI."""
        from .crm_v3_data import COTACAO_STATUS, COTACAO_STATUS_ALIASES

        # Set/2026 — bug corrigido: `cadu_cotacoes.status` é FK numérica
        # para `cadu_cotacoes_status.id`, então `row["status"]` costuma
        # ser "3" e não "Aprovada". O valor textual está em
        # `status_descricao` (LEFT JOIN em `obter_cotacoes_cliente*`).
        # Priorizamos ele para achar o slug canônico; caímos em
        # `status` só quando a query não fez o JOIN (retro-compat com
        # mocks e testes que passam string direto).
        raw_status = str(row.get("status_descricao") or row.get("status") or "").strip()
        slug = (
            COTACAO_STATUS_ALIASES.get(raw_status.casefold())
            or raw_status.casefold().replace(" ", "-")
        )
        status_label = (
            row.get("status_descricao")
            or COTACAO_STATUS.get(slug)
            or (raw_status or "—")
        )
        valor_total = row.get("valor_total_proposta") or 0
        try:
            valor_num = float(valor_total)
        except (TypeError, ValueError):
            valor_num = 0.0

        # Plataformas: db armazena string única em `plataforma_campanha`.
        plat_raw = row.get("plataforma_campanha") or ""
        plataformas = [p.strip() for p in str(plat_raw).split(",") if p.strip()]

        created = row.get("created_at")
        data_display = created.strftime("%d/%m/%Y") if hasattr(created, "strftime") else ""

        return {
            "id": str(row.get("id")),
            "numero_cotacao": row.get("numero_cotacao") or "",
            "nome_campanha": row.get("nome_campanha") or "",
            "titulo": row.get("nome_campanha") or "Cotação sem título",
            "valor_total": valor_num,
            "valor": f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "status": slug,
            "status_canonico": status_label,
            "status_label": status_label,
            "periodo_inicio": row.get("periodo_inicio").isoformat() if hasattr(row.get("periodo_inicio"), "isoformat") else (row.get("periodo_inicio") or ""),
            "periodo_fim": row.get("periodo_fim").isoformat() if hasattr(row.get("periodo_fim"), "isoformat") else (row.get("periodo_fim") or ""),
            "data": data_display,
            "objetivo": row.get("objetivo_campanha") or "",
            "plataformas": plataformas,
            "vendedor_nome": row.get("vendedor_nome") or "",
            "contato_nome": row.get("contato_nome") or "",
            "origem": row.get("origem") or "proprio",
            "cliente_nome": row.get("cliente_nome") or "",
        }

    # ---------------- Notas / histórico (sales_historico_cliente) ------------

    def _map_nota(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """DB (sales_historico_cliente) → shape v3 UI.

        Frontend consome: id, texto, autor, data.
        """
        if not row:
            return {}
        return {
            "id": str(row.get("id")),
            "texto": row.get("texto") or "",
            "autor": row.get("autor") or "",
            "data": (
                self._iso_date(row.get("data_registro"))
                or self._iso_date(row.get("created_at"))
                or ""
            ),
        }

    def list_notas(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        try:
            # Paginação server-side rasa: pegamos as 100 mais recentes.
            # O CRM legado (`/crm/api/cliente/<id>/historico`) usa 10/página,
            # mas o v3 renderiza tudo na sidebar; um cap alto evita 2ª chamada.
            data = _db().listar_historico_cliente(cliente_id, page=1, per_page=100)
        except Exception:
            return []
        return [self._map_nota(r) for r in (data.get("registros") if data else []) or []]

    def create_nota(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        texto = (data.get("texto") or "").strip()
        if not texto:
            raise ValueError("Texto é obrigatório")
        row = _db().criar_historico_cliente(
            cliente_id=cliente_id,
            executivo_id=self._current_executivo_id(),
            texto=texto,
        )
        if not row:
            return None
        # Rebuscar em SELECT para pegar o autor via JOIN.
        conn = _db().get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.id, h.texto, h.data_registro, h.created_at,
                       c.nome_completo AS autor
                FROM sales_historico_cliente h
                LEFT JOIN tbl_contato_cliente c ON c.id_contato_cliente = h.executivo_id
                WHERE h.id = %s
                """,
                (row["id"],),
            )
            detail = cur.fetchone()
        return self._map_nota(detail) if detail else self._map_nota(
            {"id": row["id"], "texto": texto, "data_registro": row.get("data_registro")}
        )

    def update_nota(self, nota_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        # `sales_historico_cliente` é append-only no CRM legado (não há PATCH).
        # Preservamos esse contrato para não vazar edições reversíveis por
        # histórico. Retornamos 404-like via (None, None).
        return None, None

    def delete_nota(self, nota_id: str) -> Tuple[bool, Optional[str]]:
        # Idem update_nota: histórico não é apagável pelo CRM v3.
        return False, None

    def import_contatos(self, cliente_id: str, rows: Iterable[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        created: List[Dict[str, Any]] = []
        for r in rows or []:
            try:
                c = self.create_contato(cliente_id, r)
                if c:
                    created.append(c)
            except Exception:
                continue
        return created


# Instância única — segue o padrão do CrmTestStore.
repository = CrmV3Repository()


def _memory_store():
    from .crm_v3_data import store as _memory_store_obj
    return _memory_store_obj


class StoreUnavailable(RuntimeError):
    """Sinaliza que o banco real do CRM v3 está indisponível.

    A partir de set/2026 o CRM v3 **não faz mais fallback silencioso**
    para o store em memória em produção. Se o Postgres estiver fora do
    ar ou o schema estiver divergente, a UI mostra um erro claro e não
    inventa dados fictícios. O CRM antigo já usa as mesmas funções em
    `db.py` (`obter_clientes_paginado`, `obter_cliente_por_id`, etc.),
    então quando o v3 falha o legado tende a falhar do mesmo jeito —
    a solução é resolver o banco, não mascarar com mock.
    """


def get_store():
    """Fábrica escolhe repositório real (default) ou store em memória.

    Regras (set/2026):
    - Default (sem env var) e qualquer valor não reconhecido → repositório
      real. Se o smoke test do banco falhar, **lança `StoreUnavailable`**
      em vez de retornar o mock. O caller (rotas) traduz para 503.
    - `USE_CRM_V3_STORE=mock|memory|in-memory|fake|fixture` → mock em
      memória (apenas dev). Nunca use em produção.

    Cada chamada atualiza `_LAST_DIAGNOSTIC` para debug via
    /crm-v3/api/_debug/store e para o banner de erro do template.
    """
    flag = _flag_raw()
    diag: Dict[str, Any] = {
        "flag_env": flag,
        "flag_recognized": (
            "mock" if flag in _MOCK_TOKENS
            else "real" if flag in _REAL_TOKENS
            else ("unknown-defaulted-to-real" if flag else "empty-defaulted-to-real")
        ),
        "at": _datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "db_error": None,
    }

    if not use_repository():
        diag.update({
            "mode": "mock",
            "reason": f"flag USE_CRM_V3_STORE='{flag}' explicitamente pede mock (dev only)",
        })
        _LAST_DIAGNOSTIC.update(diag)
        return _memory_store()

    # Smoke test: se o banco não responder, propagamos o erro. A rota
    # captura e devolve 503 com mensagem clara. Nunca mascaramos com mock.
    try:
        _db().obter_clientes_paginado(page=1, per_page=1)
        diag.update({"mode": "real", "reason": "smoke test OK"})
        _LAST_DIAGNOSTIC.update(diag)
        return repository
    except Exception as e:
        import sys, traceback
        err_short = f"{type(e).__name__}: {str(e).splitlines()[0][:240]}"
        diag.update({
            "mode": "unavailable",
            "reason": "banco indisponível ou schema divergente — o CRM v3 usa exatamente as mesmas funções do CRM legado, então verifique o Postgres/schema",
            "db_error": err_short,
        })
        _LAST_DIAGNOSTIC.update(diag)
        print(f"[crm_v3] Banco real indisponível: {err_short}", file=sys.stderr)
        print("[crm_v3] traceback do smoke test:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise StoreUnavailable(err_short) from e
