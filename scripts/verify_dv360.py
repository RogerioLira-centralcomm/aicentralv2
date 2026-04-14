#!/usr/bin/env python3
"""
Teste válido DV360 no terminal (exit 0 = sucesso, 1 = falha).

Uso (na raiz do repositório):
  python scripts/verify_dv360.py
  python scripts/verify_dv360.py --oauth-only

Carrega .env da raiz e a mesma config que run.py (development por defeito).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from aicentralv2 import create_app  # noqa: E402
from aicentralv2.config import DevelopmentConfig, ProductionConfig  # noqa: E402
from aicentralv2.services.dv360_client import DV360API  # noqa: E402

import os  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Verifica integração DV360 (OAuth + API).")
    p.add_argument(
        "--oauth-only",
        action="store_true",
        help="Só refresh OAuth; não lista advertisers.",
    )
    args = p.parse_args()

    env = os.getenv("AICENTRAL_ENV") or os.getenv("FLASK_ENV") or "development"
    cfg = ProductionConfig if env.lower() == "production" else DevelopmentConfig
    app = create_app(cfg)

    with app.app_context():
        client = DV360API(app.config)
        result = client.verify_installation(list_advertisers=not args.oauth_only)
        for line in result["messages"]:
            print(line)
        if result.get("details"):
            print("--- detalhes (sem segredos) ---")
            print(json.dumps(result["details"], ensure_ascii=False, indent=2, default=str))
        if result["ok"]:
            print("RESULTADO: OK")
            return 0
        print(f"RESULTADO: FALHA (passo: {result.get('step_failed')})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
