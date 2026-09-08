#!/usr/bin/env python
"""Valida as APIs iniciais da Modelagem de Criativos contra o banco."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run import app


def main():
    paths = (
        "/parametros/api/viewer-profiles",
        "/parametros/api/formats",
        "/parametros/api/clients",
        "/parametros/api/campaigns",
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = -1
            session["user_type"] = "admin"
        for path in paths:
            response = client.get(path)
            payload = response.get_json(silent=True)
            if response.status_code != 200 or not (
                isinstance(payload, dict) and payload.get("success") is True
            ):
                raise RuntimeError(
                    f"Verificação falhou em {path}: "
                    f"HTTP {response.status_code} {response.get_data(as_text=True)}"
                )
            print(f"{path}: HTTP 200")


if __name__ == "__main__":
    main()
