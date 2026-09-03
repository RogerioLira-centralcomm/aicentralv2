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


def _db():
    """Import lazy do módulo db, para não falhar em ambientes sem libpq.

    Se o processo nunca ativar `USE_CRM_V3_STORE=0` o import nunca é executado.
    """
    from . import db as _real_db
    return _real_db


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
        "cidade": row.get("cidade") or "",
        "bairro": row.get("bairro") or "",
        "logradouro": row.get("logradouro") or "",
        "numero": row.get("numero") or "",
        "complemento": row.get("complemento") or "",
    }

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
        "bv_percentual": float(row.get("percentual") or 0),
        "margem_cc": float(row.get("margem_cc") or 0),
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
        "agencia_id": str(row.get("pk_id_tbl_agencia")) if row.get("pk_id_tbl_agencia") else "",
        # Nome da agência quando esta ficha é de cliente-final vinculado a
        # uma agência (usado na sidebar Info do CRM v3).
        "agencia_nome": (
            row.get("agencia_nome") or row.get("agencia_razao") or ""
        ) if row.get("pk_id_tbl_agencia") and not is_agencia else "",
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
        # per_page alto: a UI já pagina em memória (8 por página) e faz o
        # filtro cliente-side por executivo/tipo/perfil/pill/busca. 1000 é
        # confortável para a base atual; se crescer, movemos a paginação
        # para server-side via query params.
        page = _db().obter_clientes_paginado(page=1, per_page=1000) or {}
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

        # Tarefas abertas + último contato baseado em atividades reais.
        tarefas_abertas = 0
        ultimo_contato = "—"
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
        except Exception:
            pass

        return {
            "contatos": len(contatos),
            "oportunidades": len(abertas),
            "faturamento": self._brl(faturamento),
            "valor_pis": self._brl(pipeline),
            "tarefas_abertas": tarefas_abertas,
            "cotacoes_abertas": len(abertas),
            "ultimo_contato": ultimo_contato,
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
        titulo = (row.get("titulo") or "").strip() or (row.get("descricao") or "").strip()
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
            "descricao": row.get("descricao") or "",
            "data": data_iso,
            "data_label": "",  # UI computa o rótulo (Hoje/Amanhã/etc.)
            "hora": hora_str,
            "prioridade": "Média",  # tabela não persiste prioridade
            "status": row.get("status") or "pendente",
            "tipo": row.get("tipo") or "atividade",
            "responsavel": row.get("responsavel_nome") or "",
            "responsavel_iniciais": self._initials(row.get("responsavel_nome") or ""),
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
        titulo = (data.get("titulo") or "").strip()
        descricao = (data.get("descricao") or "").strip() or titulo
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
            titulo = (data.get("titulo") or "").strip()
            payload["titulo"] = titulo or None
            # Quando o UI edita só o título, mantemos `descricao` sincronizada
            # (base legada usa descricao como texto principal).
            if titulo and "descricao" not in data:
                payload["descricao"] = titulo
        if "descricao" in data:
            payload["descricao"] = (data.get("descricao") or "").strip()
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
