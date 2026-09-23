from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

from aicentralv2.cadu_public_mcp.auth import required_scope
from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS, PUBLIC_WRITE_TOOLS
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import ToolInputError, load_builtin_tools
from aicentralv2.cadu_workspace.mcp.tools.media import plan_video, start_studio_session
from aicentralv2.cadu_workspace.media_creation_service import _index_generated_image, generate_studio_image


CONTEXT = RequestContext(organization_id=12, client_id=12, user_id=7,
                         conversation_id=None, surface="workspace", capabilities=("workspace",))


def test_studio_handoff_is_public_write_with_separate_scope():
    names = {item["name"] for item in load_builtin_tools().list(CONTEXT, "customer_agent")}
    assert "media.start_studio_session" in names & PUBLIC_TOOLS & PUBLIC_WRITE_TOOLS
    assert required_scope("media.start_studio_session") == "projects:content_write"


def test_studio_handoff_creates_personal_session_and_real_link():
    app = Flask(__name__)
    app.config.update(STUDIO_URL="https://studio.example.test", TESTING=True)
    created = []

    class Store:
        def create(self, client_id, user_id, payload):
            created.append((client_id, user_id, payload))
            return {"id": "session-123", "status": "draft"}

    modeling = SimpleNamespace(repository=SimpleNamespace(resolve_client_id=lambda *_: 91))
    with app.app_context(), \
         patch("aicentralv2.creative_media.studio._session_store", return_value=Store()), \
         patch("aicentralv2.creative_modeling_service.CreativeModelingService", return_value=modeling):
        result = start_studio_session(CONTEXT, {"kind": "image", "prompt": "Retrato de produto"})
    assert result["studio_url"] == "https://studio.example.test/criar?studio_session_id=session-123&creative_client_id=91"
    assert result["destination"] == "personal"
    assert result["generation_status"] == "not_started" and result["indexed"] is False
    assert created[0][2]["original_prompt"] == "Retrato de produto"


def test_studio_edit_requires_source_before_creating_session():
    with pytest.raises(ToolInputError, match="origem"):
        start_studio_session(CONTEXT, {"kind": "image_edit", "prompt": "Remova o fundo"})


def test_video_plan_uses_official_agent_and_keeps_generation_pending():
    saved = []

    class Store:
        def read(self, *_):
            return {"revision": 1, "metadata": {"source": "cadu_mcp"}}

        def save(self, *args):
            saved.append(args[-1])

    session = {"session_id": "session-video", "studio_url": "https://studio.example.test/video?studio_session_id=session-video",
               "brand_ref": None}
    model = SimpleNamespace(repository=SimpleNamespace(resolve_client_id=lambda *_: 91))
    plan = {"summary": "Movimento sutil", "patch": {"generation_mode": "single_image"}, "warnings": []}
    with patch("aicentralv2.cadu_workspace.mcp.tools.media.start_studio_session", return_value=session), \
         patch("aicentralv2.creative_modeling_service.CreativeModelingService", return_value=model), \
         patch("aicentralv2.cadu_credit_connector.CaduCreditConnector"), \
         patch("aicentralv2.services.cadu_ai_connector.CaduAIConnector"), \
         patch("aicentralv2.creative_media.studio._session_store", return_value=Store()), \
         patch("aicentralv2.creative_media.studio_agent.plan_request", return_value=plan) as planner, \
         patch("aicentralv2.cadu_workspace.mcp.tools.media.operations.execute", side_effect=lambda *args: args[-1]()):
        result = plan_video(CONTEXT, {"request_id": "12345678-1234-1234-1234-123456789abe",
                                      "confirmed_cost": True, "kind": "video",
                                      "prompt": "Anime a imagem", "source_id": "still-1"})
    assert planner.called
    assert saved[0]["metadata"]["video_plan"] == plan
    assert result["generation_status"] == "not_started"


def test_generated_image_uses_project_source_indexer_with_description():
    project = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    storage = SimpleNamespace(read_public_bytes=lambda *_: b"image bytes")
    with patch("aicentralv2.cadu_workspace.project_source_service.prepare_upload",
               return_value={"upload_token": "signed"}) as prepare, \
         patch("aicentralv2.cadu_workspace.project_source_service.save_upload",
               return_value={"source_id": 9, "status": "indexed"}) as save:
        result = _index_generated_image(project, "12345678-1234-1234-1234-123456789abc",
                                        "Produto no estúdio", {"summary": "Luz lateral"},
                                        "/static/uploads/creative_generated/a.png", storage)
    assert result["status"] == "indexed"
    assert prepare.call_args.kwargs["use_as_knowledge"] is None
    assert "Produto no estúdio" in prepare.call_args.kwargs["description"]
    assert save.call_args.args[2].read() == b"image bytes"


def test_mcp_image_passes_compiler_and_director_then_saves_studio_asset():
    app = Flask(__name__)
    app.config.update(STUDIO_URL="https://studio.example.test", TESTING=True)
    accepted = []
    completed = []

    class Store:
        def create(self, *_):
            return {"id": "session-123", "revision": 1, "metadata": {}}

        def save(self, *_):
            return {"id": "session-123", "revision": 2, "metadata": {}}

        def accept(self, *args):
            accepted.append(args[-1])

    class History:
        def __init__(self, *_):
            pass

        def claim_image(self, *_):
            return {"state": "claimed"}

        def complete_image(self, *args):
            completed.append(args[-1])

        def fail_image(self, *_):
            raise AssertionError("Unexpected failure")

    modeling = SimpleNamespace(
        repository=SimpleNamespace(resolve_client_id=lambda *_: 91),
        credit_ledger=object(), storage=object(),
        _credits_crm_id=lambda *_: 12, _estimate=lambda *_: 1,
        _charge_studio_call=lambda **_: {"tokens_cobrados": 2},
    )
    direction = {"title": "Direção principal", "summary": "Produto em destaque", "prompt": "Directed prompt"}
    optimized = {"optimized_prompt": "Optimized prompt", "detected_language": "pt-BR", "version": "v1"}
    with app.app_context(), \
         patch("aicentralv2.cadu_workspace.media_creation_service.CreativeModelingService", return_value=modeling), \
         patch("aicentralv2.cadu_workspace.media_creation_service._session_store", return_value=Store()), \
         patch("aicentralv2.cadu_workspace.media_creation_service.StudioCreationHistory", History), \
         patch("aicentralv2.cadu_workspace.media_creation_service.get_db", return_value=object()), \
         patch("aicentralv2.cadu_workspace.media_creation_service.CaduCreditConnector") as credits, \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_prompt.optimize_prompt", return_value=optimized) as compiler, \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.assert_available"), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.create", return_value=({"directions": [direction]}, {"model": "director"})) as director, \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.charge", return_value=(3, None)), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.create_image", return_value={"image_url": "/static/uploads/creative_generated/a.png", "charged_credits": 10}) as image:
        result = generate_studio_image(CONTEXT, {"request_id": "12345678-1234-1234-1234-123456789abc",
                                                       "prompt": "Produto sobre fundo claro"})
        edited = generate_studio_image(CONTEXT, {"request_id": "12345678-1234-1234-1234-123456789abd",
                                                       "prompt": "Remova o fundo",
                                                       "source_url": "/static/uploads/creative_generated/base.png"})
        edit_payload = image.call_args.args[0]
    assert compiler.called and director.called and image.called
    assert image.call_args.args[0]["prompt"] == "Directed prompt"
    assert accepted[0]["asset_url"] == "/static/uploads/creative_generated/a.png"
    assert result["image_url"] == "https://studio.example.test/static/uploads/creative_generated/a.png"
    assert result["studio_url"].startswith("https://studio.example.test/criar?studio_session_id=session-123")
    assert result["charged_credits"] == 13
    assert result in completed
    assert edited["operation"] == "image_edit"
    assert edited["studio_url"].startswith("https://studio.example.test/imagem?studio_session_id=session-123")
    assert edit_payload["references"][0]["role"] == "primary"
