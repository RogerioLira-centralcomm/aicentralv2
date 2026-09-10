"""Revisor: passou/falhou. Não muda layout, copy nem foto."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .contract import PieceContract, QaReport, parse_contract
from .runtime import call_agent_llm

SYSTEM_PROMPT = """Você confere uma peça já renderizada.
Julgue só: safe area limpa, contraste, texto pintado indevido, slots preenchidos.
Não reescreva copy, não mude params, não escolha outra foto.
Responda JSON: {"passed":true,"checks":["safe_area"],"notes":[]}."""


class In(BaseModel):
    image_url: str = ""
    expected_headline: str = ""


class Out(BaseModel):
    passed: bool = False
    checks: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


def _deterministic_checks(contract: PieceContract, expected_headline: str):
    checks = []
    notes = []
    if contract.family == "sequence_16x9" and contract.scenes:
        copy_frames = [scene for scene in contract.scenes if scene.copy_on_frame]
        if copy_frames:
            checks.append("copy_on_frame")
        else:
            notes.append("Nenhuma cena marca copy_on_frame.")
    headline = (contract.instance_data or {}).get("headline") or ""
    if expected_headline and headline and expected_headline not in headline:
        notes.append("Headline da peça não bate com o slot.")
    else:
        checks.append("slots")
    clamped = contract.clamped_params()
    drifted = [
        key for key, value in (contract.params or {}).items()
        if clamped.get(key) != value
    ]
    if drifted:
        notes.append("Params saíram do schema.")
    else:
        checks.append("schema")
    return checks, notes


class ReviewerAgent:
    name = "reviewer"

    def run(self, contract=None, *, text_callable=None, **payload):
        incoming = parse_contract(contract)
        frozen = incoming.model_copy(deep=True)
        data = In.model_validate(payload)
        checks, notes = _deterministic_checks(
            incoming, data.expected_headline or incoming.instance_data.get("headline", "")
        )
        if data.image_url and text_callable is not None:
            raw = call_agent_llm(
                self.name,
                SYSTEM_PROMPT,
                f"Headline esperado: {data.expected_headline}",
                images=[data.image_url],
                text_callable=text_callable,
            )
            judged = Out.model_validate(raw)
            checks = list(dict.fromkeys(checks + judged.checks))
            notes = list(dict.fromkeys(notes + judged.notes))
            passed = judged.passed and not notes
        else:
            passed = not notes
        next_contract = frozen.model_copy(deep=True)
        next_contract.params = frozen.params
        next_contract.instance_data = frozen.instance_data
        next_contract.scenes = frozen.scenes
        next_contract.qa = QaReport(passed=passed, checks=checks, notes=notes)
        next_contract.status = "aguardando_aprovacao" if passed else "reprovado"
        return next_contract


def run(contract=None, **kwargs):
    return ReviewerAgent().run(contract, **kwargs)
