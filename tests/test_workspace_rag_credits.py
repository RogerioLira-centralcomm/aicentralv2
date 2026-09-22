from unittest.mock import MagicMock

import pytest

from aicentralv2.cadu_skills.repository import CaduCreditUnavailable, charge_project_rag


def test_rag_charge_uses_client_credit_lots_and_records_usage():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {'id': 10, 'tokens_amount': 100, 'tokens_used': 60},
        {'id': 11, 'tokens_amount': 100, 'tokens_used': 0},
    ]
    charged = charge_project_rag(cursor, client_id=42, user_id=7, project_id='project-id',
                                 tokens=70, stage='indexacao', idempotency_key='test-rag-charge')
    assert charged == 84  # 70 processed tokens plus the default 20% operating margin.
    sql = '\n'.join(str(call.args[0]) for call in cursor.execute.call_args_list)
    assert 'FOR UPDATE' in sql
    assert 'UPDATE cadu_credits_extras' in sql
    assert 'INSERT INTO cadu_tools_token_usage' in sql
    usage_call = cursor.execute.call_args_list[-1]
    assert len(usage_call.args[1]) == 8
    assert usage_call.args[1][4:7] == (84, 84, 84)


def test_rag_charge_rejects_when_client_has_insufficient_credit():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{'id': 10, 'tokens_amount': 20, 'tokens_used': 10}]
    with pytest.raises(CaduCreditUnavailable, match='Saldo Cadu insuficiente'):
        charge_project_rag(cursor, client_id=42, user_id=7, project_id='project-id',
                           tokens=11, stage='indexacao', idempotency_key='test-rag-insufficient')


def test_project_ux_keeps_rag_processing_out_of_the_project_overview():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    component = (root / 'frontend/cadu-design-system/components/WorkspaceProject.jsx').read_text(encoding='utf-8')
    assert 'Créditos do projeto' not in component
    assert 'Fontes e arquivos' in component
    assert 'sourceErrorMessage' in component
    assert 'Revisar antes de indexar' in component
    assert 'Confirmar decisão' in component


def test_project_detail_has_brand_import_and_quality_workflows():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    component = (root / 'frontend/cadu-design-system/components/WorkspaceProject.jsx').read_text(encoding='utf-8')
    template = (root / 'aicentralv2/templates/cadu_workspace/project_detail_react.html').read_text(encoding='utf-8')
    assert 'ProjectBrandCard' in component
    assert 'ImportBrandDialog' in component
    assert 'Criar e auditar marca' in component
    assert 'Índice do projeto' in component
    assert "'updateBrands': url_for('cadu_workspace.update_project_brands'" in template
    assert "'importBrand': url_for('cadu_workspace.import_project_brand'" in template
