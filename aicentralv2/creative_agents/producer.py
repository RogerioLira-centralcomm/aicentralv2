"""Produtor: preenche slots e não edita HTML/CSS."""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field

from ..creative_brand_dna import clamp_copy, materialize_brand_dna
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
        has_bancada = bool(
            incoming.regions
            or incoming.brand_dna
            or payload.get("brand_dna")
            or payload.get("layers")
        )
        if not incoming.template_variation and not incoming.template_id and not has_bancada:
            raise ValueError("Produtor precisa de um template já escolhido.")
        frozen_params = dict(incoming.params)
        frozen_family = incoming.family
        dna = materialize_brand_dna(existing=incoming.brand_dna or payload.get("brand_dna"))
        limits = dna["text_limits"]
        data = In.model_validate(payload)
        if data.headline or data.cta:
            out = Out(
                instance_data={
                    "headline": clamp_copy(data.headline, limits["headline_max_chars"]),
                    "cta": clamp_copy(data.cta, limits["subhead_max_chars"]),
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
        if next_contract.instance_data.get("headline"):
            next_contract.instance_data["headline"] = clamp_copy(
                next_contract.instance_data["headline"],
                limits["headline_max_chars"],
            )
        if next_contract.instance_data.get("cta"):
            next_contract.instance_data["cta"] = clamp_copy(
                next_contract.instance_data["cta"],
                limits["subhead_max_chars"],
            )
        next_contract.brand_dna = dna
        next_contract.brand_dna_id = dna["id"]
        next_contract.params = frozen_params
        next_contract.family = frozen_family
        next_contract.status = "produzido"
        return next_contract.with_clamped_params()


def run(contract=None, **kwargs):
    return ProducerAgent().run(contract, **kwargs)
