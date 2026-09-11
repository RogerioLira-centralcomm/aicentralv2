"""Extrator: regiões e tokens. Nunca copy/preço/foto final."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator

from .contract import PieceContract, RegionBox, parse_contract
from .runtime import call_agent_llm

SYSTEM_PROMPT = """Você lê um criativo de referência e devolve o mapa do template.
Decida só: bounding boxes em % do canvas, tipo da região, tokens de design.
Tipos válidos: foto_pessoa, foto_produto, logo, headline, preco, cta, beneficios, fundo, icone.
Nunca preencha headline, preço, CTA ou escolha a foto final da campanha.
Responda JSON: {"family":"square_1x1"|"sequence_16x9","regions":[{"tipo":"logo","x":4,"y":6,"w":12,"h":10}],"tokens":{"palette":["#..."]},"params":{}}."""

FORBIDDEN_COPY_KEYS = {"headline", "price_value", "data_amount", "cta", "price"}


class In(BaseModel):
    image_url: str = ""
    family: str = "square_1x1"


class Out(BaseModel):
    family: str = "square_1x1"
    regions: List[RegionBox] = Field(default_factory=list)
    tokens: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _no_campaign_copy(self):
        blob = {**self.tokens, **self.params}
        for key in FORBIDDEN_COPY_KEYS:
            if blob.get(key):
                raise ValueError("Extrator não decide copy de campanha.")
        return self


class ExtractorAgent:
    name = "extractor"

    def run(self, contract=None, *, text_callable=None, **payload):
        incoming = parse_contract(contract)
        data = In.model_validate(payload)
        if incoming.instance_data.get("headline") or incoming.scenes:
            incoming = incoming.model_copy(deep=True)
            incoming.scenes = []
            incoming.instance_data = {}
        raw = call_agent_llm(
            self.name,
            SYSTEM_PROMPT,
            f"Família sugerida: {data.family}. Devolva só o mapa do template.",
            images=[data.image_url] if data.image_url else None,
            text_callable=text_callable,
        )
        out = Out.model_validate(raw)
        next_contract = incoming.model_copy(deep=True)
        next_contract.family = out.family or data.family
        next_contract.regions = out.regions
        next_contract.tokens = out.tokens or next_contract.tokens
        next_contract.params = out.params
        next_contract.template_id = next_contract.template_id or f"{next_contract.family}-draft"
        next_contract.status = "rascunho"
        return next_contract.with_clamped_params()


def run(contract=None, **kwargs):
    return ExtractorAgent().run(contract, **kwargs)
