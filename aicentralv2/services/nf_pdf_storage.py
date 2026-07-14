"""
Armazenamento de PDFs de notas fiscais importadas.
Arquivos em static/uploads/notas_fiscais/ — download via rota autenticada.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'.pdf'}
ALLOWED_MIMES = {'application/pdf', 'application/octet-stream'}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB


def _upload_root():
    root = Path(current_app.root_path) / 'static' / 'uploads' / 'notas_fiscais'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _pending_root():
    root = _upload_root() / 'pending'
    root.mkdir(parents=True, exist_ok=True)
    return root


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def validate_nf_pdf_upload(file_storage):
    """Valida extensão, mime e tamanho. Retorna (ok, error_msg)."""
    if not file_storage or not file_storage.filename:
        return False, 'Arquivo obrigatório'

    filename = secure_filename(file_storage.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f'Tipo não permitido ({ext}). Envie PDF.'

    mime = (file_storage.mimetype or '').lower()
    if mime and mime not in ALLOWED_MIMES:
        return False, f'MIME não permitido: {mime}'

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_FILE_SIZE:
        return False, 'Arquivo maior que 15 MB'
    if size == 0:
        return False, 'Arquivo vazio'

    return True, None


class NfPdfStorage:
    """Backend local para PDFs de NF (pendentes e definitivos)."""

    def save_pending(self, file_bytes: bytes, original_filename: str) -> dict:
        temp_id = uuid.uuid4().hex
        safe_name = secure_filename(original_filename) or 'nota.pdf'
        ext = Path(safe_name).suffix.lower() or '.pdf'
        key = f'pending/{temp_id}{ext}'
        dest = _upload_root() / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_bytes)
        file_hash = compute_file_hash(file_bytes)
        return {
            'temp_id': temp_id,
            'storage_key': key.replace('\\', '/'),
            'file_name': safe_name,
            'file_size': len(file_bytes),
            'hash_arquivo': file_hash,
        }

    def move_pending_to_permanent(self, temp_id: str, id_nota: int) -> str | None:
        pending_dir = _pending_root()
        matches = list(pending_dir.glob(f'{temp_id}.*'))
        if not matches:
            return None
        src = matches[0]
        ext = src.suffix.lower() or '.pdf'
        hash8 = temp_id[:8]
        key = f'{id_nota}_{hash8}{ext}'
        dest = _upload_root() / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        src.replace(dest)
        return key.replace('\\', '/')

    def absolute_path(self, storage_key: str):
        safe = storage_key.replace('..', '').lstrip('/\\')
        path = _upload_root() / safe
        if not path.is_file():
            return None
        return path

    def delete_pending(self, temp_id: str):
        pending_dir = _pending_root()
        for p in pending_dir.glob(f'{temp_id}.*'):
            p.unlink(missing_ok=True)

    def delete(self, storage_key: str):
        path = self.absolute_path(storage_key)
        if path and path.is_file():
            path.unlink(missing_ok=True)
