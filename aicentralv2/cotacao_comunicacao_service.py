"""Destinatários e histórico de e-mails da cotação."""

import logging

from flask import render_template

from .cotacao_comunicacao_repository import (
    CotacaoComunicacaoRepository,
    CotacaoNaoEncontradaError,
)
from .email_area_cc import cc_comercial


logger = logging.getLogger(__name__)


class CotacaoComunicacaoService:
    def __init__(self, repository=None, renderer=None):
        self.repository = repository or CotacaoComunicacaoRepository()
        self.renderer = renderer or render_template

    def estado(self, id_cotacao):
        cotacao = self.repository.obter_cotacao(id_cotacao)
        recipient_error = None
        destinatarios_confirmados = False
        try:
            destinatarios = self.repository.listar_destinatarios(id_cotacao)
            destinatarios_confirmados = bool(destinatarios)
            if not destinatarios_confirmados:
                destinatarios = self.repository.listar_destinatarios_sugeridos(cotacao)
        except Exception:
            logger.exception("Falha ao carregar destinatários da cotação %s", id_cotacao)
            destinatarios = []
            destinatarios_confirmados = False
            recipient_error = (
                "Não foi possível carregar os destinatários. "
                "Tente novamente ou revise os contatos."
            )
        try:
            contatos_disponiveis = self.repository.listar_contatos_disponiveis(cotacao)
        except Exception:
            logger.exception("Falha ao carregar contatos da cotação %s", id_cotacao)
            contatos_disponiveis = []
            recipient_error = recipient_error or (
                "Não foi possível carregar os contatos disponíveis."
            )
        cotacao_payload = {
            "id_cotacao": cotacao.get("id"),
            "id": cotacao.get("id"),
            "id_cliente": cotacao.get("client_id"),
            "client_id": cotacao.get("client_id"),
            "id_agencia": cotacao.get("agencia_id"),
            "agencia_id": cotacao.get("agencia_id"),
            "id_parceiro": cotacao.get("id_parceiro"),
            "cliente_nome": cotacao.get("cliente_nome"),
            "agencia_nome": cotacao.get("agencia_nome"),
            "parceiro_nome": cotacao.get("parceiro_nome"),
        }
        return {
            "cotacao": cotacao_payload,
            "destinatarios": destinatarios,
            "destinatarios_confirmados": destinatarios_confirmados,
            "contatos_disponiveis": contatos_disponiveis,
            "recipient_error": recipient_error,
            "emails": self.repository.listar_emails(id_cotacao),
            "cc_emails_padrao": cc_comercial(cotacao.get("responsavel_email")),
        }

    def salvar_destinatarios(self, id_cotacao, destinatarios, autor_id):
        return {
            "destinatarios": self.repository.substituir_destinatarios(
                id_cotacao, destinatarios, autor_id
            ),
            "message": "Destinatários salvos.",
        }

    def obter_email_log(self, id_cotacao, log_id):
        self.repository.obter_cotacao(id_cotacao)
        return self.repository.obter_email_log(id_cotacao, log_id)

    def registrar_envio(self, id_cotacao, tipo, assunto, destinatario, html, autor_id, resultado):
        log_id = self.repository.criar_email_log(
            id_cotacao,
            tipo,
            assunto,
            destinatario,
            html,
            autor_id,
        )
        self.repository.concluir_email_log(log_id, resultado)
        return log_id

    def render_template_html(self, template_path, params):
        template_vars = {}
        if params:
            template_vars = {k.lower(): v for k, v in params.items()}
        return self.renderer(template_path, **template_vars)


__all__ = ["CotacaoComunicacaoService", "CotacaoNaoEncontradaError"]
