"""MCP image workflow using the same prompt compiler, director and Studio store as the UI."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from json import dumps
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from werkzeug.datastructures import FileStorage

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from ..creative_format_lab.brand_context import build_brand_context, select_brand_logo
from ..creative_media import studio_create, studio_prompt
from ..creative_media.studio import _session_store
from ..creative_media.studio_history import StudioCreationHistory
from ..creative_modeling_service import CreativeModelingService
from ..db import get_db
from ..product_domains import product_url
from ..services.openrouter_service import chat_completion
from .agent_v2.contracts import RequestContext
from .mcp.registry import ToolInputError


def _studio_url(client_id: int, session_id: str, source_url: str = "") -> str:
    path = "/imagem" if source_url else "/criar"
    params = {"studio_session_id": session_id, "creative_client_id": client_id}
    if source_url:
        params["source"] = source_url
    return product_url("studio", f"{path}?{urlencode(params)}")


def _index_generated_image(context: RequestContext, request_id: str, prompt: str,
                           direction: dict, image_url: str, storage) -> dict:
    """Store Workspace project source only after Studio has a real image."""
    from . import project_source_service

    data = storage.read_public_bytes(image_url)
    if not data:
        raise ValueError("A imagem criada não pôde ser lida para indexação.")
    suffix = Path(image_url).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[suffix]
    description = (f"Imagem gerada no Cadu Studio para o projeto. Pedido original: {prompt}. "
                   f"Direção criativa: {direction.get('summary') or direction.get('title') or ''}.")[:4000]
    upload = project_source_service.prepare_upload(
        context, request_id=request_id, use_as_knowledge=None,
        category="brand_asset" if context.brand_ref else "reference", description=description)
    file = FileStorage(stream=BytesIO(data), filename=f"cadu-studio-{request_id}{suffix}", content_type=mime)
    return project_source_service.save_upload(context, upload["upload_token"], file)


def generate_studio_image(context: RequestContext, arguments: dict) -> dict:
    """Compile, direct, render, persist and return a Studio image to an agent."""
    request_id = str(UUID(str(arguments["request_id"])))
    original = str(arguments["prompt"]).strip()
    source_url = str(arguments.get("source_url") or "").strip()
    is_edit = bool(source_url)
    brand_id = arguments.get("brand_id")
    modeling = CreativeModelingService()
    personal_client_id = modeling.repository.resolve_client_id(context.client_id, "crm")
    if not personal_client_id:
        raise ToolInputError("Nenhum perfil Studio pertence a esta conta.")
    personal_client_id = int(personal_client_id)
    studio_client_id = int(brand_id or personal_client_id)
    store = _session_store(studio_client_id)
    history = StudioCreationHistory(get_db())
    fingerprint = sha256(dumps({"prompt": original, "brand_id": brand_id,
                                "source_url": source_url,
                                "aspect_ratio": arguments.get("aspect_ratio", "1:1"),
                                "quality": arguments.get("quality", "padrão")},
                               sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    # The account's personal shelf uses the canonical creative client even
    # when a linked brand supplies the identity for this particular image.
    claim = history.claim_image(request_id, fingerprint, personal_client_id, context.user_id, "", original)
    if claim["state"] == "completed":
        return claim["result"]
    if claim["state"] == "pending":
        raise ToolInputError("Esta imagem já está em criação. Consulte novamente em alguns instantes.")
    try:
        session = store.create(studio_client_id, context.user_id, {
            "studio_type": "edit" if is_edit else "create", "title": original[:100], "original_prompt": original,
            "metadata": {"source": "cadu_mcp", "media_kind": "image_edit" if is_edit else "ad" if brand_id else "image",
                         "workspace_project_ref": context.project_ref or "",
                         "source_url": source_url,
                         "mcp_request_id": request_id},
        })
    except Exception as error:
        history.fail_image(request_id, personal_client_id, str(error))
        raise
    session_id = session["id"]
    studio_url = _studio_url(studio_client_id, session_id, source_url)
    try:
        brand_context = (select_brand_logo(build_brand_context(modeling.get_client(studio_client_id)), None)
                         if brand_id else {})
    except Exception as error:
        history.fail_image(request_id, personal_client_id, str(error))
        raise
    provider_calls = []

    def metered_prompt(*args, **kwargs):
        response = chat_completion(*args, **kwargs)
        provider_calls.append(response)
        return response

    try:
        payer = modeling._credits_crm_id(studio_client_id) or studio_client_id
        CaduCreditConnector(modeling.credit_ledger).authorize(
            CreditActor.from_values(payer, context.user_id), 1100)
        optimized = studio_prompt.optimize_prompt(
            original, mode="edit" if is_edit else "create", context={"brand_context": brand_context,
                                               "source_url": source_url,
                                               "aspect_ratio": arguments.get("aspect_ratio", "1:1")},
            text_callable=metered_prompt)
        prompt_charge = {}
        if provider_calls:
            prompt_charge = modeling._charge_studio_call(
                client_id=studio_client_id, user_id=context.user_id,
                idempotency_key=f"studio:mcp-prompt:{request_id}",
                stage="prompt_optimization", provider_result=provider_calls[-1],
                fallback_cost=modeling._estimate("prompt"), media=False,
                metadata={"studio_session_id": session_id, "studio_root_session_id": session_id}) or {}
        references = [{"url": source_url, "source": "user", "role": "primary",
                       "label": "Imagem principal a preservar"}] if is_edit else []
        director_context = {"brand_context": brand_context, "references": references,
                            "creation_intent": "branded_creative" if brand_id else "neutral_asset",
                            "format": arguments.get("aspect_ratio", "1:1")}
        studio_create.assert_available(studio_client_id, context.user_id, 1, len(references))
        directions, director_provider = studio_create.create(
            {"prompt": optimized["optimized_prompt"], "count": 1, "context": director_context},
            chat_completion)
        director_charge, _ = studio_create.charge(
            director_provider, studio_client_id, context.user_id, 1, "", request_id,
            reference_count=len(references), studio_session_id=session_id, studio_root_session_id=session_id)
        direction = directions["directions"][0]
        session = store.save(studio_client_id, context.user_id, session_id, {
            "expected_revision": session["revision"], "status": "active",
            "optimized_prompt": optimized["optimized_prompt"],
            "prompt_language": optimized["detected_language"],
            "prompt_version": optimized["version"],
            "metadata": {**session.get("metadata", {}), "director": {"directions": directions["directions"],
                                                                  "charged_credits": director_charge}},
        })
        payload = {"request_id": request_id, "prompt": direction["prompt"],
                   "reference_plan": direction.get("reference_plan") or [],
                   "references": references,
                   "aspect_ratio": arguments.get("aspect_ratio", "1:1"),
                   "quality": arguments.get("quality", "padrão"),
                   "creation_intent": "branded_creative" if brand_id else "neutral_asset",
                   "brand_context": brand_context,
                   "studio_session_id": session_id, "studio_root_session_id": session_id}
        rendered = studio_create.create_image(payload, modeling, studio_client_id, context.user_id)
        image_url = rendered["image_url"]
        result = {"status": "completed", "image_url": product_url("studio", image_url),
                  "studio_url": studio_url,
                  "operation": "image_edit" if is_edit else "image_create",
                  "session_id": session_id, "direction": direction,
                  "charged_credits": (int(rendered.get("charged_credits") or 0)
                                      + int(director_charge or 0)
                                      + int(prompt_charge.get("tokens_cobrados") or 0)),
                  "remaining_credits": rendered.get("remaining_credits"),
                  "destination": "personal" if not context.project_ref else "project",
                  "indexed": False}
        # Record the paid image before secondary library/index writes. A retry
        # must return this image instead of calling the provider a second time.
        history.complete_image(request_id, personal_client_id, result)
        try:
            store.accept(studio_client_id, context.user_id, session_id, {
                "role": "accepted", "kind": "image", "source_type": "mcp_generation",
                "source_id": request_id, "title": direction["title"], "asset_url": image_url,
                "metadata": {"origin": "generation", "prompt": original,
                             "optimized_prompt": optimized["optimized_prompt"],
                             "direction": direction},
            })
        except Exception:
            result["session_sync_pending"] = True
        if context.project_ref:
            try:
                source = _index_generated_image(context, request_id, original, direction, image_url, modeling.storage)
                result["project_source"] = source
                result["indexed"] = source.get("status") == "indexed"
                result["project_link_status"] = source.get("status") or "attached"
            except Exception:
                # A paid, persisted image must still be returned even when the
                # secondary Workspace indexer is unavailable. The agent can
                # report this honestly and retry linking later.
                result["project_link_status"] = "pending_reconciliation"
        history.complete_image(request_id, personal_client_id, result)
        return result
    except Exception as error:
        history.fail_image(request_id, personal_client_id, str(error))
        raise
