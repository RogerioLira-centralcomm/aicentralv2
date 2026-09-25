"""Detect an explicitly requested semantic artifact, independent of its format."""

from __future__ import annotations

import re


def named_artifact_type(message: str) -> str | None:
    text = " ".join(str(message or "").casefold().split())
    delivery = re.search(r"\b(?:crie|criar|gere|gerar|monte|montar|compare|comparar|prepare|preparar|"
                         r"organize|organizar|salve|salvar|registre|registrar|mostre|mostrar)\b", text)
    editable = re.search(r"\b(?:edit[aá]vel|artefato|documento|arquivo|vers[aã]o|guardar|salvar|salve)\b", text)
    editable = editable or re.search(r"\bnota\s+curta\b", text)
    if not delivery or not editable:
        return None
    patterns = (
        ("media_plan", r"\bplano de m[ií]dia\b"),
        ("scenario", r"\bcen[aá]rios?\b"),
        ("research", r"\bpesquisa\s+edit[aá]vel\b|\b(?:pesquisa|achados)\b.{0,45}\b(?:artefato|documento|arquivo|edit[aá]vel)\b"),
        ("executive_summary", r"\bresumo executivo\b"),
        ("note", r"\bnota\s+(?:curta|edit[aá]vel)\b|\b(?:nota|anota[cç][aã]o)\b.{0,25}\bartefato\b"),
    )
    return next((artifact_type for artifact_type, pattern in patterns if re.search(pattern, text)), None)
