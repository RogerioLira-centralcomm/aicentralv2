"""Contrato que todos os agentes leem e escrevem."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..creative_compose_library import clamp_params, schema_for_family

ContractStatus = Literal[
    "rascunho",
    "roteirizado",
    "produzido",
    "aguardando_aprovacao",
    "aprovado",
    "reprovado",
]
SceneRole = Literal[
    "gancho", "contexto", "beneficio", "fechamento", "prova", "unico"
]


class SceneSlot(BaseModel):
    role: SceneRole = "unico"
    headline: str = ""
    data_amount: str = ""
    price_value: str = ""
    copy_on_frame: bool = False
    set_note: str = ""
    action_note: str = ""


class QaReport(BaseModel):
    passed: bool = False
    checks: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class RegionBox(BaseModel):
    model_config = ConfigDict(extra="allow")
    tipo: str
    x: float
    y: float
    w: float
    h: float
    content: Dict[str, Any] = Field(default_factory=dict)


class PieceContract(BaseModel):
    brand_id: str = ""
    campaign_id: str = ""
    brand_dna_id: str = ""
    template_id: str = ""
    template_variation: str = ""
    family: str = ""
    scenes: List[SceneSlot] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    instance_data: Dict[str, str] = Field(default_factory=dict)
    tokens: Dict[str, Any] = Field(default_factory=dict)
    brand_dna: Dict[str, Any] = Field(default_factory=dict)
    regions: List[RegionBox] = Field(default_factory=list)
    target_layer_id: str = ""
    target_tipo: str = ""
    status: ContractStatus = "rascunho"
    qa: Optional[QaReport] = None

    @field_validator("family")
    @classmethod
    def _family(cls, value):
        return str(value or "")

    def clamped_params(self):
        return clamp_params(schema_for_family(self.family), self.params)

    def with_clamped_params(self):
        data = self.model_copy(deep=True)
        data.params = data.clamped_params()
        return data


def parse_contract(payload):
    if isinstance(payload, PieceContract):
        return payload
    return PieceContract.model_validate(payload or {})
