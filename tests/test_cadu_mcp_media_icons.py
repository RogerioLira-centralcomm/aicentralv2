from unittest.mock import patch

import pytest
from flask import Flask

from aicentralv2.cadu_public_mcp.auth import required_scope
from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS
from aicentralv2.cadu_public_mcp.routes import _public_catalog
from aicentralv2.cadu_public_mcp.routes import bp
from aicentralv2.cadu_public_mcp.auth import PublicMcpAuthError, PublicMcpPrincipal
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import ToolInputError, load_builtin_tools
from aicentralv2.cadu_workspace.mcp.tools.media import generate_image, get_media_job, list_media_jobs
from aicentralv2.cadu_workspace.project_resource_service import _refresh_link_icons, public_link_icon


class Cursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return next(self.responses)

    def fetchone(self):
        return next(self.responses)


class Database:
    def __init__(self, cursor):
        self.query_cursor = cursor

    def cursor(self):
        return self.query_cursor


CONTEXT = RequestContext(organization_id=12, client_id=12, user_id=7,
                         conversation_id=None, surface="workspace", capabilities=("workspace",))


def test_link_icon_contract_excludes_private_worker_metadata():
    icon = public_link_icon({"icon_status": "ready", "icon_url": "/static/media/a.webp",
                             "icon_source": "image2", "icon_prompt": "private", "icon_error": "secret"})
    assert icon == {"status": "ready", "url": "/static/media/a.webp", "source": "image2",
                    "mime_type": "image/webp"}
    assert public_link_icon({"icon_status": "ready", "icon_url": "file:///secret"})["url"] == ""
    assert public_link_icon({"icon_status": "queued", "icon_url": "/static/media/a.webp"})["url"] == ""


def test_registry_link_icon_is_refreshed_from_live_project_link():
    resource = {"source_system": "workspace", "source_id": "link:9", "metadata": {"provider": "trello", "icon": {"status": "queued"}}}
    cursor = Cursor([[{"id": "9", "icon_metadata": {"icon_status": "ready", "icon_url": "/static/media/a.webp"}}]])
    with patch("aicentralv2.cadu_workspace.project_resource_service._relation", return_value=True), \
         patch("aicentralv2.cadu_workspace.project_resource_service._columns", return_value={"icon_metadata"}):
        _refresh_link_icons(cursor, 12, "ci:project-1", [resource])
    assert cursor.calls[0][1] == (12, "project-1", ["9"])
    assert resource["metadata"]["icon"]["status"] == "ready"


def test_media_generate_image_uses_canonical_billing_and_idempotency():
    request_id = "12345678-1234-1234-1234-123456789abc"
    arguments = {"request_id": request_id, "confirmed": True, "confirmed_cost": True,
                 "prompt": "Produto sobre fundo claro"}
    with patch("aicentralv2.cadu_workspace.media_creation_service.generate_studio_image",
               return_value={"image_url": "https://studio.test/static/a.png", "project_link_status": "not_linked"}) as create, \
         patch("aicentralv2.cadu_workspace.mcp.tools.media.operations.execute", side_effect=lambda *args: args[-1]()) as execute:
        result = generate_image(CONTEXT, arguments)
    assert create.call_args.args == (CONTEXT, arguments)
    assert execute.call_args.args[0] == request_id
    assert result["project_link_status"] == "not_linked"


def test_media_tools_are_public_and_use_resource_read_scope():
    names = {tool["name"] for tool in load_builtin_tools().list(CONTEXT, "customer_agent")}
    assert {"media.list_jobs", "media.get_job"} <= names & PUBLIC_TOOLS
    assert required_scope("media.get_job") == "resources:read"


def test_paid_media_generation_is_absent_from_public_catalog():
    principal = PublicMcpPrincipal("key", 12, 7, "codex", "Teste",
                                   ("projects:content_write", "resources:read"), CONTEXT)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.can_purchase_credits", return_value=False):
        tools = {item["name"]: item for item in _public_catalog(principal)}
    assert {"media.generate_image", "media.edit_image", "media.plan_video"}.isdisjoint(tools)
    assert "media.creation_capabilities" in tools


def test_list_media_jobs_is_user_scoped_and_omits_storage_details():
    cursor = Cursor([[{"id": 3, "public_id": "job-3", "status": "completed"}],
                     [{"job_id": 3, "public_id": "asset-1", "kind": "master", "mime_type": "video/mp4",
                       "storage_key": "/private/video.mp4", "provenance": {"secret": "value"}}]])
    app = Flask(__name__)
    app.config["WORKSPACE_URL"] = "https://workspace.example.test"
    with app.app_context(), patch("aicentralv2.cadu_workspace.mcp.tools.media.get_db", return_value=Database(cursor)):
        result = list_media_jobs(CONTEXT, {"limit": 10})
    assert cursor.calls[0][1] == (12, 7, 10)
    assert "brand.crm_client_id=%s" in cursor.calls[0][0]
    assert result["jobs"][0]["assets"][0]["content_access"] == "mcp_bearer"
    assert result["jobs"][0]["assets"][0]["download_url"].startswith("https://workspace.example.test/")
    assert "storage_key" not in str(result)
    assert "secret" not in str(result)


def test_get_media_job_rejects_other_users_job():
    cursor = Cursor([None])
    with patch("aicentralv2.cadu_workspace.mcp.tools.media.get_db", return_value=Database(cursor)):
        with pytest.raises(ToolInputError):
            get_media_job(CONTEXT, {"job_id": "other-user-job"})
    assert cursor.calls[0][1] == ("other-user-job", 12, 7)
    assert "brand.crm_client_id=%s" in cursor.calls[0][0]


def test_media_binary_download_requires_bearer_scope_and_ownership(tmp_path):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.register_blueprint(bp)
    principal = PublicMcpPrincipal("key", 12, 7, "codex", "Teste", ("resources:read",), CONTEXT)
    cursor = Cursor([])
    cursor.fetchone = lambda: {"storage_key": str(tmp_path / "video.mp4"), "mime_type": "video/mp4"}
    path = tmp_path / "video.mp4"
    path.write_bytes(b"video")
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.db.get_db", return_value=Database(cursor)), \
         patch("aicentralv2.creative_media.storage.read_path", return_value=path):
        response = app.test_client().get("/mcp/cadu/v1/media/assets/asset-1/content")
    assert response.status_code == 200
    assert response.data == b"video"
    assert cursor.calls[0][1] == ("asset-1", 12, 7)
    assert "brand.crm_client_id=%s" in cursor.calls[0][0]


def test_media_binary_download_denies_unauthenticated_or_foreign_asset():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.register_blueprint(bp)
    principal = PublicMcpPrincipal("key", 12, 7, "codex", "Teste", ("resources:read",), CONTEXT)
    client = app.test_client()
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", side_effect=PublicMcpAuthError("invalid")):
        assert client.get("/mcp/cadu/v1/media/assets/asset-1/content").status_code == 401
    cursor = Cursor([])
    cursor.fetchone = lambda: None
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.db.get_db", return_value=Database(cursor)):
        assert client.get("/mcp/cadu/v1/media/assets/asset-1/content").status_code == 404
