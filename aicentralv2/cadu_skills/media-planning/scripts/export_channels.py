#!/usr/bin/env python3
"""Compatibilidade: exporta os três catálogos da família oficial Cadu."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from aicentralv2.cadu_skills.scripts.export_official_catalogs import export as export_all  # noqa: E402


def export(output=None) -> int:
    return export_all()["channels.csv"]


if __name__ == "__main__":
    count = export()
    print(f"Exportados {count} canais e catálogos relacionados.")
