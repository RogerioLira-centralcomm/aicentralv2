#!/usr/bin/env python3
"""
Gera um NOVO refresh token OAuth com os scopes completos (Display Video + Bid Manager).

Isto resolve «Request had insufficient authentication scopes» no relatório DV360:
o token antigo foi criado só com display-video; Spent/KPI do relatório precisam de
https://www.googleapis.com/auth/doubleclickbidmanager.

Pré-requisitos no Google Cloud Console (mesmo projecto do DV360_CLIENT_ID):
  1. APIs e serviços → Biblioteca: activar «Display & Video 360 API» e
     «DoubleClick Bid Manager API».
  2. Credenciais → OAuth 2.0 Client ID (tipo «Aplicação Web» ou «Ambiente de trabalho»).
  3. Em «URIs de redireccionamento autorizados», adicionar EXACTAMENTE (porta = a que usar abaixo):

       http://127.0.0.1:8085/oauth2/callback

     Se usar --port 9000, o URI deve ser http://127.0.0.1:9000/oauth2/callback

Uso (na raiz do repositório, com venv):
  python scripts/dv360_oauth_refresh_token.py
  python scripts/dv360_oauth_refresh_token.py --port 9000

O script grava sozinho ``DV360_REFRESH_TOKEN`` no ``.env`` na raiz (use ``--no-write-env`` para só mostrar).
Reinicie o servidor Flask para carregar o novo token.

Teste: python scripts/verify_dv360.py --oauth-only
"""
from __future__ import annotations

import argparse
import http.server
import re
import secrets
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import os  # noqa: E402

import requests  # noqa: E402

from aicentralv2.services.dv360_client import BID_MANAGER_API_BASE, DV360_SCOPES  # noqa: E402

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
REDIRECT_PATH = "/oauth2/callback"

_ENV_PATH = ROOT / ".env"


def _dotenv_escape_value(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def upsert_dotenv_refresh_token(env_path: Path, refresh_token: str) -> None:
    """Actualiza ou acrescenta DV360_REFRESH_TOKEN= no ficheiro .env (UTF-8)."""
    key = "DV360_REFRESH_TOKEN"
    new_line = f'{key}="{_dotenv_escape_value(refresh_token)}"\n'
    if env_path.is_file():
        raw = env_path.read_text(encoding="utf-8")
    else:
        raw = ""
    out: list[str] = []
    found = False
    for line in raw.splitlines(keepends=True):
        if re.match(rf"^\s*{re.escape(key)}\s*=", line):
            out.append(new_line)
            found = True
        else:
            out.append(line)
    if not found:
        if out and not str(out[-1]).endswith("\n"):
            out[-1] = out[-1] + "\n"
        out.append(new_line)
    env_path.write_text("".join(out), encoding="utf-8")


class _OAuthHandler(http.server.BaseHTTPRequestHandler):
    server_version = "DV360OAuth/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_error(404, "Use apenas o callback OAuth")
            return
        qs = parse_qs(parsed.query)
        srv: socketserver.TCPServer = self.server
        if qs.get("error"):
            msg = " ".join(qs.get("error", []))
            desc = qs.get("error_description", [""])[0]
            srv.oauth_result = {"error": msg, "error_description": desc}  # type: ignore[attr-defined]
            srv.oauth_done.set()  # type: ignore[attr-defined]
            self._send_html(
                200,
                "<h1>Google devolveu um erro</h1><p>Pode fechar esta página.</p>",
            )
            return
        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        if not code or state != getattr(srv, "oauth_state", None):
            srv.oauth_result = {"error": "invalid_callback"}  # type: ignore[attr-defined]
            srv.oauth_done.set()  # type: ignore[attr-defined]
            self._send_html(200, "<h1>Pedido inválido</h1><p>Feche esta página.</p>")
            return
        srv.oauth_result = {"code": code}  # type: ignore[attr-defined]
        srv.oauth_done.set()  # type: ignore[attr-defined]
        self._send_html(
            200,
            "<h1>Autorização recebida</h1><p>Pode fechar esta janela e voltar ao terminal.</p>",
        )

    def _send_html(self, status: int, body: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(
        description="Obter refresh token DV360 com scopes display-video + doubleclickbidmanager.",
    )
    p.add_argument("--port", type=int, default=8085, help="Porta local do callback (default 8085)")
    p.add_argument(
        "--no-write-env",
        action="store_true",
        help="Não gravar o .env (apenas imprimir a linha DV360_REFRESH_TOKEN).",
    )
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Não pedir ENTER antes do login (CI / utilizadores avançados).",
    )
    args = p.parse_args()
    port = int(args.port)
    if port < 1 or port > 65535:
        print("ERRO: porta inválida", file=sys.stderr)
        return 1

    client_id = (os.getenv("DV360_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("DV360_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        print(
            "ERRO: defina DV360_CLIENT_ID e DV360_CLIENT_SECRET no .env (raiz do projecto).",
            file=sys.stderr,
        )
        return 1

    redirect_uri = f"http://127.0.0.1:{port}{REDIRECT_PATH}"
    state = secrets.token_urlsafe(24)
    scope_str = " ".join(DV360_SCOPES)

    proj = (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "").strip()
    creds_url = (
        f"https://console.cloud.google.com/apis/credentials?project={proj}"
        if proj
        else "https://console.cloud.google.com/apis/credentials"
    )

    print("=" * 70)
    print("DV360 — autorizar Google (uma vez ou quando mudar o refresh token)")
    print("=" * 70)
    print()
    print("O QUE FAZER (siga por ordem):")
    print()
    print("  A) No Google Cloud (conta com permissão de administrador do projecto):")
    print("     1. Abra a página de credenciais (vamos abrir o browser daqui a seguir).")
    print("     2. No topo, escolha o MESMO projecto Google onde criou o OAuth.")
    print(f"     3. Na lista «IDs de clientes OAuth 2.0», abra o que tem este ID:")
    print(f"        {client_id}")
    print("     4. Em «URIs de redireccionamento autorizados» → Adicionar URI,")
    print("        cole EXACTAMENTE (sem espaço a mais no fim):")
    print()
    print(f"        {redirect_uri}")
    print()
    print("     5. GUARDAR (em baixo da página).")
    print()
    print("  B) Depois disto, este programa abre o login Google; aceite as permissões.")
    print("     Use a conta que tem acesso ao DV360.")
    print()
    print("Opcional no .env: GOOGLE_CLOUD_PROJECT=id-do-projecto-google")
    print("                   (abre a consola já no projecto certo).")
    print()
    try:
        webbrowser.open(creds_url)
        print(f"(Aberto no browser: credenciais → {creds_url})")
    except Exception:
        print(f"Abra manualmente: {creds_url}")
    print()

    if not args.yes:
        try:
            input(
                ">> Quando tiver GUARDADO o URI acima no Google Cloud, prima ENTER para "
                "continuar e abrir o login Google…\n"
            )
        except EOFError:
            print("(sem terminal interactivo: continuar…)")
    else:
        print("(-y: sem pausa) A abrir login Google…")

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    auth_url = f"{AUTH_URI}?{urlencode(auth_params)}"

    srv = socketserver.TCPServer(("127.0.0.1", port), _OAuthHandler)
    srv.allow_reuse_address = True
    srv.oauth_state = state
    srv.oauth_done = threading.Event()
    srv.oauth_result = None

    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        webbrowser.open(auth_url)
        print("À espera do callback no browser (máx. 5 min)…")
        if not srv.oauth_done.wait(timeout=300):
            print("ERRO: tempo esgotado — não recebemos o código.", file=sys.stderr)
            return 1
    finally:
        srv.shutdown()
        srv.server_close()

    result = srv.oauth_result or {}
    if result.get("error"):
        print(f"ERRO OAuth: {result.get('error')} {result.get('error_description', '')}".strip())
        return 1
    code = result.get("code")
    if not code:
        print("ERRO: código de autorização em falta.", file=sys.stderr)
        return 1

    token_body = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    tr = requests.post(TOKEN_URI, data=token_body, timeout=60)
    try:
        tok = tr.json()
    except ValueError:
        print(f"ERRO: resposta token não-JSON: HTTP {tr.status_code} {tr.text[:400]}", file=sys.stderr)
        return 1

    if tr.status_code != 200 or "refresh_token" not in tok:
        err = tok.get("error_description") or tok.get("error") or tr.text[:500]
        print(f"ERRO ao trocar código por tokens: {err}", file=sys.stderr)
        return 1

    refresh = str(tok.get("refresh_token") or "")
    print()
    print("=" * 70)
    if args.no_write_env:
        print("SUCESSO. Copie para o .env:")
        print()
        print(f'DV360_REFRESH_TOKEN="{refresh}"')
        print()
    else:
        upsert_dotenv_refresh_token(_ENV_PATH, refresh)
        print(f"SUCESSO. DV360_REFRESH_TOKEN gravado em: {_ENV_PATH}")
        print("       Reinicie o servidor Flask para usar o novo token.")
        print()
    print("Scopes concedidos (referência):")
    print(" ", tok.get("scope", scope_str))
    print()
    print("Teste rápido Bid Manager (lista queries):")
    bm_url = f"{BID_MANAGER_API_BASE}/queries"
    at = tok.get("access_token")
    if at:
        br = requests.get(
            bm_url,
            headers={"Authorization": f"Bearer {at}"},
            timeout=30,
        )
        print(f"  GET {bm_url} → HTTP {br.status_code}")
        if br.status_code == 403:
            print("  Ainda 403: confirme APIs activas no projecto Google Cloud.", file=sys.stderr)
    print("=" * 70)
    print("Depois: python scripts/verify_dv360.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
