"""Storage local e validado para logos da Modelagem de Criativos."""

import base64
import binascii
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/octet-stream",
}
MAX_LOGO_SIZE = 5 * 1024 * 1024
PUBLIC_PREFIX = "/static/uploads/client_logos/"
REFERENCE_PREFIX = "/static/uploads/creative_references/"
GENERATED_PREFIX = "/static/uploads/creative_generated/"


def _root(folder="client_logos"):
    root = Path(current_app.root_path) / "static" / "uploads" / folder
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_logo(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("Selecione um arquivo de logo.")
    original = secure_filename(file_storage.filename)
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato inválido. Use PNG, JPG ou WEBP.")
    mime = (file_storage.mimetype or "").lower()
    if mime and mime not in ALLOWED_MIMES:
        raise ValueError("O arquivo enviado não é uma imagem válida.")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        raise ValueError("O arquivo de logo está vazio.")
    if size > MAX_LOGO_SIZE:
        raise ValueError("O logo deve ter no máximo 5 MB.")
    return extension


class ClientLogoStorage:
    def save(self, file_storage):
        extension = validate_logo(file_storage)
        filename = f"{uuid.uuid4().hex}{extension}"
        file_storage.save(str(_root("client_logos") / filename))
        return f"{PUBLIC_PREFIX}{filename}"

    def delete(self, public_path):
        if not public_path or not str(public_path).startswith(PUBLIC_PREFIX):
            return
        filename = Path(str(public_path)).name
        if filename in {"", ".", ".."}:
            return
        (_root("client_logos") / filename).unlink(missing_ok=True)


class CreativeAssetStorage:
    def save_reference(self, file_storage):
        extension = validate_logo(file_storage)
        filename = f"{uuid.uuid4().hex}{extension}"
        file_storage.save(str(_root("creative_references") / filename))
        return {
            "asset_path": f"{REFERENCE_PREFIX}{filename}",
            "original_name": secure_filename(file_storage.filename),
            "mime_type": file_storage.mimetype or "application/octet-stream",
        }

    def save_generated_base64(self, encoded, output_format="png"):
        output_format = (output_format or "png").lower()
        extensions = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp"}
        extension = extensions.get(output_format)
        if not extension:
            raise ValueError("Formato de imagem retornado não é suportado.")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("A imagem retornada pelo provedor é inválida.") from exc
        if not content:
            raise ValueError("O provedor retornou uma imagem vazia.")
        filename = f"{uuid.uuid4().hex}{extension}"
        (_root("creative_generated") / filename).write_bytes(content)
        return f"{GENERATED_PREFIX}{filename}"

    def absolute_reference_path(self, public_path):
        if not public_path or not str(public_path).startswith(REFERENCE_PREFIX):
            return None
        path = _root("creative_references") / Path(str(public_path)).name
        return path if path.is_file() else None

    def absolute_generated_path(self, public_path):
        if not public_path or not str(public_path).startswith(GENERATED_PREFIX):
            return None
        path = _root("creative_generated") / Path(str(public_path)).name
        return path if path.is_file() else None

    def reference_as_data_url(self, public_path, mime_type):
        path = self.absolute_reference_path(public_path)
        if path is None:
            raise ValueError("Imagem de referência não encontrada.")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type or 'image/png'};base64,{encoded}"

    def delete(self, public_path):
        prefixes = {
            REFERENCE_PREFIX: "creative_references",
            GENERATED_PREFIX: "creative_generated",
        }
        for prefix, folder in prefixes.items():
            if public_path and str(public_path).startswith(prefix):
                (_root(folder) / Path(str(public_path)).name).unlink(missing_ok=True)
                return
