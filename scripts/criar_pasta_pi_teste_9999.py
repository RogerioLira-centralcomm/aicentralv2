#!/usr/bin/env python3
"""Cria PI9999__9999 no servidor Linux via SSH (pasta de teste para apagar)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE_SCRIPT = ROOT / "deploy" / "criar_pasta_teste_pi9999.sh"

REMOTE_INLINE = r"""
set -euo pipefail
ROOT="${PI_UPLOAD_ROOT:-/var/www/aicentralv2/instance/uploads/pi}"
BASE="${ROOT}/PI9999__9999"
for s in principal financeiro pecas assinados; do
  mkdir -p "${BASE}/${s}"
  printf '%s\n' "TESTE PI 9999 — seção ${s}. Pode apagar: ${BASE}" > "${BASE}/${s}/APAGAR_ME.txt"
done
printf '%s\n' "PASTA DE TESTE — apague: rm -rf ${BASE}" > "${BASE}/LEIA-ME_APAGAR.txt"
echo "OK — ${BASE}"
ls -la "${BASE}"
"""


def main() -> int:
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ssh",
        default="",
        help="usuario@servidor (ou PI_VERIFY_SERVER_SSH no ambiente)",
    )
    args = parser.parse_args()
    target = (args.ssh or os.getenv("PI_VERIFY_SERVER_SSH") or os.getenv("PI_UPLOAD_REMOTE_SSH") or "").strip()
    if not target:
        print(
            "Sem SSH. No servidor, rode:\n"
            f"  bash {REMOTE_SCRIPT.as_posix()}\n"
            "Ou do PC:\n"
            "  set PI_VERIFY_SERVER_SSH=usuario@servidor\n"
            "  python scripts/criar_pasta_pi_teste_9999.py",
            file=sys.stderr,
        )
        return 2
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", target, "bash", "-s"],
        input=REMOTE_INLINE,
        text=True,
        capture_output=True,
        timeout=90,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.strip())
    return 0 if proc.returncode == 0 and "OK —" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())