"""Private project-source ingestion for the Workspace knowledge dossier."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
import mimetypes
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
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff', '.bmp', '.avif'}
CREATIVE_EXTENSIONS = {
    '.ai', '.eps', '.svg', '.psd', '.psb', '.indd', '.idml', '.fig', '.sketch', '.xd',
    '.afdesign', '.afphoto', '.afpub', '.kra', '.ora', '.blend', '.fbx', '.obj',
    '.mp4', '.mov', '.webm', '.avi', '.mkv', '.mp3', '.wav', '.m4a', '.flac',
}
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz'}


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


def _ocr_image(data: bytes) -> tuple[str, str]:
    """Best-effort OCR for visual references; never blocks preserving the asset."""
    try:
        from PIL import Image
        image = Image.open(BytesIO(data))
        image.load()
    except Exception:
        return '', 'metadata_only'


def _ocr_pdf(data: bytes) -> str:
    """Best-effort OCR for scanned PDFs when PyMuPDF and Tesseract exist."""
    try:
        import fitz
        from PIL import Image
        import pytesseract
        document = fitz.open(stream=data, filetype='pdf')
        parts = []
        for index in range(min(8, len(document))):
            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
            image = Image.frombytes('RGB', [pixmap.width, pixmap.height], pixmap.samples)
            parts.append(str(pytesseract.image_to_string(image, lang='por+eng') or ''))
        return '\n'.join(parts).strip()
    except Exception:
        return ''
    try:
        import pytesseract
        text = str(pytesseract.image_to_string(image, lang='por+eng') or '').strip()
        return text, 'ocr'
    except Exception:
        return '', 'metadata_only'


def _classify_source(name: str, suffix: str, text: str) -> dict:
    haystack = f'{name} {text[:4000]}'.casefold()
    rules = (
        ('media_plan', ('plano de mídia', 'plano de midia', 'media plan')),
        ('brief', ('briefing', 'brief ')),
        ('report', ('relatório', 'relatorio', 'report', 'dashboard')),
        ('research', ('pesquisa', 'research', 'estudo de mercado')),
        ('contract', ('contrato', 'contract', 'proposta comercial')),
        ('brand_asset', ('logo', 'marca', 'brandbook', 'brand book', 'manual de marca')),
    )
    for category, signals in rules:
        matched = next((signal for signal in signals if signal in haystack), None)
        if matched:
            return {'category': category, 'status': 'classified', 'confidence': 0.82,
                    'reason': f'Sinal identificado: {matched}.'}
    if suffix in {'.csv', '.xls', '.xlsx', '.ods'}:
        return {'category': 'spreadsheet', 'status': 'classified', 'confidence': 0.95,
                'reason': 'Formato de planilha.'}
    if suffix in IMAGE_EXTENSIONS or suffix in CREATIVE_EXTENSIONS:
        return {'category': 'reference', 'status': 'classified', 'confidence': 0.7,
                'reason': 'Arquivo visual ou criativo classificado como referência.'}
    if suffix in {'.mp4', '.mov', '.webm', '.avi', '.mkv', '.mp3', '.wav', '.m4a', '.flac'}:
        return {'category': 'reference', 'status': 'classified', 'confidence': 0.65,
                'reason': 'Mídia criativa preservada como referência do projeto.'}
    return {'category': 'other', 'status': 'needs_review', 'confidence': 0.25,
            'reason': 'Não há sinais suficientes para uma categoria específica.'}


def inspect_upload(file_storage, *, require_text: bool = False) -> dict:
    """Read metadata/text/OCR once while keeping every uploaded asset preservable.

    Text-capable formats can become knowledge after confirmation. Design files,
    media and unknown binaries remain project attachments with metadata even
    when no safe text adapter is installed.
    """
    name = secure_filename(file_storage.filename or '')[:220]
    suffix = Path(name).suffix.lower()
    if not name:
        raise BadRequest('Informe um nome de arquivo válido.')
    # Extensionless exports are still valid project assets; store them with a
    # neutral suffix while keeping the original safe display name.
    if not suffix:
        suffix = '.bin'
    data = file_storage.stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise RequestEntityTooLarge('Cada arquivo pode ter no máximo 15 MB.')
    if not data:
        raise BadRequest('O arquivo está vazio.')
    mime = str(file_storage.mimetype or mimetypes.guess_type(name)[0] or 'application/octet-stream')[:160]
    text = ''
    processing = 'metadata_only'
    if suffix == '.pdf':
        if data.startswith(b'%PDF-'):
            try:
                text = _pdf_text(data)
                processing = 'text_extraction' if text.strip() else 'metadata_only'
                if not text.strip():
                    text = _ocr_pdf(data)
                    processing = 'ocr' if text.strip() else 'metadata_only'
            except BadRequest:
                if require_text:
                    raise
        elif require_text:
            raise BadRequest('O conteúdo não corresponde a um PDF válido.')
    elif suffix == '.docx':
        try:
            text = _docx_text(data)
            processing = 'text_extraction'
        except BadRequest:
            if require_text:
                raise
    elif suffix in TEXT_EXTENSIONS | HTML_EXTENSIONS:
        try:
            decoded = _decode_text(data)
            if suffix in HTML_EXTENSIONS:
                parser = _HTMLText()
                parser.feed(decoded)
                text = parser.text()
            else:
                text = decoded
            processing = 'text_extraction'
        except BadRequest:
            if require_text:
                raise
    elif suffix in IMAGE_EXTENSIONS:
        text, processing = _ocr_image(data)
        if not text and require_text:
            raise BadRequest('Não encontramos texto suficiente para indexar esta imagem.')
    if require_text and len(text.strip()) < 20:
        raise BadRequest('Não encontramos texto suficiente para adicionar esta fonte.')
    return {
        'name': name, 'suffix': suffix, 'mime': mime, 'data': data,
        'text': text.strip()[:MAX_TEXT], 'processing': processing,
        'can_index': len(text.strip()) >= 20,
        'classification': _classify_source(name, suffix, text),
    }


def validate_upload(file_storage) -> dict:
    source = inspect_upload(file_storage, require_text=True)
    if source['suffix'] not in ALLOWED_EXTENSIONS:
        raise BadRequest('Este formato pode ser anexado, mas precisa de OCR ou adapter antes de virar fonte.')
    return source


def reextract(name: str, data: bytes, mime: str = '') -> dict:
    return inspect_upload(FileStorage(stream=BytesIO(data), filename=name, content_type=mime), require_text=True)


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
