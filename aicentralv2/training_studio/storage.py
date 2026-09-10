"""Arquivos gerados do Studio de Treinamentos."""

import base64
import binascii
import uuid
from pathlib import Path

import requests
from flask import current_app


GENERATED_PREFIX = "/static/uploads/treinamento_generated/"
LOGO_PREFIX = "/static/uploads/treinamento_generated/logos/"


def _root(folder=""):
    root = Path(current_app.root_path) / "static" / "uploads" / "treinamento_generated"
    if folder:
        root = root / folder
    root.mkdir(parents=True, exist_ok=True)
    return root


class TrainingAssetStorage:
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
        (_root() / filename).write_bytes(content)
        return f"{GENERATED_PREFIX}{filename}"

    def save_remote_logo(self, url):
        response = requests.get(
            url,
            headers={"User-Agent": "CentralX-TrainingStudio/2026", "Accept": "image/*"},
            timeout=20,
        )
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        extension = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "image/x-icon": ".ico",
            "image/vnd.microsoft.icon": ".ico",
        }.get(content_type, ".png")
        content = response.content or b""
        if not content:
            raise ValueError("Logo vazio.")
        filename = f"{uuid.uuid4().hex}{extension}"
        (_root("logos") / filename).write_bytes(content)
        return f"{LOGO_PREFIX}{filename}"
