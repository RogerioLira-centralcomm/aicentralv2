"""Contrato do Trocr: análise, elementos e intenção. Adaptador de payload legado."""

from __future__ import annotations

import re
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FIELD_LIMITS = {
    "headline": 80,
    "support": 160,
    "subtitle": 80,
    "price": 40,
    "cta": 40,
    "disclaimer": 160,
    "logo_text": 40,
    "dates": 80,
    "venue": 80,
    "note": 2000,
    "style": 200,
    "element_text": 120,
    "element_note": 160,
}

SAFETY_CAP = 2000
MAX_ELEMENTS = 80
LOCKS_SOFT_CAP = 12
VALID_KINDS = (
    "type", "face", "name_pill", "logo", "graphic", "product", "background"
)
TYPE_ROLES = ("headline", "support", "cta", "price")
PRESERVE_TOKENS = (
    "layout",
    "background",
    "people",
    "product",
    "logo",
    "text_position",
    "colors",
    "graphic",
    "style",
)
ALTER_TOKENS = (
    "price",
    "cta",
    "headline",
    "secondary",
    "people",
    "product",
    "background",
    "colors",
    "graphic",
)
_HTML_MARK = re.compile(r"<!doctype\s+html|<html[\s>]|</html>", re.IGNORECASE)

SwapKind = Literal[
    "type", "face", "name_pill", "logo", "graphic", "product", "background"
]
SwapSource = Literal["ocr", "manual", "legacy"]


def _reject_html(value):
    text = str(value or "")
    if _HTML_MARK.search(text):
        raise ValueError("O Trocr rejeita HTML solto.")
    return text


def _clip_safety(value):
    return str(value or "").strip()[:SAFETY_CAP]


class SwapBox(BaseModel):
    """Pixels da referência normalizada. [x0, y0, x1, y1], x1/y1 exclusivos."""

    model_config = ConfigDict(extra="ignore")
    x0: int
    y0: int
    x1: int
    y1: int
    ref_width: int
    ref_height: int

    @model_validator(mode="after")
    def _inside(self):
        if self.ref_width < 8 or self.ref_height < 8:
            raise ValueError("Referência pequena demais para localizar a região.")
        if self.x0 < 0 or self.y0 < 0 or self.x1 > self.ref_width or self.y1 > self.ref_height:
            raise ValueError("A região sai da imagem-base.")
        if self.x1 - self.x0 < 8 or self.y1 - self.y0 < 8:
            raise ValueError("A região não tem área útil.")
        return self

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


class SwapElement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    role: str
    kind: SwapKind
    text_original: str = ""
    text: str = ""
    note: str = ""
    bbox_px: Optional[Tuple[int, int, int, int]] = None
    container_id: Optional[str] = None
    source: SwapSource = "legacy"
    recognition_score: Optional[float] = None
    user_verified: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, value):
        text = str(value or "").strip()[:32]
        if not re.fullmatch(r"[a-z][a-z0-9_]*_[0-9]{2}", text):
            raise ValueError("id de elemento inválido.")
        return text

    @field_validator("role")
    @classmethod
    def _role(cls, value):
        return str(value or "").strip().lower()[:24]

    @field_validator("text_original", "text", "note")
    @classmethod
    def _plain(cls, value):
        return _reject_html(_clip_safety(value))

    @field_validator("container_id")
    @classmethod
    def _container(cls, value):
        if value in (None, ""):
            return None
        return _reject_html(_clip_safety(value))[:64]

    @field_validator("recognition_score")
    @classmethod
    def _score(cls, value):
        if value is None or value == "":
            return None
        number = float(value)
        if number < 0 or number > 1:
            raise ValueError("recognition_score não é probabilidade calibrada; use 0–1 só como sinal.")
        return number


class SwapCopy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    headline: str = ""
    support: str = ""
    subtitle: str = ""
    price: str = ""
    cta: str = ""
    disclaimer: str = ""
    logo_text: str = ""
    dates: str = ""
    venue: str = ""
    note: str = ""
    style: str = ""
    overflow: List[str] = Field(default_factory=list)

    @field_validator(
        "headline",
        "support",
        "subtitle",
        "price",
        "cta",
        "disclaimer",
        "logo_text",
        "dates",
        "venue",
        "note",
        "style",
    )
    @classmethod
    def _plain(cls, value):
        return _reject_html(_clip_safety(value))


class SwapIntent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lines: SwapCopy = Field(default_factory=SwapCopy)
    preserve: List[str] = Field(default_factory=list)
    alter: List[str] = Field(default_factory=list)
    elements: List[SwapElement] = Field(default_factory=list)
    faces: int = 0
    locks: List[str] = Field(default_factory=list)
    locks_overflow: bool = False
    force_image: bool = False
    quality: str = "production"
    use_brand_context: bool = True
    aspect_ratio: str = ""
    aspect_hint: str = ""
    prompt_override: str = ""

    @field_validator("preserve")
    @classmethod
    def _preserve(cls, value):
        return _token_list(value, PRESERVE_TOKENS)

    @field_validator("alter")
    @classmethod
    def _alter(cls, value):
        return _token_list(value, ALTER_TOKENS)

    @field_validator("faces")
    @classmethod
    def _faces(cls, value):
        return max(0, int(value or 0))

    @field_validator("quality")
    @classmethod
    def _quality(cls, value):
        raw = str(value or "production").strip().lower()
        if raw in {"draft", "rascunho"}:
            return "draft"
        return "production"


def infer_kind(role, text=""):
    key = str(role or "").strip().lower()
    if key == "person":
        return "name_pill" if str(text or "").strip() else "face"
    if key in TYPE_ROLES:
        return "type"
    if key in {"logo", "graphic", "product", "background"}:
        return key
    return "type"


def assign_element_id(role, kind, counters):
    key = kind if kind in {"face", "name_pill"} else (role or "item")
    counters[key] = counters.get(key, 0) + 1
    return f"{key}_{counters[key]:02d}"


def copy_from_payload(payload=None, *, strict_limits=True):
    payload = payload if isinstance(payload, dict) else {}
    note = payload.get("note") or payload.get("instruction") or payload.get("message") or ""
    raw = {
        "headline": payload.get("headline") or "",
        "support": payload.get("support") or "",
        "subtitle": payload.get("subtitle") or "",
        "price": payload.get("price") or "",
        "cta": payload.get("cta") or "",
        "disclaimer": payload.get("disclaimer") or "",
        "logo_text": payload.get("logo_text") or "",
        "dates": payload.get("dates") or "",
        "venue": payload.get("venue") or "",
        "note": note,
        "style": payload.get("style") or "",
    }
    overflow = []
    clean = {}
    for key, value in raw.items():
        text, clipped = _bounded_text(value, FIELD_LIMITS[key], strict_limits, key)
        if clipped:
            overflow.append(key)
        clean[key] = text
    clean["overflow"] = overflow
    return SwapCopy.model_validate(clean)


def normalize_elements(payload=None, *, source="legacy"):
    payload = payload if isinstance(payload, dict) else {}
    counters = {}
    used = set()
    elements = []
    overflow = False
    incoming = [item for item in (payload.get("elements") or []) if isinstance(item, dict)]
    for item in incoming:
        role = str(item.get("role") or "").strip().lower()
        if not role:
            continue
        text = _reject_html(_clip_safety(item.get("text") or item.get("text_original") or ""))
        note = _reject_html(_clip_safety(item.get("note") or ""))
        if len(text) > FIELD_LIMITS["element_text"] or len(note) > FIELD_LIMITS["element_note"]:
            overflow = True
        kind = item.get("kind") if item.get("kind") in VALID_KINDS else infer_kind(role, text)
        ident = _take_id(item.get("id"), role, kind, counters, used)
        bbox = _bbox(item.get("bbox_px"), payload)
        elements.append(
            SwapElement.model_validate({
                "id": ident,
                "role": role,
                "kind": kind,
                "text": text,
                "text_original": _reject_html(_clip_safety(item.get("text_original") or text)),
                "note": note,
                "bbox_px": bbox,
                "container_id": item.get("container_id") or None,
                "source": item.get("source") or source,
                "recognition_score": item.get("recognition_score"),
                "user_verified": bool(item.get("user_verified")),
            })
        )
        if len(elements) >= MAX_ELEMENTS:
            overflow = True
            break
    if len(incoming) > len(elements):
        overflow = True
    elements = _ensure_copy_elements(payload, elements, counters, used, source)
    return elements, overflow


def face_count(elements):
    return sum(1 for item in elements if item.kind == "face")


def locks_from_intent(copy, elements):
    locks = []
    for item in elements:
        if item.kind == "name_pill" and item.text:
            locks.append(item.text)
        if item.role == "logo" and item.text:
            locks.append(item.text)
    for key in ("dates", "venue", "logo_text", "disclaimer"):
        value = str(getattr(copy, key, "") or "").replace("\n", " ").strip()
        if value and value not in locks:
            locks.append(value)
    return locks


def apply_swap_schema(payload=None, *, strict_limits=True, source="legacy"):
    """Normaliza um payload legado sem inventar bbox nem fundir dates/subtitle."""
    data = dict(payload) if isinstance(payload, dict) else {}
    copy = copy_from_payload(data, strict_limits=strict_limits)
    elements, elements_overflow = normalize_elements({**data, **copy.model_dump()}, source=source)
    locks = []
    for item in locks_from_intent(copy, elements) + _incoming_locks(data):
        if item not in locks:
            locks.append(item)
    intent = SwapIntent.model_validate({
        "lines": copy,
        "preserve": data.get("preserve") or [],
        "alter": data.get("alter") or [],
        "elements": elements,
        "faces": face_count(elements),
        "locks": locks,
        "locks_overflow": len(locks) > LOCKS_SOFT_CAP,
        "force_image": bool(data.get("force_image")),
        "quality": data.get("quality") or "production",
        "use_brand_context": data.get("use_brand_context") is not False,
        "aspect_ratio": data.get("aspect_ratio") or data.get("output") or "",
        "aspect_hint": data.get("aspect_hint") or "",
        "prompt_override": data.get("prompt_override") or "",
    })
    dumped = copy.model_dump()
    data.update({
        "headline": dumped["headline"],
        "support": dumped["support"],
        "subtitle": dumped["subtitle"],
        "price": dumped["price"],
        "cta": dumped["cta"],
        "disclaimer": dumped["disclaimer"],
        "logo_text": dumped["logo_text"],
        "dates": dumped["dates"],
        "venue": dumped["venue"],
        "note": dumped["note"],
        "style": dumped["style"],
        "overflow": dumped["overflow"] + (["elements"] if elements_overflow else []),
        "elements": [item.model_dump() for item in intent.elements],
        "elements_overflow": elements_overflow,
        "faces": intent.faces,
        "locks": intent.locks,
        "locks_overflow": intent.locks_overflow,
        "preserve": intent.preserve,
        "alter": intent.alter,
        "quality": intent.quality,
        "force_image": intent.force_image,
        "use_brand_context": intent.use_brand_context,
    })
    return data


def normalize_read(parsed=None):
    """OCR: não corta copy. Estouro vira overflow, não sucesso truncado."""
    parsed = parsed if isinstance(parsed, dict) else {}
    return apply_swap_schema(parsed, strict_limits=False, source="ocr")


def _ensure_copy_elements(payload, elements, counters, used, source):
    have = {item.role for item in elements}
    extras = []
    mapping = (
        ("headline", payload.get("headline")),
        ("support", payload.get("support")),
        ("cta", payload.get("cta")),
        ("price", payload.get("price")),
        ("logo", payload.get("logo_text")),
    )
    for role, text in mapping:
        value = _reject_html(_clip_safety(text))
        if not value or role in have:
            continue
        kind = infer_kind(role, value)
        extras.append(
            SwapElement.model_validate({
                "id": _take_id("", role, kind, counters, used),
                "role": role,
                "kind": kind,
                "text": value,
                "text_original": value,
                "source": source,
            })
        )
    return elements + extras


def _take_id(given, role, kind, counters, used):
    text = str(given or "").strip()
    if re.fullmatch(r"[a-z][a-z0-9_]*_[0-9]{2}", text) and text not in used:
        prefix = kind if kind in {"face", "name_pill"} else (role or "item")
        try:
            counters[prefix] = max(counters.get(prefix, 0), int(text.rsplit("_", 1)[-1]))
        except ValueError:
            pass
        used.add(text)
        return text
    ident = assign_element_id(role, kind, counters)
    while ident in used:
        ident = assign_element_id(role, kind, counters)
    used.add(ident)
    return ident


def _bounded_text(value, limit, strict_limits, key):
    raw = str(value or "").strip()
    if len(raw) > SAFETY_CAP:
        if strict_limits:
            raise ValueError(
                f"{_field_label(key)} passa de {SAFETY_CAP} caracteres. Encurte o texto; o Trocr não corta sozinho."
            )
        raw = raw[:SAFETY_CAP]
        clipped = True
    else:
        clipped = False
    text = _reject_html(raw)
    if len(text) > limit:
        if strict_limits:
            raise ValueError(
                f"{_field_label(key)} passa de {limit} caracteres. Encurte o texto; o Trocr não corta sozinho."
            )
        return text, True
    return text, clipped


def _bbox(raw, payload):
    if not raw:
        return None
    try:
        if isinstance(raw, dict):
            width = raw.get("ref_width") or payload.get("ref_width")
            height = raw.get("ref_height") or payload.get("ref_height")
            if not width or not height:
                return None
            box = SwapBox.model_validate({
                **raw,
                "ref_width": width,
                "ref_height": height,
            })
            return box.as_tuple()
        if isinstance(raw, (list, tuple)) and len(raw) == 4:
            width = payload.get("ref_width")
            height = payload.get("ref_height")
            if not width or not height:
                return None
            box = SwapBox.model_validate({
                "x0": raw[0],
                "y0": raw[1],
                "x1": raw[2],
                "y1": raw[3],
                "ref_width": width,
                "ref_height": height,
            })
            return box.as_tuple()
    except Exception:
        return None
    return None


def _incoming_locks(payload):
    raw = payload.get("locks") if isinstance(payload, dict) else None
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split("|")]
    elif isinstance(raw, (list, tuple)):
        items = raw
    else:
        items = []
    seen = []
    for item in items:
        text = _reject_html(_clip_safety(item))
        if text and text not in seen:
            seen.append(text)
    return seen


def _token_list(value, allowed):
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        items = []
    seen = []
    for item in items:
        key = str(item or "").strip().lower()
        if key in allowed and key not in seen:
            seen.append(key)
    return seen


def _field_label(key):
    labels = {
        "headline": "A headline",
        "support": "O apoio",
        "subtitle": "O subtítulo",
        "price": "O preço",
        "cta": "O CTA",
        "disclaimer": "O disclaimer",
        "logo_text": "O texto da marca",
        "dates": "As datas",
        "venue": "O local",
        "note": "A instrução",
        "style": "O estilo",
    }
    return labels.get(key, key)
