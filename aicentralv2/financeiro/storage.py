"""
Storage de comprovantes — interface S3-ready com backend local (Fase 1).
Arquivos ficam em static/uploads/reembolsos/ mas NÃO são servidos como static público;
download sempre via rota autenticada.
"""
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.pdf'}
ALLOWED_MIMES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif',
    'application/pdf',
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _upload_root():
    root = Path(current_app.root_path) / 'static' / 'uploads' / 'reembolsos'
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_upload(file_storage):
    """Valida extensão, mime e tamanho. Retorna (ok, error_msg)."""
    if not file_storage or not file_storage.filename:
        return False, 'Arquivo obrigatório'

    filename = secure_filename(file_storage.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f'Tipo de arquivo não permitido ({ext}). Use imagem ou PDF.'

    mime = (file_storage.mimetype or '').lower()
    if mime and mime not in ALLOWED_MIMES:
        # alguns browsers mandam application/octet-stream
        if mime != 'application/octet-stream':
            return False, f'MIME não permitido: {mime}'

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_FILE_SIZE:
        return False, 'Arquivo maior que 10 MB'
    if size == 0:
        return False, 'Arquivo vazio'

    return True, None


class ReceiptStorage:
    """Backend local com chave storage_key estável para migração futura a S3."""

    def save(self, file_storage, expense_id):
        ok, err = validate_upload(file_storage)
        if not ok:
            raise ValueError(err)

        original = secure_filename(file_storage.filename)
        ext = Path(original).suffix.lower() or '.bin'
        key = f'{expense_id}/{uuid.uuid4().hex}{ext}'
        dest = _upload_root() / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(str(dest))

        size = dest.stat().st_size
        mime = file_storage.mimetype or 'application/octet-stream'
        return {
            'storage_key': key.replace('\\', '/'),
            'file_name': original,
            'mime_type': mime,
            'file_size': size,
        }

    def absolute_path(self, storage_key):
        safe = storage_key.replace('..', '').lstrip('/\\')
        path = _upload_root() / safe
        if not path.is_file():
            return None
        return path

    def delete(self, storage_key):
        path = self.absolute_path(storage_key)
        if path and path.is_file():
            path.unlink(missing_ok=True)

    def delete_for_expense(self, expense_id, storage_keys=None):
        """Remove comprovantes da despesa e limpa a pasta no disco."""
        keys = list(storage_keys or [])
        for key in keys:
            try:
                self.delete(key)
            except Exception:
                pass

        if not expense_id:
            return

        folder = _upload_root() / str(expense_id).replace('..', '').strip('/\\')
        if not folder.is_dir():
            return
        try:
            for child in folder.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            folder.rmdir()
        except OSError:
            pass
