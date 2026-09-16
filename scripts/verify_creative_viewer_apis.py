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
        "/parametros/api/campaign-clients",
        "/parametros/api/campaigns",
        "/parametros/api/unfoldings",
        "/parametros/api/image-tiers",
    )
    # The application's production cookie is scoped to ``centralcomm.media``.
    # Flask's test client defaults to ``localhost``; in that case it correctly
    # refuses the scoped cookie and every request below looks unauthenticated.
    # Use a host covered by the configured cookie domain for both the session
    # write and the API calls.
    cookie_domain = (
        app.config.get("CADU_SESSION_COOKIE_DOMAIN")
        or app.config.get("SESSION_COOKIE_DOMAIN")
        or "localhost"
    ).lstrip(".")
    base_url = f"https://{cookie_domain}"

    with app.test_client() as client:
        with client.session_transaction(base_url=base_url) as session:
            session["user_id"] = -1
            session["user_type"] = "admin"
        for path in paths:
            response = client.get(path, base_url=base_url)
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
