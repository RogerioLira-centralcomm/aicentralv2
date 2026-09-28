"""Configura fiscal do produto MIDIA-PI na Spedy (sandbox) e valida código/ISS."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aicentralv2 import create_app
from aicentralv2.services.spedy_service import SpedyAPIError, SpedyService, detect_spedy_environment

BH_IBGE = '3106200'
TARGET_ACTIVITY_CODE = '17.25.01'
TARGET_ISS_PERCENT = 5.0
TARGET_FISCAL_DESCRIPTION = 'Inserção de textos'


def _resolve_product_snapshot(spedy: SpedyService, product_id: str) -> Dict[str, Any]:
    """GET por id — inclui serviceInvoiceSettings (a listagem paginada não traz)."""
    return spedy.get_product(product_id)


def _code_fields_from_bh_example(example: Any, target_code: str) -> Dict[str, str]:
    """Infere cityServiceCode vs federalServiceCode a partir do exemplo municipal."""
    fields: Dict[str, str] = {}
    if not isinstance(example, dict):
        return {'cityServiceCode': target_code, 'federalServiceCode': target_code}

    candidates: list[dict] = [example]
    for key in ('examples', 'items'):
        extra = example.get(key)
        if isinstance(extra, list):
            candidates.extend(x for x in extra if isinstance(x, dict))

    for payload in candidates:
        federal = payload.get('federalServiceCode')
        city = payload.get('cityServiceCode')
        if federal:
            fields.setdefault('federalServiceCode', str(federal))
        if city:
            fields.setdefault('cityServiceCode', str(city))

    sample_federal = fields.get('federalServiceCode', '')
    sample_city = fields.get('cityServiceCode', '')

    if target_code in sample_city or sample_city.endswith(target_code.replace('.', '')):
        fields['cityServiceCode'] = target_code
    elif target_code in sample_federal:
        fields['federalServiceCode'] = target_code
    else:
        # BH: 17.25.01 é código de atividade municipal típico
        fields['cityServiceCode'] = target_code
        if not fields.get('federalServiceCode'):
            base = target_code.rsplit('.', 1)[0] if '.' in target_code else target_code
            fields['federalServiceCode'] = base

    return fields


def build_product_put_body(
    current: Dict[str, Any],
    *,
    code_fields: Dict[str, str],
    fiscal_description: str,
) -> Dict[str, Any]:
    settings = dict(current.get('serviceInvoiceSettings') or {})
    settings['fiscalDescription'] = fiscal_description
    for key, value in code_fields.items():
        if value:
            settings[key] = value

    body: Dict[str, Any] = {
        'name': current.get('name') or 'Servicos de midia e publicidade digital',
        'invoiceModel': current.get('invoiceModel') or 'serviceInvoice',
        'serviceInvoiceSettings': settings,
    }
    if current.get('code') is not None:
        body['code'] = current['code']
    if current.get('price') is not None:
        body['price'] = current['price']
    if current.get('warrantyDays') is not None:
        body['warrantyDays'] = current['warrantyDays']
    if current.get('productInvoiceSettings'):
        body['productInvoiceSettings'] = current['productInvoiceSettings']
    return body


def _fiscal_summary(product: Dict[str, Any]) -> Dict[str, Any]:
    settings = product.get('serviceInvoiceSettings') or {}
    return {
        'code': product.get('code'),
        'name': product.get('name'),
        'invoiceModel': product.get('invoiceModel'),
        'federalServiceCode': settings.get('federalServiceCode'),
        'cityServiceCode': settings.get('cityServiceCode'),
        'fiscalDescription': settings.get('fiscalDescription'),
        'cnaeCode': settings.get('cnaeCode'),
        'nbsCode': settings.get('nbsCode'),
    }


def _invoice_fiscal_check(invoice: Dict[str, Any]) -> Dict[str, Any]:
    total = invoice.get('totals') or invoice.get('total') or {}
    iss_rate = total.get('issRate')
    return {
        'id': invoice.get('id'),
        'status': invoice.get('status'),
        'federalServiceCode': invoice.get('federalServiceCode'),
        'cityServiceCode': invoice.get('cityServiceCode'),
        'description': (invoice.get('description') or '')[:120],
        'issRate': iss_rate,
        'issAmount': total.get('issAmount'),
    }


def validate_product_fiscal(summary: Dict[str, Any], target_code: str) -> list[str]:
    issues: list[str] = []
    city = (summary.get('cityServiceCode') or '').strip()
    federal = (summary.get('federalServiceCode') or '').strip()
    if target_code not in (city, federal):
        issues.append(
            f'Código {target_code} não encontrado em cityServiceCode ({city!r}) '
            f'nem federalServiceCode ({federal!r}).'
        )
    desc = (summary.get('fiscalDescription') or '').strip()
    if TARGET_FISCAL_DESCRIPTION.lower() not in desc.lower():
        issues.append(f'fiscalDescription esperada contendo {TARGET_FISCAL_DESCRIPTION!r}, veio {desc!r}.')
    return issues


def validate_iss_rate(iss_rate: Any) -> list[str]:
    if iss_rate is None:
        return [
            'issRate não disponível na última NFS-e — ajuste a regra de tributação NFS-e '
            f'no painel Spedy para {TARGET_ISS_PERCENT}% ou emita nota de teste.'
        ]
    try:
        rate = float(iss_rate)
    except (TypeError, ValueError):
        return [f'issRate inválido: {iss_rate!r}']
    if abs(rate - TARGET_ISS_PERCENT) > 0.01:
        return [
            f'issRate={rate} (esperado {TARGET_ISS_PERCENT}). '
            'Atualize a regra de tributação vinculada ao produto no painel Spedy.'
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description='Configura produto Spedy MIDIA-PI (fiscal BH).')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Não envia PUT; apenas exibe payload e validações.',
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        product_id = app.config.get('SPEDY_PRODUCT_ID', '')
        base_url = app.config.get('SPEDY_API_BASE_URL', '')
        env = detect_spedy_environment(base_url)
        print('Ambiente:', env, '|', base_url)
        print('SPEDY_PRODUCT_ID:', product_id)

        if env != 'sandbox':
            print('AVISO: ambiente não é sandbox; abortando por segurança.')
            return 1

        spedy = SpedyService()
        if not spedy._api_key:
            print('SPEDY_API_KEY ausente.')
            return 1

        try:
            bh_example = spedy.get_service_invoice_city_payload_example(BH_IBGE)
        except SpedyAPIError as exc:
            print('payload-example BH falhou:', exc)
            bh_example = {}

        print('\n--- payload-example BH (3106200) ---')
        print(json.dumps(bh_example, ensure_ascii=False, indent=2, default=str))

        code_fields = _code_fields_from_bh_example(bh_example, TARGET_ACTIVITY_CODE)
        print('\n--- mapeamento de códigos ---')
        print(json.dumps(code_fields, ensure_ascii=False, indent=2))

        try:
            before = _resolve_product_snapshot(spedy, product_id)
        except SpedyAPIError as exc:
            print('GET produto falhou:', exc)
            return 2

        print('\n--- produto ANTES ---')
        before_summary = _fiscal_summary(before)
        print(json.dumps(before_summary, ensure_ascii=False, indent=2))

        put_body = build_product_put_body(
            before,
            code_fields=code_fields,
            fiscal_description=TARGET_FISCAL_DESCRIPTION,
        )
        print('\n--- PUT body ---')
        print(json.dumps(put_body, ensure_ascii=False, indent=2))

        if args.dry_run:
            print('\n(dry-run: PUT não enviado)')
            return 0

        try:
            spedy.update_product(put_body, product_id=product_id)
        except SpedyAPIError as exc:
            print('PUT produto falhou:', exc)
            return 3

        try:
            after = _resolve_product_snapshot(spedy, product_id)
        except SpedyAPIError as exc:
            print('GET pós-PUT falhou:', exc)
            return 4

        print('\n--- produto DEPOIS ---')
        after_summary = _fiscal_summary(after)
        print(json.dumps(after_summary, ensure_ascii=False, indent=2))

        product_issues = validate_product_fiscal(after_summary, TARGET_ACTIVITY_CODE)
        print('\n--- validação produto ---')
        if product_issues:
            for issue in product_issues:
                print('PENDÊNCIA:', issue)
        else:
            print('OK: código de atividade e descrição fiscal no produto.')

        try:
            invoices_page = spedy.list_service_invoices(page=1, page_size=10)
            items = invoices_page.get('items') or []
        except SpedyAPIError as exc:
            print('Listagem NFS-e falhou:', exc)
            items = []

        print('\n--- última NFS-e (se houver) ---')
        iss_issues: list[str] = []
        if items:
            latest = items[0]
            inv_id = latest.get('id')
            if inv_id:
                try:
                    latest = spedy.get_service_invoice_by_id(str(inv_id))
                except SpedyAPIError:
                    pass
            check = _invoice_fiscal_check(latest)
            print(json.dumps(check, ensure_ascii=False, indent=2, default=str))
            iss_issues = validate_iss_rate(check.get('issRate'))
        else:
            iss_issues = validate_iss_rate(None)
            print('Nenhuma NFS-e listada para conferir issRate.')

        print('\n--- validação ISS ---')
        if iss_issues:
            for issue in iss_issues:
                print('PENDÊNCIA:', issue)
        else:
            print(f'OK: issRate = {TARGET_ISS_PERCENT}% na última NFS-e.')

        return 1 if (product_issues or iss_issues) else 0


if __name__ == '__main__':
    sys.exit(main())
