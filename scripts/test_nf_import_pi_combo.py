"""Testes da combo de PI no modal Importar NF (faturamento)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run import app
import aicentralv2.db as db

TEMPLATE = ROOT / 'aicentralv2' / 'templates' / 'partials' / 'nf_import.html'

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


def _find_user_id():
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


def _find_pi_faturamento_sem_nf():
    rows = db.listar_pis_faturamento_sem_nf()
    return rows[0] if rows else None


def _find_pi_com_nf():
    status = db.obter_status_pi_por_descricao('Faturamento')
    if not status:
        return None
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            '''
            SELECT p.id_pi, p.codigo_pi_cc, p.codigo_pi_ag, p.id_status_pi, p.id_sub_status_pi
            FROM cadu_pi p
            INNER JOIN cadu_pi_nota_fiscal nf ON nf.id_pi = p.id_pi
            WHERE p.id_status_pi = %s
            LIMIT 1
            ''',
            (status['id'],),
        )
        return cur.fetchone()


def test_template_static() -> None:
    print('\n[1] Template nf_import.html')
    text = TEMPLATE.read_text(encoding='utf-8')
    ok('bloco nf_import_pi_selecao', 'id="nf_import_pi_selecao"' in text)
    ok('select nf_import_pi_select', 'id="nf_import_pi_select"' in text)
    ok('fetch faturamento-sem-nf', '/api/cadu_pi/faturamento-sem-nf' in text)
    ok('flag pi_selecionado_manual', 'pi_selecionado_manual' in text)
    ok('id_pi_contexto no payload', 'id_pi_contexto' in text)
    ok('showNfImportPiSelecao', 'function showNfImportPiSelecao' in text)


def test_db_listar_pis() -> None:
    print('\n[2] db.listar_pis_faturamento_sem_nf()')
    rows = db.listar_pis_faturamento_sem_nf()
    ok('retorna lista', isinstance(rows, list), f'count={len(rows)}')
    if rows:
        row = rows[0]
        ok('campo id_pi', row.get('id_pi') is not None)
        ok('campo titulo_pi', 'titulo_pi' in row)
        ok('campo cliente_nome', 'cliente_nome' in row)
        ok('sem nf vinculada', not db.pi_possui_nota_fiscal(row['id_pi']))
    else:
        skip('campos do primeiro PI', 'nenhum PI em faturamento sem NF no banco')


def test_db_pi_possui_nf() -> None:
    print('\n[3] db.pi_possui_nota_fiscal()')
    sem_nf = _find_pi_faturamento_sem_nf()
    com_nf = _find_pi_com_nf()
    if sem_nf:
        ok('PI sem NF -> False', db.pi_possui_nota_fiscal(sem_nf['id_pi']) is False)
    else:
        skip('PI sem NF', 'nenhum candidato')
    if com_nf:
        ok('PI com NF -> True', db.pi_possui_nota_fiscal(com_nf['id_pi']) is True)
    else:
        skip('PI com NF', 'nenhum PI faturamento com NF no banco')


def test_api_faturamento_sem_nf(client, user_id) -> None:
    print('\n[4] GET /api/cadu_pi/faturamento-sem-nf')
    if not user_id:
        skip('API faturamento-sem-nf', 'usuario CENTRALCOMM nao encontrado')
        return
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['is_centralcomm'] = True
    resp = client.get('/api/cadu_pi/faturamento-sem-nf')
    data = resp.get_json(silent=True) or {}
    ok('status 200', resp.status_code == 200, f'status={resp.status_code}')
    ok('items e lista', isinstance(data.get('items'), list), f'count={len(data.get("items") or [])}')
    if data.get('items'):
        item = data['items'][0]
        ok('item tem id_pi', item.get('id_pi') is not None)
        ok('item tem codPi', 'codPi' in item)
        ok('item tem titulo_pi', 'titulo_pi' in item)


def test_api_requires_login(client) -> None:
    print('\n[5] API exige login')
    resp = client.get('/api/cadu_pi/faturamento-sem-nf')
    ok('sem sessao redireciona ou 401/302', resp.status_code in (302, 401), f'status={resp.status_code}')


def _minimal_pdf_bytes() -> bytes:
    return b"""%PDF-1.4
1 0 obj<<>>endobj
2 0 obj<< /Length 44 >>stream
BT /F1 12 Tf 100 700 Td (PI 999999.9 TEST) Tj ET
endstream
endobj
3 0 obj<< /Type /Catalog /Pages 4 0 R >>endobj
4 0 obj<< /Type /Pages /Kids [5 0 R] /Count 1 >>endobj
5 0 obj<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] /Contents 2 0 R >>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000052 00000 n
0000000146 00000 n
0000000205 00000 n
0000000268 00000 n
trailer<< /Size 6 /Root 3 0 R >>
startxref
365
%%EOF
"""


def test_validacao_pi_flags() -> None:
    print('\n[6] Validacao PI — flags pi_requer_selecao')
    from aicentralv2.services.nf_pdf_extraction import normalize_codigo_pi, codigo_pi_equivale

    def simular_validacao(pi_row, extracted, confirmar=False):
        erros = []
        avisos = []
        detalhes = {'pi_ok': False, 'valor_ok': True}
        pi_codes = [
            c for c in (
                (pi_row.get('codigo_pi_cc') or '').strip(),
                (pi_row.get('codigo_pi_ag') or '').strip(),
            ) if c
        ]
        cod_pi_esperado = pi_row.get('codigo_pi_cc') or pi_row.get('codigo_pi_ag') or ''
        cod_nf = normalize_codigo_pi(extracted.get('codigo_pi'), extracted.get('discriminacao'))
        if pi_codes:
            if not cod_nf:
                erros.append('codigo ausente')
            elif not any(codigo_pi_equivale(cod_nf, pc) for pc in pi_codes):
                if confirmar:
                    erros.append('mismatch')
                else:
                    avisos.append('mismatch')
                    detalhes['pi_requer_edicao'] = True
            else:
                detalhes['pi_ok'] = True
        ok_val = len(erros) == 0
        if not ok_val:
            detalhes['pi_requer_selecao'] = True
        elif detalhes.get('pi_requer_edicao') or not detalhes.get('pi_ok'):
            detalhes['pi_requer_selecao'] = True
        return ok_val, erros, avisos, detalhes

    pi_a = {'codigo_pi_cc': '11111', 'codigo_pi_ag': ''}
    ok_val, erros, avisos, det = simular_validacao(pi_a, {'codigo_pi': '22222'})
    ok('codigo diverge -> pi_requer_selecao', det.get('pi_requer_selecao') is True, str(det))
    ok('codigo diverge -> nao bloqueia analise', ok_val is True and not erros)

    ok_val2, erros2, _, det2 = simular_validacao(pi_a, {'codigo_pi': None})
    ok('codigo ausente -> pi_requer_selecao', det2.get('pi_requer_selecao') is True, str(det2))
    ok('codigo ausente -> erros na validacao', len(erros2) > 0)

    ok_val3, _, _, det3 = simular_validacao(pi_a, {'codigo_pi': '11111'})
    ok('codigo confere -> pi_ok', det3.get('pi_ok') is True)
    ok('codigo confere -> sem pi_requer_selecao', not det3.get('pi_requer_selecao'))


def test_api_analisar_nao_bloqueia(client, user_id, pi_row) -> None:
    print('\n[7] POST analisar — nao retorna inconsistencia bloqueante')
    if not user_id:
        skip('analisar pi_requer_selecao', 'usuario nao encontrado')
        return
    if not pi_row:
        skip('analisar pi_requer_selecao', 'nenhum PI faturamento sem NF')
        return

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['is_centralcomm'] = True

    data = {
        'id_pi': str(pi_row['id_pi']),
        'file': (io.BytesIO(_minimal_pdf_bytes()), 'nota_teste.pdf'),
    }
    resp = client.post(
        '/api/notas-fiscais/importar/analisar',
        data=data,
        content_type='multipart/form-data',
    )
    body = resp.get_json(silent=True) or {}
    ok('analisar status 200', resp.status_code == 200, f'status={resp.status_code} body={body.get("error")}')
    items = body.get('items') or []
    if not items:
        skip('resposta analisar', 'sem items')
        return
    item = items[0]
    ok('analisar success', item.get('success') is True, item.get('error'))
    ok('nao bloqueia inconsistencia', item.get('inconsistencia') is not True)
    ok('temp_id presente', bool(item.get('temp_id')), f'temp_id={item.get("temp_id")}')
    val = item.get('validacao') or {}
    ok(
        'validacao retornada',
        'pi_ok' in val or val.get('pi_requer_selecao') or val.get('pi_requer_edicao'),
        f'validacao={val}',
    )


def main() -> int:
    print('=' * 60)
    print('TESTES — Combo PI no Importar NF')
    print('=' * 60)

    test_template_static()

    with app.app_context():
        test_db_listar_pis()
        test_db_pi_possui_nf()
        user_id = _find_user_id()
        pi_row = _find_pi_faturamento_sem_nf()
        client = app.test_client()
        test_api_requires_login(client)
        test_api_faturamento_sem_nf(client, user_id)
        test_validacao_pi_flags()
        test_api_analisar_nao_bloqueia(client, user_id, pi_row)

    print('\n' + '=' * 60)
    print(f'RESULTADO: {passed} passou, {failed} falhou, {skipped} pulou')
    print('=' * 60)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
