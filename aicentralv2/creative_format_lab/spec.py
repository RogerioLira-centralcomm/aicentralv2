"""Contrato do lab — conceito 15s, 4 ou 5 cenas."""

from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .catalog import format_entry, resolve_format_key

Intent = Literal["reconstruct", "create", "adapt", "refine", "vary", "html"]
VariantKey = Literal["A", "B", "C", "D"]
_HTML_MARK = re.compile(r"<!doctype\s+html|<html[\s>]|</html>", re.IGNORECASE)


def _reject_html(value):
    text = str(value or "")
    if _HTML_MARK.search(text):
        raise ValueError("Spec rejeita HTML solto.")
    return text


class CanvasSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    width: int = 1920
    height: int = 1080

    @field_validator("width", "height")
    @classmethod
    def _size(cls, value):
        number = int(value)
        if number < 40 or number > 3840:
            raise ValueError("Canvas fora do intervalo.")
        return number


class SceneSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    duration: float = 3.0
    purpose: str = "hook"
    headline: str = ""
    support: str = ""
    cta: str = ""
    tip: str = ""
    timecode: str = ""
    set_note: str = ""
    action_note: str = ""
    logo_visible: Optional[bool] = None

    @field_validator("id")
    @classmethod
    def _scene_id(cls, value):
        text = str(value or "").strip()
        if not re.fullmatch(r"scene_0[1-5]", text):
            raise ValueError("Cena inválida.")
        return text

    @field_validator("headline", "support", "cta", "tip", "purpose", "timecode", "set_note", "action_note")
    @classmethod
    def _no_html(cls, value):
        return _reject_html(value)[:240]

    @field_validator("duration")
    @classmethod
    def _duration(cls, value):
        return max(0.4, min(15.0, float(value)))


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["html"] = "html"
    layers: bool = True
    animation_ready: bool = True


class CreativeFormatSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intent: Intent = "create"
    format: str
    variant: VariantKey = "A"
    adapter: str = "generic_ctv"
    platform_label: str = "16:9"
    brand_name: str = ""
    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    scenes: List[SceneSpec] = Field(default_factory=list)
    output: OutputSpec = Field(default_factory=OutputSpec)

    @field_validator("format")
    @classmethod
    def _format(cls, value):
        key = resolve_format_key(value)
        if not format_entry(key):
            raise ValueError("Formato inválido.")
        return key

    @field_validator("brand_name", "platform_label", "adapter")
    @classmethod
    def _plain(cls, value):
        return _reject_html(value)[:80]

    @model_validator(mode="after")
    def _scene_pack(self):
        count = len(self.scenes)
        if count not in (4, 5):
            raise ValueError("O conceito 15s exige 4 ou 5 cenas.")
        expected = [f"scene_0{index}" for index in range(1, count + 1)]
        ids = [scene.id for scene in self.scenes]
        if ids != expected:
            raise ValueError("Cenas devem ser scene_01 em sequência.")
        return self


class QaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer_id: str = ""
    css: str = ""
    text: str = ""

    @field_validator("layer_id")
    @classmethod
    def _layer(cls, value):
        return str(value or "")[:64]

    @field_validator("text", "css")
    @classmethod
    def _patch_text(cls, value):
        text = str(value or "")
        if _HTML_MARK.search(text):
            raise ValueError("Patch rejeita HTML solto.")
        return text[:400]


class VisualQaReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool = False
    score: float = 0
    defects: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    patches: List[QaPatch] = Field(default_factory=list)
    attempt: int = 1

    @field_validator("score")
    @classmethod
    def _score(cls, value):
        return max(0.0, min(1.0, float(value)))

    @field_validator("defects", "notes")
    @classmethod
    def _lines(cls, value):
        return [str(item)[:200] for item in (value or [])[:12]]


def parse_format_spec(payload, expected_format=None):
    if isinstance(payload, CreativeFormatSpec):
        spec = payload
    else:
        data = dict(payload or {})
        key = resolve_format_key(data.get("format"))
        if not format_entry(key):
            data["format"] = expected_format or "video-linear-15"
        spec = CreativeFormatSpec.model_validate(data)
    wanted = resolve_format_key(expected_format) if expected_format else ""
    entry = format_entry(wanted) if wanted else None
    if entry:
        spec.format = entry["key"]
        spec.adapter = entry.get("adapter") or spec.adapter
        spec.platform_label = entry.get("platform_label") or spec.platform_label
        canvas = entry.get("canvas")
        if canvas:
            spec.canvas = CanvasSpec.model_validate(canvas)
    return spec


def parse_qa_report(payload, attempt=1):
    data = dict(payload or {})
    data.setdefault("attempt", attempt)
    return VisualQaReport.model_validate(data)
