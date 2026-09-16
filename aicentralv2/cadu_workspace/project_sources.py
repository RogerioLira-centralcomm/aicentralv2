"""Private project-source ingestion for the Workspace knowledge dossier."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import re
import xml.etree.ElementTree as ET

from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


MAX_BYTES = 15 * 1024 * 1024
MAX_TEXT = 120_000
TEXT_EXTENSIONS = {'.txt', '.csv', '.md', '.markdown', '.json'}
HTML_EXTENSIONS = {'.html', '.htm'}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | HTML_EXTENSIONS | {'.pdf', '.docx'}


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self.skip += 1
        elif tag in {'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        value = re.sub(r'[ \t]+', ' ', ''.join(self.parts))
        return re.sub(r'\n{3,}', '\n\n', value).strip()


def chunks(content: str, limit: int = 1800) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r'\n\s*\n', content) if item.strip()]
    output = []
    current = ''
    for paragraph in paragraphs:
        if len(paragraph) > limit:
            if current:
                output.append(current)
                current = ''
            output.extend(paragraph[index:index + limit].strip() for index in range(0, len(paragraph), limit))
        elif current and len(current) + len(paragraph) + 2 > limit:
            output.append(current)
            current = paragraph
        else:
            current = f'{current}\n\n{paragraph}'.strip()
    if current:
        output.append(current)
    return [item for item in output if item]


def _decode_text(data: bytes) -> str:
    try:
        value = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise BadRequest('O arquivo de texto precisa estar em UTF-8.') from exc
    if '\x00' in value:
        raise BadRequest('O arquivo contém dados binários incompatíveis.')
    return value


def _pdf_text(data: bytes) -> str:
    if not data.startswith(b'%PDF-'):
        raise BadRequest('O conteúdo não corresponde a um PDF válido.')
    try:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        return '\n'.join((page.extract_text() or '') for page in reader.pages[:80])
    except Exception as exc:
        raise BadRequest('Não foi possível ler o PDF. Verifique se ele está íntegro e sem senha.') from exc


def _docx_text(data: bytes) -> str:
    try:
        with ZipFile(BytesIO(data)) as package:
            if sum(item.file_size for item in package.infolist()) > 40 * 1024 * 1024:
                raise BadRequest('O DOCX descompactado ultrapassa o limite permitido.')
            xml = package.read('word/document.xml')
    except (BadZipFile, KeyError) as exc:
        raise BadRequest('O conteúdo não corresponde a um DOCX válido.') from exc
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise BadRequest('Não foi possível ler a estrutura do DOCX.') from exc
    values = [node.text or '' for node in root.iter() if node.tag.endswith('}t')]
    return ' '.join(value for value in values if value).strip()


def validate_upload(file_storage) -> dict:
    name = secure_filename(file_storage.filename or '')[:220]
    suffix = Path(name).suffix.lower()
    if not name or suffix not in ALLOWED_EXTENSIONS:
        raise BadRequest('Use PDF, DOCX, TXT, CSV, Markdown, JSON ou HTML.')
    data = file_storage.stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise RequestEntityTooLarge('Cada fonte pode ter no máximo 15 MB.')
    if not data:
        raise BadRequest('O arquivo está vazio.')
    if suffix == '.pdf':
        text = _pdf_text(data)
        mime = 'application/pdf'
    elif suffix == '.docx':
        text = _docx_text(data)
        mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        decoded = _decode_text(data)
        if suffix in HTML_EXTENSIONS:
            parser = _HTMLText()
            parser.feed(decoded)
            text = parser.text()
            mime = 'text/html'
        else:
            text = decoded
            mime = file_storage.mimetype if str(file_storage.mimetype or '').startswith('text/') else 'text/plain'
    text = text.strip()[:MAX_TEXT]
    if len(text) < 20:
        raise BadRequest('Não encontramos texto suficiente para adicionar esta fonte.')
    return {'name': name, 'suffix': suffix, 'mime': mime, 'data': data, 'text': text}


def reextract(name: str, data: bytes, mime: str = '') -> dict:
    return validate_upload(FileStorage(stream=BytesIO(data), filename=name, content_type=mime))


def private_path(instance_path: str, client_id: int, project_id: str, suffix: str, source_id: str) -> Path:
    safe_project = re.sub(r'[^a-zA-Z0-9_-]', '', str(project_id))[:80]
    directory = Path(instance_path) / 'workspace_project_sources' / str(client_id) / safe_project
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{source_id}{suffix}'


def resolve_private_path(instance_path: str, storage_path: str) -> Path:
    root = (Path(instance_path) / 'workspace_project_sources').resolve()
    candidate = (Path(instance_path) / storage_path).resolve()
    if root not in candidate.parents:
        raise BadRequest('Caminho de fonte inválido.')
    return candidate


def extract_public_url(raw_url: str) -> dict:
    from ..crm_v3_web_scout import _firecrawl_scrape
    from ..training_studio.extract import validate_public_url

    url = validate_public_url(raw_url)
    data = _firecrawl_scrape(url, formats=['markdown'], timeout_s=40, only_main_content=True)
    metadata = data.get('metadata') or {}
    text = str(data.get('markdown') or data.get('content') or '').strip()[:MAX_TEXT]
    if len(text) < 20:
        raise BadRequest('Não encontramos conteúdo suficiente nessa página.')
    title = str(metadata.get('title') or metadata.get('ogTitle') or url).strip()[:220]
    return {'url': url, 'name': title, 'mime': 'text/uri-list', 'text': text}
