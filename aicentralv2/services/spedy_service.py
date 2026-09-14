"""
Integração com a API Spedy (NFS-e) — sandbox e produção.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from flask import current_app

from aicentralv2.campanha_pi_metrics import parse_brl_float

logger = logging.getLogger(__name__)

SPEDY_TERMINAL_STATUSES = frozenset({
    'authorized', 'rejected', 'canceled', 'denied', 'removed', 'disabled',
})
SPEDY_PENDING_STATUSES = frozenset({
    'created', 'enqueued', 'received', 'processing', 'inContingent',
})

_CITY_IBGE: Dict[str, tuple[str, str]] = {
    'belo horizonte': ('3106200', 'mg'),
    'sao paulo': ('3550308', 'sp'),
    'são paulo': ('3550308', 'sp'),
    'rio de janeiro': ('3304557', 'rj'),
    'curitiba': ('4106902', 'pr'),
    'brasilia': ('5300108', 'df'),
    'brasília': ('5300108', 'df'),
}


class SpedyAPIError(Exception):
    """Erro de comunicação ou validação com a API Spedy."""

    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class SpedyService:
    """Cliente HTTP para a API Spedy v1."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        product_id: str | None = None,
        product_code: str | None = None,
        product_name: str | None = None,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.product_id = product_id
        self.product_code = product_code
        self.product_name = product_name
        self.timeout = timeout

    def _cfg(self, key: str, default=None):
        try:
            val = current_app.config.get(key, default)
            return default if val is None else val
        except RuntimeError:
            return default

    @property
    def _api_key(self) -> str:
        return self.api_key or self._cfg('SPEDY_API_KEY', '') or ''

    @property
    def _base_url(self) -> str:
        url = self.base_url or self._cfg(
            'SPEDY_API_BASE_URL',
            'https://sandbox-api.spedy.com.br/v1',
        )
        return url.rstrip('/')

    @property
    def _product_id(self) -> str:
        return self.product_id or self._cfg(
            'SPEDY_PRODUCT_ID',
            '1dcacc78-34d8-43f9-806f-a2500b483275',
        )

    @property
    def _product_code(self) -> str:
        return self.product_code or self._cfg('SPEDY_PRODUCT_CODE', 'MIDIA-PI')

    @property
    def _product_name(self) -> str:
        return self.product_name or self._cfg(
            'SPEDY_PRODUCT_NAME',
            'Servicos de midia e publicidade digital',
        )

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            'X-Api-Key': self._api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        if not self._api_key:
            raise SpedyAPIError('SPEDY_API_KEY não configurada.')
        url = f'{self._base_url}{path}'
        timeout = kwargs.pop('timeout', self.timeout)
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.exceptions.Timeout as exc:
            raise SpedyAPIError('Timeout ao comunicar com a Spedy.') from exc
        except requests.exceptions.RequestException as exc:
            raise SpedyAPIError(f'Falha de conexão com a Spedy: {exc}') from exc

        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                errors = payload.get('errors') or []
                if errors:
                    detail = '; '.join(
                        e.get('message') or str(e) for e in errors if isinstance(e, dict)
                    ) or detail
            except ValueError:
                pass
            raise SpedyAPIError(
                detail or f'Erro Spedy HTTP {response.status_code}',
                status_code=response.status_code,
                details=detail,
            )
        return response

    def test_connection(self) -> Dict[str, Any]:
        response = self._request('GET', '/companies', timeout=20)
        return response.json()

    def get_service_invoice(self, invoice_id: str) -> Dict[str, Any]:
        response = self._request(
            'GET',
            '/service-invoices',
            params={'page': 1, 'pageSize': 50},
            timeout=30,
        )
        data = response.json()
        for item in data.get('items') or []:
            if str(item.get('id')) == str(invoice_id):
                return item
        raise SpedyAPIError(f'NFS-e Spedy não encontrada: {invoice_id}')

    def build_order_payload(
        self,
        *,
        transaction_id: str,
        customer: Dict[str, Any],
        amount: float,
        observation: str | None = None,
    ) -> Dict[str, Any]:
        if amount <= 0:
            raise SpedyAPIError('Valor da NFS-e deve ser maior que zero.')

        item: Dict[str, Any] = {
            'product': {
                'id': self._product_id,
                'code': self._product_code,
                'name': self._product_name,
            },
            'quantity': 1,
            'amount': round(float(amount), 2),
            'price': round(float(amount), 2),
        }
        if observation:
            item['observation'] = observation[:500]

        return {
            'transactionId': transaction_id,
            'customer': customer,
            'amount': round(float(amount), 2),
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            # Desligado por padrão — não enviar NFS-e por e-mail ao tomador nesta integração.
            'sendEmailToCustomer': self._cfg('SPEDY_SEND_EMAIL_TO_CUSTOMER', False),
            'status': 'approved',
            'autoIssueMode': 'immediately',
            'paymentMethod': 'bankTransfer',
            'profileType': 'producer',
            'items': [item],
        }

    def emit_order(
        self,
        *,
        transaction_id: str,
        customer: Dict[str, Any],
        amount: float,
        observation: str | None = None,
    ) -> Dict[str, Any]:
        payload = self.build_order_payload(
            transaction_id=transaction_id,
            customer=customer,
            amount=amount,
            observation=observation,
        )
        response = self._request('POST', '/orders', json=payload, timeout=self.timeout)
        return response.json()

    def wait_service_invoice(
        self,
        invoice_id: str,
        *,
        max_attempts: int = 15,
        interval_seconds: float = 2.0,
    ) -> Dict[str, Any]:
        last: Dict[str, Any] = {}
        for _ in range(max_attempts):
            last = self.get_service_invoice(invoice_id)
            status = (last.get('status') or '').lower()
            if status in SPEDY_TERMINAL_STATUSES:
                return last
            time.sleep(interval_seconds)
        return last


def _only_digits(value: str | None, *, max_len: int | None = None) -> str:
    digits = re.sub(r'\D', '', value or '')
    if max_len:
        return digits[:max_len]
    return digits


def _normalize_phone(value: str | None) -> str:
    digits = _only_digits(value)
    if len(digits) >= 10:
        return digits[-11:] if len(digits) > 11 else digits
    return '31999999999'


def _resolve_city(cidade: str | None, estado_sigla: str | None) -> tuple[str, str, str]:
    key = (cidade or '').strip().lower()
    if key in _CITY_IBGE:
        code, state = _CITY_IBGE[key]
        name = cidade.strip() if cidade else key.title()
        return code, state, name
    state = (estado_sigla or 'mg').lower()
    code, default_state = _CITY_IBGE['belo horizonte']
    if not estado_sigla:
        state = default_state
    name = (cidade or 'Belo Horizonte').strip()
    return code, state, name


def build_spedy_customer_from_pi(pi: dict, cliente: dict, contato: dict | None) -> Dict[str, Any]:
    """Monta payload de tomador Spedy a partir do PI e cadastro do cliente."""
    cnpj = _only_digits(cliente.get('cnpj'), max_len=14)
    if len(cnpj) != 14:
        raise SpedyAPIError('Cliente do PI sem CNPJ válido para emissão de NFS-e.')

    estado = None
    estado_id = cliente.get('pk_id_aux_estado') or cliente.get('estado')
    if estado_id:
        from aicentralv2 import db
        estado = db.obter_estado_por_id(estado_id)

    city_code, state_code, city_name = _resolve_city(
        cliente.get('cidade'),
        estado.get('sigla') if estado else None,
    )

    phone = _normalize_phone((contato or {}).get('telefone'))
    email = ((contato or {}).get('email') or 'faturamento@example.com').strip()

    return {
        'name': (cliente.get('nome_fantasia') or cliente.get('razao_social') or 'Cliente').strip()[:80],
        'legalName': (cliente.get('razao_social') or cliente.get('nome_fantasia') or 'Cliente').strip()[:80],
        'federalTaxNumber': cnpj,
        'stateTaxNumber': _only_digits(cliente.get('inscricao_estadual')) or None,
        'cityTaxNumber': _only_digits(cliente.get('inscricao_municipal')) or None,
        'email': email[:50],
        'phone': phone,
        'mobilePhone': phone,
        'address': {
            'street': (cliente.get('logradouro') or 'Rua nao informada').strip()[:120],
            'district': (cliente.get('bairro') or 'Centro').strip()[:60],
            'postalCode': _only_digits(cliente.get('cep'), max_len=8) or '30140071',
            'number': str(cliente.get('numero') or 'S/N')[:20],
            'additionalInformation': (cliente.get('complemento') or '')[:120],
            'city': {
                'code': city_code,
                'name': city_name,
                'state': state_code,
            },
            'country': {'name': 'Brasil', 'code': 1058},
        },
    }


def build_spedy_transaction_id(id_pi: int, codigo_pi: str | None = None, *, preview: bool = False) -> str:
    suffix = 'preview' if preview else uuid.uuid4().hex[:8]
    code = re.sub(r'[^A-Za-z0-9_-]', '', (codigo_pi or str(id_pi)))[:24]
    return f'PI-{id_pi}-{code}-{suffix}'


def parse_pi_amount(pi: dict) -> float:
    for key in ('valor_liquido', 'vr_liquido_pi', 'valor_bruto', 'vr_bruto_pi'):
        val = parse_brl_float(pi.get(key))
        if val and val > 0:
            return round(float(val), 2)
    return 0.0


def extract_invoice_from_order(order_payload: Dict[str, Any]) -> Dict[str, Any] | None:
    invoices = order_payload.get('invoices') or []
    if not invoices:
        return None
    inv = invoices[0] or {}
    processing = inv.get('processingDetail') or {}
    return {
        'spedy_order_id': order_payload.get('id'),
        'spedy_invoice_id': inv.get('id'),
        'spedy_status': inv.get('status') or processing.get('status'),
        'spedy_message': processing.get('message'),
        'spedy_environment': inv.get('environmentType') or order_payload.get('environmentType'),
    }


def detect_spedy_environment(base_url: str | None = None) -> str:
    """Retorna 'sandbox' ou 'production' conforme a URL da API Spedy."""
    url = (base_url or '').lower()
    if not url:
        try:
            url = (current_app.config.get('SPEDY_API_BASE_URL') or '').lower()
        except RuntimeError:
            url = 'https://sandbox-api.spedy.com.br/v1'
    return 'sandbox' if 'sandbox' in url else 'production'


def spedy_environment_label(environment: str) -> str:
    return 'Teste (Sandbox)' if environment == 'sandbox' else 'Produção'


def spedy_aplica_status_negocio(environment: str) -> bool:
    """Em sandbox apenas persiste dados Spedy; em produção altera status do PI/NF."""
    return environment == 'production'


def collect_spedy_customer_warnings(
    cliente: dict,
    contato: dict | None,
    customer: Dict[str, Any],
) -> list[str]:
    """Lista avisos quando dados do tomador usam fallbacks ou estão incompletos."""
    warnings: list[str] = []
    if not contato or not (contato.get('email') or '').strip():
        warnings.append(
            'E-mail do tomador será faturamento@example.com (PI sem contato financeiro com e-mail).'
        )
    if not contato or not _only_digits((contato or {}).get('telefone')):
        warnings.append(
            'Telefone do tomador será um número genérico (PI sem contato financeiro com telefone).'
        )
    if not (cliente.get('logradouro') or '').strip():
        warnings.append('Logradouro do cliente não informado — será enviado "Rua nao informada".')
    if not _only_digits(cliente.get('cep'), max_len=8):
        warnings.append('CEP do cliente não informado — será usado CEP padrão 30140071.')
    cidade_key = (cliente.get('cidade') or '').strip().lower()
    if cidade_key and cidade_key not in _CITY_IBGE:
        warnings.append(
            f'Cidade "{cliente.get("cidade")}" sem código IBGE mapeado — '
            f'será usado código de Belo Horizonte ({_CITY_IBGE["belo horizonte"][0]}).'
        )
    if not _only_digits(cliente.get('inscricao_municipal')):
        warnings.append('Inscrição municipal do cliente não informada.')
    return warnings


def build_spedy_emit_preview(
    pi: dict,
    cliente: dict,
    contato: dict | None,
    *,
    spedy: SpedyService | None = None,
) -> Dict[str, Any]:
    """Monta preview da emissão Spedy com payload, avisos e erros de validação."""
    svc = spedy or SpedyService()
    errors: list[str] = []
    warnings: list[str] = []

    if not current_app.config.get('SPEDY_API_KEY'):
        errors.append('SPEDY_API_KEY não configurada.')

    amount = parse_pi_amount(pi)
    if amount <= 0:
        errors.append('PI sem valor líquido/bruto válido para emissão.')

    customer: Dict[str, Any] | None = None
    try:
        customer = build_spedy_customer_from_pi(pi, cliente, contato)
        warnings.extend(collect_spedy_customer_warnings(cliente, contato, customer))
    except SpedyAPIError as exc:
        errors.append(str(exc))

    codigo_pi = pi.get('codigo_pi_cc') or pi.get('codigo_pi_ag')
    obs = f'PI {codigo_pi or pi.get("id_pi")} - {pi.get("titulo_pi") or ""}'.strip()
    environment = detect_spedy_environment(svc._base_url)

    payload: Dict[str, Any] = {
        'transactionId': build_spedy_transaction_id(int(pi['id_pi']), codigo_pi, preview=True),
        'transactionIdNote': 'ID final será gerado ao confirmar a emissão.',
        'amount': amount,
        'customer': customer,
        'product': {
            'id': svc._product_id,
            'code': svc._product_code,
            'name': svc._product_name,
        },
        'observation': obs[:500],
        'sendEmailToCustomer': svc._cfg('SPEDY_SEND_EMAIL_TO_CUSTOMER', False),
        'autoIssueMode': 'immediately',
        'paymentMethod': 'bankTransfer',
        'profileType': 'producer',
    }

    return {
        'ready': len(errors) == 0 and customer is not None,
        'environment': environment,
        'environment_label': spedy_environment_label(environment),
        'updates_pi_status': spedy_aplica_status_negocio(environment),
        'errors': errors,
        'warnings': warnings,
        'pi': {
            'id_pi': pi.get('id_pi'),
            'codigo_pi': codigo_pi or '',
            'titulo': pi.get('titulo_pi') or '',
            'mes_ref_comp': pi.get('mes_ref_comp') or '',
            'valor': amount,
        },
        'payload': payload,
    }


def map_spedy_invoice_to_nf_update(
    invoice: Dict[str, Any],
    *,
    apply_business_status: bool = True,
) -> Dict[str, Any]:
    """Converte resposta Spedy em campos para cadu_pi_nota_fiscal."""
    status = (invoice.get('status') or '').lower()
    processing = invoice.get('processingDetail') or {}
    update: Dict[str, Any] = {
        'spedy_status': status or invoice.get('status'),
        'spedy_message': processing.get('message') or invoice.get('spedy_message'),
        'spedy_environment': invoice.get('environmentType'),
    }

    numero = invoice.get('number')
    if numero is not None and str(numero).strip() not in ('', '0'):
        update['numero_nota'] = str(numero)

    issued_on = invoice.get('issuedOn') or processing.get('on')
    if issued_on:
        try:
            dt = datetime.fromisoformat(str(issued_on).replace('Z', '+00:00'))
            update['data_emissao'] = dt.date().isoformat()
            update['mes_ref_comp'] = f'{dt.month:02d}/{dt.year}'
        except ValueError:
            pass

    amount = invoice.get('amount')
    if amount is not None:
        try:
            update['valor'] = f'{float(amount):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (TypeError, ValueError):
            pass

    if status == 'authorized' and apply_business_status:
        from aicentralv2 import db
        status_nf_id = db.obter_nota_fiscal_status_id_por_descricao('NF Emitida')
        if status_nf_id:
            update['status'] = status_nf_id

    return update
