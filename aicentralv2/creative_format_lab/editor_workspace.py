"""Durable, brand-scoped documents and region operations for Trocr.

Provider calls never run inside a database transaction. A claimed operation is
never automatically replayed after a worker crash (the provider has no idempotency
contract); its persisted status remains available for explicit review.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import io
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path

from PIL import Image, ImageOps, ImageChops

MAX_FILE = 20 * 1024 * 1024
MAX_PIXELS = 20_000_000
ID = re.compile(r"^[a-f0-9]{32}$")
ROLES = {"person", "product", "background", "text", "logo", "graphic"}
EDIT_ACTIONS = {"replace", "erase", "recreate", "extract", "text", "format", "cutout", "fill", "similarity"}
ACTION_ROLES = {
    "replace": ROLES,
    "erase": ROLES,
    "recreate": ROLES,
    "extract": ROLES,
    "cutout": ROLES,
    "text": {"text"},
    "fill": {"background"},
    "similarity": {"background", "graphic"},
    "format": {"background"},
}
BRAND_MUTATIONS = {"replace", "erase", "recreate"}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
BACKGROUND_PRESETS = {
    "clean-studio": "clean studio background with controlled soft lighting",
    "brand-gradient": "restrained gradient using the source brand palette",
    "paper": "subtle premium paper texture with natural fibers",
    "color-wash": "soft color wash with enough quiet space for copy",
    "editorial": "premium editorial environment with realistic depth",
    "office": "realistic contemporary office environment",
    "nature": "natural outdoor environment with believable daylight",
    "architecture": "refined architectural environment with clean geometry",
    "dark-studio": "dark controlled studio with precise edge lighting",
    "bright-seamless": "bright seamless background with grounded soft shadow",
}


class Conflict(ValueError):
    pass


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Workspace:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS document_revisions(document_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(document_id, revision));
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, body TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(str(self.root / 'workspace.sqlite'), timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def asset(self, ident):
        if not ID.fullmatch(str(ident or '')):
            raise ValueError('Identificador de imagem inválido.')
        with self.db() as db:
            row = db.execute('SELECT metadata FROM assets WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError('Imagem não encontrada nesta marca.')
        return json.loads(row['metadata'])

    def upload(self, raw, name='Imagem'):
        if not raw or len(raw) > MAX_FILE:
            raise ValueError('Envie uma imagem de até 20 MB.')
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {'PNG', 'JPEG', 'WEBP'} or source.width * source.height > MAX_PIXELS:
                    raise ValueError('Use PNG, JPEG ou WebP de até 20 megapixels.')
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGBA')
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError('Imagem inválida.') from exc
        output = io.BytesIO()
        image.save(output, format='PNG')
        content = output.getvalue()
        ident = hashlib.sha256(content).hexdigest()[:32]
        path = self.root / (ident + '.png')
        if not path.exists():
            temporary = self.root / (uuid.uuid4().hex + '.tmp')
            temporary.write_bytes(content)
            temporary.replace(path)
        thumb = image.copy()
        thumb.thumbnail((256, 256))
        thumb.save(self.root / (ident + '-thumb.png'))
        meta = {'id': ident, 'name': str(name)[:120], 'width': image.width, 'height': image.height}
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO assets VALUES (?,?)', (ident, packed(meta)))
        return self.asset(ident)

    def image(self, ident):
        self.asset(ident)
        with Image.open(self.root / (ident + '.png')) as image:
            return image.convert('RGBA')

    def reference(self, ident):
        self.asset(ident)
        return 'data:image/png;base64,' + base64.b64encode((self.root / (ident + '.png')).read_bytes()).decode('ascii')

    def get(self, table, ident):
        if table not in {'documents', 'campaigns', 'jobs'}:
            raise ValueError('Coleção inválida.')
        with self.db() as db:
            row = db.execute(f'SELECT * FROM {table} WHERE id=?', (ident,)).fetchone()
        return json.loads(row['body']) if row else None

    def listing(self, table):
        if table not in {'documents', 'campaigns'}:
            raise ValueError('Coleção inválida.')
        with self.db() as db:
            return [json.loads(row['body']) for row in db.execute(f'SELECT body FROM {table} ORDER BY rowid DESC')]

    def save(self, table, ident, body, revision):
        if table not in {'documents', 'campaigns'} or not isinstance(body, dict):
            raise ValueError('Documento inválido.')
        if not ident or len(ident) > 100:
            raise ValueError('Identificador inválido.')
        data = json.loads(packed(body))
        if len(packed(data)) > 2_000_000:
            raise ValueError('Documento excede 2 MB.')
        if table == 'campaigns':
            name = str(data.get('name') or '').strip()
            if not name or len(name) > 120:
                raise ValueError('Nome da campanha: 1 a 120 caracteres.')
            data = {'name': name, 'objective': str(data.get('objective') or '')[:1000], 'archived': data.get('archived') is True,
                    'references': data.get('references') or []}
            if not isinstance(data['references'], list) or len(data['references']) > 100:
                raise ValueError('Use até 100 referências por campanha.')
            for asset in data['references']:
                self.asset(asset)
        else:
            if 'layers' in data:
                from .editor_layers import normalize
                data['layers'] = normalize(data['layers'], self)
            if data.get('campaign_id') and not self.get('campaigns', data['campaign_id']):
                raise ValueError('Campanha não encontrada.')
            if data.get('base_asset'):
                self.asset(data['base_asset'])
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute(f'SELECT revision,body FROM {table} WHERE id=?', (ident,)).fetchone()
            current = old['revision'] if old else 0
            if type(revision) is not int or current != revision:
                raise Conflict('Outra aba salvou esta edição. Sua edição local foi preservada; recarregue para comparar.')
            if table == 'documents' and old:
                db.execute('INSERT OR IGNORE INTO document_revisions VALUES (?,?,?)', (ident,current,old['body']))
            data.update(id=ident, revision=current + 1, updated_at=time.time())
            db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?)', (ident, current + 1, packed(data)))
        return data

    def enqueue(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('Pedido inválido.')
        key = str(payload.get('operation_id') or '')
        if not ID.fullmatch(key):
            raise ValueError('A operação precisa de um identificador idempotente.')
        base = payload.get('base_asset')
        self.asset(base)
        operations = payload.get('operations')
        if not isinstance(operations, list) or not 1 <= len(operations) <= 12:
            raise ValueError('Selecione de 1 a 12 operações.')
        clean = []
        for op in operations:
            if not isinstance(op, dict) or op.get('action') not in EDIT_ACTIONS:
                raise ValueError('Operação inválida.')
            if op.get('base_asset') != base:
                raise ValueError('A base mudou. Revise a máscara antes de gerar.')
            full_frame = op['action'] in {'format', 'similarity'}
            mask = self.image(op.get('mask_asset')).convert('L') if not full_frame else self.image(base).convert('L')
            if not full_frame and (mask.size != self.image(base).size or not mask.getbbox()):
                raise ValueError('Revise a máscara: ela deve conter uma região e ter o tamanho da base.')
            role = op.get('role')
            if role not in ROLES:
                raise ValueError('Escolha um elemento válido para editar.')
            if role not in ACTION_ROLES[op['action']]:
                raise ValueError('Esta ação não é compatível com o elemento selecionado.')
            explicit_brand_change = op.get('explicit_brand_change') is True
            if role == 'logo' and op['action'] in BRAND_MUTATIONS and not explicit_brand_change:
                raise ValueError('Confirme explicitamente a alteração da marca antes de editar o logo.')
            reference = op.get('reference_asset')
            if op['action'] in {'replace', 'similarity'}:
                self.asset(reference)
            elif reference:
                raise ValueError('Referências só são usadas em substituições.')
            instruction = str(op.get('instruction') or '').strip()
            original_instruction = str(op.get('original_instruction') or instruction).strip()
            if len(instruction) > 2000 or len(original_instruction) > 2000:
                raise ValueError('Instrução excede 2000 caracteres.')
            if op['action'] == 'format' and op.get('aspect_ratio') not in {'16:9','9:16','1:1','4:5'}:
                raise ValueError('Formato inválido.')
            color = str(op.get('background_color') or '').strip()
            if op['action'] == 'fill' and not HEX_COLOR.fullmatch(color):
                raise ValueError('Escolha uma cor sólida no formato #RRGGBB.')
            preset = str(op.get('background_preset') or '').strip()
            if preset and (op['action'] != 'recreate' or role != 'background' or preset not in BACKGROUND_PRESETS):
                raise ValueError('Preset de fundo inválido para esta operação.')
            if preset and not instruction:
                instruction = 'Create a ' + BACKGROUND_PRESETS[preset] + '; preserve foreground, brand and copy.'
            clean.append({'aspect_ratio': op.get('aspect_ratio') if op['action']=='format' else None, 'action': op['action'], 'role': role, 'instruction': instruction,
                          'original_instruction': original_instruction,
                          'base_asset': base, 'mask_asset': op.get('mask_asset'), 'reference_asset': reference,
                          'reference_role': 'similarity_reference' if op['action']=='similarity' else ('selected_element_reference' if reference else None),
                          'background_color': color if op['action']=='fill' else None,
                          'background_preset': preset or None,
                          'explicit_brand_change': explicit_brand_change})
        if any(op['action']=='similarity' for op in clean) and len(clean) > 1:
            raise ValueError('Gere a similaridade da peça inteira em uma operação separada.')
        if any(op['action']=='format' for op in clean) and not all(op['action']=='format' for op in clean):
            raise ValueError('Gere os formatos depois de concluir as edições por elemento.')
        incoming_protected = payload.get('protected_masks') or []
        if not isinstance(incoming_protected, list) or len(incoming_protected) > 100:
            raise ValueError('Regiões protegidas inválidas.')
        protected = []
        for item in incoming_protected:
            legacy = isinstance(item, str)
            ident = item if legacy else item.get('mask_asset') if isinstance(item, dict) else None
            role = 'legacy' if legacy else str(item.get('role') or '').strip()
            if role not in ROLES | {'wordmark', 'legacy'}:
                raise ValueError('Classifique cada região protegida.')
            if self.image(ident).size != self.image(base).size:
                raise ValueError('Revise as regiões protegidas desta base.')
            protected.append({'mask_asset': ident, 'role': role, 'label': str((item.get('label') if isinstance(item, dict) else '') or role)[:80]})
        if any(op['action']=='similarity' for op in clean) and not any(item['role'] in {'logo', 'wordmark'} for item in protected):
            raise ValueError('Antes da similaridade global, proteja e classifique uma região como logo ou wordmark.')
        if protected and any(op['action']=='format' for op in clean):
            raise ValueError('A recomposição por IA não preserva regiões protegidas. Exporte a composição com o elemento original antes de adaptar o formato.')
        seed = {'base_asset': base, 'operations': clean, 'protected_masks': protected}
        digest = hashlib.sha256(packed(seed).encode()).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT hash,body FROM jobs WHERE key=?', (key,)).fetchone()
            if old:
                if old['hash'] != digest:
                    raise Conflict('Este identificador já pertence a outro pedido.')
                return json.loads(old['body'])
            job = {'id': uuid.uuid4().hex, **seed, 'hash': digest, 'status': 'queued', 'step': 0,
                   'results': [], 'cancel_requested': False, 'created_at': time.time()}
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (job['id'], key, digest, packed(job)))
        return job

    def revisions(self, ident):
        with self.db() as db:
            return [json.loads(row['body']) for row in db.execute('SELECT body FROM document_revisions WHERE document_id=? ORDER BY revision DESC LIMIT 50', (ident,))]

    def cancel(self, ident):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('Operação não encontrada.')
            job = json.loads(row['body'])
            job['cancel_requested'] = True
            if job['status'] == 'queued':
                job['status'] = 'cancelled'
            db.execute('UPDATE jobs SET body=? WHERE id=?', (packed(job), ident))
        return job

    def retry(self, ident):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('Operação não encontrada.')
            job = json.loads(row['body'])
            if job['status'] not in {'failed', 'cancelled'}:
                raise Conflict('Somente etapas que falharam ou foram canceladas podem ser repetidas.')
            job.update(status='queued', cancel_requested=False)
            job.pop('error', None)
            db.execute('UPDATE jobs SET body=? WHERE id=?', (packed(job), ident))
        return job

    def run(self, ident, generate):
        # Transactional claim prevents double generation across workers/processes.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                return
            job = json.loads(row['body'])
            if job['status'] != 'queued':
                return
            job['status'] = 'running'
            job['started_at'] = time.time()
            db.execute('UPDATE jobs SET body=? WHERE id=?', (packed(job), ident))
        current = job['results'][-1]['result_asset'] if job['results'] else job['base_asset']
        try:
            for index in range(len(job['results']), len(job['operations'])):
                op = job['operations'][index]
                if self.get('jobs', ident)['cancel_requested']:
                    job['status'] = 'cancelled'
                    break
                job['step'] = index + 1
                self._progress(job)
                if op['action'] == 'format':
                    current = job['base_asset']
                source = self.image(current)
                full_frame = op['action'] in {'format', 'similarity'}
                mask = Image.new('L', source.size, 255) if full_frame else self.image(op['mask_asset']).convert('L')
                if op['action'] != 'format':
                    for protected in job.get('protected_masks', []):
                        ident = protected if isinstance(protected, str) else protected['mask_asset']
                        mask = ImageChops.multiply(mask, ImageOps.invert(self.image(ident).convert('L')))
                box = mask.getbbox()
                if not box:
                    raise ValueError('A região selecionada está vazia ou totalmente protegida.')
                action = {'erase': 'Remove the selected element and reconstruct the background.',
                          'recreate': 'Recreate an alternative of the selected element.',
                          'extract': 'Remove the selected element and reconstruct the background.',
                          'format': f'Recompose the entire creative for aspect ratio {op.get("aspect_ratio")}. Preserve all content, logos and people; adapt the layout to the destination.',
                          'text': 'Remove the selected text and reconstruct the background. Do not add any text.',
                          'replace': 'Replace the selected element using the SECOND image only as reference for that selected element.',
                          'similarity': 'Restyle the whole creative using the SECOND image only as visual-direction reference. The FIRST image remains the source of truth for advertiser, logo, wordmark, people and copy.',
                          'cutout': 'Isolate the selected element on transparency.',
                          'fill': f'Fill the selected background with exact solid color {op.get("background_color")}.'}[op['action']]
                instruction = '' if op['action']=='text' else op['instruction']
                original_instruction = '' if op['action']=='text' else op.get('original_instruction') or instruction
                dimensions = 'Keep exactly the original dimensions.' if op['action'] != 'format' else ''
                prompt = (f'Edit the {op["role"]} inside pixel region {box} of the FIRST image ({source.width}x{source.height}). '
                          f'{action} Preserve the original advertiser, all logos, wordmarks, typography and other unselected elements. {dimensions} '
                          f'Never replace a bank, institution or brand unless this operation explicitly targets role logo. '
                          f'Do not infer missing price, CTA or logo. Never invent offer terms. Preserve buildings exactly: facade geometry, floors, balconies and windows; do not redesign architecture. '
                          f'The literal user request is the source of truth: {original_instruction}. '
                          f'Organized instruction (never override the literal request): {instruction}')
                refs = [self.reference(current)]
                if op['reference_asset']:
                    refs.append(self.reference(op['reference_asset']))
                if op['action'] == 'cutout':
                    generated = source.copy()
                    generated.putalpha(mask)
                elif op['action'] == 'fill':
                    generated = Image.new('RGBA', source.size, op['background_color'])
                else:
                    raw = generate(prompt, input_references=refs, aspect_ratio=op.get('aspect_ratio') or f'{source.width}:{source.height}', background='opaque')
                    from .swap import _png_bytes
                    generated = Image.open(io.BytesIO(_png_bytes(raw))).convert('RGBA')
                if op['action'] == 'format':
                    target = {'16:9':(1920,1080),'9:16':(1080,1920),'1:1':(1080,1080),'4:5':(1080,1350)}[op['aspect_ratio']]
                    composed = ImageOps.fit(generated, target, method=Image.Resampling.LANCZOS)
                elif op['action'] == 'cutout':
                    composed = generated
                else:
                    if generated.size != source.size:
                        generated = generated.resize(source.size, Image.Resampling.LANCZOS)
                    composed = Image.composite(generated, source, mask)
                if op['action'] not in {'format', 'cutout'} and _changed_outside_mask(source, composed, mask):
                    raise ValueError('A edição tentou alterar pixels protegidos ou fora da seleção.')
                output = io.BytesIO()
                composed.save(output, format='PNG')
                asset = self.upload(output.getvalue(), 'Resultado da edição')
                entry = {'base_asset': current, 'operation': op, 'result_asset': asset['id'],
                         'qa': {'outside_mask_preserved': None if op['action'] in {'format', 'cutout'} else True,
                                'protected_regions': len(job.get('protected_masks', [])),
                                'reference_role': op.get('reference_role')}}
                if op['action'] in {'extract', 'text', 'cutout'}:
                    layer = {'id': uuid.uuid4().hex, 'kind': 'image' if op['action']=='extract' else 'text',
                             'x': box[0], 'y': box[1], 'width': box[2]-box[0], 'height': box[3]-box[1],
                             'visible': True, 'opacity': 1, 'protected': False}
                    if op['action'] in {'extract', 'cutout'}:
                        layer['kind'] = 'image'
                        cut = source.copy(); cut.putalpha(mask); cut = cut.crop(box)
                        cut_bytes = io.BytesIO(); cut.save(cut_bytes, 'PNG')
                        layer['asset_id'] = self.upload(cut_bytes.getvalue(), 'Camada recortada')['id']
                    else:
                        layer.update(text=op['instruction'], font='Open Sans', font_size=48, color='#ffffff', align='left', spacing=4)
                    entry['layer'] = layer
                job['results'].append(entry)
                current = asset['id']
                self._progress(job)
            else:
                job['status'] = 'succeeded'
            job['result_asset'] = current
        except Exception as exc:
            job['status'] = 'failed'
            job['error'] = str(exc)[:1000]
        job['finished_at'] = time.time()
        self._progress(job)

    def _progress(self, job):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM jobs WHERE id=?', (job['id'],)).fetchone()
            job['cancel_requested'] = json.loads(row['body'])['cancel_requested']
            db.execute('UPDATE jobs SET body=? WHERE id=?', (packed(job), job['id']))


def _changed_outside_mask(source, result, mask):
    """True when a localized edit leaked into pixels it did not own."""
    if source.size != result.size or source.size != mask.size:
        return True
    outside = ImageOps.invert(mask.convert('L'))
    difference = ImageChops.difference(source.convert('RGBA'), result.convert('RGBA'))
    return any(ImageChops.multiply(channel, outside).getbbox() for channel in difference.split())
