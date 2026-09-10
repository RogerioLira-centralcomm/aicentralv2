"""Fechamento operacional do PI e handoff para o financeiro."""

import logging
import os

from flask import current_app, has_app_context, has_request_context, render_template, url_for

from .campanha_pi_metrics import parse_brl_float, parse_volume_float
from .pi_fechamento_repository import PiFechamentoRepository
from .pi_operacao_service import PiOperacaoService
from .services.brevo_service import get_brevo_service


logger = logging.getLogger(__name__)

STATUS_FINANCEIRO_LABELS = {
    "aguardando_comprovacao": "Aguardando comprovação",
    "aguardando_assinatura": "Aguardando assinatura",
    "pronto_nf": "Pronto para NF",
    "nf_emitida": "NF emitida",
    "aguardando_pagamento": "Aguardando pagamento",
    "encerrado": "Encerrado",
    "bloqueado": "Bloqueado",
}

ZONA_LABELS = {
    1: "Lucro elevado",
    2: "Lucrativa",
    3: "No orçado",
    4: "Atenção",
    5: "Ruptura",
}

SAUDE_LABELS = {
    "saudavel": "Saudável",
    "atencao": "Atenção",
    "risco": "Risco",
    "sem_dados": "Sem dados",
}


class HandoffBloqueadoError(ValueError):
    def __init__(self, pendencias):
        self.pendencias = list(pendencias or [])
        super().__init__("PI com pendências de fechamento.")


def _flag(name, default=True):
    raw = os.getenv(name)
    if raw is None and has_app_context():
        raw = current_app.config.get(name)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _money(value):
    parsed = parse_brl_float(value)
    if parsed is None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return float(parsed)


def _volume(value):
    parsed = parse_volume_float(value)
    if parsed is None:
        return None
    return float(parsed)


def _safe_float(value, default=0.0):
    parsed = _money(value)
    if parsed is None:
        return default
    return parsed


def classificar_zona(custo_real, zonas):
    if custo_real is None or not zonas:
        return None
    if custo_real <= _safe_float(zonas.get("limite_inf")):
        return 1
    if custo_real <= _safe_float(zonas.get("orcado")):
        return 2
    if custo_real <= _safe_float(zonas.get("limite_sup")):
        return 3
    if custo_real <= _safe_float(zonas.get("ruptura")):
        return 4
    return 5


def calcular_zonas(pi, desvio_pct, ruptura_mult=10.0):
    obj_contr = _safe_float(pi.get("objetivo_contratado_pi") or pi.get("objetivo_contratado"))
    cbase = _safe_float(pi.get("custo_base_unitario"))
    is_cpm = bool(pi.get("meta_baseada_em_cpm"))
    volume = (obj_contr / 1000.0) if is_cpm else obj_contr
    midia_orcado = volume * cbase
    try:
        desvio = float(desvio_pct) / 100.0
    except (TypeError, ValueError):
        desvio = 0.05
    if desvio < 0:
        desvio = 0.0
    ruptura = midia_orcado * (1.0 + float(ruptura_mult) * desvio)
    return {
        "volume": round(volume, 4),
        "midia_orcado": round(midia_orcado, 2),
        "ruptura_mult_desvio": float(ruptura_mult),
        "zonas": {
            "limite_inf": round(midia_orcado * (1 - desvio), 2),
            "orcado": round(midia_orcado, 2),
            "limite_sup": round(midia_orcado * (1 + desvio), 2),
            "ruptura": round(ruptura, 2),
        },
    }


def _pct(realizado, previsto):
    if not previsto:
        return 0
    return round((float(realizado or 0) / float(previsto)) * 100, 2)


def _desvio_pi(pi):
    desvio = _money(pi.get("desvio_aceitavel_pct"))
    if desvio is None and has_app_context():
        desvio = float(current_app.config.get("PI_DESVIO_ACEITAVEL_PERCENTUAL", 5.0))
    if desvio is None:
        desvio = 5.0
    return desvio


def _ruptura_mult():
    if has_app_context():
        return float(current_app.config.get("PI_RUPTURA_MULT_DESVIO", 10.0))
    return 10.0


def label_status_financeiro(codigo):
    return STATUS_FINANCEIRO_LABELS.get(codigo or "", "Aguardando comprovação")


class PiFechamentoService:
    def __init__(self, repository=None, operacao=None, brevo_service=None, renderer=None):
        self.repository = repository or PiFechamentoRepository()
        self.operacao = operacao or PiOperacaoService()
        self._brevo = brevo_service
        self.renderer = renderer or render_template

    @property
    def brevo(self):
        return self._brevo or get_brevo_service()

    def preview(self, id_pi):
        estado = self.operacao.estado_completo(id_pi)
        pi = estado["pi"]
        campanhas = estado["campanhas"]
        snapshot = self._montar_snapshot(pi, campanhas, estado.get("saude") or {})
        snapshot["pendencias"] = self._pendencias(pi, campanhas, estado, snapshot)
        snapshot["gate_ok"] = not snapshot["pendencias"]
        snapshot["status_financeiro"] = self._status_exibido(id_pi, pi)
        snapshot["status_financeiro_label"] = label_status_financeiro(snapshot["status_financeiro"])
        snapshot["modo"] = "pre-handoff" if str(pi.get("id_sub_status_pi")) == "3" else "pos-handoff"
        snapshot["resultado_persistido"] = self.repository.obter_resultado(id_pi)
        return snapshot

    def resultado(self, id_pi):
        gravado = self.repository.obter_resultado(id_pi)
        if gravado:
            campanhas = self.repository.listar_campanhas(id_pi, gravado.get("versao"))
            status = self._status_exibido(id_pi, {"id_pi": id_pi})
            payload = gravado.get("payload_json") or {}
            return {
                "persistido": True,
                "id_pi": gravado.get("id_pi"),
                "codigo_pi": payload.get("codigo_pi"),
                "cliente_nome": payload.get("cliente_nome"),
                "agencia_nome": payload.get("agencia_nome"),
                "gasto_midia_realizado": gravado.get("gasto_midia_realizado"),
                "gasto_midia_previsto": gravado.get("gasto_midia_previsto"),
                "pct_gasto_midia": gravado.get("pct_gasto_midia"),
                "objetivo_contratado": gravado.get("objetivo_contratado"),
                "objetivo_atingido": gravado.get("objetivo_atingido"),
                "pct_objetivo": gravado.get("pct_objetivo"),
                "valor_bruto": gravado.get("valor_bruto"),
                "valor_liquido": gravado.get("valor_liquido"),
                "margem_cc": gravado.get("margem_cc"),
                "tech_fee": gravado.get("tech_fee"),
                "com_vendas": gravado.get("com_vendas"),
                "pl_incentivos": gravado.get("pl_incentivos"),
                "impostos": gravado.get("impostos"),
                "margem_liquida_calculada": gravado.get("margem_liquida_calculada"),
                "zona_lucratividade": gravado.get("zona_lucratividade"),
                "zona_label": ZONA_LABELS.get(int(gravado.get("zona_lucratividade") or 0), "—"),
                "zonas": gravado.get("zonas_json") or {},
                "saude_pi": gravado.get("saude_pi") or "sem_dados",
                "saude_label": SAUDE_LABELS.get(gravado.get("saude_pi") or "sem_dados"),
                "saude": gravado.get("saude_json") or {},
                "desvio_aceitavel_pct": gravado.get("desvio_aceitavel_pct"),
                "lucrativo": gravado.get("lucrativo"),
                "observacoes_operacao": gravado.get("observacoes_operacao") or "",
                "drive": payload.get("drive") or {},
                "campanhas": campanhas,
                "pendencias": [],
                "gate_ok": True,
                "status_financeiro": status,
                "status_financeiro_label": label_status_financeiro(status),
                "modo": "pos-handoff",
                "resultado_persistido": gravado,
            }
        preview = self.preview(id_pi)
        preview["persistido"] = False
        return preview

    def validar_handoff(self, id_pi):
        preview = self.preview(id_pi)
        if preview["pendencias"]:
            raise HandoffBloqueadoError(preview["pendencias"])
        return preview

    def enviar_financeiro(self, id_pi, autor_id, observacoes=None):
        if _flag("PI_HANDOFF_GATE", True):
            preview = self.validar_handoff(id_pi)
        else:
            preview = self.preview(id_pi)

        if observacoes:
            preview["observacoes_operacao"] = str(observacoes).strip()

        versao = self.repository.proxima_versao(id_pi)
        payload = self._payload_persistencia(preview, versao, autor_id)
        self.repository.gravar_resultado(payload)
        self.repository.gravar_campanhas(
            self._payload_campanhas(preview, versao)
        )
        campanhas_finalizadas = self.repository.finalizar_handoff(id_pi)
        self.repository.upsert_status(id_pi, "aguardando_comprovacao", autor_id)

        email_result = None
        if _flag("BREVO_HANDOFF_INTERNO", True):
            email_result = self.notificar_financeiro_interno(id_pi, preview, autor_id)

        make_warning = None
        if _flag("MAKE_HANDOFF_FALLBACK", False):
            make_warning = self._disparar_make(preview, campanhas_finalizadas)

        from .pi_operacao_service import sincronizar_operacao_pi

        try:
            sincronizar_operacao_pi(int(id_pi), autor_id)
        except Exception:
            logger.exception("Falha ao sincronizar operação após handoff do PI %s", id_pi)

        return {
            "success": True,
            "campanhas_finalizadas": campanhas_finalizadas,
            "versao": versao,
            "email": email_result,
            "warning": make_warning,
            "redirect": self._url_workspace(id_pi),
        }

    def notificar_financeiro_interno(self, id_pi, snapshot, autor_id):
        destinatarios = self._destinatarios_internos(snapshot.get("pi") or {})
        if not destinatarios:
            logger.warning("Handoff PI %s sem destinatários internos configurados.", id_pi)
            return {"enviados": [], "success": False, "skipped": True}

        assunto = f"PI {snapshot.get('codigo_pi') or id_pi} enviado ao Financeiro"
        html = self.renderer(
            "emails/internos/pi_operacao/handoff_financeiro.html",
            snapshot=snapshot,
            workspace_url=self._url_workspace(id_pi, external=True),
        )
        resultados = []
        for destinatario in destinatarios:
            log_id = self.operacao.repository.criar_email_log(
                id_pi,
                "handoff_financeiro_interno",
                assunto,
                destinatario,
                html,
                autor_id,
            )
            resultado = self.brevo.enviar_email(
                to_email=destinatario["email"],
                to_name=destinatario.get("nome_completo") or "Financeiro",
                subject=assunto,
                html_content=html,
            )
            self.operacao.repository.concluir_email_log(log_id, resultado)
            resultados.append(resultado)
        return {
            "enviados": resultados,
            "success": all(item.get("success") or item.get("messageId") for item in resultados),
        }

    def anexar_lista(self, pis):
        ids = [item.get("id_pi") for item in (pis or []) if item.get("id_pi")]
        status_map = self.repository.listar_status(ids)
        snap_map = self.repository.listar_resultados_lote(ids)
        for pi in pis or []:
            snap = snap_map.get(pi.get("id_pi")) or {}
            gasto = _money(snap.get("gasto_midia_realizado"))
            previsto = _money(snap.get("gasto_midia_previsto"))
            if gasto is None:
                gasto = _money(pi.get("camp_midia_gasto_total"))
            if previsto is None:
                previsto = _money(pi.get("camp_midia_prev_total"))
            zona = snap.get("zona_lucratividade")
            if zona is None:
                calc = calcular_zonas(pi, _desvio_pi(pi), _ruptura_mult())
                zona = classificar_zona(gasto, calc["zonas"])
            saude = snap.get("saude_pi") or pi.get("saude_pi") or "sem_dados"
            status = status_map.get(pi.get("id_pi"))
            if not status:
                status = "nf_emitida" if pi.get("nf_id") else "aguardando_comprovacao"
            pi["camp_midia_gasto_total"] = gasto if gasto is not None else pi.get("camp_midia_gasto_total")
            pi["camp_midia_prev_total"] = previsto if previsto is not None else pi.get("camp_midia_prev_total")
            pi["camp_pct_midia"] = int(_pct(gasto, previsto))
            pi["zona_lucratividade"] = zona
            pi["zona_label"] = ZONA_LABELS.get(int(zona), "—") if zona else "—"
            pi["saude_pi"] = saude
            pi["saude_label"] = SAUDE_LABELS.get(saude, "Sem dados")
            pi["status_financeiro"] = status
            pi["status_financeiro_label"] = label_status_financeiro(status)
        return pis

    def _montar_snapshot(self, pi, campanhas, saude):
        desvio = _desvio_pi(pi)
        calc = calcular_zonas(pi, desvio, _ruptura_mult())
        gasto = 0.0
        previsto = 0.0
        obj_contr = 0.0
        obj_ating = 0.0
        linhas = []
        for campanha in campanhas:
            gasto_c = _money(campanha.get("totalizador_gasto")) or 0.0
            previsto_c = _money(
                campanha.get("custo_midia_orcado") or campanha.get("valor_plataforma")
            ) or 0.0
            obj_c = _volume(campanha.get("obj_contratados")) or 0.0
            ating_c = _volume(campanha.get("totalizador_atingido")) or 0.0
            gasto += gasto_c
            previsto += previsto_c
            obj_contr += obj_c
            obj_ating += ating_c
            linhas.append(
                {
                    "id_campanha": campanha.get("id_campanha"),
                    "plataforma": campanha.get("plataforma_nome") or campanha.get("plataforma"),
                    "nome_campanha": campanha.get("nome_campanha"),
                    "gasto_realizado": round(gasto_c, 2),
                    "gasto_previsto": round(previsto_c, 2),
                    "pct_gasto": _pct(gasto_c, previsto_c),
                    "obj_contratado": obj_c,
                    "obj_atingido": ating_c,
                    "pct_objetivo": _pct(ating_c, obj_c),
                    "preco_unitario_orcado": _money(campanha.get("preco_unitario")) or _money(campanha.get("custo_base_unitario")),
                    "preco_unitario_realizado": None,
                    "periodo_inicio": campanha.get("periodo_inicio"),
                    "periodo_fim": campanha.get("periodo_fim"),
                    "status_nome": campanha.get("status_descricao") or campanha.get("status_nome"),
                    "link_dash": campanha.get("link_dash"),
                    "flags_json": {"saude": (saude.get("campanhas") or [])},
                }
            )
        if not previsto:
            previsto = calc["midia_orcado"]
        zona = classificar_zona(gasto, calc["zonas"])
        liquido = _money(pi.get("valor_liquido") or pi.get("vr_liquido_pi")) or 0.0
        bruto = _money(pi.get("valor_bruto") or pi.get("vr_bruto_pi")) or 0.0
        margem = _money(pi.get("val_margem_cc")) or 0.0
        return {
            "pi": pi,
            "id_pi": pi.get("id_pi"),
            "codigo_pi": pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag"),
            "cliente_nome": pi.get("cliente_nome"),
            "agencia_nome": pi.get("agencia_nome"),
            "executivo": pi.get("resp_comercial_nome") or pi.get("responsavel_comercial_nome"),
            "gasto_midia_realizado": round(gasto, 2),
            "gasto_midia_previsto": round(previsto, 2),
            "pct_gasto_midia": _pct(gasto, previsto),
            "objetivo_contratado": obj_contr,
            "objetivo_atingido": obj_ating,
            "pct_objetivo": _pct(obj_ating, obj_contr),
            "valor_bruto": bruto,
            "valor_liquido": liquido,
            "margem_cc": margem,
            "tech_fee": _money(pi.get("val_tech_fee")) or 0.0,
            "com_vendas": _money(pi.get("val_com_vendas")) or 0.0,
            "pl_incentivos": _money(pi.get("val_pl_incentivos")) or 0.0,
            "impostos": _money(pi.get("val_impostos")) or 0.0,
            "margem_liquida_calculada": round(liquido - gasto, 2),
            "zona_lucratividade": zona,
            "zona_label": ZONA_LABELS.get(zona or 0, "—"),
            "zonas": calc["zonas"],
            "saude": saude,
            "saude_pi": saude.get("status") or "sem_dados",
            "saude_label": SAUDE_LABELS.get(saude.get("status") or "sem_dados"),
            "desvio_aceitavel_pct": desvio,
            "lucrativo": zona in (1, 2) if zona else None,
            "observacoes_operacao": (pi.get("observacoes_operacao") or pi.get("obs_operacao") or "").strip(),
            "drive": {
                "principal": pi.get("googled_pi_princ"),
                "financeiro": pi.get("googled_pi_financ"),
                "assinados": pi.get("googled_pi_arq_ass"),
            },
            "campanhas": linhas,
        }

    def _pendencias(self, pi, campanhas, estado, snapshot):
        pendencias = []
        itens = (estado.get("checklist_operacional") or {}).get("itens_pi") or estado.get("checklist") or []
        relatorio = next(
            (item for item in itens if item.get("codigo") == "enviar_relatorios_faturamento"),
            None,
        )
        if relatorio and not relatorio.get("concluido"):
            pendencias.append(
                {
                    "codigo": "enviar_relatorios_faturamento",
                    "mensagem": "Conclua o item “Enviar dashboard e relatórios para faturamento”.",
                }
            )
        ativas = [
            campanha.get("nome_campanha") or campanha.get("id_campanha")
            for campanha in campanhas
            if str(campanha.get("status_descricao") or "").lower() in {"ativa", "ativo", "em veiculação", "em veiculacao"}
        ]
        if ativas:
            pendencias.append(
                {
                    "codigo": "campanhas_ativas",
                    "mensagem": f"Existem campanhas ainda ativas: {', '.join(str(item) for item in ativas[:4])}.",
                }
            )
        if not (pi.get("googled_pi_princ") or "").strip():
            pendencias.append(
                {
                    "codigo": "pasta_drive",
                    "mensagem": "Pasta principal do Drive ainda não foi gerada.",
                }
            )
        exigir_obs = snapshot.get("zona_lucratividade") in (4, 5) or (
            snapshot.get("pct_gasto_midia") or 0
        ) > 100
        if exigir_obs and not snapshot.get("observacoes_operacao"):
            pendencias.append(
                {
                    "codigo": "observacoes_operacao",
                    "mensagem": "Informe observações da operação: zona crítica ou gasto acima do previsto.",
                }
            )
        if _flag("PI_HANDOFF_BLOQUEIA_RISCO", False) and snapshot.get("saude_pi") == "risco":
            pendencias.append(
                {
                    "codigo": "saude_risco",
                    "mensagem": "Saúde do PI em risco — peça aprovação de gestor para o handoff.",
                }
            )
        return pendencias

    def _payload_persistencia(self, snapshot, versao, autor_id):
        return {
            "id_pi": snapshot["id_pi"],
            "versao": versao,
            "gasto_midia_realizado": snapshot["gasto_midia_realizado"],
            "gasto_midia_previsto": snapshot["gasto_midia_previsto"],
            "pct_gasto_midia": snapshot["pct_gasto_midia"],
            "objetivo_contratado": snapshot["objetivo_contratado"],
            "objetivo_atingido": snapshot["objetivo_atingido"],
            "pct_objetivo": snapshot["pct_objetivo"],
            "valor_bruto": snapshot["valor_bruto"],
            "valor_liquido": snapshot["valor_liquido"],
            "margem_cc": snapshot["margem_cc"],
            "tech_fee": snapshot["tech_fee"],
            "com_vendas": snapshot["com_vendas"],
            "pl_incentivos": snapshot["pl_incentivos"],
            "impostos": snapshot["impostos"],
            "margem_liquida_calculada": snapshot["margem_liquida_calculada"],
            "zona_lucratividade": snapshot["zona_lucratividade"],
            "zonas_json": snapshot["zonas"],
            "saude_pi": snapshot["saude_pi"],
            "saude_json": snapshot.get("saude"),
            "desvio_aceitavel_pct": snapshot["desvio_aceitavel_pct"],
            "lucrativo": snapshot["lucrativo"],
            "observacoes_operacao": snapshot.get("observacoes_operacao"),
            "payload_json": {
                "codigo_pi": snapshot.get("codigo_pi"),
                "cliente_nome": snapshot.get("cliente_nome"),
                "agencia_nome": snapshot.get("agencia_nome"),
                "drive": snapshot.get("drive"),
            },
            "fechado_por": autor_id,
        }

    def _payload_campanhas(self, snapshot, versao):
        rows = []
        for linha in snapshot.get("campanhas") or []:
            rows.append({**linha, "id_pi": snapshot["id_pi"], "versao": versao})
        return rows

    def _status_exibido(self, id_pi, pi):
        row = self.repository.obter_status(id_pi)
        if row:
            return row.get("status_financeiro")
        if pi.get("nf_id"):
            return "nf_emitida"
        if str(pi.get("id_sub_status_pi")) in {"4", "5"}:
            return "aguardando_comprovacao"
        return None

    def _destinatarios_internos(self, pi):
        raw = os.getenv("FINANCEIRO_HANDOFF_EMAILS", "")
        if has_app_context() and not raw:
            raw = current_app.config.get("FINANCEIRO_HANDOFF_EMAILS") or ""
        emails = [item.strip() for item in str(raw).split(",") if item.strip()]
        destinatarios = [
            {"email": email, "nome_completo": "Financeiro CentralComm"}
            for email in emails
        ]
        extra = (pi.get("resp_comercial_email") or "").strip()
        if extra and extra not in {item["email"] for item in destinatarios}:
            destinatarios.append(
                {
                    "email": extra,
                    "nome_completo": pi.get("resp_comercial_nome") or "Executivo",
                }
            )
        return destinatarios

    def _url_workspace(self, id_pi, external=False):
        if has_request_context():
            return url_for("pi_financeiro.workspace", id_pi=id_pi, _external=external)
        return f"/cadu_pi/{id_pi}/financeiro"

    def _disparar_make(self, snapshot, quant_campanhas):
        url = os.getenv("MAKE_WEBHOOK_PI_FATURAMENTO")
        if not url:
            return None
        try:
            import requests
            from .services.pi_make_webhooks import valor_liquido_pi_webhook

            pi = snapshot.get("pi") or {}
            is_dev = has_app_context() and current_app.config.get("DEBUG", False)
            params = {
                "testeparam": "yes" if is_dev else "no",
                "codPI": snapshot.get("codigo_pi") or "",
                "razaosccliente": pi.get("cliente_razao_social") or "",
                "nomefcliente": snapshot.get("cliente_nome") or "",
                "pastaprgoogle": (snapshot.get("drive") or {}).get("principal") or "",
                "valorliquidopi": valor_liquido_pi_webhook(pi),
                "quantcampanhas": quant_campanhas,
                "zona_lucratividade": snapshot.get("zona_lucratividade"),
                "saude_pi": snapshot.get("saude_pi"),
                "gasto_midia_realizado": snapshot.get("gasto_midia_realizado"),
                "gasto_midia_previsto": snapshot.get("gasto_midia_previsto"),
                "workspace": self._url_workspace(snapshot["id_pi"], external=True),
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.exception("Fallback Make no handoff do PI %s", snapshot.get("id_pi"))
            return str(exc)
        return None
