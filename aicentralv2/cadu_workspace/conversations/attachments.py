"""Bounded upload validation; never trust browser MIME or user identifiers."""
from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4
import warnings
from zipfile import BadZipFile, ZipFile

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from ...cadu_family import dify, repository

MAX_BYTES = 15 * 1024 * 1024
ACCEPT = '.png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.csv,.md,.json,.docx,.xlsx,.pptx'
IMAGE_FORMATS = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP', '.gif': 'GIF'}
TEXT_TYPES = {'.txt': 'text/plain', '.csv': 'text/csv', '.md': 'text/markdown', '.json': 'application/json'}
OFFICE_TYPES = {
    '.docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'word/document.xml'),
    '.xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xl/workbook.xml'),
    '.pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', 'ppt/presentation.xml'),
}
MAX_OFFICE_ENTRIES = 5000
MAX_OFFICE_UNCOMPRESSED_BYTES = 60 * 1024 * 1024


def validate_office(data, suffix):
    """Accept only bounded, structurally valid OOXML packages.

    The file remains opaque to this application and is forwarded to the
    provider. This check prevents an arbitrary zip or a zip bomb from reaching
    the provider under an Office extension.
    """
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            required = OFFICE_TYPES[suffix][1]
            if len(entries) > MAX_OFFICE_ENTRIES or '[Content_Types].xml' not in names or required not in names:
                raise ValueError('Missing OOXML parts')
            total = sum(entry.file_size for entry in entries)
            if total > MAX_OFFICE_UNCOMPRESSED_BYTES:
                raise ValueError('Office package expands beyond its limit')
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe OOXML package path')
    except (BadZipFile, ValueError, KeyError) as exc:
        raise BadRequest('Arquivo Office inválido ou grande demais para processamento seguro.') from exc


def validate(file):
    name = secure_filename(file.filename or '')[:180]
    suffix = PurePosixPath(name).suffix.lower()
    data = file.stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise RequestEntityTooLarge('Cada arquivo pode ter no máximo 15 MB.')
    if not data or not name:
        raise BadRequest('O arquivo está vazio ou não tem um nome válido.')
    kind = 'document'
    if suffix in IMAGE_FORMATS:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as img:
                    if img.format != IMAGE_FORMATS[suffix] or img.width * img.height > 25_000_000:
                        raise ValueError('Image format or dimensions')
                    img.verify()
            mime = Image.MIME[IMAGE_FORMATS[suffix]]
            kind = 'image'
        except Exception as exc:
            raise BadRequest('Imagem inválida, muito grande ou incompatível com a extensão.') from exc
    elif suffix == '.pdf':
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-4096:]:
            raise BadRequest('O conteúdo não corresponde a um PDF válido.')
        mime = 'application/pdf'
    elif suffix in TEXT_TYPES:
        try:
            text = data.decode('utf-8-sig')
            if '\x00' in text:
                raise ValueError('Binary content')
        except (UnicodeError, ValueError) as exc:
            raise BadRequest('Use um arquivo de texto em UTF-8, sem conteúdo binário.') from exc
        mime = TEXT_TYPES[suffix]
    elif suffix in OFFICE_TYPES:
        validate_office(data, suffix)
        mime = OFFICE_TYPES[suffix][0]
    else:
        raise BadRequest('Formato ainda não disponível. Use imagem, PDF, texto ou Office; SVG segue em migração.')
    return FileStorage(stream=BytesIO(data), filename=name, content_type=mime), kind, len(data)


def upload(file, user, selected):
    validated, kind, size = validate(file)
    conn = repository.get_db()
    # Check storage before sending any bytes to the provider.
    if not repository.family_table_available('cadu_family_chat_uploads'):
        raise BadRequest('O armazenamento de anexos ainda não está disponível.')
    provider_id = dify.upload(validated, 'user-' + str(user['id']))
    upload_id = str(uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_family_chat_uploads
                (id, user_id, client_id, provider_id, name, kind) VALUES (%s, %s, %s, %s, %s, %s)''',
                (upload_id, user['id'], selected['client_id'], provider_id, validated.filename, kind))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {'id': upload_id, 'name': validated.filename, 'kind': kind, 'size': size}
