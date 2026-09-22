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
