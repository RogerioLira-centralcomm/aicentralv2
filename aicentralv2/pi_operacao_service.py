"""Regras de negócio da Operação do PI."""

import logging
from datetime import date, datetime
from html import escape

from flask import has_request_context, render_template, url_for

from .campanha_pi_metrics import parse_brl_float, parse_volume_float
from .pi_operacao_repository import PiOperacaoRepository, PropriedadeInvalidaError
from .services.brevo_service import get_brevo_service


logger = logging.getLogger(__name__)


ETAPAS = (
    "dados_validados",
    "campanhas_configuradas",
    "materiais_recebidos",
    "campanha_iniciada",
    "otimizacao_enviada",
    "fechamento_comunicado",
    "enviado_financeiro",
)

TIPOS_POR_SUBSTATUS = {
    2: (
        "solicitar_materiais",
        "confirmar_recebimento_pi",
        "pendencias_dados",
        "atualizacao_manual",
    ),
    1: (
        "solicitar_ajustes",
        "informar_pendencias",
        "confirmar_aprovacao",
        "previsao_inicio",
        "atualizacao_manual",
    ),
    3: (
        "campanha_iniciada",
        "campanha_otimizada",
        "risco_entrega",
        "campanha_finalizada",
        "relatorios_faturamento",
        "atualizacao_manual",
    ),
    4: (
        "cliente_fechamento",
        "agencia_fechamento",
        "atualizacao_manual",
    ),
}

ASSUNTOS = {
    "solicitar_materiais": "Falta material para começar a campanha — {codigo}",
    "confirmar_recebimento_pi": "Recebemos o {codigo} e já estamos configurando",
    "pendencias_dados": "O {codigo} está parado por falta de dados",
    "atualizacao_manual": "Atualização da campanha — {codigo}",
    "solicitar_ajustes": "Precisamos de um ajuste no {codigo} antes de seguir",
    "informar_pendencias": "O {codigo} ainda tem pendências para aprovação",
    "confirmar_aprovacao": "{codigo} aprovado — seguimos para o ar",
    "previsao_inicio": "Previsão de início da campanha — {codigo}",
    "campanha_iniciada": "Sua campanha já está no ar — {codigo}",
    "campanha_otimizada": "Ajustamos a campanha — o que mudou no {codigo}",
    "risco_entrega": "Precisamos alinhar o ritmo da campanha — {codigo}",
    "campanha_finalizada": "Encerramos a campanha — {codigo}",
    "relatorios_faturamento": "Relatórios do {codigo} para faturamento",
    "cliente_fechamento": "Fechamento da campanha — relatórios do {codigo}",
    "agencia_fechamento": "Fechamento do {codigo} para a agência",
    "financeiro_cliente": "Resultado financeiro do {codigo}",
    "nota_fiscal_cliente": "Nota fiscal do {codigo}",
    "documentos_assinados": "Documentos assinados do {codigo}",
}

EMAIL_CARTA = frozenset(
    {
        "campanha_iniciada",
        "campanha_otimizada",
        "previsao_inicio",
        "atualizacao_manual",
        "solicitar_materiais",
        "solicitar_ajustes",
        "informar_pendencias",
        "pendencias_dados",
        "confirmar_recebimento_pi",
        "confirmar_aprovacao",
        "campanha_finalizada",
    }
)

ITENS_PI = (
    {
        "codigo": "verificar_informacoes_pi",
        "descricao": "Verificar informações do PI",
        "fase": "preparacao",
        "ordem": 10,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "verificar_cotacao_enviada",
        "descricao": "Verificar cotação enviada",
        "fase": "preparacao",
        "ordem": 20,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "comunicar_campanha_iniciada",
        "descricao": "Enviar e-mail ao cliente com campanha iniciada",
        "fase": "veiculacao",
        "ordem": 60,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "comunicar_campanha_otimizada",
        "descricao": "Enviar e-mail com campanha otimizada",
        "fase": "veiculacao",
        "ordem": 100,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "comunicar_campanha_finalizada",
        "descricao": "Informar cliente sobre campanha finalizada",
        "fase": "fechamento",
        "ordem": 110,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "enviar_relatorios_faturamento",
        "descricao": "Enviar dashboard e relatórios para faturamento",
        "fase": "fechamento",
        "ordem": 120,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "enviar_financeiro",
        "descricao": "Enviar PI para o Financeiro",
        "fase": "fechamento",
        "ordem": 130,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "comprovacao_veiculacao",
        "descricao": "Comprovação de veiculação anexada/gerada",
        "fase": "financeiro",
        "ordem": 140,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "carta_bonificacao",
        "descricao": "Carta de bonificação gerada (se aplicável)",
        "fase": "financeiro",
        "ordem": 150,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "relatorio_cliente_enviado",
        "descricao": "Relatório enviado ao cliente",
        "fase": "financeiro",
        "ordem": 160,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "assinatura_d4sign",
        "descricao": "Documentos assinados via D4Sign",
        "fase": "financeiro",
        "ordem": 170,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "nf_vinculada",
        "descricao": "NF vinculada ao PI",
        "fase": "financeiro",
        "ordem": 180,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "pagamento_confirmado",
        "descricao": "Pagamento registrado",
        "fase": "financeiro",
        "ordem": 190,
        "modo_conclusao": "automatico",
    },
)

ITENS_CAMPANHA = (
    {
        "codigo": "verificar_criativos",
        "descricao": "Verificar criativos",
        "fase": "preparacao",
        "ordem": 30,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "preparar_plataforma",
        "descricao": "Preparar campanha na plataforma",
        "fase": "preparacao",
        "ordem": 40,
        "modo_conclusao": "manual",
    },
    {
        "codigo": "campanha_iniciada",
        "descricao": "Campanha iniciada",
        "fase": "veiculacao",
        "ordem": 50,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "objetivo_50",
        "descricao": "Objetivo atingido em 50%",
        "fase": "veiculacao",
        "ordem": 70,
        "modo_conclusao": "automatico",
    },
    {
        "codigo": "objetivo_90",
        "descricao": "Objetivo atingido em 90%",
        "fase": "veiculacao",
        "ordem": 90,
        "modo_conclusao": "automatico",
    },
)


def assunto_email(tipo, codigo):
    modelo = ASSUNTOS.get(tipo) or "Atualização da campanha — PI {codigo}"
    return modelo.format(codigo=codigo)


def _data(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


class PiOperacaoService:
    def __init__(self, repository=None, brevo_service=None, renderer=None):
        self.repository = repository or PiOperacaoRepository()
        self._brevo = brevo_service
        self.renderer = renderer or render_template

    @property
    def brevo(self):
        return self._brevo or get_brevo_service()

    def catalogo(self, id_pi):
        pi = self.repository.obter_pi(id_pi)
        substatus = int(pi["id_sub_status_pi"]) if pi.get("id_sub_status_pi") is not None else None
        permitidos = TIPOS_POR_SUBSTATUS.get(substatus, ())
        codigo = pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag") or id_pi
        return {
            "substatus": substatus,
            "substatus_descricao": pi.get("sub_status_descricao"),
            "tipos": [
                {"tipo": tipo, "assunto_padrao": assunto_email(tipo, codigo)}
                for tipo in permitidos
            ],
        }

    def _itens_canonicos(self, id_pi, campanhas):
        itens = [
            {**item, "id_pi": id_pi, "id_campanha": None, "escopo": "pi"}
            for item in ITENS_PI
        ]
        for campanha in campanhas:
            itens.extend(
                {
                    **item,
                    "id_pi": id_pi,
                    "id_campanha": campanha["id_campanha"],
                    "escopo": "campanha",
                }
                for item in ITENS_CAMPANHA
            )
        return itens

    def _conclusoes_automaticas(self, pi, campanhas, emails):
        conclusoes = []
        emails_sucesso = {
            item.get("tipo")
            for item in emails
            if item.get("status") == "sucesso"
        }
        email_por_codigo = {
            "campanha_iniciada": "comunicar_campanha_iniciada",
            "campanha_otimizada": "comunicar_campanha_otimizada",
            "campanha_finalizada": "comunicar_campanha_finalizada",
            "cliente_fechamento": "relatorio_cliente_enviado",
        }
        for tipo, codigo in email_por_codigo.items():
            if tipo in emails_sucesso:
                conclusoes.append(
                    {
                        "codigo": codigo,
                        "id_campanha": None,
                        "evidencia": "E-mail consolidado enviado pelo CentralX",
                    }
                )

        for campanha in campanhas:
            campanha_id = campanha["id_campanha"]
            status = str(campanha.get("status_descricao") or "").strip().lower()
            if status in {
                "ativa",
                "finalizada",
                "concluída",
                "concluida",
                "encerrada",
            }:
                conclusoes.append(
                    {
                        "codigo": "campanha_iniciada",
                        "id_campanha": campanha_id,
                        "evidencia": f"Status: {campanha.get('status_descricao')}",
                    }
                )
            meta = parse_volume_float(campanha.get("obj_contratados"))
            atingido = parse_volume_float(campanha.get("totalizador_atingido"))
            percentual = (
                (float(atingido) / float(meta)) * 100
                if meta and atingido is not None
                else None
            )
            for limite, codigo in ((50, "objetivo_50"), (90, "objetivo_90")):
                if percentual is not None and percentual >= limite:
                    conclusoes.append(
                        {
                            "codigo": codigo,
                            "id_campanha": campanha_id,
                            "evidencia": f"{percentual:.1f}% do objetivo atingido",
                        }
                    )

        try:
            em_faturamento = int(pi.get("id_sub_status_pi")) in (4, 5)
        except (TypeError, ValueError):
            em_faturamento = False
        if em_faturamento:
            conclusoes.append(
                {
                    "codigo": "enviar_financeiro",
                    "id_campanha": None,
                    "evidencia": "PI enviado para faturamento",
                }
            )
        return conclusoes

    def _aplicar_evidencias(self, checklist, conclusoes, campanhas, pi=None):
        automaticas = {
            (item["codigo"], item.get("id_campanha")): item
            for item in conclusoes
        }
        campanhas_por_id = {
            item["id_campanha"]: item for item in campanhas
        }
        resultado = []
        for original in checklist:
            item = dict(original)
            chave = (item.get("codigo"), item.get("id_campanha"))
            evidencia = automaticas.get(chave)
            if evidencia and item.get("modo_conclusao") == "automatico":
                item["concluido"] = True
                item["evidencia"] = item.get("evidencia") or evidencia["evidencia"]
            elif item.get("modo_conclusao") == "automatico" and not item.get("evidencia"):
                campanha = campanhas_por_id.get(item.get("id_campanha"))
                if item.get("codigo") in ("objetivo_50", "objetivo_90") and campanha:
                    meta = parse_volume_float(campanha.get("obj_contratados"))
                    atingido = parse_volume_float(campanha.get("totalizador_atingido"))
                    percentual = (
                        (float(atingido) / float(meta)) * 100
                        if meta and atingido is not None
                        else None
                    )
                    item["evidencia"] = (
                        f"{percentual:.1f}% do objetivo"
                        if percentual is not None
                        else "Aguardando dados de entrega"
                    )
                else:
                    item["evidencia"] = "Aguardando evidência no CentralX"
            elif (
                item.get("codigo") == "verificar_cotacao_enviada"
                and not item.get("evidencia")
                and pi is not None
            ):
                enviada_em = pi.get("proposta_enviada_em")
                if enviada_em:
                    data_envio = (
                        enviada_em.strftime("%d/%m/%Y")
                        if hasattr(enviada_em, "strftime")
                        else str(enviada_em)
                    )
                    item["evidencia"] = f"Cotação enviada em {data_envio}"
                elif pi.get("cotacao_id"):
                    item["evidencia"] = "Sem envio registrado no CentralX"
                else:
                    item["evidencia"] = "PI sem cotação vinculada"
            resultado.append(item)
        return resultado

    def _estrutura_checklist(self, checklist, campanhas):
        codigos_pi = {item["codigo"] for item in ITENS_PI}
        codigos_campanha = {item["codigo"] for item in ITENS_CAMPANHA}
        itens_pi = [
            item
            for item in checklist
            if item.get("codigo") in codigos_pi and item.get("id_campanha") is None
        ]
        grupos = []
        for campanha in campanhas:
            itens = [
                item
                for item in checklist
                if item.get("codigo") in codigos_campanha
                and item.get("id_campanha") == campanha["id_campanha"]
            ]
            concluidos = sum(bool(item.get("concluido")) for item in itens)
            grupos.append(
                {
                    "id_campanha": campanha["id_campanha"],
                    "nome": campanha.get("nome_campanha")
                    or f"Campanha {campanha['id_campanha']}",
                    "plataforma": campanha.get("plataforma_nome") or "Sem plataforma",
                    "concluidos": concluidos,
                    "total": len(itens),
                    "completo": bool(itens) and concluidos == len(itens),
                    "itens": itens,
                }
            )
        grupos.sort(key=lambda item: (item["completo"], item["nome"].lower()))
        todos = itens_pi + [
            item for grupo in grupos for item in grupo["itens"]
        ]
        concluidos = sum(bool(item.get("concluido")) for item in todos)
        pendentes = sorted(
            (item for item in todos if not item.get("concluido")),
            key=lambda item: (
                int(item.get("ordem") or 0),
                str(item.get("nome_campanha") or ""),
            ),
        )
        proxima = dict(pendentes[0]) if pendentes else None
        return {
            "progresso": {
                "concluidos": concluidos,
                "total": len(todos),
                "percentual": round((concluidos / len(todos)) * 100)
                if todos
                else 0,
            },
            "proxima_pendencia": proxima,
            "itens_pi": itens_pi,
            "campanhas": grupos,
        }

    def estado_completo(self, id_pi):
        pi = self.repository.obter_pi(id_pi)
        campanhas = self.repository.listar_campanhas(id_pi)
        emails = self.repository.listar_emails(id_pi)
        checklist = self._aplicar_evidencias(
            self.repository.listar_checklist(id_pi),
            self._conclusoes_automaticas(pi, campanhas, emails),
            campanhas,
            pi,
        )
        recipient_error = None
        destinatarios_confirmados = False
        try:
            destinatarios = self.repository.listar_destinatarios(id_pi)
            destinatarios_confirmados = bool(destinatarios)
            if not destinatarios_confirmados:
                destinatarios = self.repository.listar_destinatarios_sugeridos(id_pi)
        except Exception:
            logger.exception("Falha ao carregar destinatários do PI %s", id_pi)
            if hasattr(self.repository, "rollback"):
                try:
                    self.repository.rollback()
                except Exception:
                    logger.exception("Falha ao reverter leitura de destinatários")
            destinatarios = []
            destinatarios_confirmados = False
            recipient_error = (
                "Não foi possível carregar os destinatários. "
                "Tente novamente ou revise os contatos do PI."
            )
        try:
            contatos_disponiveis = self.repository.listar_contatos_disponiveis(id_pi)
        except Exception:
            logger.exception("Falha ao carregar contatos disponíveis do PI %s", id_pi)
            if hasattr(self.repository, "rollback"):
                try:
                    self.repository.rollback()
                except Exception:
                    logger.exception("Falha ao reverter leitura de contatos")
            contatos_disponiveis = []
            recipient_error = (
                "Não foi possível carregar os contatos disponíveis. "
                "Tente novamente ou revise os vínculos do cliente e da agência."
            )
        etapas_gravadas = self.repository.listar_etapas(id_pi)
        timeline = self._timeline(
            pi, campanhas, checklist, emails, etapas_gravadas
        )
        saude = self._calcular_saude(campanhas, pi.get("desvio_aceitavel_pct"))
        sla = self._calcular_sla(pi, campanhas)
        ultima_atualizacao = self.repository.obter_ultima_atualizacao(id_pi)
        inicio_operacao = etapas_gravadas.get("campanha_iniciada", {}).get("concluida_em")
        return {
            "pi": pi,
            "campanhas": campanhas,
            "destinatarios": destinatarios,
            "destinatarios_confirmados": destinatarios_confirmados,
            "contatos_disponiveis": contatos_disponiveis,
            "recipient_error": recipient_error,
            "checklist": checklist,
            "checklist_operacional": self._estrutura_checklist(
                checklist, campanhas
            ),
            "interacoes": self.repository.listar_interacoes(id_pi),
            "emails": emails,
            "timeline": timeline,
            "sla": sla,
            "saude": saude,
            "resumo": {
                "total_campanhas": len(campanhas),
                "executivo_vendas": pi.get("responsavel_comercial_nome"),
                "agencia": pi.get("agencia_nome"),
                "ultima_atualizacao": ultima_atualizacao,
                "inicio_operacao": inicio_operacao,
                "previsao_fechamento": pi.get("periodo_fim"),
                "sla": sla,
            },
            "recomendacoes": self._recomendacoes(
                pi, campanhas, checklist, destinatarios, saude
            ),
        }

    def estado_campanha(self, id_pi, id_campanha):
        """Projeta a operação para uma campanha sem misturar seu checklist."""
        campanha = self.repository.obter_campanha(id_campanha)
        if int(campanha["id_pi"]) != int(id_pi):
            raise PropriedadeInvalidaError("Campanha não pertence ao PI informado.")

        estado = self.estado_completo(id_pi)
        campanhas_relacionadas = [
            {
                "id_campanha": item["id_campanha"],
                "nome": item.get("nome_campanha")
                or f"Campanha {item['id_campanha']}",
                "plataforma": item.get("plataforma_nome") or "Sem plataforma",
                "atual": int(item["id_campanha"]) == int(id_campanha),
            }
            for item in estado["campanhas"]
        ]
        campanha_estado = next(
            (
                item
                for item in estado["campanhas"]
                if int(item["id_campanha"]) == int(id_campanha)
            ),
            campanha,
        )
        itens = [
            item
            for item in estado["checklist"]
            if item.get("id_campanha") is not None
            and int(item["id_campanha"]) == int(id_campanha)
        ]
        concluidos = sum(bool(item.get("concluido")) for item in itens)
        pendentes = sorted(
            (item for item in itens if not item.get("concluido")),
            key=lambda item: (int(item.get("ordem") or 0), int(item.get("id") or 0)),
        )
        grupo = {
            "id_campanha": campanha_estado["id_campanha"],
            "nome": campanha_estado.get("nome_campanha")
            or f"Campanha {id_campanha}",
            "plataforma": campanha_estado.get("plataforma_nome")
            or "Sem plataforma",
            "concluidos": concluidos,
            "total": len(itens),
            "completo": bool(itens) and concluidos == len(itens),
            "itens": itens,
        }
        progresso = {
            "concluidos": concluidos,
            "total": len(itens),
            "percentual": round((concluidos / len(itens)) * 100) if itens else 0,
        }
        return {
            **estado,
            "campanhas": [campanha_estado],
            "campanhas_relacionadas": campanhas_relacionadas,
            "campanha": campanha_estado,
            "checklist": itens,
            "checklist_operacional": {
                "progresso": progresso,
                "proxima_pendencia": dict(pendentes[0]) if pendentes else None,
                "itens_pi": [],
                "campanhas": [grupo],
            },
            "saude": self._calcular_saude(
                [campanha_estado], estado["pi"].get("desvio_aceitavel_pct")
            ),
        }

    def _timeline(self, pi, campanhas, checklist, emails, gravadas):
        por_codigo = {}
        for item in checklist:
            if item.get("codigo"):
                por_codigo.setdefault(item["codigo"], []).append(item)

        def todos_concluidos(codigo):
            itens = por_codigo.get(codigo, [])
            return bool(itens) and all(item.get("concluido") for item in itens)

        fatos = {
            "dados_validados": todos_concluidos("verificar_informacoes_pi"),
            "campanhas_configuradas": todos_concluidos("preparar_plataforma"),
            "materiais_recebidos": todos_concluidos("verificar_criativos"),
            "campanha_iniciada": todos_concluidos("campanha_iniciada"),
            "otimizacao_enviada": todos_concluidos(
                "comunicar_campanha_otimizada"
            ),
            "fechamento_comunicado": todos_concluidos(
                "comunicar_campanha_finalizada"
            ),
            "enviado_financeiro": todos_concluidos("enviar_financeiro"),
        }
        return [
            {
                "etapa": etapa,
                "concluida": fatos[etapa],
                "concluida_em": (
                    gravadas.get(etapa, {}).get("concluida_em")
                    if fatos[etapa]
                    else None
                ),
                "concluida_por": (
                    gravadas.get(etapa, {}).get("concluida_por")
                    if fatos[etapa]
                    else None
                ),
            }
            for etapa in ETAPAS
        ]

    def sincronizar(self, id_pi, autor_id=None):
        """Sincronização pública para endpoints mutantes e transições legadas."""
        pi = self.repository.obter_pi(id_pi)
        campanhas = self.repository.listar_campanhas(id_pi)
        self.repository.gerar_checklist(
            id_pi, self._itens_canonicos(id_pi, campanhas), autor_id
        )
        emails = self.repository.listar_emails(id_pi)
        checklist = self.repository.concluir_itens_automaticos(
            id_pi,
            self._conclusoes_automaticas(pi, campanhas, emails),
        )
        timeline = self._timeline(
            pi, campanhas, checklist, emails, self.repository.listar_etapas(id_pi)
        )
        concluidas = [item["etapa"] for item in timeline if item["concluida"]]
        return self.repository.sincronizar_etapas(id_pi, concluidas, autor_id)

    def salvar_destinatarios(self, id_pi, destinatarios, autor_id):
        if destinatarios and isinstance(destinatarios[0], str):
            pi = self.repository.obter_pi(id_pi)
            disponiveis = self.repository.listar_contatos_disponiveis(id_pi)
            por_email = {
                str(item.get("email") or "").strip().lower(): item
                for item in disponiveis
            }
            convertidos = []
            for email in destinatarios:
                contato = por_email.get(str(email).strip().lower())
                if not contato:
                    raise ValueError("Destinatário não pertence ao cliente ou à agência do PI.")
                papel = (
                    "agencia"
                    if contato.get("pk_id_tbl_cliente") == pi.get("id_agencia")
                    else "cliente_final"
                )
                convertidos.append(
                    {
                        "id_contato_cliente": contato["id_contato_cliente"],
                        "papel": papel,
                        "padrao": not any(
                            item["papel"] == papel for item in convertidos
                        ),
                    }
                )
            destinatarios = convertidos
        resultado = self.repository.substituir_destinatarios(
            id_pi, destinatarios, autor_id
        )
        self.sincronizar(id_pi, autor_id)
        return resultado

    def gerar_checklist(self, id_pi, payload, autor_id):
        campanhas = self.repository.listar_campanhas(id_pi)
        solicitadas = payload.get("campanhas")
        if solicitadas is not None:
            ids = self.repository.validar_campanhas(id_pi, solicitadas)
            campanhas = [item for item in campanhas if item["id_campanha"] in ids]
        itens = self._itens_canonicos(id_pi, campanhas)
        self.repository.gerar_checklist(id_pi, itens, autor_id)
        self.sincronizar(id_pi, autor_id)
        pi = self.repository.obter_pi(id_pi)
        emails = self.repository.listar_emails(id_pi)
        todas_campanhas = self.repository.listar_campanhas(id_pi)
        resultado = self._aplicar_evidencias(
            self.repository.listar_checklist(id_pi),
            self._conclusoes_automaticas(pi, todas_campanhas, emails),
            todas_campanhas,
            pi,
        )
        return {
            "checklist": resultado,
            "checklist_operacional": self._estrutura_checklist(
                resultado, todas_campanhas
            ),
        }

    def atualizar_item(self, id_pi, item_id, concluido, autor_id):
        item = self.repository.atualizar_item_checklist(
            id_pi, item_id, bool(concluido), autor_id
        )
        self.sincronizar(id_pi, autor_id)
        return item

    def criar_interacao(self, id_pi, payload, autor_id):
        descricao = str(payload.get("descricao", "")).strip()
        if not descricao:
            raise ValueError("Descrição é obrigatória.")
        tipo = str(payload.get("tipo") or "nota").strip()[:40]
        item = self.repository.criar_interacao(id_pi, tipo, descricao, autor_id)
        self.sincronizar(id_pi, autor_id)
        return item

    def _validar_tipo(self, pi, tipo):
        try:
            substatus = int(pi.get("id_sub_status_pi"))
        except (TypeError, ValueError):
            substatus = None
        if tipo not in TIPOS_POR_SUBSTATUS.get(substatus, ()):
            raise ValueError("Tipo de comunicação não permitido para o estágio do PI.")

    def _destinatarios(self, id_pi, ids=None):
        vinculados = self.repository.listar_destinatarios(id_pi)
        if ids is not None:
            ids = {int(item) for item in ids}
            vinculados = [
                item for item in vinculados if item["id_contato_cliente"] in ids
            ]
            if {item["id_contato_cliente"] for item in vinculados} != ids:
                raise ValueError("Destinatário não está vinculado à operação deste PI.")
        else:
            padroes = [item for item in vinculados if item.get("padrao")]
            vinculados = padroes or vinculados
        if not vinculados:
            raise ValueError("Nenhum destinatário operacional foi selecionado.")
        return vinculados

    def _contato_remetente(self, contato_id, origem, papel, fallback_nome=""):
        if not contato_id:
            return None
        contato = self.repository.obter_contato(contato_id)
        if not contato:
            return None
        return {
            "id": contato.get("id_contato_cliente") or contato_id,
            "nome": contato.get("nome_completo") or fallback_nome or "",
            "email": contato.get("email") or "",
            "origem": origem,
            "papel": papel,
        }

    def _autor_remetente(self, autor):
        if not autor:
            return None
        autor_id = autor.get("id")
        contato = self.repository.obter_contato(autor_id) if autor_id else None
        nome = (contato or {}).get("nome_completo") or autor.get("nome") or ""
        email = (contato or {}).get("email") or autor.get("email") or ""
        if not nome and not email:
            return None
        return {
            "id": autor_id,
            "nome": nome,
            "email": email,
            "origem": "voce",
            "papel": "Operação",
        }

    def _remetentes_disponiveis(self, pi, campanhas, autor):
        vistos = set()
        itens = []

        def adicionar(item):
            if not item:
                return
            chave = item.get("id") or item.get("email")
            if not chave or chave in vistos:
                return
            if not (item.get("nome") or item.get("email")):
                return
            vistos.add(chave)
            itens.append(item)

        adicionar(self._autor_remetente(autor))
        adicionar(
            self._contato_remetente(
                pi.get("id_resp_comercial"),
                "comercial",
                "Comercial",
                pi.get("responsavel_comercial_nome") or "",
            )
        )
        for campanha in campanhas or []:
            adicionar(
                self._contato_remetente(
                    campanha.get("id_responsavel_operacao"),
                    "operacao",
                    "Operação",
                    campanha.get("responsavel_operacao_nome") or "",
                )
            )
        return itens

    def _escolher_remetente(self, disponiveis, payload):
        wanted = payload.get("remetente_id")
        if wanted is not None:
            for item in disponiveis:
                if str(item.get("id")) == str(wanted):
                    return item
        return disponiveis[0] if disponiveis else None

    def _reply_to(self, remetente):
        if not remetente or not str(remetente.get("email") or "").strip():
            return None
        return {
            "email": remetente["email"],
            "name": remetente.get("nome") or remetente["email"],
        }

    def _resolver_autor(self, autor_id, autor=None):
        if autor and (autor.get("id") or autor.get("email") or autor.get("nome")):
            return {
                "id": autor.get("id") or autor_id,
                "nome": autor.get("nome") or "",
                "email": autor.get("email") or "",
            }
        if not autor_id:
            return None
        contato = self.repository.obter_contato(autor_id)
        if not contato:
            return {"id": autor_id}
        return {
            "id": autor_id,
            "nome": contato.get("nome_completo") or "",
            "email": contato.get("email") or "",
        }

    def preview_email(self, id_pi, payload, autor=None):
        pi = self.repository.obter_pi(id_pi)
        tipo = str(payload.get("tipo", "")).strip()
        self._validar_tipo(pi, tipo)
        destinatarios = self._destinatarios(
            id_pi, payload.get("destinatarios")
        )
        campanhas = self.repository.listar_campanhas(id_pi)
        codigo = pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag") or id_pi
        assunto = str(payload.get("assunto") or assunto_email(tipo, codigo)).strip()
        remetentes = self._remetentes_disponiveis(pi, campanhas, autor)
        remetente = self._escolher_remetente(remetentes, payload)
        campanha_destaque_id = None
        if payload.get("id_campanha") is not None:
            campanha_destaque_id = int(payload["id_campanha"])
            self.repository.validar_campanhas(id_pi, [campanha_destaque_id])
        corpo = escape(str(payload.get("mensagem") or "").strip()).replace(
            "\n", "<br>"
        )
        campanhas_email = []
        for item in campanhas:
            meta = parse_volume_float(item.get("obj_contratados"))
            atingido = parse_volume_float(item.get("totalizador_atingido"))
            percentual = (
                round((float(atingido) / float(meta)) * 100, 1)
                if meta and atingido is not None
                else None
            )
            campanhas_email.append(
                {
                    "id_campanha": item["id_campanha"],
                    "nome": item.get("nome_campanha")
                    or f"Campanha {item['id_campanha']}",
                    "plataforma": item.get("plataforma_nome")
                    or "Plataforma não informada",
                    "status": item.get("status_descricao") or "Sem status",
                    "percentual_objetivo": percentual,
                    "link_dashboard": item.get("link_dash"),
                    "destaque": item["id_campanha"] == campanha_destaque_id,
                }
            )
        contexto = {
            "pi": pi,
            "cliente": pi.get("cliente_nome") or "",
            "agencia": pi.get("agencia_nome") or "",
            "codigo_pi": codigo,
            "titulo_pi": pi.get("titulo_pi") or "",
            "periodo_inicio": pi.get("periodo_inicio"),
            "periodo_fim": pi.get("periodo_fim"),
            "executivo_vendas": pi.get("responsavel_comercial_nome") or "",
            "campanhas": campanhas_email,
            "destinatarios": destinatarios,
            "destinatario_nome": (
                destinatarios[0].get("nome_completo") if len(destinatarios) == 1 else ""
            ),
            "corpo_editavel": corpo,
            "mensagem": str(payload.get("mensagem") or "").strip(),
            "link_drive": (pi.get("googled_pi_princ") or "").strip(),
            "remetente": remetente,
            "modo_email": "carta" if tipo in EMAIL_CARTA else "aviso",
            "logo_centralcomm_url": (
                url_for("static", filename="images/cc_logo.png", _external=True)
                if has_request_context()
                else "https://ai.centralcomm.media/static/images/cc_logo.png"
            ),
        }
        html = self.renderer(
            f"emails/externos/pi_operacao/{tipo}.html", **contexto
        )
        return {
            "tipo": tipo,
            "assunto": assunto,
            "html": html,
            "destinatarios": destinatarios,
            "remetentes": remetentes,
            "remetente": remetente,
        }

    def enviar_email(self, id_pi, payload, autor_id, autor=None):
        autor = self._resolver_autor(autor_id, autor)
        preview = self.preview_email(id_pi, payload, autor)
        reply_to = self._reply_to(preview.get("remetente"))
        resultados = []
        for destinatario in preview["destinatarios"]:
            individual = self.preview_email(
                id_pi,
                {
                    **payload,
                    "destinatarios": [destinatario["id_contato_cliente"]],
                    "assunto": preview["assunto"],
                },
                autor,
            )
            log_id = self.repository.criar_email_log(
                id_pi,
                individual["tipo"],
                individual["assunto"],
                destinatario,
                individual["html"],
                autor_id,
            )
            resultado = self.brevo.enviar_email(
                to_email=destinatario["email"],
                to_name=destinatario.get("nome_completo") or "Cliente",
                subject=individual["assunto"],
                html_content=individual["html"],
                reply_to=reply_to,
            )
            self.repository.concluir_email_log(log_id, resultado)
            resultados.append(
                {
                    "log_id": log_id,
                    "destinatario": destinatario["email"],
                    **resultado,
                }
            )
        self.sincronizar(id_pi, autor_id)
        return {
            "enviados": resultados,
            "success": all(item.get("success") for item in resultados),
        }

    def enviar_email_teste(self, id_pi, payload, autor):
        autor = self._resolver_autor((autor or {}).get("id"), autor)
        email = str((autor or {}).get("email") or "").strip()
        if not email:
            raise ValueError("Seu usuário não tem e-mail para receber o teste.")
        preview = self.preview_email(id_pi, payload, autor)
        resultado = self.brevo.enviar_email(
            to_email=email,
            to_name=autor.get("nome") or "Você",
            subject="[Teste] " + preview["assunto"],
            html_content=preview["html"],
            reply_to=self._reply_to(preview.get("remetente")),
        )
        return {
            "success": bool(resultado.get("success")),
            "destinatario": email,
            "envio": resultado,
        }

    def _calcular_saude(self, campanhas, desvio_aceitavel_pct=None):
        if not campanhas:
            return {"status": "sem_dados"}
        total_meta = 0.0
        total_atingido = 0.0
        percentuais_tempo = []
        diagnosticos = []
        tolerancia = max(float(desvio_aceitavel_pct or 10) / 100, 0)
        hoje = date.today()
        for campanha in campanhas:
            meta = parse_volume_float(campanha.get("obj_contratados"))
            atingido = parse_volume_float(campanha.get("totalizador_atingido"))
            inicio = _data(campanha.get("periodo_inicio"))
            fim = _data(campanha.get("periodo_fim"))
            if (
                not meta
                or campanha.get("totalizador_atingido") in (None, "")
                or not inicio
                or not fim
                or fim < inicio
            ):
                diagnosticos.append(
                    {
                        "id_campanha": campanha.get("id_campanha"),
                        "status": "sem_dados",
                        "motivo": "Meta, realizado ou período incompleto.",
                    }
                )
                continue
            total_meta += float(meta)
            total_atingido += float(atingido)
            total = max((fim - inicio).days + 1, 1)
            decorridos = min(max((hoje - inicio).days + 1, 0), total)
            tempo_campanha = decorridos / total
            percentuais_tempo.append(tempo_campanha)
            entrega_campanha = float(atingido) / float(meta)
            ritmo_entrega = entrega_campanha / tempo_campanha if tempo_campanha > 0 else None
            gasto = parse_brl_float(campanha.get("totalizador_gasto"))
            orcamento = parse_brl_float(
                campanha.get("custo_midia_orcado") or campanha.get("valor_plataforma")
            )
            ritmo_gasto = (
                (gasto / orcamento) / tempo_campanha
                if gasto is not None and orcamento and tempo_campanha > 0
                else None
            )
            status_campanha = "saudavel"
            motivos = []
            if ritmo_entrega is not None and ritmo_entrega < max(1 - (2 * tolerancia), 0):
                status_campanha = "risco"
                motivos.append("Entrega abaixo do ritmo esperado.")
            elif ritmo_entrega is not None and ritmo_entrega < max(1 - tolerancia, 0):
                status_campanha = "atencao"
                motivos.append("Entrega próxima do limite de desvio.")
            if ritmo_gasto is not None and ritmo_gasto > 1 + (2 * tolerancia):
                status_campanha = "risco"
                motivos.append("Gasto acima do ritmo planejado.")
            elif ritmo_gasto is not None and ritmo_gasto > 1 + tolerancia and status_campanha == "saudavel":
                status_campanha = "atencao"
                motivos.append("Gasto próximo do limite de desvio.")
            diagnosticos.append(
                {
                    "id_campanha": campanha.get("id_campanha"),
                    "nome_campanha": campanha.get("nome_campanha"),
                    "status": status_campanha,
                    "entrega_percentual": round(entrega_campanha * 100, 1),
                    "tempo_percentual": round(tempo_campanha * 100, 1),
                    "ritmo_entrega": round(ritmo_entrega, 2) if ritmo_entrega is not None else None,
                    "ritmo_gasto": round(ritmo_gasto, 2) if ritmo_gasto is not None else None,
                    "motivo": " ".join(motivos) or "Entrega dentro do desvio aceitável.",
                }
            )
        if total_meta <= 0:
            return {"status": "sem_dados", "campanhas": diagnosticos}
        entrega = total_atingido / total_meta
        tempo = sum(percentuais_tempo) / len(percentuais_tempo)
        ritmo = entrega / tempo if tempo > 0 else None
        statuses = {item["status"] for item in diagnosticos}
        status = "risco" if "risco" in statuses else "atencao" if "atencao" in statuses else "saudavel"
        return {
            "status": status,
            "entrega_percentual": round(entrega * 100, 1),
            "tempo_percentual": round(tempo * 100, 1),
            "ritmo": round(ritmo, 2) if ritmo is not None else None,
            "desvio_aceitavel_pct": round(tolerancia * 100, 2),
            "campanhas": diagnosticos,
        }

    def _calcular_sla(self, pi, campanhas):
        """Usa os marcos reais de início/fim; não inventa prazo sem data-base."""
        try:
            substatus = int(pi.get("id_sub_status_pi"))
        except (TypeError, ValueError):
            return {"status": "sem_dados"}
        if substatus in (4, 5):
            return {"status": "concluido", "dias_restantes": 0}
        if substatus == 6:
            return {"status": "cancelado"}
        datas = []
        if substatus in (1, 2):
            datas = [
                _data(item.get("periodo_inicio")) for item in campanhas
            ] or [_data(pi.get("periodo_inicio"))]
            datas = [item for item in datas if item]
            limite = min(datas) if datas else _data(pi.get("periodo_inicio"))
        elif substatus == 3:
            datas = [_data(item.get("periodo_fim")) for item in campanhas]
            datas = [item for item in datas if item]
            limite = max(datas) if datas else _data(pi.get("periodo_fim"))
        else:
            return {"status": "sem_dados"}
        if not limite:
            return {"status": "sem_dados"}
        dias = (limite - date.today()).days
        return {
            "status": "no_prazo" if dias >= 0 else "atrasado",
            "data_limite": limite,
            "dias_restantes": dias,
        }

    def _recomendacoes(self, pi, campanhas, checklist, destinatarios, saude):
        substatus = pi.get("id_sub_status_pi")
        recomendacoes = []
        estrutura = self._estrutura_checklist(checklist, campanhas)
        proxima = estrutura.get("proxima_pendencia")
        if proxima:
            descricao = proxima.get("descricao") or "Concluir próxima pendência"
            if proxima.get("nome_campanha"):
                descricao += f" — {proxima['nome_campanha']}"
            recomendacoes.append(descricao)
        if not destinatarios:
            recomendacoes.append("Defina os destinatários operacionais.")
        if substatus == 1:
            if not proxima:
                recomendacoes.append("Revise pendências e confirme a aprovação do PI.")
        elif substatus == 2:
            if not checklist:
                recomendacoes.append("Atualize o checklist operacional deste PI.")
        elif substatus == 3:
            if saude.get("status") == "sem_dados":
                recomendacoes.append("Atualize métricas e período para calcular a saúde.")
            elif saude.get("status") in ("atencao", "risco"):
                recomendacoes.append("Revise o ritmo de entrega e comunique o cliente.")
        return recomendacoes[:3]


def sincronizar_operacao_pi(id_pi, autor_id=None, repository=None):
    """Ponto público para as rotas legadas de transição chamarem futuramente."""
    return PiOperacaoService(repository=repository).sincronizar(id_pi, autor_id)
