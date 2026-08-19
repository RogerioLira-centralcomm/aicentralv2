"""Testes da validacao Margem CC 0-100% no fluxo de cotacao."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run import app
import aicentralv2.db as db
from aicentralv2.cotacoes_routes import _perc_margem_cc_fracao_audiencia

TEMPLATE = ROOT / 'aicentralv2' / 'templates' / 'cadu_cotacoes_detalhes.html'

passed = 0
failed = 0
skipped = 0


def ok(name: str, cond: bool, detail: str = '') -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f'  PASS  {name}' + (f' — {detail}' if detail else ''))
    else:
        failed += 1
        print(f'  FAIL  {name}' + (f' — {detail}' if detail else ''))


def skip(name: str, reason: str) -> None:
    global skipped
    skipped += 1
    print(f'  SKIP  {name} — {reason}')


def near(a, b, tol=1e-9) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) < tol


def js_ler_margem_cc_override(raw: str):
    """Replica lerMargemCcOverride do template."""
    if raw is None or str(raw).strip() == '':
        return {'valid': False, 'percent': None}
    s = str(raw).replace('.', '').replace(',', '.') if ',' in str(raw) else str(raw).replace(',', '.')
    try:
        v = float(s)
    except ValueError:
        return {'valid': False, 'percent': None}
    return {'valid': v >= 0 and v <= 100, 'percent': v}


def js_precificacao_satisfeita(mcc_valid: bool, plat: bool, val_tab: float, kpi: bool, xor_inv_vol: bool) -> bool:
    return bool(plat and val_tab > 0 and kpi and mcc_valid and xor_inv_vol)


def test_template_static() -> None:
    print('\n[1] Template HTML (cadu_cotacoes_detalhes.html)')
    text = TEMPLATE.read_text(encoding='utf-8')
    ok('validacao JS 0-100', 'v >= 0 && v <= 100' in text)
    ok('sem validacao antiga 5-30 JS', 'v >= 5 && v <= 30' not in text)
    ok('labels (0–100%) x3', text.count('(0–100%)') >= 3, f'count={text.count("(0–100%)")}')
    ok('sem labels antigos (5–30%)', '(5–30%)' not in text)
    ok('hints 0–100%', text.count('informe manualmente (0–100%)') >= 2, f'count={text.count("informe manualmente (0–100%)")}')
    ok('sem hints antigos', 'informe manualmente (5–30%)' not in text)


def test_js_validation() -> None:
    print('\n[2] Validacao JS simulada (lerMargemCcOverride + precificacaoTesteSatisfeita)')
    for raw, expect_valid in [('0', True), ('35', True), ('100', True), ('101', False), ('-1', False), ('', False)]:
        r = js_ler_margem_cc_override(raw)
        ok(f'lerMargemCcOverride({raw!r})', r['valid'] == expect_valid, f'valid={r["valid"]}')

    ok('precificacao com mcc=0 habilita calcular', js_precificacao_satisfeita(True, True, 10.0, True, True))
    ok('precificacao com mcc=101 bloqueia calcular', not js_precificacao_satisfeita(False, True, 10.0, True, True))


def test_perc_margem_cc_fracao_audiencia() -> None:
    print('\n[3] _perc_margem_cc_fracao_audiencia (cotacoes_routes.py)')
    cotacao = {'client_id': None}
    cases = [
        ('0', 0.0),
        ('35', 0.35),
        ('100', 1.0),
        (0, 0.0),
        (35, 0.35),
        ('35,5', 0.355),
    ]
    for raw, expected in cases:
        got = _perc_margem_cc_fracao_audiencia(cotacao, {'margem_cc': raw})
        ok(f'override {raw!r} -> {expected}', near(got, expected), f'got={got}')

    got101 = _perc_margem_cc_fracao_audiencia(cotacao, {'margem_cc': 101})
    ok('override 101 rejeitado (sem cliente)', got101 is None, f'got={got101}')


def test_calcular_preco_unitario(app_ctx) -> None:
    print('\n[4] calcular_preco_unitario_teste_calculo (db.py)')
    base = dict(
        valor_unitario_tabela=10.0,
        nome_plataforma='Meta',
        cliente_id=1,
        id_resp_comercial=1,
        volume_contratado=1000,
        imposto_percentual_externo=15,
    )
    for mcc, expect_applied, expect_success in [
        (0, 0.0, True),
        (35, 0.35, True),
        (100, 1.0, False),  # soma margens >= 100%
        (101, None, True),  # fallback cadastro
    ]:
        out = db.calcular_preco_unitario_teste_calculo(**base, margem_cc_override=mcc)
        applied = out.get('mcc_override_aplicado')
        if mcc == 101:
            ok(f'override={mcc} ignorado', applied is None and out.get('success'), f'warnings={out.get("warnings")}')
        elif mcc == 100:
            ok(f'override={mcc} aceito mas soma>=100%', out.get('success') is False, out.get('message', ''))
            det = out.get('detalhe') or {}
            ok(f'override={mcc} mcc=1.0 no detalhe', near(det.get('mcc'), 1.0), f'detalhe={det}')
        else:
            ok(f'override={mcc} success', out.get('success') == expect_success, out.get('message', ''))
            ok(f'override={mcc} aplicado', near(applied, expect_applied), f'applied={applied}')


def test_calcular_breakdown(app_ctx, cotacao) -> None:
    print('\n[5] calcular_breakdown_linha_cotacao com margem_cc')
    if not cotacao:
        skip('breakdown linha', 'nenhuma cotacao no banco')
        return
    data_base = {
        'plataforma': 'Meta',
        'objetivo_kpi': 'CPM',
        'valor_unitario_tabela': 10,
        'volume_contratado': 1000,
    }
    for mcc in [0, 35]:
        data = {**data_base, 'margem_cc': mcc}
        try:
            bd = db.calcular_breakdown_linha_cotacao(cotacao, data)
            ok(f'breakdown mcc={mcc}', near(bd.get('perc_margem_cc'), mcc / 100.0), f'perc={bd.get("perc_margem_cc")}')
        except Exception as e:
            ok(f'breakdown mcc={mcc}', False, str(e))


def _find_centralcomm_user_id():
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id_contato_cliente
            FROM tbl_contato_cliente c
            JOIN tbl_cliente cl ON cl.id_cliente = c.pk_id_tbl_cliente
            WHERE UPPER(cl.nome_fantasia) = 'CENTRALCOMM'
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return row['id_contato_cliente'] if row else None


def _find_cotacao_id():
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM cadu_cotacoes ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        return row['id'] if row else None


def test_api_preco_calculo(client, cotacao_id, user_id) -> None:
    print('\n[6] API GET /api/cotacoes/<id>/preco-calculo')
    if not cotacao_id or not user_id:
        skip('API preco-calculo', 'cotacao ou usuario CENTRALCOMM nao encontrado')
        return

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['is_centralcomm'] = True

    for mcc, expect_ok in [(0, True), (35, True), (101, True)]:
        qs = f'plataforma=Meta&valor_unitario_tabela=10&volume_contratado=1000&margem_cc={mcc}'
        resp = client.get(f'/api/cotacoes/{cotacao_id}/preco-calculo?{qs}')
        data = resp.get_json(silent=True) or {}
        if mcc == 101:
            ok(f'API mcc=101 usa cadastro (200)', resp.status_code == 200, f'status={resp.status_code}')
        else:
            ok(f'API mcc={mcc} status 200', resp.status_code == 200, f'status={resp.status_code} body={data.get("message")}')
            if expect_ok and resp.status_code == 200:
                mcc_resp = data.get('mcc') or data.get('mcc_override_aplicado')
                ok(f'API mcc={mcc} refletido', mcc_resp is not None, f'mcc={mcc_resp}')


def test_api_mcc_100(client, cotacao_id, user_id) -> None:
    print('\n[7] API mcc=100 (validacao aceita, calculo falha por soma)')
    if not cotacao_id or not user_id:
        skip('API mcc=100', 'cotacao ou usuario nao encontrado')
        return
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['is_centralcomm'] = True
    resp = client.get(
        f'/api/cotacoes/{cotacao_id}/preco-calculo'
        '?plataforma=Meta&valor_unitario_tabela=10&volume_contratado=1000&margem_cc=100'
    )
    data = resp.get_json(silent=True) or {}
    ok('API mcc=100 retorna 400', resp.status_code == 400, f'status={resp.status_code}')
    ok('API mcc=100 mensagem soma margens', '100%' in (data.get('message') or ''), data.get('message'))


def main() -> int:
    print('=' * 60)
    print('TESTES Margem CC 0-100% — Cotacao')
    print('=' * 60)

    test_template_static()
    test_js_validation()

    with app.app_context():
        test_perc_margem_cc_fracao_audiencia()
        test_calcular_preco_unitario(None)
        cotacao_id = _find_cotacao_id()
        cotacao = db.obter_cotacao_por_id(cotacao_id) if cotacao_id else None
        test_calcular_breakdown(None, cotacao)

        user_id = _find_centralcomm_user_id()
        client = app.test_client()
        test_api_preco_calculo(client, cotacao_id, user_id)
        test_api_mcc_100(client, cotacao_id, user_id)

    print('\n' + '=' * 60)
    print(f'RESULTADO: {passed} passou, {failed} falhou, {skipped} pulou')
    print('=' * 60)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
