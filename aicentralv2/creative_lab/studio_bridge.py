"""Runs the Studio's own creation and edit pipelines with a Lab model in place of the production engine.

The Studio does not send a bare prompt to a model: a director writes the creative direction, a composition
mask (the "mockup") fixes where subject, headline, CTA and logo go, the official logo is applied afterwards,
and the result is fitted to the delivery size. The Lab reuses that code unchanged (``studio_create.create``
and ``create_image``, ``swap.swap_reference``) and only swaps the three things that touch the outside world:
the image generator (the Lab connector, one explicit route), the storage (kept in memory) and the billing
(none). Every piece of the pipeline is a test variable the run can switch off, because several models do not
accept what the Studio sends (reference images, masks).
"""

from __future__ import annotations

import base64
import logging
import re
import time
import uuid

from ..creative_media import ad_masks, studio_create
from . import adapter, catalog, connector

log = logging.getLogger(__name__)

LAB_TO_MASK_FORMAT = {"wide-16x9": "youtube-16x9"}
MOCKUP_MODES = ("image", "text", "none")
ROLE_TO_STUDIO = {"BASE": "primary", "COMPOSITION": "composition", "PRODUCT": "identity", "PERSON": "identity",
                  "STYLE": "style", "OTHER": "reference"}
QUALITY_TO_STUDIO = {"draft": "econômica", "standard": "padrão", "high": "alta"}
STUDIO_QUALITY_TO_LAB = {"low": "draft", "medium": "standard", "high": "high"}
MAX_STUDIO_REFERENCES = studio_create.MAX_IMAGE_REFERENCES

_served = None


def mask_format(lab_format: str | None) -> str | None:
    key = LAB_TO_MASK_FORMAT.get(lab_format or "", lab_format or "")
    return key if key in ad_masks.FORMATS else None


def served_specs() -> list[dict]:
    global _served
    if _served is None:
        _served = ad_masks.served_specs()
    return _served


def mask_url(spec: dict) -> str:
    return ad_masks.MASK_URL_PREFIX + ad_masks.mask_filename(spec)


def mask_view(spec: dict) -> dict:
    return {"id": spec["id"], "format": spec["format"], "format_label": spec["format_label"], "group": spec["group"],
            "family": spec["family"], "family_label": spec["family_label"], "logo": spec["logo"], "cta": spec["cta"],
            "width": spec["width"], "height": spec["height"], "url": mask_url(spec), "zones": list(spec["zones"])}


def mockup_catalog() -> dict:
    """Every composition mask the Studio serves, grouped by format, plus the family descriptions."""
    return {"masks": [mask_view(spec) for spec in served_specs()],
            "families": [{"key": key, "label": label, "description": text} for key, (label, text) in ad_masks.FAMILIES.items()],
            "formats": [{"key": key, "label": value[0], "width": value[1], "height": value[2], "group": value[3]}
                        for key, value in ad_masks.FORMATS.items()]}


def get_mask(mask_id: str) -> dict | None:
    return next((spec for spec in served_specs() if spec["id"] == mask_id), None)


def pick_mask(lab_format: str | None, family: str = "") -> dict | None:
    """The served mask of a format: the requested family, else the first one with logo and CTA."""
    key = mask_format(lab_format)
    if not key:
        return None
    options = [spec for spec in served_specs() if spec["format"] == key]
    if family:
        match = [spec for spec in options if spec["family"] == family]
        if match:
            return next((spec for spec in match if spec["logo"] != "none" and spec["cta"]), match[0])
    return next((spec for spec in options if spec["logo"] != "none" and spec["cta"]), options[0] if options else None)


def text_contract(spec: dict) -> str:
    """The mask as words only, for models that cannot take the wireframe as an input image."""
    frame = ad_masks.provider_frame(spec)
    has_cta, has_logo = "cta" in spec["zones"], "logo" in spec["zones"]
    lines = [
        f"LAYOUT (binding, described in words): {spec['family_label']} for a {spec['width']}x{spec['height']} px canvas. "
        "The zones override any placement written elsewhere in this prompt. Zones as percentage of the canvas (x from the left, y from the top):",
        *ad_masks.zone_lines(spec, frame),
        ad_masks.safe_line(spec, frame),
        "FULL BLEED: the picture fills the whole canvas edge to edge as one continuous image; the text sits on a calm part of the scene.",
        "Render a solid, high-contrast CTA button with a readable label inside the CTA zone." if has_cta
        else "There is NO call-to-action button: do not draw any button, arrow or action label.",
        "Leave the LOGO zone empty; the official logo is applied afterwards." if has_logo
        else "There is NO logo: do not draw any logo, wordmark or brand mark.",
    ]
    if "headline" not in spec["zones"]:
        lines.append("There is NO headline or any other text in this piece: render a pure visual.")
    return "\n".join(lines)


def brand_context(snapshot: dict, payload: dict | None) -> dict:
    """The Lab's frozen brand snapshot in the shape the Studio hands to its director."""
    data = payload or {}
    context = {
        "name": data.get("name") or snapshot.get("name") or "",
        "logo_url": snapshot.get("logo_url") or "",
        "palette": list(data.get("palette") or []),
        "fonts": [{"family": family, "role": "display" if index == 0 else "body"} for index, family in enumerate(data.get("fonts") or [])],
        "assets": {"logo": [snapshot["logo_url"]] if snapshot.get("logo_url") else [], "references": []},
    }
    for key in ("brand_summary", "creative_guidelines"):
        if data.get(key):
            context[key] = data[key]
    for key in ("products_services", "mandatory_elements", "forbidden_elements"):
        if data.get(key):
            context[key] = list(data[key])
    return context


def briefing_text(spec: dict) -> str:
    """The briefing the director reads: instruction, offer and the literal copy in the Studio's own notation."""
    brief = spec.get("brief") or {}
    copy = brief.get("copy") or {}
    parts = [spec.get("instruction") or ""]
    if brief.get("offer"):
        parts.append(f"Oferta: {brief['offer']}")
    if brief.get("audience"):
        parts.append(f"Público: {brief['audience']}")
    if copy.get("headline"):
        parts.append(f"Título: {copy['headline']}")
    if copy.get("highlight"):
        # The highlight ("+20% EXTRA", "NA PALMA DA MÃO") is the "Destaque:": protected, outside the title's word
        # budget and set as the hero (as support, "10% OFF NA 1ª COMPRA" ate the title of a 300×250 down to "Leve").
        parts.append(f"Destaque: {copy['highlight']}")
    if copy.get("support"):
        parts.append(f"Texto de apoio: {copy['support']}")
    if copy.get("cta"):
        parts.append(f"Botão: {copy['cta']}")
    return "\n".join(part for part in parts if part)


class _Capture:
    def __init__(self):
        self.calls: list[dict] = []
        self.saved: list[tuple[str, str]] = []
        self.dropped_references = 0


class _Storage:
    def __init__(self, capture: _Capture):
        self.capture = capture

    def save_generated_base64(self, encoded, output_format):
        self.capture.saved.append((encoded, output_format))
        return f"lab-output:{len(self.capture.saved)}"

    def generated_as_data_url(self, _url):
        raise ValueError("O Lab não guarda peças geradas no armazenamento do Studio.")

    reference_as_data_url = generated_as_data_url


class _Credits:
    def authorize(self, *_args, **_kwargs):
        return True

    def balance(self, *_args, **_kwargs):
        return 0


class _Generator:
    """Stands where the production image generator stands, but calls the Lab connector for one model."""
    text_callable = None

    def __init__(self, model_key: str, capture: _Capture):
        self.manifest = catalog.manifest(model_key)
        self.caps = catalog.capabilities(model_key)
        self.capture = capture

    def generate_image(self, prompt, input_references=None, aspect_ratio="16:9", quality="high", output_format="png",
                       resolution="2K", background="opaque", model=None, max_input_references=2, size=None):
        references = list(input_references or [])
        limit = int(self.caps.get("max_references") or 0)
        if len(references) > limit:
            self.capture.dropped_references += len(references) - limit
            references = references[:limit]
        tier = STUDIO_QUALITY_TO_LAB.get(str(quality), "standard")
        shadow = adapter.plan({"task": "generate", "aspect_ratio": aspect_ratio, "quality": tier, "logo_mode": "none"},
                              self.manifest, self.caps, [])
        parameters = dict(shadow["parameters"]["applied"])
        if self.manifest["provider"] == "openai_direct" and size:
            parameters["size"] = size
        result = connector.call(self.manifest["provider"], model_id=self.manifest["provider_model_id"], prompt=prompt,
                                parameters=parameters, references=references, pricing=self.caps.get("pricing") or [])
        self.capture.calls.append({"prompt": prompt, "parameters": parameters, "references": len(references),
                                   "latency_ms": result["latency_ms"], "cost_usd": result["cost_usd"],
                                   "cost_source": result["cost_source"], "usage": result["usage"],
                                   "request_id": result.get("request_id"), "model": result.get("model"),
                                   "raw_b64": result["b64"]})
        return {"b64_json": result["b64"], "output_format": "png", "usage": result["usage"], "model": result.get("model"),
                "actual_cost_usd": result["cost_usd"]}


class LabModeling:
    """The slice of CreativeModelingService that the Studio pipelines touch."""

    # The Lab refines every Studio-pipeline piece: version 1 from the Studio prompt, then up to four edits of the
    # best version, each fixing what the reviewer found, until the score reaches the target.
    auto_review = True
    review_attempts = 5
    refine_target = 90
    # Draft (low quality, structure only) + finishing edit at the requested quality.
    two_pass = False  # measured: same score at twice the cost (A/B of 6 scenarios, 2026-10-03)
    typeset_social = None  # None follows the Studio (CREATIVE_STUDIO_SOCIAL_TYPESET); the A/B sets True/False
    position_layout = None  # an A/B may force a layout by position on any scenario (v5)
    position_sketch = True

    def __init__(self, model_key: str):
        self.capture = _Capture()
        self.storage = _Storage(self.capture)
        self.generator = _Generator(model_key, self.capture)
        self.credit_connector = _Credits()
        self.credit_ledger = None

    def _credits_crm_id(self, client_id):
        return client_id

    def _charge_studio_call(self, **_kwargs):
        return {}

    def get_client(self, client_id):
        return {"id": client_id}


def _text_callable():
    from ..services.openrouter_service import chat_completion
    return chat_completion


def direct(spec: dict, snapshot: dict) -> dict:
    """The Studio director's direction for this briefing, asked once and frozen so every model gets the same one."""
    brief = spec.get("brief") or {}
    context = {
        "brief": briefing_text(spec)[:1800], "objective": spec.get("objective") or "", "format": spec.get("aspect_ratio") or "",
        "format_key": brief.get("format_key") or "", "creation_intent": "branded_creative" if snapshot else "neutral_asset",
        # The size lets the director fit the copy to the piece (copy budget).
        **(dict(zip(("width", "height"), ad_masks.FORMATS[mask_format(brief.get("format_key"))][1:3]))
           if mask_format(brief.get("format_key")) else {}),
        "brand_context": brand_context(snapshot, spec.get("brand_payload")) if snapshot else {},
        "references": [],
        "typeset_social": bool(LabModeling.typeset_social),
    }
    briefing = briefing_text(spec)
    layout = spec.get("layout") or ({"position": LabModeling.position_layout} if LabModeling.position_layout else {})
    if layout.get("position"):
        from ..creative_media import position_layouts
        item = position_layouts.get(layout["position"])
        if item:
            # The director writes the scene for this layout (who and what, light, mood), not its own composition.
            # Before the copy: after "Botão:" it would be read as part of the button on a flattened briefing.
            briefing = ("Layout da peça (já definido, não reposicione nada): " + item["label"] + ". "
                        + " ".join(item["scene"]) + "\n" + briefing)
    result, _response = studio_create.create({"prompt": briefing, "count": 1, "context": context}, _text_callable())
    direction = result["directions"][0]
    return {"title": direction["title"], "prompt": direction["prompt"], "reference_plan": direction.get("reference_plan") or [],
            "copy": direction.get("copy"),
            "model": result.get("model"), "provider": result.get("provider")}


def _reference_items(spec: dict, plan: dict, by_ref: dict, mask: dict | None, files_module,
                     logo_composed: bool = False) -> list[dict]:
    items = []
    if mask and plan.get("mockup", {}).get("effective") == "image":
        items.append({"id": "lab-mockup", "url": mask_url(mask), "role": "composition", "source": "global",
                      "label": f"Mockup · {mask['family_label']}"})
    for ref in plan["sent"]:
        if logo_composed and ref["role"] == "LOGO":
            continue  # applied by the Studio after generation: it would only take an image slot (and get redrawn)
        stored = by_ref[ref["ref_id"]]
        role = ROLE_TO_STUDIO.get(ref["role"], "reference")
        items.append({"id": f"lab-ref-{ref['ref_id']}", "url": files_module.provider_data_url(stored["file_id"]),
                      "role": role, "source": "user", "label": ref.get("label") or ref["role"]})
    if sum(1 for item in items if item["role"] == "primary") > 1:
        raise ValueError("Escolha somente uma imagem principal.")
    return items


def _finish(modeling: LabModeling, extra: dict) -> dict:
    capture = modeling.capture
    if not capture.saved or not capture.calls:
        raise ValueError("O pipeline do Studio não devolveu imagem.")
    encoded, output_format = capture.saved[-1]
    costs = [call["cost_usd"] for call in capture.calls]
    cost = None if any(item is None for item in costs) else round(sum(costs), 6)
    sources = {call["cost_source"] for call in capture.calls if call["cost_source"]}
    usage: dict = {}
    for call in capture.calls:
        for key, value in (call["usage"] or {}).items():
            if isinstance(value, (int, float)):
                usage[key] = usage.get(key, 0) + value
    return {"b64": encoded, "format": output_format, "raw_b64": capture.calls[0]["raw_b64"],
            "latency_ms": sum(call["latency_ms"] for call in capture.calls), "usage": usage, "cost_usd": cost,
            "cost_source": sources.pop() if len(sources) == 1 else ("mixed" if sources else None),
            "request_id": capture.calls[-1].get("request_id"), "model": capture.calls[-1].get("model"),
            "prompt": capture.calls[0]["prompt"], "calls": len(capture.calls),
            "dropped_references": capture.dropped_references, **extra}


def _position(spec: dict) -> dict:
    """The v5 layout by position of this test (or the one an A/B forces), as Studio payload fields."""
    layout = spec.get("layout") or ({"position": LabModeling.position_layout, "sketch": LabModeling.position_sketch}
                                    if LabModeling.position_layout else {})
    if not layout.get("position"):
        return {}
    return {"position_layout": layout["position"], "position_sketch": layout.get("sketch") is not False}


def run_create(*, model_key: str, spec: dict, snapshot: dict, plan: dict, by_ref: dict, direction: dict, files_module,
               client_id: int, user_id: int | None) -> dict:
    """The Studio's ``create_image`` for one model: mask, references, logo composed afterwards, fit to the format."""
    # A layout by position replaces the box mask entirely (v5): never send both.
    mask = None if _position(spec) else get_mask((plan.get("mockup") or {}).get("id") or "")
    fmt = mask_format((spec.get("brief") or {}).get("format_key"))
    width, height = (mask["width"], mask["height"]) if mask else ((ad_masks.FORMATS[fmt][1], ad_masks.FORMATS[fmt][2]) if fmt else (0, 0))
    ratio = ad_masks.ratio_label(width, height) if width else spec["aspect_ratio"]
    prompt = direction["prompt"]
    if mask and plan["mockup"]["effective"] == "text":
        prompt = prompt + "\n" + text_contract(mask)
    if plan.get("converted_to_text"):
        prompt += "\nNOT SUPPLIED AS IMAGES (describe faithfully from this text): " + "; ".join(
            f"{ref['role']}: {ref.get('label') or 'reference'}" for ref in plan["converted_to_text"])
    modeling = LabModeling(model_key)
    brand = brand_context(snapshot, spec.get("brand_payload")) if snapshot else {}
    logo_ref = next((ref for ref in spec.get("references") or [] if ref.get("role") == "LOGO"), None)
    if brand and logo_ref and files_module is not None:
        # The test carries the official logo: the Studio composes that file (the brand record's URL may be missing or
        # live only on the production disk, and then the logo went to the model as a fourth image and the run failed).
        try:
            brand["logo_url"] = files_module.provider_data_url(logo_ref["file_id"])
            brand["assets"] = {**(brand.get("assets") or {}), "logo": [brand["logo_url"]]}
        except Exception:
            log.warning("Lab logo reference could not be embedded", exc_info=True)
    payload = {
        "request_id": uuid.uuid4().hex, "prompt": prompt, "original_prompt": briefing_text(spec),
        "reference_plan": direction.get("reference_plan") or [], "aspect_ratio": ratio, "copy": direction.get("copy"),
        "quality": QUALITY_TO_STUDIO.get(spec.get("quality"), "padrão"),
        "creation_intent": "branded_creative" if snapshot and spec.get("logo_mode") != "none" else "neutral_asset",
        "brand_context": brand,
        "references": _reference_items(spec, plan, by_ref, mask, files_module, logo_composed=bool(brand.get("logo_url"))),
        "channel": "", "direction_intensity": 70,
        # The mockup mode is a Lab test variable (off, image or text): the Studio's default display layout stays out of it.
        **({"auto_mask": False} if (plan.get("mockup") or {}).get("requested") else {}),
        **_position(spec),
    }
    if width and height:
        payload.update({"width": width, "height": height})
    started = time.monotonic()
    created = studio_create.create_image(payload, modeling, client_id, user_id or 0)
    return _finish(modeling, {"pipeline": "studio_create", "wall_ms": round((time.monotonic() - started) * 1000),
                              "review": (created or {}).get("review"),
                              "mask_id": mask["id"] if mask else None, "mockup": plan.get("mockup"),
                              "delivered": [width, height] if width else None})
