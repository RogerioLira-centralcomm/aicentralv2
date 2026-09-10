"""Produtor: preenche slots e não edita HTML/CSS."""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field

from .contract import PieceContract, parse_contract
from .runtime import call_agent_llm

SYSTEM_PROMPT = """Você preenche os slots de um template já escolhido.
Decida só os valores de copy: headline, CTA, preço, legal.
Nunca altere HTML, CSS, adjust_schema, photo_side, regiões ou família.
Responda JSON: {"instance_data":{"headline":"...","cta":"...","price":"...","legal":"..."}}."""


class In(BaseModel):
    headline: str = ""
    cta: str = ""
    price: str = ""
    legal: str = ""
    extra: Dict[str, str] = Field(default_factory=dict)


class Out(BaseModel):
    instance_data: Dict[str, str] = Field(default_factory=dict)


class ProducerAgent:
    name = "producer"

    def run(self, contract=None, *, text_callable=None, **payload):
        incoming = parse_contract(contract)
        if not incoming.template_variation and not incoming.template_id:
            raise ValueError("Produtor precisa de um template já escolhido.")
        frozen_params = dict(incoming.params)
        frozen_family = incoming.family
        data = In.model_validate(payload)
        if data.headline or data.cta:
            out = Out(
                instance_data={
                    "headline": data.headline,
                    "cta": data.cta,
                    "price": data.price,
                    "legal": data.legal,
                    **data.extra,
                }
            )
        else:
            raw = call_agent_llm(
                self.name,
                SYSTEM_PROMPT,
                (
                    f"Variação {incoming.template_variation}. "
                    f"Slots atuais: {incoming.instance_data}"
                ),
                text_callable=text_callable,
            )
            out = Out.model_validate(raw)
        next_contract = incoming.model_copy(deep=True)
        next_contract.instance_data = {
            key: str(value or "")
            for key, value in (out.instance_data or {}).items()
        }
        next_contract.params = frozen_params
        next_contract.family = frozen_family
        next_contract.status = "produzido"
        return next_contract.with_clamped_params()


def run(contract=None, **kwargs):
    return ProducerAgent().run(contract, **kwargs)
