"""Extrator: regiões e tokens. Nunca copy/preço/foto final."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator

from .contract import PieceContract, RegionBox, parse_contract
from .runtime import call_agent_llm

SYSTEM_PROMPT = """Você lê um criativo de referência e devolve o mapa do template.
Decida só: bounding boxes em % do canvas, tipo da região, tokens de design.
Tipos válidos: foto_pessoa, elenco, foto_produto, logo, headline, meta, chip, lockup, preco, cta, beneficios, fundo, ornamento, icone.
Cartaz de evento (elenco + campo + bandeirinhas + tipo): use elenco, fundo, ornamento, meta, chip e lockup. Tipo e data nunca viram foto.
Nunca preencha headline, preço, CTA ou escolha a foto final da campanha.
Em cartaz, params pode ter field, chips (nomes das pílulas), meta (datas/local) e lockup (rodapé). Isso é estrutura do cartaz, não copy nova.
Responda JSON: {"family":"square_1x1"|"sequence_16x9","regions":[{"tipo":"logo","x":4,"y":6,"w":12,"h":10}],"tokens":{"palette":["#..."],"field":"#7c4dff"},"params":{}}."""

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

    def run(self, contract=None, *, text_callable=None, image_callable=None, decompose=False, **payload):
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
        next_contract.params = dict(out.params or {})
        if decompose and data.image_url:
            from ..creative_format_lab.decompose import decompose_creative

            field = ""
            tokens = next_contract.tokens if isinstance(next_contract.tokens, dict) else {}
            if tokens.get("field"):
                field = str(tokens.get("field"))
            elif isinstance(tokens.get("palette"), list) and tokens["palette"]:
                field = str(tokens["palette"][0])
            parts = decompose_creative(data.image_url, image_callable, field=field)
            next_contract.params.update({key: value for key, value in parts.items() if value})
        next_contract.template_id = next_contract.template_id or f"{next_contract.family}-draft"
        next_contract.status = "rascunho"
        return next_contract.with_clamped_params()


def run(contract=None, **kwargs):
    return ExtractorAgent().run(contract, **kwargs)
