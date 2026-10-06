"""Admin CentralX /cadu/creditos: compra vira lote real e a lista lê o ledger."""
from pathlib import Path
from unittest import mock

from aicentralv2 import db


class _Cursor:
    def __init__(self, package):
        self.sql, self.package, self._last = [], package, ''

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        self._last = sql

    def fetchone(self):
        if 'FROM cadu_client_plans' in self._last:
            return {'id': 5, 'id_cliente': 12}
        if 'FROM cadu_credit_packages' in self._last:
            return self.package
        if 'INSERT INTO cadu_credit_purchases' in self._last:
            return {'id': 9}
        if 'INSERT INTO cadu_credits_extras' in self._last:
            return {'id': 77}
        return None


def _purchase(package):
    cursor = _Cursor(package)
    conn = mock.MagicMock()
    conn.cursor.return_value = cursor
    with mock.patch.object(db, 'get_db', return_value=conn):
        assert db.registrar_compra_creditos(5, 3, created_by=1) == 9
    conn.commit.assert_called_once()
    return cursor


def test_token_package_purchase_creates_lot_and_keeps_legacy_records():
    cursor = _purchase({'id': 3, 'name': 'Extra Essencial', 'credits': 100000, 'price': 49, 'kind': 'tokens'})
    sql = [s for s, _ in cursor.sql]
    assert any('INSERT INTO cadu_credit_purchases' in s for s in sql)
    assert any('INSERT INTO cadu_credit_movements' in s for s in sql)
    lot = [p for s, p in cursor.sql if 'INSERT INTO cadu_credits_extras' in s]
    assert lot == [(12, 100000)]


def test_legacy_image_package_does_not_create_token_lot():
    cursor = _purchase({'id': 3, 'name': 'Pacote 25', 'credits': 25, 'price': 250, 'kind': None})
    assert not any('cadu_credits_extras' in s for s, _ in cursor.sql)


def test_plan_list_reads_usage_from_ledger():
    conn = mock.MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    with mock.patch.object(db, 'get_db', return_value=conn):
        db.obter_planos_clientes({})
    query = cursor.execute.call_args.args[0]
    assert 'cadu_tools_token_usage' in query and 'ledger_tokens_used' in query
    assert 'p.tokens_used_current_month::decimal' not in query
    template = Path('aicentralv2/templates/cadu_planos.html').read_text()
    assert 'plano.ledger_tokens_used' in template
    assert 'plano.tokens_used_current_month' not in template
