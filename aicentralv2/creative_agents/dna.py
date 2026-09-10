"""DNA da marca: tokens. Nunca copy de campanha."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field

from ..creative_compose_library import tokens_from_brand_profile
from .contract import PieceContract, parse_contract
from .runtime import call_agent_llm

SYSTEM_PROMPT = """Você extrai o sistema visual de uma marca.
Decida só: paleta, papéis de fonte, espaçamento e tom.
Nunca invente headline, preço, CTA, oferta ou foto de campanha.
Responda JSON: {"name":"...","tokens":{"palette":["#..."],"fonts":{"display":null,"body":null},"spacing":{"unit":8},"voice":"..."}}."""


class In(BaseModel):
    brand_id: str = ""
    brand_profile: Dict[str, Any] = Field(default_factory=dict)
    website_notes: str = ""


class Out(BaseModel):
    name: str = ""
    tokens: Dict[str, Any] = Field(default_factory=dict)
    voice: str = ""


class DnaAgent:
    name = "dna"

    def run(self, contract=None, *, text_callable=None, **payload):
        incoming = parse_contract(contract)
        data = In.model_validate(payload)
        if data.brand_profile:
            tokens = tokens_from_brand_profile(data.brand_profile)
            voice = ""
            line = data.brand_profile.get("creative_line") or {}
            if isinstance(line, dict):
                voice = str(line.get("signature_summary") or "")[:400]
            out = Out(name=data.brand_id, tokens=tokens, voice=voice)
        else:
            raw = call_agent_llm(
                self.name,
                SYSTEM_PROMPT,
                data.website_notes or data.brand_id,
                text_callable=text_callable,
            )
            out = Out.model_validate(raw)
        next_contract = incoming.model_copy(deep=True)
        next_contract.brand_id = data.brand_id or incoming.brand_id
        next_contract.tokens = out.tokens
        next_contract.scenes = []
        next_contract.instance_data = {}
        return next_contract


def run(contract=None, **kwargs):
    return DnaAgent().run(contract, **kwargs)
