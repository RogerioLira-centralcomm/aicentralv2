"""Pastas de arquivos do PI no servidor (substitui criação via Make/Google Drive)."""

from __future__ import annotations

import logging
import os
import platform
import re
import secrets
import shlex
import tempfile
from pathlib import Path, PurePosixPath

from flask import current_app, has_request_context, url_for
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class PiLocalStorageError(Exception):
    """Falha ao preparar ou acessar pastas locais do PI."""


SECOES = (
    "principal",
    "financeiro",
    "pecas",
    "assinados",
)

_SECAO_PARA_CAMPO = {
    "principal": "googled_pi_princ",
    "financeiro": "googled_pi_financ",
    "pecas": "googled_pi_pecas",
    "assinados": "googled_pi_arq_ass",
}

_CAMPO_PARA_SECAO = {v: k for k, v in _SECAO_PARA_CAMPO.items()}


def normalize_pi_pastas_backend(value: str | None) -> str:
    text = str(value or "local").strip().lower()
    if text in ("padrão", "padrao", "default"):
        return "local"
    return text or "local"


def _backend() -> str:
    try:
        raw = current_app.config.get("PI_PASTAS_BACKEND") or os.getenv("PI_PASTAS_BACKEND", "local")
    except RuntimeError:
        raw = os.getenv("PI_PASTAS_BACKEND", "local")
    return normalize_pi_pastas_backend(raw)


def use_local_pastas() -> bool:
    mode = _backend()
    if mode == "make":
        return False
    if mode == "local":
        return True
    # auto: local quando o webhook Drive não estiver configurado
    return not (os.getenv("MAKE_WEBHOOK_GDRIVE") or "").strip()


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").lower() in ("true", "1", "yes", "on")


def pi_local_disk_disabled() -> bool:
    """No Windows com PI_FILES_SERVER_ONLY: não gravar em instance/uploads/pi no PC."""
    if platform.system() != "Windows":
        return False
    try:
        cfg = current_app.config.get("PI_FILES_SERVER_ONLY")
        if cfg is not None:
            return bool(cfg)
    except RuntimeError:
        pass
    return _env_bool("PI_FILES_SERVER_ONLY")


def _public_base_for_pi_files() -> str:
    for key in ("PI_VERIFY_BASE_URL", "CENTRALX_URL", "BASE_URL"):
        val = (os.getenv(key) or "").strip().rstrip("/")
        if val and "localhost" not in val.lower() and "127.0.0.1" not in val:
            return val
    return "https://ai.centralcomm.media"


def _exigir_disco_local_pi_permitido() -> None:
    if not pi_local_disk_disabled():
        return
    base = _public_base_for_pi_files()
    raise PiLocalStorageError(
        "Arquivos do PI ficam somente no servidor Linux (deploy/gunicorn), não neste PC. "
        "Gere pastas e administre upload pela URL logada após publicar: "
        f"{base}/cadu_pi/<id>/arquivos/principal. "
        "Smoke: python scripts/verify_pi_storage.py --remote "
        "(PI_VERIFY_BASE_URL, credenciais, PI_VERIFY_ID_PI)."
    )


def _configured_upload_root() -> str:
    override = ""
    try:
        override = str(current_app.config.get("PI_UPLOAD_ROOT") or "").strip()
    except RuntimeError:
        pass
    if not override:
        override = os.getenv("PI_UPLOAD_ROOT", "").strip()
    return override


def pi_upload_root() -> Path:
    from . import pi_storage_ssh

    _exigir_disco_local_pi_permitido()
    override = _configured_upload_root()
    if override:
        if override.startswith("/"):
            if pi_storage_ssh.remote_storage_enabled():
                return Path(override)  # caminho lógico no servidor Linux
            if platform.system() == "Windows":
                raise PiLocalStorageError(
                    "No dev (Windows), não use caminho Linux em PI_UPLOAD_ROOT. "
                    "Use um caminho Windows (ex.: PI_UPLOAD_ROOT=D:\\centralcomm\\pi) "
                    "ou comente PI_UPLOAD_ROOT. "
                    "Acesso aos arquivos é pela URL /cadu_pi/<id>/arquivos/... (login), "
                    "não por pasta de rede no disco. "
                    "Em produção, /var/www/... fica só no .env do servidor."
                )
        root = Path(override).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    try:
        root = Path(current_app.instance_path) / "uploads" / "pi"
    except RuntimeError:
        root = Path(os.getenv("INSTANCE_PATH", "instance")) / "uploads" / "pi"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_codigo_pi(codigo: str) -> str:
    text = str(codigo or "").strip()
    text = re.sub(r"[^\w.\-]+", "_", text, flags=re.UNICODE)
    return text[:120] or "pi_sem_codigo"


def pi_storage_dir(pi: dict) -> Path:
    id_pi = int(pi.get("id_pi") or 0)
    if id_pi <= 0:
        raise PiLocalStorageError("PI sem id_pi")
    codigo = _safe_codigo_pi(pi.get("codigo_pi_cc") or "")
    root = pi_upload_root()
    name = f"{codigo}__{id_pi}"
    return root / name


def production_pi_upload_root_posix() -> str:
    """Raiz Linux de PI (só exibição/script; não grava neste host)."""
    root = _configured_upload_root()
    if root.startswith("/"):
        return root
    return "/var/www/aicentralv2/instance/uploads/pi"


def pi_storage_dir_posix(pi: dict) -> str:
    """Caminho POSIX do PI (servidor ou local)."""
    from . import pi_storage_ssh

    id_pi = int(pi.get("id_pi") or 0)
    if id_pi <= 0:
        raise PiLocalStorageError("PI sem id_pi")
    codigo = _safe_codigo_pi(pi.get("codigo_pi_cc") or "")
    root = _configured_upload_root()
    if not root or not root.startswith("/"):
        if pi_local_disk_disabled() or platform.system() == "Windows":
            root = production_pi_upload_root_posix()
        else:
            root = str(pi_upload_root())
    return pi_storage_ssh.posix_path(root, f"{codigo}__{id_pi}")


def secao_dir_posix(pi: dict, secao: str) -> str:
    from . import pi_storage_ssh

    secao = str(secao or "").strip().lower()
    if secao not in SECOES:
        raise PiLocalStorageError(f"Seção de arquivos inválida: {secao}")
    return pi_storage_ssh.posix_path(pi_storage_dir_posix(pi), secao)


def secao_dir(pi: dict, secao: str) -> Path:
    secao = str(secao or "").strip().lower()
    if secao not in SECOES:
        raise PiLocalStorageError(f"Seção de arquivos inválida: {secao}")
    base = pi_storage_dir(pi).resolve()
    target = (base / secao).resolve()
    if base not in target.parents and target != base:
        raise PiLocalStorageError("Caminho fora da pasta do PI.")
    return target


def is_local_arquivos_url(url: str | None) -> bool:
    text = str(url or "").strip().lower()
    if "drive.google.com" in text:
        return False
    if "/arquivos/" not in text:
        return False
    return "/cadu_pi/" in text or "/campanha/p/" in text


def arquivos_url_publica_pi(pi: dict, secao: str) -> str:
    """
    URL de arquivos sem login (mesmo token do link público de acompanhamento).
    Usada em googled_pi_* para e-mail Brevo e página pública.
    """
    from aicentralv2 import db

    id_pi = int(pi.get("id_pi") or 0)
    if id_pi <= 0:
        raise PiLocalStorageError("PI sem id_pi")
    secao = str(secao or "").strip().lower()
    if secao not in SECOES:
        raise PiLocalStorageError(f"Seção inválida: {secao}")

    info = db.obter_link_publico_pi(id_pi) or {}
    token = (info.get("link_publico_token") or "").strip()
    ativo = bool(info.get("link_publico_ativo"))
    if not token or not ativo:
        token = db.gerar_link_publico_pi(id_pi)
    if not token:
        raise PiLocalStorageError(
            "Não foi possível ativar o link público do PI para pastas de arquivos."
        )

    if has_request_context():
        return url_for(
            "campanha_publica_arquivos_secao",
            token=token,
            secao=secao,
            _external=True,
        )
    base = (os.getenv("BASE_URL") or os.getenv("CENTRALX_URL") or "").rstrip("/")
    path = f"/campanha/p/{token}/arquivos/{secao}"
    return f"{base}{path}" if base else path


def _portal_url(id_pi: int, secao: str, *, external: bool = True) -> str:
    """Rota autenticada (equipe): upload no Central logado."""
    if not has_request_context():
        base = (os.getenv("BASE_URL") or os.getenv("CENTRALX_URL") or "").rstrip("/")
        if base:
            return f"{base}/cadu_pi/{id_pi}/arquivos/{secao}"
        return f"/cadu_pi/{id_pi}/arquivos/{secao}"
    return url_for("cadu_pi_arquivos_secao", id_pi=id_pi, secao=secao, _external=external)


def gerar_pastas_local_pi(pi: dict, *, strict: bool = False) -> dict[str, str]:
    """
    Cria subpastas do PI no disco e grava URLs do portal no cadastro.

    Mantém os campos googled_pi_* por compatibilidade (legado Drive + UI).
    """
    from aicentralv2 import db

    _exigir_disco_local_pi_permitido()
    id_pi = pi.get("id_pi")
    if not id_pi:
        raise PiLocalStorageError("PI sem id_pi")

    if pi.get("googled_pi_princ"):
        if strict and not is_local_arquivos_url(pi.get("googled_pi_princ")):
            raise PiLocalStorageError("Pastas já foram geradas para este PI")
        return {
            "googled_pi_princ": pi.get("googled_pi_princ") or "",
            "googled_pi_financ": pi.get("googled_pi_financ") or "",
            "googled_pi_pecas": pi.get("googled_pi_pecas") or "",
            "googled_pi_arq_ass": pi.get("googled_pi_arq_ass") or "",
        }

    if not pi.get("codigo_pi_cc"):
        raise PiLocalStorageError("PI sem código (codigo_pi_cc)")

    from . import pi_storage_ssh

    urls: dict[str, str] = {}
    readme_text = lambda s: (
        f"PI {pi.get('codigo_pi_cc')} — pasta {s}\n"
        "Arquivos desta seção ficam neste diretório no servidor.\n"
    )

    if pi_storage_ssh.remote_storage_enabled():
        base = pi_storage_dir_posix(pi)
        pi_storage_ssh.remote_mkdir_p(base)
        for secao in SECOES:
            folder = pi_storage_ssh.posix_path(base, secao)
            pi_storage_ssh.remote_mkdir_p(folder)
            pi_storage_ssh.remote_write_text(
                pi_storage_ssh.posix_path(folder, "LEIA-ME.txt"),
                readme_text(secao),
            )
            urls[_SECAO_PARA_CAMPO[secao]] = arquivos_url_publica_pi(pi, secao)
        storage_path = base
    else:
        base_path = pi_storage_dir(pi)
        for secao in SECOES:
            folder = base_path / secao
            folder.mkdir(parents=True, exist_ok=True)
            readme = folder / "LEIA-ME.txt"
            if not readme.exists():
                readme.write_text(readme_text(secao), encoding="utf-8")
            urls[_SECAO_PARA_CAMPO[secao]] = arquivos_url_publica_pi(pi, secao)
        storage_path = str(base_path)

    db.atualizar_cadu_pi_gdrive(
        id_pi,
        urls["googled_pi_princ"],
        urls["googled_pi_financ"],
        urls["googled_pi_pecas"],
        urls["googled_pi_arq_ass"],
    )

    logger.info(
        "Pastas locais do PI %s em %s",
        pi.get("codigo_pi_cc"),
        storage_path,
    )

    result = dict(urls)
    result["storage_path"] = storage_path
    exigir_pastas_pi_acessiveis({**pi, **urls})
    return result


def pi_usa_pastas_locais(pi: dict) -> bool:
    """PI com pastas neste servidor (não Google Drive legado)."""
    if not use_local_pastas():
        return False
    url = (pi.get("googled_pi_princ") or "").strip()
    if not url:
        return True
    return is_local_arquivos_url(url)


def diagnosticar_pastas_pi(pi: dict) -> dict:
    """Estado das pastas no disco: acessível ou não."""
    from . import pi_storage_ssh

    out = {
        "ok": False,
        "motivo": "",
        "storage_path": "",
        "gravavel": False,
        "secoes": {s: False for s in SECOES},
    }
    if not pi.get("id_pi") or not pi.get("codigo_pi_cc"):
        out["motivo"] = "PI incompleto (id ou código)"
        return out
    if not pi_usa_pastas_locais(pi):
        out["ok"] = True
        out["motivo"] = "legado_drive_ou_make"
        return out
    if not (pi.get("googled_pi_princ") or "").strip():
        out["motivo"] = "Pastas ainda não geradas"
        return out
    try:
        if pi_storage_ssh.remote_storage_enabled():
            base = pi_storage_dir_posix(pi)
            out["storage_path"] = base
            for secao in SECOES:
                folder = pi_storage_ssh.posix_path(base, secao)
                pi_storage_ssh.run_remote_bash(f"test -d {shlex.quote(folder)}")
                out["secoes"][secao] = True
            probe = pi_storage_ssh.posix_path(base, "principal", f".probe_{os.getpid()}")
            pi_storage_ssh.remote_write_text(probe, "ok\n")
            pi_storage_ssh.run_remote_bash(f"rm -f {shlex.quote(probe)}")
            out["gravavel"] = True
            out["ok"] = all(out["secoes"].values())
            out["motivo"] = "ok" if out["ok"] else "subpasta ausente"
            return out

        base = pi_storage_dir(pi)
        out["storage_path"] = str(base)
        if not base.is_dir():
            out["motivo"] = f"Pasta do PI não existe: {base}"
            return out
        for secao in SECOES:
            folder = base / secao
            out["secoes"][secao] = folder.is_dir()
        probe = base / "principal" / f".probe_{os.getpid()}"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        out["gravavel"] = True
        out["ok"] = all(out["secoes"].values()) and out["gravavel"]
        out["motivo"] = "ok" if out["ok"] else "subpasta ausente ou sem permissão"
        return out
    except PiLocalStorageError as exc:
        out["motivo"] = str(exc)
        return out
    except OSError as exc:
        out["motivo"] = str(exc)
        return out


def exigir_pastas_pi_acessiveis(pi: dict) -> dict:
    """Levanta erro se o PI deve ter pastas locais e não há acesso ao disco."""
    diag = diagnosticar_pastas_pi(pi)
    if diag.get("motivo") == "legado_drive_ou_make":
        return diag
    if not diag.get("ok"):
        raise PiLocalStorageError(
            diag.get("motivo") or "Sem acesso às pastas do PI no disco"
        )
    return diag


def listar_arquivos_secao(pi: dict, secao: str) -> list[dict]:
    from . import pi_storage_ssh

    exigir_pastas_pi_acessiveis(pi)

    if pi_storage_ssh.remote_storage_enabled():
        folder = secao_dir_posix(pi, secao)
        pi_storage_ssh.remote_mkdir_p(folder)
        return pi_storage_ssh.remote_list_files(folder)

    folder = secao_dir(pi, secao)
    folder.mkdir(parents=True, exist_ok=True)
    items = []
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file():
            continue
        stat = entry.stat()
        items.append(
            {
                "name": entry.name,
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    return items


def resolve_arquivo(pi: dict, secao: str, filename: str) -> Path:
    from . import pi_storage_ssh

    name = secure_filename(str(filename or "").strip())
    if not name or name != str(filename or "").strip().replace("\\", "/").split("/")[-1]:
        raise PiLocalStorageError("Nome de arquivo inválido.")

    if pi_storage_ssh.remote_storage_enabled():
        remote = pi_storage_ssh.posix_path(secao_dir_posix(pi, secao), name)
        if not pi_storage_ssh.remote_is_file(remote):
            raise PiLocalStorageError("Arquivo não encontrado.")
        return pi_storage_ssh.remote_fetch_to_temp(remote)

    folder = secao_dir(pi, secao)
    path = (folder / name).resolve()
    folder_resolved = folder.resolve()
    if folder_resolved not in path.parents:
        raise PiLocalStorageError("Arquivo fora da pasta permitida.")
    if not path.is_file():
        raise PiLocalStorageError("Arquivo não encontrado.")
    return path


def salvar_upload(pi: dict, secao: str, file_storage) -> dict:
    exigir_pastas_pi_acessiveis(pi)
    if not file_storage or not getattr(file_storage, "filename", None):
        raise PiLocalStorageError("Nenhum arquivo enviado.")
    raw_name = str(file_storage.filename or "").strip()
    safe = secure_filename(raw_name)
    if not safe:
        raise PiLocalStorageError("Nome de arquivo inválido.")

    from . import pi_storage_ssh

    if pi_storage_ssh.remote_storage_enabled():
        folder = secao_dir_posix(pi, secao)
        pi_storage_ssh.remote_mkdir_p(folder)
        dest_name = safe
        remote = pi_storage_ssh.posix_path(folder, dest_name)
        if pi_storage_ssh.remote_is_file(remote):
            stem = PurePosixPath(safe).stem
            suffix = PurePosixPath(safe).suffix
            dest_name = f"{stem}__{secrets.token_hex(3)}{suffix}"
            remote = pi_storage_ssh.posix_path(folder, dest_name)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_storage.save(tmp.name)
            size = Path(tmp.name).stat().st_size
            pi_storage_ssh.remote_put_file(Path(tmp.name), remote)
        Path(tmp.name).unlink(missing_ok=True)
        return {"name": dest_name, "size": size, "path": remote}

    folder = secao_dir(pi, secao)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / safe
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        token = secrets.token_hex(3)
        dest = folder / f"{stem}__{token}{suffix}"
    file_storage.save(dest)
    stat = dest.stat()
    return {"name": dest.name, "size": stat.st_size, "path": str(dest)}