#!/usr/bin/env python3
"""
Teste operacional: 1º PI da lista (como na tela) + pastas no SERVIDOR Linux.

Do PC (com SSH):
  set PI_VERIFY_SERVER_SSH=usuario@servidor
  python scripts/test_pi_primeiro_lista.py --servidor

Após deploy (URL logada + API):
  set PI_VERIFY_BASE_URL=https://ai.centralcomm.media
  set PI_VERIFY_EMAIL=...
  set PI_VERIFY_PASSWORD=...
  python scripts/test_pi_primeiro_lista.py --remoto

Só mostrar caminhos / comando bash (sem SSH):
  python scripts/test_pi_primeiro_lista.py
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REMOTE_ROOT_DEFAULT = "/var/www/aicentralv2/instance/uploads/pi"


def _remote_mkdir_bash(base: str, token: str) -> str:
    return f"""set -euo pipefail
ROOT={REMOTE_ROOT_DEFAULT!r}
BASE="{base}"
for s in principal financeiro pecas assinados; do
  mkdir -p "${{BASE}}/${{s}}"
  printf '%s\\n' "TESTE admin servidor — PI lista — token {token}" > "${{BASE}}/${{s}}/TESTE_ADMIN_{token}.txt"
done
printf '%s\\n' "Pasta de teste do 1º PI da lista. Pode apagar: rm -rf ${{BASE}}" > "${{BASE}}/LEIA-ME_TESTE.txt"
ls -la "${{BASE}}"
ls -la "${{BASE}}/principal"
echo REMOTE_PI_TEST_OK
"""


def _run_ssh(ssh_target: str, script: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=25", ssh_target, "bash", "-s"],
            input=script,
            text=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        return 1, "Cliente ssh não encontrado no PATH."
    except subprocess.TimeoutExpired:
        return 1, "Timeout SSH."
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _test_remoto(base_url: str, email: str, password: str, id_pi: int) -> int:
    try:
        import requests
    except ImportError:
        print("Instale requests no venv.", file=sys.stderr)
        return 1

    base = base_url.rstrip("/")
    session = requests.Session()
    session.headers.update({"User-Agent": "test-pi-primeiro-lista/1.0"})

    login = session.post(
        f"{base}/login",
        data={"email": email, "password": password},
        allow_redirects=True,
        timeout=45,
    )
    if login.status_code >= 400 and not session.cookies:
        print(f"FALHA login HTTP {login.status_code}", file=sys.stderr)
        return 1

    status = session.get(
        f"{base}/api/cadu_pi/{id_pi}/pastas/status",
        headers={"Accept": "application/json"},
        timeout=30,
    )
    print(f"pastas/status → HTTP {status.status_code}")
    if status.status_code == 200:
        print(status.json())

    gen = session.post(f"{base}/api/cadu_pi/{id_pi}/gerar-pastas", timeout=60)
    print(f"gerar-pastas → HTTP {gen.status_code}")
    if gen.status_code in (200, 201):
        try:
            print(gen.json())
        except Exception:
            print(gen.text[:500])

    token = f"lista_{uuid.uuid4().hex[:8]}.txt"
    body = b"teste-pi-primeiro-lista\n"
    up = session.post(
        f"{base}/api/cadu_pi/{id_pi}/arquivos/principal",
        files={"arquivo": (token, io.BytesIO(body), "text/plain")},
        timeout=60,
    )
    print(f"upload → HTTP {up.status_code}")
    if up.status_code == 200:
        print(up.json())
        return 0 if up.json().get("success") else 1
    print(up.text[:400], file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste 1º PI da lista + servidor")
    parser.add_argument("--servidor", action="store_true", help="Cria arquivos de teste no Linux via SSH")
    parser.add_argument("--remoto", action="store_true", help="Smoke login + API na URL publicada")
    parser.add_argument("--ssh", default="", help="usuario@host (ou PI_VERIFY_SERVER_SSH)")
    args = parser.parse_args()

    from aicentralv2 import create_app, db
    from aicentralv2.config import DevelopmentConfig
    from aicentralv2.services.pi_local_storage import (
        _safe_codigo_pi,
        is_local_arquivos_url,
        production_pi_upload_root_posix,
        pi_storage_dir_posix,
    )

    app = create_app(DevelopmentConfig)
    with app.app_context():
        pis = db.obter_cadu_pi_lista({})
        if not pis:
            print("Nenhum PI na lista.", file=sys.stderr)
            return 1
        pi = pis[0]
        id_pi = int(pi["id_pi"])
        codigo = pi.get("codigo_pi_cc") or ""
        pasta_servidor = pi_storage_dir_posix(pi)
        root = production_pi_upload_root_posix()
        url_princ = (pi.get("googled_pi_princ") or "").strip()

    print("=== 1º PI da lista (ORDER BY created_at DESC) ===")
    print(f"id_pi:          {id_pi}")
    print(f"codigo_pi_cc:   {codigo}")
    print(f"titulo:         {(pi.get('titulo_pi') or '')[:100]}")
    print(f"pasta servidor: {pasta_servidor}")
    print(f"raiz Linux:     {root}")
    print(f"principal (BD): {url_princ[:100] or '(vazio)'}")
    if url_princ and not is_local_arquivos_url(url_princ):
        print(
            "\nAVISO: este PI ainda tem link Google Drive no banco. "
            "Este teste cria só estrutura no disco Linux; não altera o BD "
            "(após deploy, 'Gerar pastas' migra para URL local se quiser)."
        )

    token = uuid.uuid4().hex[:8]
    bash = _remote_mkdir_bash(pasta_servidor, token)
    print("\n--- Cole no SSH do servidor se não tiver chave no PC ---")
    print(bash)

    if args.remoto:
        base = (os.getenv("PI_VERIFY_BASE_URL") or "https://ai.centralcomm.media").strip()
        email = os.getenv("PI_VERIFY_EMAIL", "").strip()
        password = os.getenv("PI_VERIFY_PASSWORD", "").strip()
        if not email or not password:
            print("Defina PI_VERIFY_EMAIL e PI_VERIFY_PASSWORD para --remoto.", file=sys.stderr)
            return 2
        os.environ.setdefault("PI_VERIFY_ID_PI", str(id_pi))
        return _test_remoto(base, email, password, id_pi)

    if args.servidor:
        ssh_target = (args.ssh or os.getenv("PI_VERIFY_SERVER_SSH") or os.getenv("PI_UPLOAD_REMOTE_SSH") or "").strip()
        if not ssh_target:
            print("Defina PI_VERIFY_SERVER_SSH=usuario@servidor ou use --ssh", file=sys.stderr)
            return 2
        code, out = _run_ssh(ssh_target, bash)
        print(out)
        if code != 0 or "REMOTE_PI_TEST_OK" not in out:
            return 1
        print("\nOK — pastas de teste no servidor. Apague quando quiser:")
        print(f"  rm -rf {pasta_servidor}")
        return 0

    print(
        "\nPróximo passo: configure SSH e rode:\n"
        "  set PI_VERIFY_SERVER_SSH=usuario@servidor\n"
        "  python scripts/test_pi_primeiro_lista.py --servidor\n"
        "\nOu após deploy:\n"
        "  set PI_VERIFY_EMAIL / PI_VERIFY_PASSWORD\n"
        "  python scripts/test_pi_primeiro_lista.py --remoto"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())