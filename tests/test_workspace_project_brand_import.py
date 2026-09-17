from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2.cadu_workspace.routes import _ensure_brand_audit_credit


def test_project_brand_import_prioritizes_new_brand_assets():
    root = Path(__file__).resolve().parents[1]
    template = (root / 'aicentralv2/templates/cadu_workspace/project_detail.html').read_text(encoding='utf-8')
    script = (root / 'aicentralv2/static/js/cadu-workspace-project-experience.js').read_text(encoding='utf-8')

    assert 'name="logo"' in template
    assert 'name="images"' in template
    assert 'workspace-brand-dropzone' in template
    assert '<details class="workspace-project-brand-existing">' in template
    assert 'new DataTransfer()' in script


def test_project_brand_audit_reads_balance_through_the_shared_connector():
    with patch('aicentralv2.cadu_workspace.routes.CaduCreditConnector') as connector:
        connector.return_value.balance.return_value = 100

        _ensure_brand_audit_credit(42)

    connector.return_value.balance.assert_called_once_with(42)


def test_project_brand_audit_retries_a_transient_credit_read_once():
    app = Flask(__name__)
    with app.app_context():
        with patch('aicentralv2.cadu_workspace.routes.CaduCreditConnector') as connector, \
             patch('aicentralv2.cadu_workspace.routes.get_db') as get_db, \
             patch('aicentralv2.cadu_workspace.routes.close_db') as close_db:
            connector.return_value.balance.side_effect = [RuntimeError('connection reset'), 100]

            _ensure_brand_audit_credit(42)

        assert connector.return_value.balance.call_count == 2
        get_db.return_value.rollback.assert_called_once_with()
        close_db.assert_called_once_with()
