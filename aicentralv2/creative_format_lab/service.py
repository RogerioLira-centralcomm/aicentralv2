"""Fachada do lab: sessão nas tabelas de conceito e snapshot em format_lab."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..creative_modeling_generation import OpenRouterError
from ..creative_modeling_repository import CreativeConflictError, CreativeNotFoundError
from ..creative_modeling_service import _integer, _serialize
from .campaign_models import list_campaign_models, load_campaign_model
from .catalog import catalog_payload
from .close import close_scene
from .pipeline import apply_manual_patch, new_session_id, run_session
from .swap import preview_swap_prompt, quote_swap, read_swap_reference, swap_reference
from .plates import (
    apply_bindings,
    build_plate_kit,
    kit_summary,
    normalize_bindings,
    patch_plate_kit,
)
from .storyboard import build_storyboard, quote_concept

logger = logging.getLogger(__name__)


def _preview_lab_result(result):
    """Um still no retorno; as versões ficam só com o HTML."""
    data = dict(result or {})
    mockup = data.get("mockup")
    if isinstance(mockup, dict):
        slim = dict(mockup)
        slim["versions"] = [
            {key: value for key, value in item.items() if key != "png_data_url"}
            if isinstance(item, dict) else item
            for item in (slim.get("versions") or [])
        ]
        data["mockup"] = slim
    chosen = (mockup or {}).get("render_url") if isinstance(mockup, dict) else ""
    data["renders"] = [
        {**item, "png_data_url": chosen if index == 0 else ""}
        if isinstance(item, dict) else item
        for index, item in enumerate(data.get("renders") or [])
    ]
    return data


def _slim_lab_session(session):
    """Tira stills em base64 da persistência — o HTML da base basta."""
    data = dict(session or {})
    mockup = data.get("mockup")
    if isinstance(mockup, dict):
        slim = dict(mockup)
        slim["versions"] = [
            {key: value for key, value in item.items() if key != "png_data_url"}
            for item in (slim.get("versions") or [])
            if isinstance(item, dict)
        ]
        data["mockup"] = slim
    data["renders"] = [
        {**item, "png_data_url": ""}
        if isinstance(item, dict)
        else item
        for item in (data.get("renders") or [])
    ]
    return data


def _session_stage(session):
    data = session if isinstance(session, dict) else {}
    if data.get("status") == "handed_off" or (data.get("handoff") or {}).get("bancada"):
        return "approve"
    if data.get("closed") or (isinstance(data.get("qa"), dict) and data["qa"].get("passed") and data.get("scenes")):
        if any(item.get("closed_url") for item in (data.get("scenes") or []) if isinstance(item, dict)):
            return "close"
    if any(item.get("html") for item in (data.get("scenes") or []) if isinstance(item, dict)):
        return "scene"
    if data.get("base_html") or (isinstance(data.get("mockup"), dict) and data["mockup"].get("html")):
        return "base"
    if data.get("storyboard"):
        return "concept"
    return "draft"


def _history_entry(session):
    stage = _session_stage(session)
    if stage == "draft":
        return None
    storyboard = session.get("storyboard") or []
    first = storyboard[0] if storyboard and isinstance(storyboard[0], dict) else {}
    return {
        "session_id": session.get("id"),
        "stage": stage,
        "format": session.get("format") or session.get("format_key") or "",
        "campaign_slug": session.get("campaign_slug") or "",
        "brand_name": session.get("brand_name") or (session.get("brand") or {}).get("name") or "",
        "headline": first.get("headline") or "",
        "has_base": bool(session.get("base_html")),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _desk_session(session):
    if not isinstance(session, dict):
        return None
    data = _preview_lab_result(dict(session))
    return {
        "id": data.get("id"),
        "campaign_id": data.get("campaign_id"),
        "client_id": data.get("client_id"),
        "status": data.get("status") or "draft",
        "stage": _session_stage(data),
        "format": data.get("format") or data.get("format_key") or "",
        "format_key": data.get("format_key") or data.get("format") or "",
        "variant": data.get("variant") or "A",
        "campaign_slug": data.get("campaign_slug") or "",
        "storyboard": data.get("storyboard") or [],
        "scenes": data.get("scenes") or [],
        "base_html": data.get("base_html") or "",
        "mockup": data.get("mockup") if isinstance(data.get("mockup"), dict) else {},
        "spec": data.get("spec") if isinstance(data.get("spec"), dict) else {},
        "qa": data.get("qa") if isinstance(data.get("qa"), dict) else {},
        "cost": data.get("cost") or data.get("quote") or {},
        "quote": data.get("quote") if isinstance(data.get("quote"), dict) else {},
        "versions": data.get("versions") or [],
        "passes": data.get("passes") or [],
        "brand_name": data.get("brand_name") or "",
        "offer": data.get("offer") or "",
        "scene_count": data.get("scene_count") or len(data.get("storyboard") or []),
    }


def _session_summary(session):
    entry = _history_entry(session) or {}
    return {
        "id": session.get("id"),
        "campaign_id": session.get("campaign_id"),
        "client_id": session.get("client_id"),
        "status": session.get("status") or "draft",
        "stage": entry.get("stage") or _session_stage(session),
        "format": session.get("format") or session.get("format_key") or "",
        "campaign_slug": session.get("campaign_slug") or "",
        "headline": entry.get("headline") or "",
        "has_base": bool(session.get("base_html")),
        "scene_count": session.get("scene_count") or len(session.get("storyboard") or []),
    }


class FormatLabService:
    def __init__(self, modeling):
        self.modeling = modeling
        self.repository = modeling.repository

    def list_formats(self):
        data = catalog_payload()
        data["campaigns"] = list_campaign_models()
        data["quote"] = quote_concept({"scene_count": 4})
        return _serialize(data)

    def quote(self, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        if str(payload.get("kind") or "") == "swap":
            return _serialize(quote_swap(payload))
        return _serialize(quote_concept(payload))

    def read_swap(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        try:
            result = read_swap_reference(
                payload,
                text_callable=self._text_callable(payload),
            )
        except ValueError as exc:
            raise CreativeConflictError(str(exc)) from exc
        return _serialize(result)

    def preview_swap(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        brand = self._swap_brand(payload) if payload.get("use_brand_context") is not False else {}
        return _serialize(preview_swap_prompt(payload, brand))

    def swap(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        brand = self._swap_brand(payload) if payload.get("use_brand_context") is not False else {}
        try:
            result = swap_reference(
                payload,
                brand=brand,
                image_callable=self._image_callable({**payload, "generate": True}),
            )
        except ValueError as exc:
            raise CreativeConflictError(str(exc)) from exc
        result["brand_name"] = payload.get("brand_name") or brand.get("name") or ""
        return _serialize(result)

    def list_campaigns(self):
        return _serialize(list_campaign_models())

    def build_plates(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = _integer(payload.get("client_id"), "Cliente")
        client = self._client(client_id)
        kit = build_plate_kit(
            client,
            text_callable=self._text_callable(payload),
            image_callable=self._image_callable({**payload, "generate": True})
            if payload.get("product")
            else None,
            product=payload.get("product"),
            refine=payload.get("refine") is not False,
            passes=payload.get("passes"),
            assets=payload.get("assets"),
        )
        kit["client_id"] = client_id
        bindings = {
            item["key"]: list(item.get("selected_channels") or [])
            for item in kit.get("plates") or []
        }
        stored = self._persist_plate_kit(kit, bindings, user_id)
        if stored:
            kit = stored
        return _serialize(kit)

    def list_plates(self, client_id):
        client_id = _integer(client_id, "Cliente")
        self._client(client_id)
        listing = getattr(self.repository, "list_plate_kits", None)
        if not callable(listing):
            return _serialize([])
        return _serialize([kit_summary(item) for item in listing(client_id)])

    def get_plates(self, kit_id):
        kit_id = _integer(kit_id, "Geração")
        getter = getattr(self.repository, "get_plate_kit", None)
        if not callable(getter):
            raise CreativeNotFoundError("Geração de placas não encontrada.")
        return _serialize(getter(kit_id))

    def patch_plates(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        kit_id = _integer(payload.get("kit_id") or payload.get("id"), "Geração")
        getter = getattr(self.repository, "get_plate_kit", None)
        if not callable(getter):
            raise CreativeNotFoundError("Geração de placas não encontrada.")
        kit = getter(kit_id)
        updated = patch_plate_kit(
            kit,
            payload,
            text_callable=self._text_callable(payload) if payload.get("refine") else None,
        )
        updater = getattr(self.repository, "update_plate_kit", None)
        if callable(updater):
            updated = updater(kit_id, {
                "campaign": updated.get("campaign"),
                "product": updated.get("product") or kit.get("product"),
                "product_assets": updated.get("product_assets"),
                "plates": updated.get("plates"),
                "bindings": {
                    item["key"]: list(item.get("selected_channels") or [])
                    for item in updated.get("plates") or []
                },
                "passes": updated.get("passes"),
            })
        return _serialize(updated)

    def bind_plates(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = _integer(payload.get("client_id"), "Cliente")
        client = self._client(client_id)
        bindings = normalize_bindings(payload)
        profile = dict(client.get("brand_profile") or {})
        profile["plate_channels"] = bindings
        updater = getattr(self.repository, "update_client_brand_profile", None)
        if callable(updater):
            updater(client_id, profile)
        kit_id = payload.get("kit_id") or payload.get("id")
        if kit_id not in (None, ""):
            getter = getattr(self.repository, "get_plate_kit", None)
            store = getattr(self.repository, "update_plate_kit", None)
            if callable(getter) and callable(store):
                kit = apply_bindings(getter(_integer(kit_id, "Geração")), bindings)
                return _serialize(store(_integer(kit_id, "Geração"), {
                    "plates": kit.get("plates"),
                    "bindings": bindings,
                    "campaign": kit.get("campaign"),
                    "product": kit.get("product"),
                    "product_assets": kit.get("product_assets"),
                    "passes": kit.get("passes"),
                }))
        kit = build_plate_kit(
            {**client, "brand_profile": profile},
            bindings=bindings,
            refine=False,
        )
        kit["client_id"] = client_id
        return _serialize(kit)

    def _persist_plate_kit(self, kit, bindings, user_id=None):
        create = getattr(self.repository, "create_plate_kit", None)
        if not callable(create):
            return None
        payload = {
            "client_id": kit.get("client_id"),
            "name": kit.get("name"),
            "product": kit.get("product") or "",
            "campaign": kit.get("campaign") or {},
            "product_assets": kit.get("product_assets") or {},
            "plates": kit.get("plates") or [],
            "bindings": bindings,
            "passes": kit.get("passes") or [],
        }
        try:
            stored = create(payload, created_by=user_id)
        except Exception:
            try:
                stored = create(payload, created_by=None)
            except Exception:
                return None
        if not isinstance(stored, dict):
            return None
        kit = dict(kit)
        kit.update({
            "id": stored.get("id"),
            "name": stored.get("name") or kit.get("name"),
            "created_at": stored.get("created_at"),
        })
        return kit

    def get_campaign_model(self, slug):
        model = load_campaign_model(slug)
        if not model:
            raise CreativeNotFoundError("Campanha-modelo não encontrada.")
        return _serialize(model)

    def create_session(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = _integer(payload.get("client_id"), "Cliente")
        client = self._client(client_id)
        campaign_id = payload.get("campaign_id")
        if campaign_id not in (None, ""):
            campaign_id = _integer(campaign_id, "Campanha")
            campaign = self.repository.get_campaign(campaign_id)
        else:
            campaign = self._ensure_campaign(client_id, client)
            campaign_id = campaign["id"]
        if not payload.get("fresh"):
            existing = self._open_session(
                client_id,
                payload.get("format") or payload.get("format_key"),
                payload.get("campaign_slug"),
            )
            if existing:
                existing["campaign_id"] = existing.get("campaign_id") or campaign_id
                if payload.get("format") and not existing.get("format"):
                    existing["format"] = payload.get("format")
                    self._write_session(existing["campaign_id"], existing, active=True)
                return _serialize(existing)
        session_id = new_session_id()
        session = {
            "id": session_id,
            "client_id": client_id,
            "campaign_id": campaign_id,
            "status": "draft",
            "intent": str(payload.get("intent") or "create"),
            "format": str(payload.get("format") or payload.get("format_key") or ""),
            "variant": str(payload.get("variant") or "A").upper(),
            "campaign_slug": str(payload.get("campaign_slug") or ""),
            "message": str(payload.get("message") or ""),
            "qa": {"passed": False},
            "scenes": [],
            "renders": [],
            "layers": [],
            "cards": [],
        }
        self._write_session(campaign_id, session, active=True)
        return _serialize(session)

    def storyboard(self, session_id, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign, session = self._find_session(session_id)
        client = self._session_client(session, campaign)
        merged = {
            **session,
            **payload,
            "session_id": session_id,
            "client_id": session.get("client_id") or client.get("id"),
        }
        try:
            result = build_storyboard(
                merged,
                client=client,
                text_callable=self._text_callable(payload),
            )
        except (ValueError, OpenRouterError):
            result = build_storyboard(
                merged,
                client=client,
                text_callable=None,
            )
        result["id"] = session_id
        result["client_id"] = session.get("client_id") or client.get("id")
        result["campaign_id"] = campaign["id"]
        result["status"] = "concept"
        self._write_session(campaign["id"], {**session, **result}, active=True)
        cost = self._bill_prompt(
            campaign["id"],
            session_id,
            user_id,
            {"kind": "storyboard", "format": result.get("format"), "scene_count": result.get("scene_count")},
        )
        result["cost"] = cost
        stored = {**session, **result}
        self._write_session(campaign["id"], stored, active=True)
        return _serialize(result)

    def mockup(self, session_id, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign, session = self._find_session(session_id)
        client = self._session_client(session, campaign)
        merged = {
            **session,
            **payload,
            "session_id": session_id,
            "client_id": session.get("client_id") or client.get("id"),
            "stage": "mockup",
            "mockup_passes": payload.get("mockup_passes") or 3,
        }
        if not merged.get("storyboard") and session.get("storyboard"):
            merged["storyboard"] = session.get("storyboard")
        try:
            result = run_session(
                merged,
                client=client,
                text_callable=self._text_callable(payload),
                screenshot=payload.get("screenshot"),
            )
        except Exception:
            logger.exception("Mockup da sessão %s falhou; entrega a placa HTML", session_id)
            try:
                result = run_session(
                    merged,
                    client=client,
                    text_callable=None,
                    screenshot=lambda *_args, **_kwargs: b"",
                )
            except Exception as exc:
                logger.exception("Placa de fallback da sessão %s também falhou", session_id)
                raise CreativeConflictError("Não montou a base. Tente de novo.") from exc
        if session.get("storyboard") and not result.get("storyboard"):
            result["storyboard"] = session.get("storyboard")
        result["id"] = session_id
        result["client_id"] = session.get("client_id") or client.get("id")
        result["campaign_id"] = campaign["id"]
        result["status"] = "review" if result.get("base_html") else "concept"
        result["cost"] = self._bill_prompt(
            campaign["id"],
            session_id,
            user_id,
            {
                "kind": "mockup",
                "format": result.get("format"),
                "passes": (result.get("mockup") or {}).get("passes"),
            },
        )
        stored = {**session, **result}
        self._write_session(campaign["id"], stored, active=True)
        return _serialize(_preview_lab_result(result))

    def get_session(self, session_id):
        campaign, session = self._find_session(session_id)
        data = dict(session)
        data["campaign_id"] = campaign.get("id")
        data["stage"] = _session_stage(data)
        return _serialize(data)

    def list_sessions(self, payload=None):
        empty = {"sessions": [], "active": None, "history": []}
        payload = payload if isinstance(payload, dict) else {}
        client_id = payload.get("client_id")
        if client_id in (None, ""):
            return _serialize(empty)
        try:
            client_id = _integer(client_id, "Cliente")
            listed = self._list_open_sessions(
                client_id,
                payload.get("format") or payload.get("format_key"),
                payload.get("campaign_slug"),
            )
            active = _desk_session(listed[0]) if listed else None
            history = [
                item for item in (_history_entry(row) for row in listed or [])
                if item
            ]
            return _serialize({
                "sessions": [_session_summary(item) for item in listed],
                "active": active,
                "history": history,
            })
        except Exception:
            logger.exception("Não listou as sessões da Mesa")
            return _serialize(empty)

    def run(self, session_id, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign, session = self._find_session(session_id)
        client = self._session_client(session, campaign)
        merged = {
            **session,
            **payload,
            "session_id": session_id,
            "client_id": session.get("client_id") or client.get("id"),
            "renders": payload.get("renders") or payload.get("attempts") or 3,
        }
        if not payload.get("storyboard") and session.get("storyboard"):
            merged["storyboard"] = session.get("storyboard")
        if not payload.get("base_html") and session.get("base_html"):
            merged["base_html"] = session.get("base_html")
            merged["mockup"] = session.get("mockup") or {}
        result = run_session(
            merged,
            client=client,
            text_callable=self._text_callable(payload),
            screenshot=payload.get("screenshot"),
        )
        if session.get("storyboard") and not result.get("storyboard"):
            result["storyboard"] = session.get("storyboard")
        result["client_id"] = session.get("client_id") or client.get("id")
        result["campaign_id"] = campaign["id"]
        result["cost"] = self._bill_prompt(
            campaign["id"],
            session_id,
            user_id,
            {
                "kind": "scene" if payload.get("scene_id") else "html",
                "format": result.get("format"),
                "qa": result.get("qa"),
                "scene_id": payload.get("scene_id"),
                "renders": len(result.get("versions") or result.get("renders") or []),
            },
        )
        self._write_session(campaign["id"], result, active=True)
        return _serialize(result)

    def patch(self, session_id, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign, session = self._find_session(session_id)
        if not session.get("spec"):
            raise CreativeConflictError("Sessão ainda não rodou.")
        result = apply_manual_patch(
            session,
            payload,
            text_callable=self._text_callable(payload),
            screenshot=payload.get("screenshot"),
        )
        result["client_id"] = session.get("client_id")
        result["campaign_id"] = campaign["id"]
        result["cost"] = self._bill_prompt(
            campaign["id"],
            session_id,
            user_id,
            {"kind": "patch", "qa": result.get("qa")},
        )
        self._write_session(campaign["id"], result, active=True)
        return _serialize(result)

    def close(self, session_id, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign, session = self._find_session(session_id)
        client = self._session_client(session, campaign)
        scene_id = str(payload.get("scene_id") or session.get("scene_id") or "scene_01")
        scenes = [dict(item) for item in session.get("scenes") or []]
        scene = next((item for item in scenes if item.get("id") == scene_id), None)
        if scene is None:
            raise CreativeConflictError("Gere a cena antes de fechar o still.")
        brand = session.get("brand") if isinstance(session.get("brand"), dict) else {}
        if not brand:
            from .brand_context import build_brand_context
            brand = build_brand_context(client)
        assets = {
            "scene_image": scene.get("key_visual") or payload.get("scene_image"),
            "logo_url": brand.get("logo_url"),
            "product_url": payload.get("product_url") or scene.get("key_visual"),
        }
        closed = close_scene(
            scene,
            brand=brand,
            assets=assets,
            image_callable=self._image_callable(payload),
            generate=payload.get("generate") is not False,
        )
        scene["stack"] = closed["stack"]
        scene["guidelines"] = closed["guidelines"]
        scene["closed_url"] = closed["png_data_url"]
        scene["ready_for_motion"] = True
        session = dict(session)
        session["scenes"] = [
            scene if item.get("id") == scene_id else item for item in scenes
        ]
        session["closed"] = closed
        session["qa"] = {
            **(session.get("qa") if isinstance(session.get("qa"), dict) else {}),
            "guidelines": closed["guidelines"],
            "passed": bool((session.get("qa") or {}).get("passed")) and closed["passed"],
        }
        session["cost"] = self._bill_prompt(
            campaign["id"],
            session_id,
            user_id,
            {
                "kind": "close",
                "format": session.get("format"),
                "scene_id": scene_id,
                "generated": closed.get("generated"),
            },
        )
        self._write_session(campaign["id"], session, active=True)
        result = dict(session)
        result["closed"] = closed
        return _serialize(result)

    def handoff(self, session_id):
        campaign, session = self._find_session(session_id)
        qa = session.get("qa") if isinstance(session.get("qa"), dict) else {}
        if not qa.get("passed"):
            raise CreativeConflictError("QA ainda não passou.")
        cards = session.get("cards") or []
        if not cards:
            raise CreativeConflictError("Sessão sem camadas para a Bancada.")
        saved = self.modeling.save_bancada_document(
            campaign["id"],
            {
                "title": session.get("brand_name") or campaign.get("name") or "Mesa de Formato",
                "scenes": cards,
                "cards": cards,
                "layers": cards[0].get("layers") or session.get("layers") or [],
                "brand_dna": session.get("brand_dna"),
            },
        )
        session = dict(session)
        session["status"] = "handed_off"
        session["handoff"] = {"campaign_id": campaign["id"], "bancada": True}
        self._write_session(campaign["id"], session, active=True)
        return _serialize({
            "session": session,
            "campaign_id": campaign["id"],
            "bancada": saved.get("bancada"),
        })

    def _swap_brand(self, payload):
        client_id = payload.get("client_id")
        if client_id in (None, ""):
            return {}
        try:
            from .brand_context import build_brand_context

            client = self._client(_integer(client_id, "Cliente"))
            brand = build_brand_context(client)
            logo = ""
            official = getattr(self.modeling, "_official_logo_data_url", None)
            if callable(official):
                logo = official(client) or ""
            if not (isinstance(logo, str) and logo.startswith(("https://", "http://", "data:image/"))):
                logo = str(brand.get("logo_url") or "")
            brand["logo_url"] = logo if logo.startswith(("https://", "http://", "data:image/")) else ""
            return brand
        except Exception:
            return {}

    def _client(self, client_id):
        if hasattr(self.modeling, "get_client"):
            try:
                client = self.modeling.get_client(client_id)
                if isinstance(client, dict):
                    return client
            except Exception:
                pass
        getter = getattr(self.repository, "get_client", None)
        if not callable(getter):
            raise CreativeNotFoundError("Cliente não encontrado.")
        client = getter(client_id)
        if not isinstance(client, dict):
            raise CreativeNotFoundError("Cliente não encontrado.")
        return client

    def _session_client(self, session, campaign):
        client_id = session.get("client_id")
        if client_id:
            try:
                return self._client(client_id)
            except Exception:
                pass
        client = campaign.get("client")
        return client if isinstance(client, dict) else {}

    def _ensure_campaign(self, client_id, client):
        name = f"Mesa de Formato — {client.get('name') or client_id}"
        created = self.repository.create_campaign_with_variation_a({
            "client_id": client_id,
            "client_source": "profile",
            "name": name,
            "objective": "Mesa de formato",
            "campaign_text": "",
            "cta_text": "",
            "show_price": False,
            "budget_usd": 5,
            "first_step": {
                "format_template_id": 7,
                "mockup": "tv",
                "scene_description": "Lab de formato CTV",
            },
        })
        return self.repository.get_campaign(created["id"])

    def _lab(self, campaign):
        brief = campaign.get("creative_brief")
        brief = dict(brief) if isinstance(brief, dict) else {}
        lab = brief.get("format_lab")
        lab = dict(lab) if isinstance(lab, dict) else {}
        sessions = lab.get("sessions")
        sessions = dict(sessions) if isinstance(sessions, dict) else {}
        lab["sessions"] = sessions
        brief["format_lab"] = lab
        return brief, lab, sessions

    def _write_session(self, campaign_id, session, active=False):
        session = _slim_lab_session(dict(session or {}))
        try:
            campaign = self.repository.get_campaign(campaign_id, productions=False)
        except TypeError:
            campaign = self.repository.get_campaign(campaign_id)
        session["campaign_id"] = campaign_id
        client = campaign.get("client") if isinstance(campaign.get("client"), dict) else {}
        if not session.get("client_id"):
            session["client_id"] = client.get("id")
        brief, lab, sessions = self._lab(campaign)
        sessions[session["id"]] = session
        lab["sessions"] = sessions
        if active:
            lab["active_session_id"] = session["id"]
        entry = _history_entry(session)
        if entry:
            previous = [
                item for item in (lab.get("history") or [])
                if isinstance(item, dict)
                and not (
                    item.get("session_id") == entry["session_id"]
                    and item.get("stage") == entry["stage"]
                )
            ]
            lab["history"] = [entry, *previous][:12]
        brief["format_lab"] = lab
        index = getattr(self.repository, "format_lab_index", None)
        if not isinstance(index, dict):
            index = {}
            self.repository.format_lab_index = index
        index[session["id"]] = campaign_id
        try:
            updater = getattr(self.repository, "update_campaign_bancada", None)
            if callable(updater):
                updater(campaign_id, brief)
            persist = getattr(self.repository, "upsert_concept_session", None)
            if callable(persist):
                persist(session)
        except Exception:
            logger.exception("Não gravou a sessão %s; o retorno da mesa segue", session.get("id"))

    def _open_session(self, client_id, format_key=None, campaign_slug=None):
        listed = self._list_open_sessions(client_id, format_key, campaign_slug)
        return listed[0] if listed else None

    def _list_open_sessions(self, client_id, format_key=None, campaign_slug=None):
        finder = getattr(self.repository, "list_concept_sessions", None)
        if callable(finder):
            try:
                return [
                    item for item in (finder(client_id, format_key, campaign_slug) or [])
                    if isinstance(item, dict) and item.get("id")
                ]
            except Exception:
                logger.exception("Não leu as sessões de conceito da Mesa")
                return []
        stored = getattr(self.repository, "concept_sessions", None)
        if isinstance(stored, dict):
            slug = str(campaign_slug or "").strip()
            key = str(format_key or "").strip()
            rows = []
            for item in stored.values():
                if not isinstance(item, dict):
                    continue
                if int(item.get("client_id") or 0) != int(client_id):
                    continue
                if item.get("status") == "handed_off":
                    continue
                stored_key = str(item.get("format") or item.get("format_key") or "")
                if key and stored_key and stored_key != key:
                    continue
                stored_slug = str(item.get("campaign_slug") or "")
                if slug and stored_slug and stored_slug != slug:
                    continue
                rows.append(item)
            return list(reversed(rows))
        return []

    def _find_session(self, session_id):
        session_id = str(session_id or "").strip()
        if not session_id:
            raise CreativeNotFoundError("Sessão não encontrada.")
        getter = getattr(self.repository, "get_concept_session", None)
        if callable(getter):
            stored = getter(session_id)
            if stored:
                campaign = self.repository.get_campaign(stored["campaign_id"])
                return campaign, stored
        campaign_id = self._guess_campaign_id(session_id)
        campaign = self.repository.get_campaign(campaign_id)
        _brief, _lab, sessions = self._lab(campaign)
        session = sessions.get(session_id)
        if not session:
            raise CreativeNotFoundError("Sessão não encontrada.")
        return campaign, session

    def _guess_campaign_id(self, session_id):
        index = getattr(self.repository, "format_lab_index", None)
        if isinstance(index, dict) and session_id in index:
            return index[session_id]
        stored = getattr(self.repository, "campaign_briefs", None)
        if isinstance(stored, dict):
            for campaign_id, brief in stored.items():
                lab = (brief or {}).get("format_lab") or {}
                if session_id in (lab.get("sessions") or {}):
                    return campaign_id
        created = getattr(self.repository, "created_campaign", None)
        if isinstance(created, dict) and created.get("id"):
            return created["id"]
        return 30

    def _text_callable(self, payload):
        if "text_callable" in (payload or {}):
            return payload.get("text_callable")
        generator = getattr(self.modeling, "generator", None)
        return getattr(generator, "text_callable", None)

    def _image_callable(self, payload):
        if payload.get("generate") is False:
            return None
        if payload.get("image_callable"):
            return payload["image_callable"]
        generator = getattr(self.modeling, "generator", None)
        generate = getattr(generator, "generate_image", None)
        if not callable(generate):
            return None

        def _run(prompt, aspect_ratio="1:1", background="opaque", input_references=None, **_extra):
            result = generate(
                prompt,
                input_references=input_references,
                aspect_ratio=aspect_ratio,
                background=background,
                output_format="png",
            )
            raw = result.get("b64_json") if isinstance(result, dict) else None
            if not raw:
                return None
            import base64
            return base64.b64decode(raw)

        return _run

    def _bill_prompt(self, campaign_id, session_id, user_id, metadata):
        from .storyboard import PROMPT_ESTIMATE_USD, quote_concept

        quote = quote_concept(metadata if isinstance(metadata, dict) else {})
        estimate = float(quote.get("cost_usd") or PROMPT_ESTIMATE_USD * 2)
        create = getattr(self.repository, "create_generation_job", None)
        complete = getattr(self.repository, "complete_generation_job", None)
        if not callable(create):
            return quote
        try:
            job_id = create(
                campaign_id,
                None,
                None,
                "prompt",
                "openrouter",
                "openai/gpt-4o-mini" if str((metadata or {}).get("kind") or "") == "mockup" else "openai/gpt-5.4",
                estimate,
                prompt=session_id,
                request_payload=metadata if isinstance(metadata, dict) else {},
                created_by=user_id,
                concept_session_id=session_id,
            )
            if callable(complete) and job_id:
                complete(job_id, estimate, metadata if isinstance(metadata, dict) else {})
            recorder = getattr(self.repository, "record_concept_pass", None)
            if callable(recorder) and job_id:
                kind = str((metadata or {}).get("kind") or "create")
                pass_kind = {
                    "storyboard": "refine",
                    "html": "implement",
                    "scene": "implement",
                    "mockup": "implement",
                    "close": "validate",
                    "patch": "patch",
                }.get(kind, "create")
                position = {"create": 1, "refine": 2, "implement": 3, "validate": 4, "patch": 5}[pass_kind]
                recorder(
                    session_id,
                    pass_kind,
                    position,
                    status="done",
                    job_id=job_id,
                    estimated_cost_usd=estimate,
                    actual_cost_usd=estimate,
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
        except Exception:
            pass
        quote["spent_usd"] = estimate
        return quote
