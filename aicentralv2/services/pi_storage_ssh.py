"""Acesso ao disco de PI no servidor Linux via SSH (dev no Windows → /var/www/...)."""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from .pi_local_storage import PiLocalStorageError

_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=25", "-o", "StrictHostKeyChecking=accept-new"]


def ssh_target() -> str:
    for key in ("PI_UPLOAD_REMOTE_SSH", "PI_VERIFY_SERVER_SSH"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def ssh_dev_enabled() -> bool:
    return os.getenv("PI_STORAGE_SSH_DEV", "").lower() in ("true", "1", "yes", "on")


def remote_storage_enabled() -> bool:
    """SSH só com opt-in explícito (não é o fluxo normal de dev/produção)."""
    if not ssh_dev_enabled() or not ssh_target():
        return False
    root = os.getenv("PI_UPLOAD_ROOT", "").strip()
    return root.startswith("/")


def run_remote_bash(script: str, *, timeout: int = 120) -> str:
    target = ssh_target()
    if not target:
        raise PiLocalStorageError("Defina PI_UPLOAD_REMOTE_SSH=usuario@servidor no .env do dev.")
    try:
        proc = subprocess.run(
            ["ssh", *_SSH_OPTS, target, "bash", "-s"],
            input=script,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise PiLocalStorageError("Cliente SSH não encontrado. Instale OpenSSH no Windows.") from exc
    except subprocess.TimeoutExpired as exc:
        raise PiLocalStorageError("Timeout ao conectar/comandar o servidor via SSH.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise PiLocalStorageError(detail or f"SSH falhou (código {proc.returncode})")
    return (proc.stdout or "").strip()


def remote_mkdir_p(path: str) -> None:
    run_remote_bash(f"mkdir -p {shlex.quote(path)}")


def remote_write_text(path: str, text: str) -> None:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    run_remote_bash(
        f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(path)}"
    )


def remote_write_bytes(path: str, data: bytes) -> None:
    encoded = base64.b64encode(data).decode("ascii")
    run_remote_bash(
        f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(path)}"
    )


def remote_list_files(directory: str) -> list[dict]:
    script = (
        f"export DIR={shlex.quote(directory)}\n"
        'mkdir -p "$DIR"\n'
        "python3 -c \"import json, os; d=os.environ['DIR']; "
        "items=[{'name':n,'size':os.path.getsize(os.path.join(d,n)),'modified_at':os.path.getmtime(os.path.join(d,n))} "
        "for n in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d,n))]; print(json.dumps(items))\""
    )
    raw = run_remote_bash(script)
    if not raw:
        return []
    return json.loads(raw)


def remote_is_file(path: str) -> bool:
    try:
        run_remote_bash(f"test -f {shlex.quote(path)}")
        return True
    except PiLocalStorageError:
        return False


def remote_fetch_to_temp(path: str) -> Path:
    target = ssh_target()
    suffix = PurePosixPath(path).suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    try:
        proc = subprocess.run(
            ["scp", *_SSH_OPTS, f"{target}:{path}", tmp.name],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise PiLocalStorageError("Cliente scp não encontrado.") from exc
    if proc.returncode != 0:
        Path(tmp.name).unlink(missing_ok=True)
        raise PiLocalStorageError((proc.stderr or proc.stdout or "scp falhou").strip())
    return Path(tmp.name)


def remote_put_file(local_path: Path, remote_path: str) -> None:
    target = ssh_target()
    remote_dir = str(PurePosixPath(remote_path).parent)
    remote_mkdir_p(remote_dir)
    proc = subprocess.run(
        ["scp", *_SSH_OPTS, str(local_path), f"{target}:{remote_path}"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise PiLocalStorageError((proc.stderr or proc.stdout or "scp falhou").strip())


def posix_path(*parts: str) -> str:
    return str(PurePosixPath(*parts))