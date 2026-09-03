"""
Painel administrativo de migrations do banco de dados.

Expõe uma página web (`/admin/migrations`) e endpoints JSON para:
- listar as migrations disponíveis no diretório `migrations/` do projeto;
- ver o status de cada uma (executada em / pendente);
- executar migrations sob demanda (SQL puro OU runner `run_*.py`);
- inspecionar o histórico com stdout/stderr da última execução.

Segurança
---------
Apenas **superadmin** consegue ver ou executar. Migrations modificam o
schema — nunca deveriam rodar por usuários normais. O rastreamento
persiste em uma tabela `schema_migrations` criada on-demand.

Descoberta
----------
- `*.sql` em `migrations/` → executada via `psycopg` direto.
- `run_*.py` em `migrations/` → executado via `subprocess` chamando
  `venv/bin/python` (ou `sys.executable` no dev local).
- Outros `.py` (utilitários como `check_tables.py`, `backup_database.py`)
  ficam de fora — só rodam manualmente por SSH.

Idempotência
-----------
Deixamos a responsabilidade de idempotência para cada migration (a maioria
já usa `IF NOT EXISTS`). O painel bloqueia rerrun por padrão; um checkbox
"forçar reexecução" desbloqueia quando você realmente precisa (ex.: SQL de
correção que quer aplicar de novo).
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
)

from .auth import superadmin_required, superadmin_required_api
from . import db as _db_mod


bp = Blueprint("admin_migrations", __name__, url_prefix="/admin/migrations")


# ---------------------------------------------------------------------------
# Descoberta de arquivos
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """Raiz do projeto (onde vive `migrations/`, `deploy.sh` etc.)."""
    # Este arquivo está em aicentralv2/admin_migrations_routes.py — subimos 2.
    return Path(__file__).resolve().parents[1]


def _migrations_dir() -> Path:
    return _project_root() / "migrations"


def _venv_python() -> str:
    """Interpretador Python a usar para rodar runners `.py`.

    Prioridades:
      1. `venv/bin/python` no root (padrão do deploy).
      2. `venv_new/bin/python` (fallback do deploy.sh).
      3. `sys.executable` (dev local).
    """
    root = _project_root()
    for candidate in ("venv/bin/python", "venv_new/bin/python"):
        p = root / candidate
        if p.exists():
            return str(p)
    return sys.executable


_RUNNER_RX = re.compile(r"^run_.*\.py$")


def _discover_migrations() -> List[Dict[str, Any]]:
    """Lista migrations disponíveis, ordenadas por nome.

    Cada item:
      {
        "name": "add_valid_until_column.sql",
        "type": "sql" | "python",
        "size": <bytes>,
        "mtime_iso": "...",
        "runnable": True/False (falso se .py não começa com run_),
      }
    """
    directory = _migrations_dir()
    if not directory.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for entry in sorted(directory.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        name = entry.name
        if name.endswith(".sql"):
            mtype, runnable = "sql", True
        elif name.endswith(".py"):
            mtype = "python"
            runnable = bool(_RUNNER_RX.match(name))
        elif name.endswith(".sh"):
            # deploy_admin_migrations.sh — só documentação/atalho.
            continue
        else:
            continue
        stat = entry.stat()
        items.append(
            {
                "name": name,
                "type": mtype,
                "size": stat.st_size,
                "mtime_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "runnable": runnable,
            }
        )
    return items


# ---------------------------------------------------------------------------
# Tabela de rastreamento
# ---------------------------------------------------------------------------

_ENSURE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name         TEXT PRIMARY KEY,
    executed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_by  TEXT,
    ok           BOOLEAN NOT NULL DEFAULT TRUE,
    duration_ms  INTEGER,
    output       TEXT
);
"""


def _ensure_tracking_table() -> None:
    """Cria `schema_migrations` se ainda não existir. Idempotente."""
    conn = _db_mod.get_db()
    with conn.cursor() as cur:
        cur.execute(_ENSURE_TABLE_SQL)
    conn.commit()


def _fetch_history() -> Dict[str, Dict[str, Any]]:
    """Índice `{name: row}` das migrations já registradas."""
    _ensure_tracking_table()
    conn = _db_mod.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT name, executed_at, executed_by, ok, duration_ms, output
            FROM schema_migrations
            ORDER BY executed_at DESC
            """
        )
        rows = cur.fetchall() or []
    idx: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        # `dict_row` factory garante dict; se não, converte manualmente.
        if isinstance(row, dict):
            idx[row["name"]] = row
        else:  # pragma: no cover — segurança
            idx[row[0]] = {
                "name": row[0],
                "executed_at": row[1],
                "executed_by": row[2],
                "ok": row[3],
                "duration_ms": row[4],
                "output": row[5],
            }
    return idx


def _record_execution(
    name: str,
    ok: bool,
    duration_ms: int,
    output: str,
    executed_by: Optional[str],
) -> None:
    conn = _db_mod.get_db()
    with conn.cursor() as cur:
        # UPSERT — se rodar de novo, sobrescreve o histórico.
        cur.execute(
            """
            INSERT INTO schema_migrations (name, executed_by, ok, duration_ms, output)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                executed_at = NOW(),
                executed_by = EXCLUDED.executed_by,
                ok = EXCLUDED.ok,
                duration_ms = EXCLUDED.duration_ms,
                output = EXCLUDED.output
            """,
            (name, executed_by, ok, duration_ms, output),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def _run_sql_migration(path: Path) -> Tuple[bool, str]:
    """Executa um arquivo `.sql` na conexão atual do Flask.

    Retorna (ok, output_string). Em erro, ok=False e output contém o
    traceback do psycopg.
    """
    buf = io.StringIO()
    sql_text = path.read_text(encoding="utf-8")
    buf.write(f"[SQL] {path.name}\n")
    buf.write(f"[SIZE] {len(sql_text)} chars\n")
    buf.write("-" * 60 + "\n")
    try:
        conn = _db_mod.get_db()
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
        buf.write("[OK] SQL executado e commit efetuado.\n")
        return True, buf.getvalue()
    except Exception:  # pragma: no cover — depende do banco
        try:
            _db_mod.get_db().rollback()
        except Exception:
            pass
        buf.write("[ERRO] Falha ao executar SQL:\n")
        buf.write(traceback.format_exc())
        return False, buf.getvalue()


def _run_python_runner(path: Path) -> Tuple[bool, str]:
    """Executa um `run_*.py` via subprocess isolado.

    O runner cuida da própria conexão (segue o padrão dos existentes,
    ex.: `run_add_pi_status_cancelado.py`). Capturamos stdout+stderr para
    exibir no painel.
    """
    py = _venv_python()
    env = os.environ.copy()
    # Garante que o subprocesso enxergue a raiz do projeto no PYTHONPATH,
    # senão `from aicentralv2 import ...` (raro) falharia.
    env.setdefault("PYTHONPATH", str(_project_root()))
    try:
        proc = subprocess.run(
            [py, str(path)],
            cwd=str(_project_root()),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return False, "[ERRO] Timeout: runner passou de 180s."
    except Exception:  # pragma: no cover
        return False, "[ERRO] Falha ao invocar subprocess:\n" + traceback.format_exc()

    body = (
        f"[PY]  {path.name}\n"
        f"[CMD] {py} {path.name}\n"
        f"[EXIT] {proc.returncode}\n"
        + "-" * 60 + "\n"
        + "[stdout]\n" + (proc.stdout or "(vazio)") + "\n"
        + "[stderr]\n" + (proc.stderr or "(vazio)") + "\n"
    )
    return proc.returncode == 0, body


def _executor_label() -> str:
    """Nome amigável do usuário que disparou a execução."""
    from flask import session
    return (
        session.get("user_fullname")
        or session.get("username")
        or f"user_id={session.get('user_id')}"
    )


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@bp.route("/", methods=["GET"])
@bp.route("", methods=["GET"])
@superadmin_required
def page():
    """Renderiza a página do painel de migrations."""
    _ensure_tracking_table()
    return render_template("admin/migrations.html")


@bp.route("/api/list", methods=["GET"])
@superadmin_required_api
def api_list():
    """Retorna migrations descobertas + histórico."""
    files = _discover_migrations()
    history = _fetch_history()
    # Enriquecer com histórico
    for item in files:
        h = history.get(item["name"])
        if h:
            executed_at = h.get("executed_at")
            item["executed_at"] = (
                executed_at.isoformat() if hasattr(executed_at, "isoformat") else executed_at
            )
            item["executed_by"] = h.get("executed_by")
            item["ok"] = bool(h.get("ok"))
            item["duration_ms"] = h.get("duration_ms")
            item["output"] = h.get("output")
        else:
            item["executed_at"] = None
            item["ok"] = None
    return jsonify({
        "success": True,
        "migrations_dir": str(_migrations_dir()),
        "python": _venv_python(),
        "items": files,
    })


@bp.route("/api/run", methods=["POST"])
@superadmin_required_api
def api_run():
    """Executa a migration solicitada.

    Body JSON:
      { "name": "<arquivo>", "force": <bool> }
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    force = bool(payload.get("force"))
    if not name:
        return jsonify({"success": False, "error": "Campo 'name' obrigatório"}), 400

    # Sanidade: só nomes simples (sem path traversal).
    if "/" in name or "\\" in name or ".." in name:
        return jsonify({"success": False, "error": "Nome inválido"}), 400

    path = _migrations_dir() / name
    if not path.is_file():
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404

    # Detectar tipo
    if name.endswith(".sql"):
        mtype = "sql"
    elif name.endswith(".py") and _RUNNER_RX.match(name):
        mtype = "python"
    else:
        return jsonify({"success": False, "error": "Tipo não executável (só .sql e run_*.py)"}), 400

    # Verificar execução anterior
    history = _fetch_history()
    if name in history and history[name].get("ok") and not force:
        return jsonify({
            "success": False,
            "already_executed": True,
            "history": {
                "executed_at": (
                    history[name]["executed_at"].isoformat()
                    if hasattr(history[name]["executed_at"], "isoformat")
                    else history[name]["executed_at"]
                ),
                "executed_by": history[name].get("executed_by"),
            },
            "error": "Migration já executada — envie force=true para reexecutar.",
        }), 409

    started_at = datetime.utcnow()
    if mtype == "sql":
        ok, output = _run_sql_migration(path)
    else:
        ok, output = _run_python_runner(path)
    duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)

    try:
        _record_execution(name, ok, duration_ms, output, _executor_label())
    except Exception:  # pragma: no cover
        current_app.logger.exception("Falha ao registrar migration %s", name)

    return jsonify({
        "success": ok,
        "name": name,
        "duration_ms": duration_ms,
        "output": output,
    })


@bp.route("/api/mark", methods=["POST"])
@superadmin_required_api
def api_mark():
    """Marca uma migration como já aplicada — sem executar.

    Útil para adotar bases legadas em que o schema já está lá, mas a
    tabela `schema_migrations` está vazia. Registra ok=True e um
    output curto explicando que foi apenas uma marcação manual.
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"success": False, "error": "Nome inválido"}), 400
    path = _migrations_dir() / name
    if not path.is_file():
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    _record_execution(
        name,
        ok=True,
        duration_ms=0,
        output=f"[MARCADA MANUALMENTE] Registrada como aplicada em {datetime.utcnow().isoformat()}Z sem executar o SQL/runner.",
        executed_by=_executor_label(),
    )
    return jsonify({"success": True, "name": name, "marked": True})


@bp.route("/api/preview", methods=["GET"])
@superadmin_required_api
def api_preview():
    """Retorna o conteúdo bruto de um arquivo de migration (só leitura)."""
    name = (request.args.get("name") or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return jsonify({"success": False, "error": "Nome inválido"}), 400
    path = _migrations_dir() / name
    if not path.is_file():
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")
    return jsonify({"success": True, "name": name, "content": content})
