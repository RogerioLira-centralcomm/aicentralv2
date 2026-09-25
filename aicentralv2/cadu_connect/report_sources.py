"""Private, bounded report evidence ingestion; no AI calls or credit charges."""
import hashlib
import io
import json
import secrets
import uuid
import warnings
from datetime import date

from flask import abort, flash, redirect, request, send_file, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from ..auth import login_required
from ..cadu_family import context
from ..db import get_db
from .report_rules import PROCESSING_LIMITS as LIMITS


def prepare_image(upload):
    raw = upload.stream.read(LIMITS['bytes_per_image'] + 1)
    if not raw or len(raw) > LIMITS['bytes_per_image']:
        raise ValueError('Cada print deve ter até 10 MiB e não pode estar vazio.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as picture:
                if picture.format not in ('PNG', 'JPEG', 'WEBP') or getattr(picture, 'n_frames', 1) != 1:
                    raise ValueError('Envie apenas PNG, JPEG ou WebP estáticos.')
                width, height = picture.size
                if width * height > LIMITS['pixels_per_image'] or max(width, height) > LIMITS['max_image_side']:
                    raise ValueError('O print excede 25 megapixels ou 12.000 pixels de lado.')
                picture.load()
                clean = ImageOps.exif_transpose(picture).convert('RGB')
                clean.info.clear()
                output = io.BytesIO()
                clean.save(output, format='PNG')
                image_bytes = output.getvalue()
                if len(image_bytes) > LIMITS['bytes_per_image']:
                    raise ValueError('O print normalizado excede 10 MiB. Reduza a resolução.')
                width, height = clean.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError('Não foi possível ler o print. Envie uma imagem válida.') from exc
    return {'original_name': secure_filename(upload.filename or 'print')[:200] or 'print',
            'sha256': hashlib.sha256(raw).hexdigest(), 'image_bytes': image_bytes,
            'mime_type': 'image/png', 'width': width, 'height': height, 'input_bytes': len(raw)}


def source_storage_ready(rows):
    return rows("SELECT to_regclass('public.cadu_connect_report_sources') IS NOT NULL AS ready")[0]['ready']


def authorized_report(rows, report_id, *, lock=False):
    selected = context.resolve()
    reports = rows('''SELECT * FROM cadu_connect_report_workspaces
        WHERE id=%s AND organization_id=%s AND client_id=%s''' + (' FOR UPDATE' if lock else ''),
        (report_id, selected['organization_id'], selected['client_id']))
    if not reports:
        abort(404)
    refs = {e['ref'] for e in context.inventory(selected['client_id']) if e['kind'] == 'project'}
    if reports[0]['project_ref'] and reports[0]['project_ref'] not in refs:
        abort(404)
    return reports[0], selected


def bound_multipart_request(upload_request):
    """Read at most one report batch before multipart parsing starts."""
    size_limit = LIMITS['bytes_per_batch'] + 1024 * 1024
    if upload_request.content_length is not None and upload_request.content_length > size_limit:
        raise RequestEntityTooLarge('O lote de prints excede o limite permitido.')
    body = upload_request.stream.read(size_limit + 1)
    if len(body) > size_limit:
        raise RequestEntityTooLarge('O lote de prints excede o limite permitido.')
    upload_request._cached_data = body


def register(bp, rows):
    @bp.post('/relatorios/<int:report_id>/fontes')
    @login_required
    def report_upload_sources(report_id):
        report, selected = authorized_report(rows, report_id, lock=True)
        if selected['role'] == 'viewer':
            abort(403)
        # Authenticate before reading; then bound the body before form parsing.
        bound_multipart_request(request)
        token = session.get('family_csrf', '')
        if not token or not secrets.compare_digest(token, request.form.get('_csrf', '')):
            abort(403)
        if not source_storage_ready(rows):
            abort(503)
        conn = get_db()
        try:
            uploads = request.files.getlist('prints')
            if not 1 <= len(uploads) <= LIMITS['images_per_batch']:
                raise ValueError('Envie de 1 a 20 prints por atualização.')
            supplier = request.form.get('supplier', '').strip()
            if len(supplier) > 200:
                raise ValueError('Fornecedor deve ter até 200 caracteres.')
            start = date.fromisoformat(request.form['period_start']) if request.form.get('period_start') else None
            end = date.fromisoformat(request.form['period_end']) if request.form.get('period_end') else None
            if start and end and start > end:
                raise ValueError('O período dos dados está invertido.')
            total = 0
            added = 0
            batch = str(uuid.uuid4())
            for upload in uploads:
                image = prepare_image(upload)
                total += image['input_bytes']
                if total > LIMITS['bytes_per_batch']:
                    raise ValueError('O lote excede 100 MiB.')
                inserted = rows('''INSERT INTO cadu_connect_report_sources
                    (report_id,batch_id,original_name,sha256,image_bytes,mime_type,width,height,
                     supplier,period_start,period_end,created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (report_id,sha256) DO NOTHING RETURNING id''',
                    (report_id,batch,image['original_name'],image['sha256'],image['image_bytes'],
                     image['mime_type'],image['width'],image['height'],supplier,start,end,session['user_id']))
                added += bool(inserted)
            if added:
                revision = report['revision'] + 1
                with conn.cursor() as cur:
                    cur.execute('''UPDATE cadu_connect_report_workspaces SET revision=%s,
                        updated_by=%s,updated_at=NOW() WHERE id=%s''', (revision,session['user_id'],report_id))
                    cur.execute('''INSERT INTO cadu_connect_report_workspace_versions
                        (report_id,revision,document,note,created_by) VALUES (%s,%s,%s::jsonb,%s,%s)''',
                        (report_id,revision,json.dumps(report['document']),
                         f'{added} print(s) recebido(s), lote {batch}. Aguardando revisão; dados ainda não compilados.',session['user_id']))
            conn.commit()
            flash(f'{added} print(s) recebido(s). {len(uploads)-added} duplicado(s) ignorado(s). Nenhum crédito consumido.', 'report_sources')
        except ValueError as exc:
            conn.rollback()
            flash(str(exc), 'report_sources_error')
        except Exception:
            conn.rollback()
            raise
        return redirect(url_for('cadu_connect.report_library', report_id=report_id) + '#sources')

    @bp.get('/relatorios/<int:report_id>/fontes/<int:source_id>')
    @login_required
    def report_source_image(report_id, source_id):
        authorized_report(rows, report_id)
        found = rows('''SELECT image_bytes,mime_type FROM cadu_connect_report_sources
            WHERE id=%s AND report_id=%s''', (source_id, report_id))
        if not found:
            abort(404)
        response = send_file(io.BytesIO(bytes(found[0]['image_bytes'])), mimetype=found[0]['mime_type'],
                             download_name=f'print-{source_id}.png', max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
