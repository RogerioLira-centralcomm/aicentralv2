"""Storage local e validado para logos da Modelagem de Criativos."""

import base64
import binascii
import hashlib
import ipaddress
import os
import socket
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
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


def _validated_public_asset_url(raw):
    value = str(raw or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("A referência deve usar uma URL pública HTTP ou HTTPS.")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        }
    except socket.gaierror as exc:
        raise ValueError("Não foi possível resolver a imagem de referência.") from exc
    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("A referência deve apontar para um endereço público.")
    return value


def _remote_extension(content_type):
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type)


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
        path = _root("creative_references") / filename
        file_storage.save(str(path))
        return {
            "asset_path": f"{REFERENCE_PREFIX}{filename}",
            "original_name": secure_filename(file_storage.filename),
            "mime_type": file_storage.mimetype or "application/octet-stream",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
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

    def save_remote_reference(self, url, referer=None):
        current = _validated_public_asset_url(url)
        response = None
        for _ in range(4):
            response = requests.get(
                current,
                headers={
                    "User-Agent": "CentralX-Brand-Curator/2026",
                    "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.4",
                    **({"Referer": referer} if referer else {}),
                },
                timeout=20,
                stream=True,
                allow_redirects=False,
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Redirecionamento inválido na referência.")
                current = _validated_public_asset_url(urljoin(current, location))
                continue
            break
        if response is None or response.status_code // 100 != 2:
            raise ValueError("Não foi possível baixar a imagem selecionada.")
        content_type = (
            response.headers.get("Content-Type") or ""
        ).split(";", 1)[0].strip().lower()
        extension = _remote_extension(content_type)
        if not extension:
            raise ValueError("A URL selecionada não retornou PNG, JPG ou WEBP.")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content.extend(chunk)
            if len(content) > MAX_LOGO_SIZE:
                raise ValueError("A imagem selecionada excede 5 MB.")
        signatures = {
            ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": content.startswith(b"\xff\xd8\xff"),
            ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        }
        if not content or not signatures.get(extension):
            raise ValueError("O conteúdo baixado não corresponde a uma imagem válida.")
        filename = f"{uuid.uuid4().hex}{extension}"
        (_root("creative_references") / filename).write_bytes(content)
        return {
            "asset_path": f"{REFERENCE_PREFIX}{filename}",
            "original_name": Path(urlparse(current).path).name[:255],
            "mime_type": content_type,
            "sha256": hashlib.sha256(content).hexdigest(),
            "source_url": current,
        }

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

    def public_as_data_url(self, public_path, mime_type=None):
        path = self.absolute_public_path(public_path)
        if path is None:
            raise ValueError("Imagem oficial não encontrada.")
        mime = mime_type or {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/png")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def generated_as_data_url(self, public_path):
        path = self.absolute_generated_path(public_path)
        if path is None:
            raise ValueError("Mockup anterior não encontrado.")
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/png")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def absolute_public_path(self, public_path):
        mapping = {
            PUBLIC_PREFIX: "client_logos",
            REFERENCE_PREFIX: "creative_references",
            GENERATED_PREFIX: "creative_generated",
        }
        value = str(public_path or "")
        for prefix, folder in mapping.items():
            if value.startswith(prefix):
                path = _root(folder) / Path(value).name
                return path if path.is_file() else None
        return None

    def read_public_bytes(self, public_path):
        path = self.absolute_public_path(public_path)
        if path is None:
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def delete(self, public_path):
        prefixes = {
            REFERENCE_PREFIX: "creative_references",
            GENERATED_PREFIX: "creative_generated",
        }
        for prefix, folder in prefixes.items():
            if public_path and str(public_path).startswith(prefix):
                (_root(folder) / Path(str(public_path)).name).unlink(missing_ok=True)
                return
