from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_management_routes_are_tenant_scoped_and_transactional():
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')

    assert "def delete_project(project_id):" in routes
    assert "def merge_project(project_id):" in routes
    assert "confirmation.casefold() != expected.casefold()" in routes
    assert "target_id == str(project_id)" in routes
    assert "AND id_cliente = %s" in routes
    assert "connection.rollback()" in routes
    assert "status = 'deletado'" in routes
