"""Roteirista: cenas e variação existente. Nunca layout novo."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..creative_compose_library import catalog_variations
from .contract import PieceContract, SceneSlot, parse_contract
from .runtime import call_agent_llm

SYSTEM_PROMPT = """Você roteiriza um anúncio dentro da biblioteca da marca.
Decida: quantidade de cenas (1, 4, 6 ou 8), papel de cada cena, variation_id já existente.
Nunca invente layout, HTML, CSS ou uma variação que não esteja na lista.
Responda JSON: {"template_variation":"...","scenes":[{"role":"gancho","copy_on_frame":false}]}."""

ALLOWED_COUNTS = {1, 4, 6, 8}
DEFAULT_ROLES = {
    1: ["unico"],
    4: ["gancho", "contexto", "beneficio", "fechamento"],
    6: ["gancho", "contexto", "beneficio", "prova", "contexto", "fechamento"],
    8: ["gancho", "gancho", "contexto", "beneficio", "prova", "contexto", "fechamento", "fechamento"],
}


class In(BaseModel):
    brief: str = ""
    family: str = "sequence_16x9"
    scene_count: int = 4
    library: List[dict] = Field(default_factory=list)


class Out(BaseModel):
    template_variation: str = ""
    scenes: List[SceneSlot] = Field(default_factory=list)


class ScriptwriterAgent:
    name = "scriptwriter"

    def run(self, contract=None, *, text_callable=None, repository=None, **payload):
        incoming = parse_contract(contract)
        data = In.model_validate(payload)
        family = data.family or incoming.family or "sequence_16x9"
        library = data.library or catalog_variations(family)
        ids = {str(item.get("id")) for item in library if item.get("id") is not None}
        count = data.scene_count if data.scene_count in ALLOWED_COUNTS else 4
        raw = call_agent_llm(
            self.name,
            SYSTEM_PROMPT,
            (
                f"Brief: {data.brief}\nFamília: {family}\n"
                f"Variações legais: {sorted(ids)}\nCenas pedidas: {count}"
            ),
            text_callable=text_callable,
        )
        out = Out.model_validate(raw)
        variation_id = str(out.template_variation or incoming.template_variation or "")
        if ids and variation_id not in ids:
            raise ValueError("Roteirista só escolhe variação que já existe na biblioteca.")
        if len(out.scenes) not in ALLOWED_COUNTS:
            roles = DEFAULT_ROLES[count]
            out.scenes = [
                SceneSlot(role=role, copy_on_frame=(index == len(roles)))
                for index, role in enumerate(roles, start=1)
            ]
        else:
            last = len(out.scenes)
            for index, scene in enumerate(out.scenes, start=1):
                if scene.headline or scene.price_value:
                    scene.headline = ""
                    scene.price_value = ""
                    scene.data_amount = ""
                if family == "sequence_16x9":
                    scene.copy_on_frame = index >= last
        next_contract = incoming.model_copy(deep=True)
        next_contract.family = family
        next_contract.template_variation = variation_id
        next_contract.scenes = out.scenes
        next_contract.status = "roteirizado"
        return next_contract.with_clamped_params()


def run(contract=None, **kwargs):
    return ScriptwriterAgent().run(contract, **kwargs)
