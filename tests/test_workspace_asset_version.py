from aicentralv2 import _workspace_asset_version


def test_workspace_asset_version_changes_when_css_changes(tmp_path):
    bundle_dir = tmp_path / "cadu_workspace" / "conversations" / "react"
    bundle_dir.mkdir(parents=True)
    css_path = bundle_dir / "app.css"
    js_path = bundle_dir / "app.js"
    css_path.write_text(".nav { color: red; }", encoding="utf-8")
    js_path.write_text("console.log('workspace')", encoding="utf-8")

    first_version = _workspace_asset_version(str(tmp_path), "39")
    css_path.write_text(".nav { color: green; }", encoding="utf-8")
    second_version = _workspace_asset_version(str(tmp_path), "39")

    assert first_version.startswith("39-")
    assert second_version.startswith("39-")
    assert first_version != second_version


def test_workspace_asset_version_is_stable_when_only_mtime_changes(tmp_path):
    bundle_dir = tmp_path / "cadu_workspace" / "conversations" / "react"
    bundle_dir.mkdir(parents=True)
    css_path = bundle_dir / "app.css"
    js_path = bundle_dir / "app.js"
    css_path.write_text(".nav { color: green; }", encoding="utf-8")
    js_path.write_text("console.log('workspace')", encoding="utf-8")

    first_version = _workspace_asset_version(str(tmp_path), "39")
    css_path.touch()
    js_path.touch()

    assert _workspace_asset_version(str(tmp_path), "39") == first_version


def test_workspace_asset_version_covers_public_and_auth_shells(tmp_path):
    public_css = tmp_path / "css" / "cadu-workspace-public.css"
    auth_js = tmp_path / "cadu_auth" / "app.js"
    public_css.parent.mkdir(parents=True)
    auth_js.parent.mkdir(parents=True)
    public_css.write_text(".hero { color: teal; }", encoding="utf-8")
    auth_js.write_text("console.log('auth-v1')", encoding="utf-8")

    first_version = _workspace_asset_version(str(tmp_path), "release")
    public_css.write_text(".hero { color: green; }", encoding="utf-8")
    public_version = _workspace_asset_version(str(tmp_path), "release")
    auth_js.write_text("console.log('auth-v2')", encoding="utf-8")
    auth_version = _workspace_asset_version(str(tmp_path), "release")

    assert first_version != public_version
    assert public_version != auth_version


def test_workspace_asset_version_without_manual_prefix_is_a_clean_fingerprint(tmp_path):
    public_css = tmp_path / "css" / "cadu-workspace-public.css"
    public_css.parent.mkdir(parents=True)
    public_css.write_text(".hero { display: grid; }", encoding="utf-8")

    version = _workspace_asset_version(str(tmp_path))

    assert len(version) == 12
    assert version.isalnum()
