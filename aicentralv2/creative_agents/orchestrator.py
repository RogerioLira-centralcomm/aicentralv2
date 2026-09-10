"""Orquestra os cinco agentes sobre o mesmo contrato."""

from __future__ import annotations

from . import dna, extractor, producer, reviewer, scriptwriter
from .contract import parse_contract

AGENTS = {
    "dna": dna.run,
    "extractor": extractor.run,
    "scriptwriter": scriptwriter.run,
    "producer": producer.run,
    "reviewer": reviewer.run,
}


def run_agent(name, payload=None, contract=None, **kwargs):
    runner = AGENTS.get(str(name or ""))
    if runner is None:
        raise ValueError("Agente da Modelagem desconhecido.")
    data = payload if isinstance(payload, dict) else {}
    current = parse_contract(data.get("contract") if contract is None else contract)
    merged = {**data}
    merged.pop("contract", None)
    merged.update(kwargs)
    return runner(current, **merged)
