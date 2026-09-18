from pathlib import Path


def test_studio_creation_history_tables_are_part_of_fresh_and_rollout_migrations():
    root = Path(__file__).resolve().parents[1]
    fresh = (root / "migrations" / "add_creative_media.sql").read_text(encoding="utf-8")
    rollout = (root / "migrations" / "add_cadu_studio_creation_history.sql").read_text(encoding="utf-8")

    for table in ("cx_studio_creation_runs", "cx_studio_creation_directions", "cx_studio_project_items", "cx_studio_image_generations"):
        assert table in fresh
        assert table in rollout

    assert "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ" in fresh
    assert "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ" in rollout


def test_deploy_runs_the_studio_creation_history_rollout_before_serving_requests():
    root = Path(__file__).resolve().parents[1]
    deploy = (root / "deploy.sh").read_text(encoding="utf-8")

    assert '"$VENV_PYTHON" migrations/run_add_cadu_studio_creation_history.py' in deploy


def test_creation_history_is_scoped_by_project_and_client():
    source = (Path(__file__).resolve().parents[1] / "aicentralv2" / "creative_media" / "studio_history.py").read_text(encoding="utf-8")

    assert "WHERE r.project_id=%s AND r.client_id=%s" in source
    assert "WHERE project_id=%s AND client_id=%s" in source
    assert "def select_direction" in source
    assert "def add_references" in source
    assert "def add_item" in source
    assert "def claim_image" in source
    assert "def complete_image" in source
    assert "UNIQUE (client_id, request_id)" in (Path(__file__).resolve().parents[1] / "migrations" / "add_creative_media.sql").read_text(encoding="utf-8")


def test_create_route_exposes_project_history_and_direction_selection():
    root = Path(__file__).resolve().parents[1]
    source = (root / "aicentralv2" / "creative_media" / "studio.py").read_text(encoding="utf-8")

    assert "creation-history" in source
    assert "directions/<direction_id>/select" in source
    assert "projects/<ident>/items" in source
    assert "claim_image" in source
    assert "complete_image" in source
