"""
=====================================================
BREVO EMAIL SERVICE
Serviço de envio de emails via API Brevo
=====================================================
"""

import requests
import json
import logging
from flask import current_app, render_template
from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger(__name__)

# Constantes da API Brevo
BREVO_API_URL = "https://api.brevo.com/v3"

# IDs das listas no Brevo
LISTA_USUARIOS_ATIVOS = 21
LISTA_CONVITES_PENDENTES = 22
LISTA_USUARIOS_INATIVOS = 23


class BrevoService:
    """Serviço para integração com API Brevo"""
    
    def __init__(self, api_key: str = None, sender_name: str = None, sender_email: str = None):
        """
        Inicializa o serviço Brevo
        
        Args:
            api_key: Chave da API Brevo (opcional, usa config se não fornecida)
            sender_name: Nome do remetente (opcional)
            sender_email: Email do remetente (opcional)
        """
        self.api_key = api_key
        self.sender_name = sender_name
        self.sender_email = sender_email
    
    def _get_config(self, key: str, default: str = None) -> str:
        """Obtém configuração do Flask ou usa default"""
        try:
            return current_app.config.get(key, default)
        except RuntimeError:
            return default
    
    @property
    def _api_key(self) -> str:
        """Retorna a API key configurada"""
        return self.api_key or self._get_config('BREVO_API_KEY', '')
    
    @property
    def _sender(self) -> Dict[str, str]:
        """Retorna o remetente configurado"""
        return {
            "name": self.sender_name or self._get_config('BREVO_SENDER_NAME', 'Cadu'),
            "email": self.sender_email or self._get_config('BREVO_SENDER_EMAIL', 'contato@centralcomm.media')
        }
    
    @property
    def _headers(self) -> Dict[str, str]:
        """Retorna headers padrão para API Brevo"""
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self._api_key
        }
    
    def enviar_email(
        self,
        to_email: Union[str, List[str]],
        to_name: str,
        subject: str,
        html_content: str,
        text_content: str = None,
        params: Dict[str, Any] = None,
        reply_to: Dict[str, str] = None,
        attachments: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Envia email transacional via API Brevo
        
        Args:
            to_email: Email(s) do destinatário
            to_name: Nome do destinatário
            subject: Assunto do email
            html_content: Conteúdo HTML do email
            text_content: Conteúdo texto plano (opcional)
            params: Parâmetros para substituição no template
            reply_to: Email de resposta {"name": "...", "email": "..."}
            attachments: Lista de anexos [{"name": "...", "content": "base64..."}]
        
        Returns:
            Dict com messageId em caso de sucesso ou error em caso de falha
        """
        # Normalizar destinatários
        if isinstance(to_email, str):
            recipients = [{"email": to_email, "name": to_name}]
        else:
            recipients = [{"email": email, "name": to_name} for email in to_email]
        
        payload = {
            "sender": self._sender,
            "to": recipients,
            "subject": subject,
            "htmlContent": html_content
        }
        
        if text_content:
            payload["textContent"] = text_content
        
        if params:
            payload["params"] = params
        
        if reply_to:
            payload["replyTo"] = reply_to
        
        if attachments:
            payload["attachment"] = attachments
        
        try:
            response = requests.post(
                f"{BREVO_API_URL}/smtp/email",
                headers=self._headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Email enviado com sucesso para {to_email}. MessageId: {result.get('messageId')}")
                return {"success": True, "messageId": result.get("messageId")}
            else:
                logger.error(f"Erro ao enviar email: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text, "status_code": response.status_code}
                
        except requests.exceptions.Timeout:
            logger.error("Timeout ao enviar email via Brevo")
            return {"success": False, "error": "Timeout na requisição"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de requisição ao enviar email: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar email: {e}")
            return {"success": False, "error": str(e)}
    
    def enviar_email_com_template(
        self,
        template_name: str,
        to_email: Union[str, List[str]],
        to_name: str,
        subject: str,
        params: Dict[str, Any] = None,
        template_folder: str = "emails/externos"
    ) -> Dict[str, Any]:
        """
        Envia email usando template Flask/Jinja2
        
        Args:
            template_name: Nome do arquivo template (ex: "convite.html")
            to_email: Email(s) do destinatário
            to_name: Nome do destinatário
            subject: Assunto do email
            params: Parâmetros para o template
            template_folder: Pasta do template (default: emails/externos)
        
        Returns:
            Dict com resultado do envio
        """
        try:
            # Renderizar template - passar params como variáveis separadas (minúsculas)
            template_path = f"{template_folder}/{template_name}"
            template_vars = {}
            if params:
                # Converter chaves para minúsculas para compatibilidade com Jinja2
                template_vars = {k.lower(): v for k, v in params.items()}
            html_content = render_template(template_path, **template_vars)
            
            return self.enviar_email(
                to_email=to_email,
                to_name=to_name,
                subject=subject,
                html_content=html_content,
                params=params
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar template {template_name}: {e}")
            return {"success": False, "error": f"Erro no template: {str(e)}"}
    
    def adicionar_contato(
        self,
        email: str,
        nome: str = None,
        atributos: Dict[str, Any] = None,
        lista_ids: List[int] = None,
        update_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Adiciona ou atualiza contato no Brevo
        
        Args:
            email: Email do contato
            nome: Nome do contato (opcional)
            atributos: Atributos customizados (opcional)
            lista_ids: IDs das listas para adicionar o contato
            update_enabled: Se True, atualiza contato existente
        
        Returns:
            Dict com resultado da operação
        """
        payload = {
            "email": email,
            "updateEnabled": update_enabled
        }
        
        # Adicionar atributos
        attrs = atributos or {}
        if nome:
            attrs["NOME"] = nome
        
        if attrs:
            payload["attributes"] = attrs
        
        if lista_ids:
            payload["listIds"] = lista_ids
        
        try:
            response = requests.post(
                f"{BREVO_API_URL}/contacts",
                headers=self._headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"Contato {email} adicionado/atualizado com sucesso")
                return {"success": True}
            else:
                logger.error(f"Erro ao adicionar contato: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"Erro ao adicionar contato: {e}")
            return {"success": False, "error": str(e)}
    
    def remover_contato_da_lista(self, email: str, lista_id: int) -> Dict[str, Any]:
        """
        Remove contato de uma lista específica
        
        Args:
            email: Email do contato
            lista_id: ID da lista
        
        Returns:
            Dict com resultado da operação
        """
        payload = {"emails": [email]}
        
        try:
            response = requests.post(
                f"{BREVO_API_URL}/contacts/lists/{lista_id}/contacts/remove",
                headers=self._headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"Contato {email} removido da lista {lista_id}")
                return {"success": True}
            else:
                logger.error(f"Erro ao remover contato da lista: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"Erro ao remover contato da lista: {e}")
            return {"success": False, "error": str(e)}
    
    def mover_para_lista(
        self,
        email: str,
        lista_destino: int,
        lista_origem: int = None
    ) -> Dict[str, Any]:
        """
        Move contato para uma nova lista
        
        Args:
            email: Email do contato
            lista_destino: ID da lista de destino
            lista_origem: ID da lista de origem (opcional, remove se fornecido)
        
        Returns:
            Dict com resultado da operação
        """
        # Adicionar à nova lista
        result = self.adicionar_contato(email=email, lista_ids=[lista_destino])
        
        if result.get("success") and lista_origem:
            # Remover da lista anterior
            self.remover_contato_da_lista(email, lista_origem)
        
        return result


# Instância global do serviço
_brevo_service = None


def get_brevo_service() -> BrevoService:
    """Retorna instância do serviço Brevo"""
    global _brevo_service
    if _brevo_service is None:
        _brevo_service = BrevoService()
    return _brevo_service


# =====================================================
# FUNÇÕES DE CONVENIÊNCIA
# =====================================================

def enviar_email_convite(
    to_email: str,
    to_name: str,
    invite_link: str,
    invited_by: str,
    cliente_nome: str,
    expires_at: str,
    role_label: str = "Usuário",
    dias_validade: int = 7
) -> Dict[str, Any]:
    """
    Envia email de convite para novo usuário
    
    Args:
        to_email: Email do convidado
        to_name: Nome do convidado
        invite_link: Link de aceite do convite
        invited_by: Nome de quem convidou
        cliente_nome: Nome do cliente/empresa
        expires_at: Data de expiração formatada
        role_label: Label da função do usuário
        dias_validade: Dias de validade do convite
    
    Returns:
        Dict com resultado do envio
    """
    service = get_brevo_service()
    
    params = {
        "CONVIDADO_POR": invited_by,
        "EMPRESA": cliente_nome,
        "ROLE_LABEL": role_label,
        "DIAS_VALIDADE": dias_validade,
        "LINK_CONVITE": invite_link,
        "EXPIRA_EM": expires_at
    }
    
    # Adicionar contato à lista de convites pendentes
    service.adicionar_contato(
        email=to_email,
        nome=to_name,
        lista_ids=[LISTA_CONVITES_PENDENTES],
        atributos={"EMPRESA": cliente_nome, "CONVIDADO_POR": invited_by}
    )
    
    return service.enviar_email_com_template(
        template_name="convite-usuario.html",
        to_email=to_email,
        to_name=to_name or "Usuário",
        subject=f"Você foi convidado para o Cadu por {invited_by}",
        params=params,
        template_folder="emails/externos"
    )


def enviar_email_boas_vindas(
    to_email: str,
    to_name: str,
    cliente_nome: str = "",
    role_label: str = "",
    login_link: str = None,
    token: str = None
) -> Dict[str, Any]:
    """
    Envia email de boas-vindas após aceitar convite
    
    Args:
        to_email: Email do usuário
        to_name: Nome do usuário
        cliente_nome: Nome da empresa
        role_label: Função do usuário
        login_link: Link de login (opcional)
        token: Token do invite (opcional, para link de aceitar convite)
    
    Returns:
        Dict com resultado do envio
    """
    service = get_brevo_service()
    
    # Extrair primeiro nome
    primeiro_nome = to_name.split()[0] if to_name else "Usuário"
    
    params = {
        "NOME": to_name,
        "PRIMEIRO_NOME": primeiro_nome,
        "EMAIL": to_email,
        "EMPRESA": cliente_nome,
        "ROLE_LABEL": role_label,
        "LINK_DASHBOARD": login_link or "",
        "LINK_LOGIN": login_link or "",
        "TOKEN": token or ""
    }
    
    # Mover da lista de pendentes para ativos
    service.mover_para_lista(
        email=to_email,
        lista_destino=LISTA_USUARIOS_ATIVOS,
        lista_origem=LISTA_CONVITES_PENDENTES
    )
    
    return service.enviar_email_com_template(
        template_name="bem-vindo.html",
        to_email=to_email,
        to_name=to_name,
        subject="Bem-vindo ao Cadu!",
        params=params,
        template_folder="emails/externos"
    )


def enviar_email_reset_senha(
    to_email: str,
    to_name: str,
    reset_link: str,
    expires_hours: int = 1
) -> Dict[str, Any]:
    """
    Envia email de recuperação de senha
    
    Args:
        to_email: Email do usuário
        to_name: Nome do usuário
        reset_link: Link de reset
        expires_hours: Horas até expiração
    
    Returns:
        Dict com resultado do envio
    """
    service = get_brevo_service()
    
    # Extrair primeiro nome
    primeiro_nome = to_name.split()[0] if to_name else "Usuário"
    
    # Converter horas para minutos
    minutos_validade = expires_hours * 60
    
    params = {
        "NOME": to_name,
        "PRIMEIRO_NOME": primeiro_nome,
        "LINK_RESET": reset_link,
        "MINUTOS_VALIDADE": minutos_validade,
        "HORAS_VALIDADE": expires_hours
    }
    
    return service.enviar_email_com_template(
        template_name="reset-senha.html",
        to_email=to_email,
        to_name=to_name,
        subject="Recuperação de Senha - Cadu",
        params=params,
        template_folder="emails/externos"
    )


def enviar_email_senha_alterada(
    to_email: str,
    to_name: str
) -> Dict[str, Any]:
    """
    Envia confirmação de senha alterada
    
    Args:
        to_email: Email do usuário
        to_name: Nome do usuário
    
    Returns:
        Dict com resultado do envio
    """
    service = get_brevo_service()
    
    # Extrair primeiro nome
    primeiro_nome = to_name.split()[0] if to_name else "Usuário"
    
    # Como não existe template específico, enviar HTML direto
    html_content = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Senha Alterada - Cadu</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f4f4f5;">
        <tr>
            <td style="padding:40px 15px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="520" align="center" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
                    <tr>
                        <td style="background-color:#ffffff;padding:24px 32px;text-align:center;border-bottom:1px solid #e5e7eb;">
                            <img src="https://cadu.centralcomm.media/assets/images/cadu-logo-variant-2.png" alt="Cadu" width="100" style="display:block;margin:0 auto;">
                        </td>
                    </tr>
                    <tr>
                        <td style="background:linear-gradient(135deg,#10b981 0%,#059669 100%);padding:20px 32px;text-align:center;">
                            <span style="color:#ffffff;font-size:15px;font-weight:700;">✓ Senha Alterada com Sucesso</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <p style="margin:0 0 16px;font-size:14px;color:#333842;">
                                Olá, <strong>{primeiro_nome}</strong>
                            </p>
                            <p style="margin:0 0 24px;font-size:13px;color:#6b7280;line-height:1.6;">
                                Sua senha do Cadu foi alterada com sucesso. Se você realizou esta alteração, nenhuma ação adicional é necessária.
                            </p>
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#fef2f2;border-radius:6px;border-left:4px solid #ef4444;">
                                <tr>
                                    <td style="padding:16px;">
                                        <span style="font-size:12px;color:#991b1b;">
                                            <strong>Não foi você?</strong> Se você não alterou sua senha, entre em contato conosco imediatamente ou solicite uma nova recuperação de senha.
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color:#F7F8FA;padding:20px 32px;text-align:center;border-top:1px solid #e5e7eb;">
                            <span style="font-size:11px;color:#9ca3af;">Este é um email automático. Por favor, não responda.</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    
    return service.enviar_email(
        to_email=to_email,
        to_name=to_name,
        subject="Senha Alterada - Cadu",
        html_content=html_content
    )


def enviar_notificacao_interna(
    to_email: str,
    to_name: str,
    titulo: str,
    mensagem: str,
    acao_link: str = None,
    acao_texto: str = None
) -> Dict[str, Any]:
    """
    Envia notificação interna do sistema
    
    Args:
        to_email: Email do destinatário
        to_name: Nome do destinatário
        titulo: Título da notificação
        mensagem: Corpo da mensagem
        acao_link: Link de ação (opcional)
        acao_texto: Texto do botão de ação (opcional)
    
    Returns:
        Dict com resultado do envio
    """
    service = get_brevo_service()
    
    params = {
        "NOME": to_name,
        "TITULO": titulo,
        "MENSAGEM": mensagem,
        "ACAO_LINK": acao_link or "",
        "ACAO_TEXTO": acao_texto or "Ver Detalhes"
    }
    
    return service.enviar_email_com_template(
        template_name="notificacao.html",
        to_email=to_email,
        to_name=to_name,
        subject=titulo,
        params=params,
        template_folder="emails/internos"
    )


def enviar_alerta_consumo(
    to_email: str,
    to_name: str,
    percentual: int,
    plano: str,
    usado: int,
    limite: int
) -> Dict[str, Any]:
    """
    Envia alerta de consumo de tokens
    
    Args:
        to_email: Email do usuário
        to_name: Nome do usuário
        percentual: Percentual consumido
        plano: Nome do plano
        usado: Tokens usados
        limite: Limite do plano
    
    Returns:
        Dict com resultado do envio
    """
    service = get_brevo_service()
    
    params = {
        "NOME": to_name,
        "PERCENTUAL": percentual,
        "PLANO": plano,
        "USADO": usado,
        "LIMITE": limite
    }
    
    return service.enviar_email_com_template(
        template_name="alerta_consumo.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"Alerta: {percentual}% do limite de tokens consumido",
        params=params,
        template_folder="emails/internos"
    )


# =====================================================
# FUNÇÕES DE COTAÇÕES
# =====================================================

def enviar_email_cotacao_aprovada(
    to_email: str,
    to_name: str,
    numero_cotacao: str,
    nome_campanha: str,
    cliente_nome: str,
    cliente_email: str,
    valor_total: str,
    link_proposta: str,
    data_aprovacao: str,
    cliente_empresa: str = None,
    link_admin: str = None,
    tem_agencia: bool = False,
    agencia_nome: str = None,
    agencia_email: str = None
) -> Dict[str, Any]:
    """
    Envia email interno de cotação aprovada
    
    Args:
        to_email: Email do destinatário interno (responsável comercial, apolo, etc.)
        to_name: Nome do destinatário
        numero_cotacao: Número da cotação
        nome_campanha: Nome da campanha
        cliente_nome: Nome do cliente
        cliente_email: Email do cliente
        valor_total: Valor formatado
        link_proposta: Link para ver a proposta
        data_aprovacao: Data da aprovação formatada
        cliente_empresa: Nome da empresa cliente
        link_admin: Link para o admin
        tem_agencia: Se True, indica que a cotação tem uma agência vinculada
        agencia_nome: Nome da agência (quando tem_agencia=True)
        agencia_email: Email da agência (quando tem_agencia=True)
    """
    service = get_brevo_service()
    
    params = {
        "NUMERO_COTACAO": numero_cotacao,
        "NOME_CAMPANHA": nome_campanha,
        "CLIENTE_NOME": cliente_nome,
        "CLIENTE_EMAIL": cliente_email,
        "CLIENTE_EMPRESA": cliente_empresa or "",
        "VALOR_TOTAL": valor_total,
        "LINK_PROPOSTA": link_proposta,
        "LINK_ADMIN": link_admin or "",
        "DATA_APROVACAO": data_aprovacao,
        "TEM_AGENCIA": tem_agencia,
        "AGENCIA_NOME": agencia_nome or "",
        "AGENCIA_EMAIL": agencia_email or ""
    }
    
    return service.enviar_email_com_template(
        template_name="cotacao-aprovada.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"✓ Proposta Aprovada - {numero_cotacao}",
        params=params,
        template_folder="emails/internos"
    )


def enviar_email_cotacao_rejeitada(
    to_email: str,
    to_name: str,
    numero_cotacao: str,
    nome_campanha: str,
    cliente_nome: str,
    motivo: str = None,
    link_proposta: str = None,
    data_rejeicao: str = None,
    tem_agencia: bool = False,
    agencia_nome: str = None,
    agencia_email: str = None
) -> Dict[str, Any]:
    """
    Envia email interno de cotação rejeitada
    
    Args:
        to_email: Email do destinatário interno (responsável comercial, apolo, etc.)
        to_name: Nome do destinatário
        numero_cotacao: Número da cotação
        nome_campanha: Nome da campanha
        cliente_nome: Nome do cliente
        motivo: Motivo da rejeição
        link_proposta: Link para ver a proposta
        data_rejeicao: Data da rejeição formatada
        tem_agencia: Se True, indica que a cotação tem uma agência vinculada
        agencia_nome: Nome da agência (quando tem_agencia=True)
        agencia_email: Email da agência (quando tem_agencia=True)
    """
    service = get_brevo_service()
    
    params = {
        "NUMERO_COTACAO": numero_cotacao,
        "NOME_CAMPANHA": nome_campanha,
        "CLIENTE_NOME": cliente_nome,
        "MOTIVO": motivo or "Não informado",
        "LINK_PROPOSTA": link_proposta or "",
        "DATA_REJEICAO": data_rejeicao or "",
        "TEM_AGENCIA": tem_agencia,
        "AGENCIA_NOME": agencia_nome or "",
        "AGENCIA_EMAIL": agencia_email or ""
    }
    
    return service.enviar_email_com_template(
        template_name="cotacao-rejeitada.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"✗ Proposta Rejeitada - {numero_cotacao}",
        params=params,
        template_folder="emails/internos"
    )


def enviar_email_cotacao_recebida(
    to_email: str,
    to_name: str,
    numero_cotacao: str,
    nome_campanha: str,
    cliente_nome: str,
    valor_total: str,
    link_proposta: str,
    data_recebimento: str = None
) -> Dict[str, Any]:
    """
    Envia email interno de nova cotação recebida
    """
    service = get_brevo_service()
    
    params = {
        "NUMERO_COTACAO": numero_cotacao,
        "NOME_CAMPANHA": nome_campanha,
        "CLIENTE_NOME": cliente_nome,
        "VALOR_TOTAL": valor_total,
        "LINK_PROPOSTA": link_proposta,
        "DATA_RECEBIMENTO": data_recebimento or ""
    }
    
    return service.enviar_email_com_template(
        template_name="cotacao-recebida.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"Nova Proposta - {numero_cotacao}",
        params=params,
        template_folder="emails/internos"
    )


def enviar_email_novo_usuario_admin(
    to_email: str,
    to_name: str,
    nome_usuario: str,
    email_usuario: str,
    empresa: str,
    role_label: str = None,
    data_cadastro: str = None,
    link_admin: str = None
) -> Dict[str, Any]:
    """
    Envia email interno de novo usuário cadastrado (para admin)
    """
    service = get_brevo_service()
    
    params = {
        "NOME": nome_usuario,
        "EMAIL": email_usuario,
        "EMPRESA": empresa,
        "ROLE_LABEL": role_label or "Usuário",
        "DATA_CADASTRO": data_cadastro or "",
        "LINK_ADMIN": link_admin or ""
    }
    
    return service.enviar_email_com_template(
        template_name="novo-usuario.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"Novo Usuário Cadastrado - {nome_usuario}",
        params=params,
        template_folder="emails/internos"
    )


# =====================================================
# FUNÇÕES PARA EMAILS AO CLIENTE (externos)
# =====================================================

def enviar_email_cotacao_enviada_cliente(
    to_email: str,
    to_name: str,
    numero_cotacao: str,
    nome_campanha: str,
    valor_total: str,
    link_proposta: str = None,
    validade: str = None,
    executivo_nome: str = None,
    executivo_email: str = None,
    periodo: str = None,
    objetivo: str = None,
    audiencia_nome: str = None,
    audiencia_categoria: str = None,
    prazo_resposta: str = "até 24 horas úteis",
    data_envio: str = None,
    tem_agencia: bool = False,
    agencia_nome: str = None,
    cliente_nome: str = None
) -> Dict[str, Any]:
    """
    Envia email para cliente ou agência de cotação enviada
    
    Args:
        to_email: Email do destinatário (cliente ou agência)
        to_name: Nome do destinatário
        numero_cotacao: Número da cotação
        nome_campanha: Nome da campanha
        valor_total: Valor formatado
        link_proposta: Link para ver a proposta
        validade: Data de validade da proposta
        executivo_nome: Nome do executivo comercial
        executivo_email: Email do executivo comercial
        periodo: Período da campanha
        objetivo: Objetivo da campanha
        audiencia_nome: Nome da audiência
        audiencia_categoria: Categoria da audiência
        prazo_resposta: Prazo de resposta
        data_envio: Data de envio formatada
        tem_agencia: Se True, indica que o destinatário é uma agência
        agencia_nome: Nome da agência (quando tem_agencia=True)
        cliente_nome: Nome do cliente (usado quando tem agência para informar de qual cliente é a cotação)
    """
    from datetime import datetime
    
    service = get_brevo_service()
    
    primeiro_nome = to_name.split()[0] if to_name else "Cliente"
    
    params = {
        "NOME": to_name,
        "PRIMEIRO_NOME": primeiro_nome,
        "NUMERO_COTACAO": numero_cotacao,
        "NOME_CAMPANHA": nome_campanha,
        "VALOR_INVESTIMENTO": valor_total,
        "LINK_COTACAO": link_proposta or "",
        "VALIDADE": validade or "",
        "EXECUTIVO_NOME": executivo_nome or "",
        "EXECUTIVO_EMAIL": executivo_email or "",
        "PERIODO": periodo or "",
        "OBJETIVO": objetivo or "",
        "AUDIENCIA_NOME": audiencia_nome or "",
        "AUDIENCIA_CATEGORIA": audiencia_categoria or "",
        "PRAZO_RESPOSTA": prazo_resposta,
        "DATA_ENVIO": data_envio or datetime.now().strftime('%d/%m/%Y às %H:%M'),
        "TEM_AGENCIA": tem_agencia,
        "AGENCIA_NOME": agencia_nome or "",
        "CLIENTE_NOME": cliente_nome or ""
    }
    
    return service.enviar_email_com_template(
        template_name="cotacao-enviada.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"Sua Proposta - {numero_cotacao}",
        params=params,
        template_folder="emails/externos"
    )


def enviar_email_cotacao_aprovada_cliente(
    to_email: str,
    to_name: str,
    numero_cotacao: str,
    nome_campanha: str,
    valor_total: str,
    proximos_passos: str = None,
    executivo_nome: str = None,
    executivo_email: str = None,
    data_aprovacao: str = None,
    link_proposta: str = None,
    tem_agencia: bool = False,
    agencia_nome: str = None,
    cliente_nome: str = None
) -> Dict[str, Any]:
    """
    Envia email para cliente/agência de cotação aprovada
    
    Args:
        to_email: Email do destinatário (cliente ou agência)
        to_name: Nome do destinatário
        numero_cotacao: Número da cotação
        nome_campanha: Nome da campanha
        valor_total: Valor formatado
        proximos_passos: Próximos passos (opcional)
        executivo_nome: Nome do executivo comercial
        executivo_email: Email do executivo comercial
        data_aprovacao: Data da aprovação formatada
        link_proposta: Link para ver a proposta
        tem_agencia: Se True, indica que o destinatário é uma agência
        agencia_nome: Nome da agência (quando tem_agencia=True)
        cliente_nome: Nome do cliente (usado quando tem agência para informar de qual cliente é a cotação)
    """
    from datetime import datetime
    
    service = get_brevo_service()
    
    primeiro_nome = to_name.split()[0] if to_name else "Cliente"
    
    params = {
        "NOME": to_name,
        "PRIMEIRO_NOME": primeiro_nome,
        "NUMERO_COTACAO": numero_cotacao,
        "NOME_CAMPANHA": nome_campanha,
        "VALOR_TOTAL": valor_total,
        "PROXIMOS_PASSOS": proximos_passos or "",
        "CONTATO_COMERCIAL": executivo_nome or "",
        "EMAIL_COMERCIAL": executivo_email or "",
        "DATA_APROVACAO": data_aprovacao or datetime.now().strftime('%d/%m/%Y às %H:%M'),
        "LINK_PROPOSTA": link_proposta or "",
        "TEM_AGENCIA": tem_agencia,
        "AGENCIA_NOME": agencia_nome or "",
        "CLIENTE_NOME": cliente_nome or ""
    }
    
    return service.enviar_email_com_template(
        template_name="cotacao-aprovada-cliente.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"Proposta Aprovada - {numero_cotacao}",
        params=params,
        template_folder="emails/externos"
    )


def enviar_email_cotacao_rejeitada_cliente(
    to_email: str,
    to_name: str,
    numero_cotacao: str,
    nome_campanha: str,
    mensagem: str = None,
    executivo_nome: str = None,
    executivo_email: str = None,
    data_rejeicao: str = None,
    link_nova_cotacao: str = None,
    tem_agencia: bool = False,
    agencia_nome: str = None,
    cliente_nome: str = None
) -> Dict[str, Any]:
    """
    Envia email para cliente/agência de cotação rejeitada/cancelada
    
    Args:
        to_email: Email do destinatário (cliente ou agência)
        to_name: Nome do destinatário
        numero_cotacao: Número da cotação
        nome_campanha: Nome da campanha
        mensagem: Motivo da rejeição (opcional)
        executivo_nome: Nome do executivo comercial
        executivo_email: Email do executivo comercial
        data_rejeicao: Data da rejeição formatada
        link_nova_cotacao: Link para solicitar nova cotação
        tem_agencia: Se True, indica que o destinatário é uma agência
        agencia_nome: Nome da agência (quando tem_agencia=True)
        cliente_nome: Nome do cliente (usado quando tem agência para informar de qual cliente é a cotação)
    """
    from datetime import datetime
    
    service = get_brevo_service()
    
    primeiro_nome = to_name.split()[0] if to_name else "Cliente"
    
    params = {
        "NOME": to_name,
        "PRIMEIRO_NOME": primeiro_nome,
        "NUMERO_COTACAO": numero_cotacao,
        "NOME_CAMPANHA": nome_campanha,
        "MOTIVO_REJEICAO": mensagem or "",
        "CONTATO_COMERCIAL": executivo_nome or "",
        "EMAIL_COMERCIAL": executivo_email or "",
        "DATA_REJEICAO": data_rejeicao or datetime.now().strftime('%d/%m/%Y às %H:%M'),
        "LINK_NOVA_COTACAO": link_nova_cotacao or "",
        "TEM_AGENCIA": tem_agencia,
        "AGENCIA_NOME": agencia_nome or "",
        "CLIENTE_NOME": cliente_nome or ""
    }
    
    return service.enviar_email_com_template(
        template_name="cotacao-rejeitada-cliente.html",
        to_email=to_email,
        to_name=to_name,
        subject=f"Atualização da Proposta - {numero_cotacao}",
        params=params,
        template_folder="emails/externos"
    )
