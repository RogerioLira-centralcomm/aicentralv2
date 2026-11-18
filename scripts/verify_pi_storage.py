#!/usr/bin/env python3
"""
Verificação do armazenamento local de PI (dev → produção).

Uso local (código + pasta do PI_UPLOAD_ROOT nesta máquina — ex. C:\\var\\www\\... no Windows):
  python scripts/verify_pi_storage.py

Disco no servidor Linux sem deploy (só SSH, não mexe no .env de produção):
  set PI_VERIFY_SERVER_SSH=usuario@seu-servidor
  set PI_UPLOAD_ROOT=/var/www/aicentralv2/instance/uploads/pi
  python scripts/verify_pi_storage.py --server-ssh

Smoke na URL publicada (login + API de arquivos):
  set PI_VERIFY_BASE_URL=https://ai.centralcomm.media
  set PI_VERIFY_EMAIL=seu@centralcomm.media
  set PI_VERIFY_PASSWORD=***
  set PI_VERIFY_ID_PI=12345
  python scripts/verify_pi_storage.py --remote
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@dataclass
class Check:
    name: str
    status: str  # PASS, FAIL, WARN, SKIP
    detail: str = ""


class Reporter:
    def __init__(self) -> None:
        self.items: list[Check] = []

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.items.append(Check(name, status, detail.upper() if status == "FAIL" else detail))

    def ok(self, name: str, detail: str = "") -> None:
        self.add(name, "PASS", detail)

    def fail(self, name: str, detail: str) -> None:
        self.add(name, "FAIL", detail)

    def warn(self, name: str, detail: str) -> None:
        self.add(name, "WARN", detail)

    def skip(self, name: str, detail: str = "") -> None:
        self.add(name, "SKIP", detail)

    def exit_code(self) -> int:
        return 1 if any(i.status == "FAIL" for i in self.items) else 0

    def print_report(self) -> None:
        width = max((len(c.name) for c in self.items), default=10)
        print("\n=== Verificação PI — armazenamento local ===\n")
        for item in self.items:
            mark = {"PASS": "OK ", "FAIL": "FAL", "WARN": "!!!", "SKIP": "---"}[item.status]
            line = f"[{mark}] {item.name.ljust(width)}"
            if item.detail:
                line += f" — {item.detail}"
            print(line)
        fails = sum(1 for i in self.items if i.status == "FAIL")
        warns = sum(1 for i in self.items if i.status == "WARN")
        print(f"\nResumo: {sum(1 for i in self.items if i.status == 'PASS')} OK, {fails} falhas, {warns} avisos")
        if fails:
            print("Corrija as falhas antes de considerar o deploy validado em produção.")


def run_unit_tests(rep: Reporter) -> None:
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_pi_local_storage",
        "tests.test_pi_make_webhooks_local",
        "-v",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode == 0:
        rep.ok("Testes unitários", "test_pi_local_storage + test_pi_make_webhooks_local")
    else:
        rep.fail("Testes unitários", (proc.stderr or proc.stdout)[-2000:])


def check_config(rep: Reporter, app) -> None:
    from aicentralv2.services.pi_local_storage import use_local_pastas
    from aicentralv2.services.pi_make_webhooks import (
        make_configuracao_enabled,
        make_invites_enabled,
    )

    from aicentralv2.services.pi_local_storage import normalize_pi_pastas_backend

    with app.app_context():
        backend = normalize_pi_pastas_backend(app.config.get("PI_PASTAS_BACKEND"))
        root_cfg = app.config.get("PI_UPLOAD_ROOT") or "(default instance/uploads/pi)"
        if backend not in ("local", "auto"):
            rep.fail("PI_PASTAS_BACKEND", f"modo inválido: {app.config.get('PI_PASTAS_BACKEND')!r}")
        else:
            rep.ok("PI_PASTAS_BACKEND", backend)
        if not use_local_pastas():
            rep.fail("use_local_pastas()", "deveria ser True com backend local")
        else:
            rep.ok("Pastas sem Make (GDRIVE)", "use_local_pastas=True")
        if make_invites_enabled() or make_configuracao_enabled():
            rep.fail("Flags Make PI", "invites ou configuração ainda ativos no .env carregado")
        else:
            rep.ok("Flags Make PI", "invites e configuração desligados")
        from aicentralv2.services.pi_local_storage import pi_local_disk_disabled

        if platform.system() == "Windows":
            if pi_local_disk_disabled():
                rep.ok("PI_FILES_SERVER_ONLY", "pastas só no servidor (correto no dev)")
            else:
                rep.fail(
                    "PI_FILES_SERVER_ONLY",
                    "no Windows deve ser true — ver deploy/pi-arquivos.env.dev.example",
                )
            root_explicit = (app.config.get("PI_UPLOAD_ROOT") or "").strip()
            if root_explicit:
                rep.fail(
                    "PI_UPLOAD_ROOT no dev",
                    "remova do .env do PC; disco só em produção",
                )
            else:
                rep.ok("PI_UPLOAD_ROOT (.env)", "ausente no dev (correto)")
        else:
            if not (app.config.get("PI_UPLOAD_ROOT") or "").strip():
                rep.fail("PI_UPLOAD_ROOT", "obrigatório no Linux — ver deploy/pi-arquivos.env.production.example")
            else:
                rep.ok("PI_UPLOAD_ROOT (.env)", str(root_cfg))


def check_disk(rep: Reporter, app) -> None:
    from aicentralv2.services.pi_local_storage import (
        gerar_pastas_local_pi,
        listar_arquivos_secao,
        pi_storage_dir,
        pi_upload_root,
        resolve_arquivo,
        salvar_upload,
    )
    from unittest.mock import patch

    from aicentralv2.services import pi_storage_ssh

    with app.app_context():
        from aicentralv2.services.pi_local_storage import pi_local_disk_disabled

        if pi_local_disk_disabled():
            rep.skip(
                "Disco no PC (Windows)",
                "PI_FILES_SERVER_ONLY=true — pastas só no servidor; use --remote",
            )
            return
        root_cfg = (app.config.get("PI_UPLOAD_ROOT") or "").strip()
        rep.ok("Caminho Linux (.env)", root_cfg or "(padrão instance/uploads/pi)")
        if pi_storage_ssh.remote_storage_enabled():
            rep.ok("SSH → servidor", pi_storage_ssh.ssh_target())
        elif root_cfg.startswith("/") and platform.system() == "Windows":
            rep.fail(
                "SSH para servidor",
                "PI_UPLOAD_ROOT é Linux mas falta PI_UPLOAD_REMOTE_SSH=usuario@servidor",
            )
            return
        root = pi_upload_root()
        rep.ok("Caminho resolvido", str(root))
        token = f"verify_{uuid.uuid4().hex[:8]}.txt"
        pi = {"id_pi": 777777, "codigo_pi_cc": "PI_VERIFY_AUTO"}
        try:
            with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True):
                urls = gerar_pastas_local_pi(pi, strict=False)
            pi = {**pi, **urls}

            class Buf:
                filename = token
                def save(self, dest):
                    Path(dest).write_bytes(b"verify-pi-storage\n")

            salvar_upload(pi, "principal", Buf())
            path = resolve_arquivo(pi, "principal", token)
            if path.read_text(encoding="utf-8") != "verify-pi-storage\n":
                rep.fail("Leitura após escrita", str(path))
            else:
                rep.ok("Escrita/leitura no disco", str(pi_storage_dir(pi)))
            names = [x["name"] for x in listar_arquivos_secao(pi, "principal")]
            if token not in names:
                rep.fail("Listagem de arquivos", f"{token} não listado em {names}")
            else:
                rep.ok("Listagem de arquivos")
            # limpa arquivo de teste
            path.unlink(missing_ok=True)
        except Exception as exc:
            rep.fail("Acesso ao disco", str(exc))


def check_database_hint(rep: Reporter, app, id_pi: int | None) -> None:
    if not id_pi:
        rep.skip("PI no banco", "defina PI_VERIFY_ID_PI para checar registro")
        return
    try:
        from aicentralv2 import db
        from aicentralv2.services.pi_local_storage import is_local_arquivos_url

        with app.app_context():
            pi = db.obter_cadu_pi_por_id(id_pi)
            if not pi:
                rep.fail("PI no banco", f"id_pi {id_pi} não encontrado")
                return
            url = pi.get("googled_pi_princ") or ""
            if not url:
                rep.warn("PI no banco", f"{id_pi} sem pasta principal ainda")
            elif is_local_arquivos_url(url):
                rep.ok("PI no banco", f"principal local: {url[:80]}")
            else:
                rep.warn("PI no banco", f"principal ainda é legado (Drive?): {url[:80]}")
    except Exception as exc:
        rep.fail("PI no banco", str(exc))


def check_server_ssh(rep: Reporter) -> None:
    ssh = os.getenv("PI_VERIFY_SERVER_SSH", "").strip()
    root = (os.getenv("PI_UPLOAD_ROOT") or "/var/www/aicentralv2/instance/uploads/pi").strip()
    if not ssh:
        rep.skip(
            "Disco no servidor (SSH)",
            "PI_VERIFY_SERVER_SSH=usuario@host e --server-ssh (valida sem deploy)",
        )
        return
    remote = f"""set -e
ROOT={root!r}
mkdir -p "$ROOT"
PROBE="$ROOT/.pi_storage_verify"
rm -rf "$PROBE"
mkdir -p "$PROBE"
echo ok > "$PROBE/escrita.txt"
GUNI=$(systemctl show gunicorn --property=User --value 2>/dev/null || true)
if [ -n "$GUNI" ]; then
  if sudo -u "$GUNI" touch "$PROBE/guni.txt" 2>/dev/null; then
    rm -f "$PROBE/guni.txt"
    echo GUNI_WRITE=OK
  else
    echo GUNI_WRITE=FAIL
  fi
else
  echo GUNI_WRITE=SKIP
fi
rm -rf "$PROBE"
ls -ld "$ROOT"
echo DISK_ROOT_OK
"""
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", ssh, "bash", "-s"],
            input=remote,
            text=True,
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError:
        rep.fail("Disco no servidor (SSH)", "ssh não encontrado no PATH")
        return
    except subprocess.TimeoutExpired:
        rep.fail("Disco no servidor (SSH)", "timeout")
        return

    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        rep.fail("Disco no servidor (SSH)", out.strip()[-500:] or f"exit {proc.returncode}")
        return
    if "DISK_ROOT_OK" not in out:
        rep.fail("Disco no servidor (SSH)", out.strip()[-500:])
        return
    rep.ok("Disco no servidor (SSH)", root)
    if "GUNI_WRITE=FAIL" in out:
        rep.fail("Gunicorn grava no servidor", f"usuário gunicorn sem escrita em {root}")
    elif "GUNI_WRITE=OK" in out:
        rep.ok("Gunicorn grava no servidor", "sudo -u gunicorn conseguiu criar arquivo")


def check_remote(rep: Reporter, base_url: str, email: str, password: str, id_pi: int) -> None:
    try:
        import requests
    except ImportError:
        rep.fail("Smoke remoto", "instale requests no venv")
        return

    base = base_url.rstrip("/")
    session = requests.Session()
    session.headers.update({"User-Agent": "verify-pi-storage/1.0"})

    login = session.post(
        f"{base}/login",
        data={"email": email, "password": password},
        allow_redirects=False,
        timeout=30,
    )
    if login.status_code not in (302, 303) and "user_id" not in session.cookies.get_dict():
        # Flask session cookie pode existir mesmo com 200 em alguns hosts
        if login.status_code == 200 and "login" in (login.url or "").lower():
            rep.fail("Login produção", f"HTTP {login.status_code} — credenciais ou host incorretos")
            return
    if not session.cookies:
        rep.warn("Login produção", f"HTTP {login.status_code}; seguindo com cookies={session.cookies.get_dict()}")
    else:
        rep.ok("Login produção", f"HTTP {login.status_code}")

    api_list = session.get(
        f"{base}/api/cadu_pi/{id_pi}/arquivos/principal",
        headers={"Accept": "application/json"},
        timeout=30,
    )
    if api_list.status_code == 302:
        rep.fail("API listar (auth)", "redirecionou para login — sessão não vale na produção")
        return
    if api_list.status_code != 200:
        rep.fail("API listar", f"HTTP {api_list.status_code}: {api_list.text[:200]}")
        return
    data = api_list.json()
    if not data.get("success"):
        rep.fail("API listar", data.get("message", "success=false"))
        return
    rep.ok("API listar arquivos", f"{len(data.get('arquivos') or [])} arquivo(s)")

    token = f"remote_verify_{uuid.uuid4().hex[:8]}.txt"
    body = b"verify-pi-storage-remote\n"
    files = {"arquivo": (token, io.BytesIO(body), "text/plain")}
    upload = session.post(
        f"{base}/api/cadu_pi/{id_pi}/arquivos/principal",
        files=files,
        timeout=60,
    )
    if upload.status_code != 200:
        rep.fail("API upload", f"HTTP {upload.status_code}: {upload.text[:300]}")
        return
    up = upload.json()
    if not up.get("success"):
        rep.fail("API upload", up.get("message", "success=false"))
        return
    rep.ok("API upload", up.get("name", token))

    download = session.get(
        f"{base}/cadu_pi/{id_pi}/arquivos/principal/{token}",
        timeout=30,
    )
    if download.status_code != 200:
        rep.fail("Download", f"HTTP {download.status_code}")
        return
    if download.content != body:
        rep.fail("Download", "conteúdo diferente do enviado")
    else:
        rep.ok("Download", token)

    page = session.get(f"{base}/cadu_pi/{id_pi}/arquivos/principal", timeout=30)
    if page.status_code == 200 and token in page.text:
        rep.ok("Página portal arquivos", "arquivo visível no HTML")
    elif page.status_code == 200:
        rep.warn("Página portal arquivos", "HTTP 200 mas nome do arquivo não apareceu no HTML")
    else:
        rep.fail("Página portal arquivos", f"HTTP {page.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica armazenamento local do PI")
    parser.add_argument("--remote", action="store_true", help="Smoke HTTP na URL de produção/staging")
    parser.add_argument(
        "--server-ssh",
        action="store_true",
        help="Testa mkdir/escrita em PI_UPLOAD_ROOT no Linux via SSH (sem alterar .env de produção)",
    )
    parser.add_argument("--skip-unit", action="store_true")
    args = parser.parse_args()

    from aicentralv2 import create_app
    from aicentralv2.config import DevelopmentConfig

    rep = Reporter()
    if not args.skip_unit:
        run_unit_tests(rep)

    app = create_app(DevelopmentConfig)
    check_config(rep, app)
    check_disk(rep, app)

    id_pi = os.getenv("PI_VERIFY_ID_PI", "").strip()
    id_pi_int = int(id_pi) if id_pi.isdigit() else None
    check_database_hint(rep, app, id_pi_int)

    if args.server_ssh:
        check_server_ssh(rep)
    else:
        rep.skip("Disco no servidor (SSH)", "use --server-ssh quando quiser validar o path Linux")

    if args.remote:
        base = (os.getenv("PI_VERIFY_BASE_URL") or os.getenv("BASE_URL") or "").strip()
        email = os.getenv("PI_VERIFY_EMAIL", "").strip()
        password = os.getenv("PI_VERIFY_PASSWORD", "")
        if not base or not email or not password or not id_pi_int:
            rep.fail(
                "Smoke remoto",
                "defina PI_VERIFY_BASE_URL, PI_VERIFY_EMAIL, PI_VERIFY_PASSWORD e PI_VERIFY_ID_PI",
            )
        else:
            check_remote(rep, base, email, password, id_pi_int)
    else:
        rep.skip(
            "Smoke remoto",
            "rode com --remote após deploy (variáveis PI_VERIFY_*)",
        )

    rep.print_report()
    return rep.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())