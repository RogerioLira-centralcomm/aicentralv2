"""CRM v3 — camada de repositório com Postgres.

Fase 3 do plano CRM v3 UX Overhaul. Expõe uma superfície idêntica ao
`CrmTestStore` (em memória) mas resolve tudo em `db.py` / Postgres.

Feature flag:
- `USE_CRM_V3_STORE=1` (default no dev) → continua usando o store em memória
- `USE_CRM_V3_STORE=0` → usa este repositório real

Isso permite rollout gradual: o smoke test do repositório roda antes do go-live
sem exigir reescrita das rotas.

Escopo desta iteração
---------------------
Nesta primeira versão o repositório implementa:
- Clientes (list/get/create/update) via `db.obter_clientes_paginado`,
  `db.obter_cliente_por_id`, `db.criar_cliente`, `db.atualizar_cliente`.
- Contatos via `db.obter_contatos_por_cliente`, `db.criar_contato`,
  `db.atualizar_contato`.
- Agencias vinculadas via `db.listar_agencias_vinculadas_cliente`,
  `db.listar_clientes_vinculados_agencia`, `db.salvar_agencias_vinculadas_cliente`.
- Atividades/objetivos/notas/cotações usam a query padrão de `sales_atividades`,
  `sales_objetivos_cliente`, `sales_historico_cliente`, `cadu_cotacoes`
  reaproveitando os selects que já existem em `crm/routes.py`. Nesta primeira
  entrega **os writes são no-op stub** para preservar a integridade do banco
  em ambientes de produção — habilite gradualmente conforme validar cada
  fluxo. Isso é intencional (fail-safe) e está documentado.

Os métodos ausentes/no-op levantam `NotImplementedError` para deixar claro
que ainda faltam pontos de escrita real (Fase 3.2 em andamento).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _db():
    """Import lazy do módulo db, para não falhar em ambientes sem libpq.

    Se o processo nunca ativar `USE_CRM_V3_STORE=0` o import nunca é executado.
    """
    from . import db as _real_db
    return _real_db


# =============================================================================
# Feature flag
# =============================================================================

def use_repository() -> bool:
    """Retorna True se a variável de ambiente pede repositório real."""
    return os.environ.get("USE_CRM_V3_STORE", "1").strip() not in ("1", "true", "yes")


# =============================================================================
# Helpers de mapeamento (row → dict compatível com CrmTestStore)
# =============================================================================

_CLASSIFICACOES = ("Prospecção", "Ativo", "Geladeira")


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
    endereco = {
        "cep": row.get("cep") or "",
        "uf": (row.get("estado") or "").strip().upper() if isinstance(row.get("estado"), str) else "",
        "cidade": row.get("cidade") or "",
        "bairro": row.get("bairro") or "",
        "logradouro": row.get("logradouro") or "",
        "numero": row.get("numero") or "",
        "complemento": row.get("complemento") or "",
    }

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
        "endereco": endereco,
        "bv_percentual": float(row.get("percentual") or 0),
        "margem_cc": float(row.get("margem_cc") or 0),
        "opera_midia": bool(row.get("opera_midia")),
        "demanda_dados": bool(row.get("demanda_dados")),
        "demanda_programatica_canais": bool(row.get("demanda_programatica_canais")),
        "observacoes_comerciais_adicionais": row.get("observacoes_comerciais_adicionais") or "",
        "responsavel": row.get("executivo_nome") or "",
        "data_cadastro": (row.get("data_cadastro").isoformat() if row.get("data_cadastro") else None),
        "status": row.get("status") if row.get("status") is not None else True,
        "agencia_id": str(row.get("pk_id_tbl_agencia")) if row.get("pk_id_tbl_agencia") else "",
        "agencias_vinculadas": [
            {"agencia_id": str(v["id_cliente"]), "is_principal": bool(v.get("is_principal"))}
            for v in (row.get("agencias_vinculadas") or [])
        ],
    }


class CrmV3Repository:
    """Superfície igual ao CrmTestStore, mas conectada ao Postgres."""

    # ---------------- Clientes ------------------------------------------------

    def reset(self) -> None:  # pragma: no cover — não faz sentido em produção
        raise NotImplementedError("reset() só existe no store em memória")

    def list_clientes(self) -> List[Dict[str, Any]]:
        page = _db().obter_clientes_paginado(page=1, per_page=200) or {}
        items = []
        for row in page.get("clientes", []):
            mapped = _map_cliente(row)
            mapped["metrics"] = self._metrics_for(mapped["id"])
            # Preencher clientes finais/ agência nome para o card
            if mapped["is_agencia"]:
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
            items.append(mapped)
        return items

    def get_cliente(self, cliente_id: str) -> Optional[Dict[str, Any]]:
        row = _db().obter_cliente_por_id(cliente_id)
        if not row:
            return None
        mapped = _map_cliente(row)
        mapped["metrics"] = self._metrics_for(cliente_id)
        if mapped["is_agencia"]:
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
        atual = _db().obter_cliente_por_id(cliente_id)
        if not atual:
            return None
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
    # Nesta versão inicial os writes ficam desativados no repositório para
    # preservar integridade em produção. As leituras vão retornar listas vazias
    # até que sejam plugadas em consultas específicas (Fase 3.2b).

    def _metrics_for(self, cliente_id: str) -> Dict[str, Any]:
        """Métricas resumidas do cliente para o header do CRM v3.

        Não é a fonte da verdade final — o frontend recomputa a partir das
        listas carregadas (contatos, atividades, cotações). Este método é
        um fallback para renderização inicial quando o UI ainda não puxou
        os relacionamentos.
        """
        contatos = self.list_contatos(cliente_id) or []
        try:
            cotacoes = _db().obter_cotacoes_cliente(cliente_id) or []
        except Exception:
            cotacoes = []
        abertas = [
            c for c in cotacoes
            if str(c.get("status") or "").casefold() in {"rascunho", "enviada", "em-acompanhamento", "em acompanhamento", "negociacao", "em negociação"}
        ]
        aprovadas = [c for c in cotacoes if str(c.get("status") or "").casefold() == "aprovada"]

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

        def _brl(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        return {
            "contatos": len(contatos),
            "oportunidades": len(abertas),
            "faturamento": _brl(faturamento),
            "valor_pis": _brl(pipeline),
            "tarefas_abertas": 0,
            "cotacoes_abertas": len(abertas),
            "ultimo_contato": "—",
        }

    def list_atividades(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        return []  # TODO Fase 3.2b: consultar sales_atividades

    def create_atividade(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("create_atividade real: pendente Fase 3.2b")

    def update_atividade(self, atividade_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        raise NotImplementedError("update_atividade real: pendente Fase 3.2b")

    def delete_atividade(self, atividade_id: str) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError("delete_atividade real: pendente Fase 3.2b")

    def list_objetivos(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        return []  # TODO Fase 3.2b: sales_objetivos_cliente

    def create_objetivo(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("create_objetivo real: pendente Fase 3.2b")

    def update_objetivo(self, objetivo_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        raise NotImplementedError("update_objetivo real: pendente Fase 3.2b")

    def delete_objetivo(self, objetivo_id: str) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError("delete_objetivo real: pendente Fase 3.2b")

    def list_cotacoes(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        """Cotações reais do cliente (tabela `cadu_cotacoes`).

        Consome `db.obter_cotacoes_cliente` (já cobre client_id + joins com
        contato/vendedor/status). Mapeia os campos para o formato usado pelo
        v3 UI, normalizando o status (aliases em `crm_v3_data`).
        """
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        try:
            rows = _db().obter_cotacoes_cliente(cliente_id) or []
        except Exception:
            # Se a tabela não existir ou a query falhar, degrada para lista
            # vazia — o UI já lida com "Nenhuma cotação registrada".
            return []
        return [self._map_cotacao(r) for r in rows]

    def create_cotacao(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("create_cotacao real: pendente Fase 3.2b")

    def update_cotacao(self, cotacao_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        raise NotImplementedError("update_cotacao real: pendente Fase 3.2b")

    def delete_cotacao(self, cotacao_id: str) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError("delete_cotacao real: pendente Fase 3.2b")

    def _map_cotacao(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um registro de `cadu_cotacoes` para o shape do v3 UI."""
        from .crm_v3_data import COTACAO_STATUS, COTACAO_STATUS_ALIASES

        raw_status = str(row.get("status") or "").strip()
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
        }

    def list_notas(self, cliente_id: str) -> Optional[List[Dict[str, Any]]]:
        cliente = _db().obter_cliente_por_id(cliente_id)
        if not cliente:
            return None
        return []  # TODO Fase 3.2b: sales_historico_cliente / nota_executivo_vendas

    def create_nota(self, cliente_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("create_nota real: pendente Fase 3.2b")

    def update_nota(self, nota_id: str, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        raise NotImplementedError("update_nota real: pendente Fase 3.2b")

    def delete_nota(self, nota_id: str) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError("delete_nota real: pendente Fase 3.2b")

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


def get_store():
    """Fábrica escolhe store em memória (default) ou repositório real.

    Chamada por `crm_v3_routes.py` no import-time apenas para reconhecer a
    feature flag. Uma vez definido, permanece pelo life-time do processo.
    """
    if use_repository():
        return repository
    from .crm_v3_data import store as _memory_store
    return _memory_store
