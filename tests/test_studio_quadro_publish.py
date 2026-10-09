"""Quadro → biblioteca da marca: papel do ativo por tipo e só arquivos gerados pelo Studio."""
import pytest

from aicentralv2.creative_media import studio_quadro


def test_publish_role_by_creation_type():
    assert studio_quadro.publish_role('ilustracao_interface') == 'illustration'
    assert studio_quadro.publish_role('ilustracao') == 'icon'
    assert studio_quadro.publish_role('anuncio') == 'creative'
    assert studio_quadro.publish_role(None) == 'creative'


@pytest.mark.parametrize('url', ['/static/uploads/creative_references/a.png', 'https://evil.example/a.png',
                                 '/static/uploads/creative_generated/../../config.py'])
def test_resolve_rejects_foreign_or_traversal(url):
    with pytest.raises(ValueError):
        studio_quadro.resolve_generated_file(url, object())


def test_illustration_is_a_brand_asset_role():
    from aicentralv2.creative_modeling_service import BRAND_ASSET_ROLES
    from aicentralv2.cadu_workspace.brand_mcp_service import BRAND_ASSET_ROLES as MCP_ROLES
    assert 'illustration' in BRAND_ASSET_ROLES and 'illustration' in MCP_ROLES
