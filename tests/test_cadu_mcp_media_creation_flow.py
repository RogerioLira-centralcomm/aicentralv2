from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.media_creation_service import generate_studio_image


def test_image_generation_runs_studio_pipeline_and_persists_result():
    context = RequestContext(organization_id=12, client_id=12, user_id=7,
                             conversation_id=None, surface="workspace", capabilities=("workspace",))
    request_id = "12345678-1234-1234-1234-123456789abc"
    args = {"request_id": request_id, "prompt": "Produto sobre fundo claro"}
    store = Mock()
    store.create.return_value = {"id": "session-1", "revision": 1, "metadata": {}}
    store.save.return_value = {"id": "session-1", "revision": 2}
    history = Mock()
    history.claim_image.return_value = {"state": "claimed"}
    modeling = SimpleNamespace(repository=SimpleNamespace(resolve_client_id=lambda *_: 91),
                               credit_ledger=object(), _credits_crm_id=lambda *_: 12)
    directions = {"directions": [{"title": "Produto", "prompt": "Create product image"}], "count": 1}
    app = Flask(__name__)
    app.config["STUDIO_URL"] = "https://studio.example.test"
    with app.app_context(), \
         patch("aicentralv2.cadu_workspace.media_creation_service.CreativeModelingService", return_value=modeling), \
         patch("aicentralv2.cadu_workspace.media_creation_service._session_store", return_value=store), \
         patch("aicentralv2.cadu_workspace.media_creation_service.StudioCreationHistory", return_value=history), \
         patch("aicentralv2.cadu_workspace.media_creation_service.get_db", return_value=object()), \
         patch("aicentralv2.cadu_workspace.media_creation_service.CaduCreditConnector"), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_prompt.optimize_prompt",
               return_value={"optimized_prompt": "Create product image", "detected_language": "pt-BR", "version": "v1"}), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.assert_available"), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.create", return_value=(directions, {})), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.charge", return_value=(2, 100)), \
         patch("aicentralv2.cadu_workspace.media_creation_service.studio_create.create_image",
               return_value={"image_url": "/static/uploads/creative_generated/a.png", "charged_credits": 10,
                             "remaining_credits": 90}):
        result = generate_studio_image(context, args)
    assert result["status"] == "completed"
    assert result["charged_credits"] == 12
    assert result["indexed"] is False
    assert result["studio_url"].startswith("https://studio.example.test/")
    store.accept.assert_called_once()
    assert history.complete_image.call_count == 2
    assert history.complete_image.call_args.args == (request_id, 91, result)
