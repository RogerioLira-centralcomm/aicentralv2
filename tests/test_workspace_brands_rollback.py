from unittest import mock

import psycopg
from flask import Flask, g

from aicentralv2.cadu_workspace import routes as workspace_routes


def _connection(status):
    connection = mock.MagicMock()
    connection.closed = False
    connection.info.transaction_status = status
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = {}
    return connection


def _read_brands(status):
    app = Flask(__name__)
    connection = _connection(status)
    with app.app_context():
        g.db = connection
        with mock.patch.object(workspace_routes, 'get_db', return_value=connection):
            workspace_routes._workspace_brands(12)
    return connection


def test_brand_catalog_does_not_discard_a_healthy_transaction():
    connection = _read_brands(psycopg.pq.TransactionStatus.INTRANS)
    connection.rollback.assert_not_called()


def test_brand_catalog_clears_an_aborted_transaction_before_reading():
    connection = _read_brands(psycopg.pq.TransactionStatus.INERROR)
    connection.rollback.assert_called_once_with()


def test_project_lookup_reads_one_project_instead_of_the_catalog():
    connection = _connection(psycopg.pq.TransactionStatus.IDLE)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{'id': 'p1', 'nome': 'Projeto'}]
    with mock.patch.object(workspace_routes, 'get_db', return_value=connection), \
            mock.patch.object(workspace_routes, '_attach_project_identity', side_effect=lambda _c, records, **_k: records):
        records = workspace_routes._workspace_projects(12, status='todos', only_id='p1')
    sql, params = cursor.execute.call_args.args
    assert 'p.id::text = %s' in sql
    assert params == (12, 'p1')
    assert [item['id'] for item in records] == ['p1']


def test_workspace_project_asks_for_its_own_id_only():
    with mock.patch.object(workspace_routes, '_workspace_projects', return_value=[]) as read:
        assert workspace_routes._workspace_project(12, 'p1') is None
    read.assert_called_once_with(12, status='todos', only_id='p1')


def test_brand_lookup_reads_one_brand_instead_of_the_catalog():
    connection = _connection(psycopg.pq.TransactionStatus.IDLE)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    with mock.patch.object(workspace_routes, 'get_db', return_value=connection):
        workspace_routes._workspace_brands(12, only_id=81)
    sql, params = cursor.execute.call_args_list[0].args
    assert '(%s::int IS NULL OR c.id = %s)' in sql
    assert params == (12, '%%', 81, 81)


def test_workspace_brand_asks_for_its_own_id_only():
    with mock.patch.object(workspace_routes, '_workspace_brands', return_value=[]) as read:
        assert workspace_routes._workspace_brand(12, 81) is None
    read.assert_called_once_with(12, only_id=81)


def test_brand_catalog_metrics_only_aggregate_the_linked_projects():
    connection = _connection(psycopg.pq.TransactionStatus.IDLE)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{'brand_ref': 'studio:81', 'active_projects': 2, 'conversations': 5,
                                     'files': 7, 'file_categories': {'logo': 3}}]
    app = Flask(__name__)
    with app.app_context(), mock.patch.object(workspace_routes, 'get_db', return_value=connection):
        metrics = workspace_routes._workspace_brand_catalog_metrics(12)
    sql, params = cursor.execute.call_args.args
    assert 'linked_projects AS' in sql
    assert 'projeto_id IN (SELECT id FROM linked_projects)' in sql
    assert sql.count('%s') == len(params) == 4
    assert metrics == {'81': {'activeProjects': 2, 'conversationCount': 5, 'fileCount': 7, 'fileCategories': {'logo': 3}}}


def test_brand_detail_caps_the_asset_list():
    connection = _connection(psycopg.pq.TransactionStatus.IDLE)
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    brand = {'id': 81, 'name': 'Acme'}
    with mock.patch.object(workspace_routes, 'get_db', return_value=connection), \
            mock.patch.object(workspace_routes, '_workspace_brands', return_value=[brand]):
        workspace_routes._workspace_brand(12, 81)
    asset_sql = next(call.args[0] for call in cursor.execute.call_args_list if 'FROM cx_client_brand_assets' in call.args[0])
    assert 'LIMIT 500' in asset_sql
