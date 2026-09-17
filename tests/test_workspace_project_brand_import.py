from pathlib import Path


def test_project_brand_import_prioritizes_new_brand_assets():
    root = Path(__file__).resolve().parents[1]
    template = (root / 'aicentralv2/templates/cadu_workspace/project_detail.html').read_text(encoding='utf-8')
    script = (root / 'aicentralv2/static/js/cadu-workspace-project-experience.js').read_text(encoding='utf-8')

    assert 'name="logo"' in template
    assert 'name="images"' in template
    assert 'workspace-brand-dropzone' in template
    assert '<details class="workspace-project-brand-existing">' in template
    assert 'new DataTransfer()' in script
