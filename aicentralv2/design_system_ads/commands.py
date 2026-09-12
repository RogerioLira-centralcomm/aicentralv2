"""Comandos de edição. Extra no JSON público é ignorado; não entra no documento."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

REVISION_REQUIRED = "Informe a revisão da marca."


class PatchBrandCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expected_revision: int = Field(ge=0)
    tokens: Optional[Dict[str, Any]] = None
    ad_copy: Optional[Dict[str, Any]] = None
    dna: Optional[Dict[str, Any]] = None
    archetype: Optional[str] = None


class RefineBrandCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attempts: int = 4
    intent: Optional[str] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)


class ApproveBrandCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expected_revision: int = Field(ge=0)


class AdaptCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format: Optional[str] = None
    layers: Optional[Any] = None
    swaps: Optional[List[Any]] = None
    archetype: Optional[str] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)


class CampaignComposeCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expected_revision: Optional[int] = Field(default=None, ge=0)


class ValidateRenderCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format: Optional[str] = None
    layers: Optional[Any] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)


class OptionalRevisionCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expected_revision: Optional[int] = Field(default=None, ge=0)
    extra: Optional[str] = None


def _parse_command(model, payload, message="Pedido inválido."):
    try:
        return model.model_validate(payload or {})
    except ValidationError as exc:
        for error in exc.errors():
            if "expected_revision" in (error.get("loc") or ()):
                raise ValueError(REVISION_REQUIRED) from exc
        raise ValueError(message) from exc


def parse_patch_brand(payload):
    return _parse_command(PatchBrandCommand, payload, REVISION_REQUIRED)


def parse_refine_brand(payload):
    command = _parse_command(RefineBrandCommand, payload)
    if str(command.intent or "").strip() and command.expected_revision is None:
        raise ValueError(REVISION_REQUIRED)
    return command


def parse_approve_brand(payload):
    return _parse_command(ApproveBrandCommand, payload, REVISION_REQUIRED)


def parse_adapt(payload):
    return _parse_command(AdaptCommand, payload)


def parse_optional_revision(payload):
    return _parse_command(OptionalRevisionCommand, payload)


def parse_campaign_compose(payload):
    return _parse_command(CampaignComposeCommand, payload)


def parse_validate_render(payload):
    return _parse_command(ValidateRenderCommand, payload)
