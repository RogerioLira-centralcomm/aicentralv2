"""Editor de vídeo sobre o OpenCut: projeto unificado, biblioteca/upload, comandos, extensões e fila de render."""
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import jsonify, request
from PIL import Image

from tests import test_video_studio as fixtures
from aicentralv2.creative_media import studio_video_editor as editor

BASE = '/parametros/api/format-lab/studio/video-editor'
HEADERS = {'X-Trocr-CSRF-Token': 'token'}
TICKS = editor.TICKS


def timeline(ident, width=1080, height=1920):
    """Projeto serializado mínimo, no formato que o OpenCut grava (versão 31)."""
    scene = {'id': 'scene-1', 'name': 'Main scene', 'isMain': True, 'bookmarks': [], 'createdAt': '2026-10-23T00:00:00.000Z',
             'updatedAt': '2026-10-23T00:00:00.000Z',
             'tracks': {'overlay': [], 'audio': [], 'main': {'id': 'main', 'name': 'Main', 'type': 'video', 'elements': [], 'muted': False, 'hidden': False}}}
    return {'metadata': {'id': ident, 'name': 'Teste', 'duration': 0, 'createdAt': '2026-10-23T00:00:00.000Z', 'updatedAt': '2026-10-23T00:00:00.000Z'},
            'scenes': [scene], 'currentSceneId': 'scene-1', 'version': 31,
            'settings': {'fps': {'numerator': 30, 'denominator': 1}, 'canvasSize': {'width': width, 'height': height}}}


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (64, 48), (200, 30, 30)).save(buffer, format='PNG')
    return buffer.getvalue()


class CommandsTest(unittest.TestCase):
    links = {'vid': {'ref': 'clip:' + 'a' * 32, 'type': 'video', 'name': 'Clipe', 'duration': 6.0},
             'img': {'ref': 'image:' + 'b' * 32, 'type': 'image', 'name': 'Capa'},
             'aud': {'ref': 'sound:' + 'c' * 32, 'type': 'audio', 'name': 'Trilha', 'duration': 4.0}}

    def test_media_text_split_trim_and_ripple(self):
        base = timeline('p1')
        result, out = editor.apply_commands(base, [
            {'op': 'add_media', 'args': {'asset_id': 'img', 'duration': 3}},
            {'op': 'add_media', 'args': {'asset_id': 'vid'}},
            {'op': 'add_media', 'args': {'asset_id': 'aud', 'start': 1}},
            {'op': 'add_text', 'args': {'text': 'Oferta', 'start': .5, 'duration': 2, 'y': .9}},
        ], self.links)
        self.assertEqual(base['scenes'][0]['tracks']['main']['elements'], [], 'a entrada não pode ser alterada')
        tracks = result['scenes'][0]['tracks']
        image, video = tracks['main']['elements']
        self.assertEqual((image['startTime'], image['duration']), (0, 3 * TICKS))
        self.assertEqual((video['startTime'], video['duration'], video['sourceDuration']), (3 * TICKS, 6 * TICKS, 6 * TICKS))
        self.assertEqual(tracks['audio'][0]['elements'][0]['startTime'], TICKS)
        text = tracks['overlay'][0]['elements'][0]
        self.assertEqual(text['params']['content'], 'Oferta')
        self.assertAlmostEqual(text['params']['transform.positionY'], .4 * 1920)
        self.assertEqual(result['metadata']['duration'], 9 * TICKS)

        result, out = editor.apply_commands(result, [{'op': 'split', 'args': {'element_id': video['id'], 'at': 5}}], self.links)
        left, right = result['scenes'][0]['tracks']['main']['elements'][1:]
        self.assertEqual((left['duration'], left['trimEnd']), (2 * TICKS, 4 * TICKS))
        self.assertEqual((right['startTime'], right['trimStart'], right['duration']), (5 * TICKS, 2 * TICKS, 4 * TICKS))

        result, _ = editor.apply_commands(result, [{'op': 'delete', 'args': {'element_id': left['id'], 'ripple': True}}], self.links)
        remaining = result['scenes'][0]['tracks']['main']['elements']
        self.assertEqual([e['startTime'] for e in remaining], [0, 3 * TICKS])

        result, _ = editor.apply_commands(result, [{'op': 'trim', 'args': {'element_id': right['id'], 'trim_start': 1, 'trim_end': 2}}], self.links)
        trimmed = result['scenes'][0]['tracks']['main']['elements'][1]
        self.assertEqual(trimmed['duration'], 3 * TICKS)

    def test_rejections_are_atomic(self):
        base = timeline('p1')
        cases = [
            [{'op': 'add_text', 'args': {'text': 'ok'}}, {'op': 'drop_table', 'args': {}}],
            [{'op': 'add_media', 'args': {'asset_id': 'outra-marca'}}],
            [{'op': 'add_text', 'args': {'text': 'x', 'color': 'red; drop'}}],
            [{'op': 'add_text', 'args': {'text': 'x'}}, {'op': 'set_params', 'args': {'element_id': 'nao-existe', 'params': {'opacity': 1}}}],
        ]
        for commands in cases:
            with self.subTest(commands=commands[-1]['op']), self.assertRaises(ValueError):
                editor.apply_commands(base, commands, self.links)
        self.assertEqual(base, timeline('p1'))
        result, out = editor.apply_commands(base, [{'op': 'add_text', 'args': {'text': 'x'}}], self.links)
        element = out[0]['element_id']
        with self.assertRaises(ValueError):
            editor.apply_commands(result, [{'op': 'set_params', 'args': {'element_id': element, 'params': {'mediaId': '../../etc'}}}], self.links)

    def test_batched_captions_share_one_track(self):
        commands = [{'op': 'add_text', 'args': {'text': 'um', 'start': 0, 'duration': 1}},
                    {'op': 'add_text', 'args': {'text': 'dois', 'start': 1, 'duration': 1, 'track_id': '@previous'}}]
        result, _ = editor.apply_commands(timeline('p1'), commands, {})
        overlay = result['scenes'][0]['tracks']['overlay']
        self.assertEqual(len(overlay), 1)
        self.assertEqual([e['params']['content'] for e in overlay[0]['elements']], ['um', 'dois'])

    def test_null_numbers_are_validation_errors(self):
        for args in ({'text': 'x', 'x': None}, {'text': 'x', 'size': {'a': 1}}, {'text': 'x', 'y': 'meio'}):
            with self.subTest(args=args):
                try:
                    editor.apply_commands(timeline('p1'), [{'op': 'add_text', 'args': args}], {})
                except ValueError:
                    pass
                else:
                    self.assertIn(None, args.values(), 'nulo usa o padrão; texto ou objeto precisa ser recusado')

    def test_exit_url_stays_on_site(self):
        for raw, expected in (('/studio/projetos?x=1', '/studio/projetos?x=1'), ('//evil.com', '/studio'), ('/\\evil.com', '/studio'),
                              ('https://evil.com', '/studio'), (None, '/studio')):
            self.assertEqual(editor._local_path(raw), expected)

    def test_vertical_text_fits_and_finishing_commands(self):
        result, out = editor.apply_commands(timeline('p1'), [
            {'op': 'set_canvas', 'args': {'width': 1080, 'height': 1920, 'background': '#3a0b3d'}},
            {'op': 'add_media', 'args': {'asset_id': 'img', 'duration': 2, 'scale': 1.5, 'motion': 'zoom_in'}},
            {'op': 'add_text', 'args': {'text': 'Gestão em qualquer tela', 'size': 8, 'bold': True}},
            {'op': 'animate', 'args': {'element_id': '@last', 'property': 'opacity', 'keyframes': [{'at': 0, 'value': 0}, {'at': .3, 'value': 1}]}},
        ], self.links)
        self.assertEqual(result['settings']['canvasSize'], {'width': 1080, 'height': 1920})
        image = result['scenes'][0]['tracks']['main']['elements'][0]
        scale = image['animations']['transform.scaleX']['keys']
        self.assertEqual([(k['time'], k['value']) for k in scale], [(0, 1.5), (2 * TICKS, 1.5 * 1.08)])
        text = result['scenes'][0]['tracks']['overlay'][0]['elements'][0]
        longest = max(len(line) for line in text['params']['content'].split('\n'))
        pixels = text['params']['fontSize'] * 1920 / editor.FONT_SIZE_REFERENCE
        self.assertLessEqual(longest * .6 * pixels, 1080 * .88 + 1, 'o texto cabe na largura do quadro vertical')
        self.assertEqual([k['value'] for k in text['animations']['opacity']['keys']], [0, 1])
        for bad in ({'op': 'set_canvas', 'args': {'width': 1081, 'height': 1920}},
                    {'op': 'animate', 'args': {'element_id': text['id'], 'property': 'mediaId', 'keyframes': [{'at': 0, 'value': 0}, {'at': 1, 'value': 1}]}},
                    {'op': 'animate', 'args': {'element_id': text['id'], 'property': 'opacity', 'keyframes': [{'at': 0, 'value': 0}, 'lixo']}}):
            with self.subTest(op=bad['op']), self.assertRaises(ValueError):
                editor.apply_commands(result, [bad], self.links)
        self.assertEqual(editor.fit_text('Gestão em qualquer tela', 8, 1920, 1080, True), ('Gestão em qualquer tela', 8.0), 'no horizontal cabe sem mexer')

    def test_timeline_contract(self):
        self.assertEqual(editor.validate_timeline(timeline('p1'), 'p1')['metadata']['id'], 'p1')
        for broken in (timeline('outro'), {**timeline('p1'), 'scenes': []}, [], {**timeline('p1'), 'scenes': [{'tracks': {}}]}):
            with self.assertRaises(ValueError):
                editor.validate_timeline(broken, 'p1')


@unittest.skipUnless(fixtures.shutil.which('ffmpeg') and fixtures.shutil.which('ffprobe'), 'FFmpeg required')
class EditorApiTest(unittest.TestCase):
    setUpClass = classmethod(fixtures.MediaTest.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MediaTest.tearDownClass.__func__)
    app = fixtures.MediaTest.app

    def setUp(self):
        self.client = self.app().test_client()
        with self.client.session_transaction() as sess:
            sess.update(user_id=7, user_type='admin', is_centralcomm=True, studio_csrf_token='token')

        def execute(fn):
            try:
                return fn()
            except ValueError as error:
                return jsonify(success=False, error=str(error)), 400
        service = Mock()
        service.return_value.load_format_lab_swap_library.return_value = {'items': []}
        self.http = patch('aicentralv2.creative_media.studio_video_editor._http',
                          return_value=(execute, lambda: request.get_json(silent=True), lambda data: jsonify(success=True, data=data), service))
        self.http.start()
        self.addCleanup(self.http.stop)

    def create(self, client='31'):
        result = self.client.post(f'{BASE}/projects?client_id={client}', json={'name': 'Campanha'}, headers=HEADERS)
        self.assertEqual(result.status_code, 200, result.json)
        return result.json['data']['id']

    def put(self, ident, body, client='31'):
        return self.client.put(f'{BASE}/projects/{ident}?client_id={client}', json=body, headers=HEADERS)

    def upload(self, ident, payload, kind, name):
        return self.client.post(f'{BASE}/projects/{ident}/media?client_id=31', headers=HEADERS,
                                data={'asset_id': f'asset-{kind}-0001', 'type': kind, 'name': name, 'file': (io.BytesIO(payload), name)})

    def test_project_revisions_and_document_merge(self):
        ident = self.create()
        opened = self.client.get(f'{BASE}/projects/{ident}?client_id=31')
        self.assertEqual(opened.json['data'], {'revision': 1, 'project': None})
        saved = self.put(ident, {'expected_revision': 1, 'project': timeline(ident)})
        self.assertEqual(saved.json['data']['revision'], 2)
        stale = self.put(ident, {'expected_revision': 1, 'project': timeline(ident)})
        self.assertEqual((stale.status_code, stale.json['code']), (409, 'revision_conflict'))
        self.assertEqual(self.put(ident, {'expected_revision': 2, 'project': timeline('outro')}).status_code, 400)
        self.assertEqual(self.client.get(f'{BASE}/projects/{ident}?client_id=32').status_code, 400)
        self.assertEqual(self.client.put(f'{BASE}/projects/{ident}?client_id=31', json={}).status_code, 403)
        from aicentralv2.creative_media import studio_projects
        with self.app().test_request_context():
            store = studio_projects
            root = editor._scope('31')
            document = store.read(root, ident)['document']
            store.save(root, {**document, 'external_project_id': 'ws-9'}, ident, 2)
        self.assertEqual(self.put(ident, {'expected_revision': 3, 'project': timeline(ident)}).status_code, 200)
        with self.app().test_request_context():
            document = studio_projects.read(editor._scope('31'), ident)['document']
        self.assertEqual(document['external_project_id'], 'ws-9', 'gravar a timeline não pode apagar o restante do projeto')
        self.assertEqual(document['video_editor']['metadata']['id'], ident)

    def test_upload_library_link_content_and_brand_boundary(self):
        ident = self.create()
        video = self.upload(ident, self.voiced.read_bytes(), 'video', 'voz.mp4')
        self.assertEqual(video.status_code, 200, video.json)
        self.assertTrue(video.json['data']['hasAudio'])
        self.assertTrue(video.json['data']['ref'].startswith('clip:'))
        audio = self.upload(ident, self.sound.read_bytes(), 'audio', 'trilha.wav')
        self.assertEqual(audio.status_code, 200, audio.json)
        image = self.upload(ident, png_bytes(), 'image', 'capa.png')
        self.assertEqual((image.status_code, image.json['data']['width']), (200, 64))
        self.assertEqual(self.upload(ident, b'not a movie', 'video', 'falso.mp4').status_code, 400)
        self.assertEqual(self.upload(ident, self.voiced.read_bytes(), 'image', 'video-como-imagem.png').status_code, 400)

        listed = self.client.get(f'{BASE}/projects/{ident}/media?client_id=31').json['data']['items']
        self.assertEqual(sorted(item['type'] for item in listed), ['audio', 'image', 'video'])
        with self.client.get(listed[0]['contentUrl']) as content:
            self.assertEqual(content.status_code, 200)
            self.assertEqual(content.headers['Cache-Control'], 'private, max-age=3600')
        video_item = next(item for item in listed if item['type'] == 'video')
        self.assertGreater(video_item['fps'], 0)
        with self.client.get(video_item['thumbnailUrl']) as thumb:
            self.assertEqual((thumb.status_code, thumb.mimetype), (200, 'image/jpeg'), 'timeline precisa da miniatura para mostrar os quadros')
        self.assertIsNone(next(item for item in listed if item['type'] == 'audio')['thumbnailUrl'])
        self.assertEqual(self.client.get(listed[0]['contentUrl'].replace('client_id=31', 'client_id=32')).status_code, 400)

        library = self.client.get(f'{BASE}/library?client_id=31').json['data']['items']
        refs = {item['ref'] for item in library}
        sounds = [item for item in library if item['kind'] == 'audio']
        self.assertTrue(sounds and all(item.get('preview_url') for item in sounds), 'aba Áudio precisa ouvir antes de adicionar')
        public = next(item for item in sounds if item['ref'].startswith('public-sound:'))
        # O app de teste não serve a pasta static real; o arquivo apontado precisa existir nela.
        self.assertTrue(public['preview_url'].startswith('/static/audio/studio/'))
        real_static = Path(editor.__file__).resolve().parents[1] / 'static'
        self.assertTrue((real_static / public['preview_url'].removeprefix('/static/')).is_file())
        self.assertIn(video.json['data']['ref'], refs, 'o vídeo enviado no editor entra na biblioteca da marca')
        other = self.create()
        linked = self.client.post(f'{BASE}/projects/{other}/media/link?client_id=31', json={'ref': video.json['data']['ref']}, headers=HEADERS)
        self.assertEqual(linked.status_code, 200, linked.json)
        foreign = self.create('32')
        self.assertEqual(self.client.post(f'{BASE}/projects/{foreign}/media/link?client_id=32', json={'ref': video.json['data']['ref']},
                                          headers=HEADERS).status_code, 400)
        removed = self.client.delete(f'{BASE}/projects/{ident}/media/{listed[0]["id"]}?client_id=31', headers=HEADERS)
        self.assertEqual(removed.status_code, 200)
        self.assertIn(video.json['data']['ref'], {item['ref'] for item in self.client.get(f'{BASE}/library?client_id=31').json['data']['items']})

    def test_commands_extensions_and_render_queue(self):
        ident = self.create()
        self.put(ident, {'expected_revision': 1, 'project': timeline(ident)})
        empty = self.client.post(f'{BASE}/projects/{ident}/renders?client_id=31', json={}, headers=HEADERS)
        self.assertEqual(empty.status_code, 400)
        self.assertIn('vazia', empty.json['error'])

        asset = self.upload(ident, png_bytes(), 'image', 'capa.png').json['data']['id']
        applied = self.client.post(f'{BASE}/projects/{ident}/commands?client_id=31', headers=HEADERS,
                                   json={'commands': [{'op': 'add_media', 'args': {'asset_id': asset, 'duration': 2}}]})
        self.assertEqual((applied.status_code, applied.json['data']['revision']), (200, 3), applied.json)

        catalog = self.client.get(f'{BASE}/extensions?client_id=31').json['data']['items']
        self.assertEqual({item['id'] for item in catalog}, {'titulo', 'legendas'})
        title = self.client.post(f'{BASE}/projects/{ident}/extensions/titulo/run?client_id=31', headers=HEADERS,
                                 json={'params': {'text': 'Compre', 'duration': 2, 'position': 'top', 'style': 'box', 'size': 12, 'color': '#ffcc00',
                                                  'playhead_seconds': 1.5}})
        self.assertEqual(title.status_code, 200, title.json)
        bad = self.client.post(f'{BASE}/projects/{ident}/extensions/titulo/run?client_id=31', headers=HEADERS,
                               json={'params': {'text': 'x', 'position': '../../'}})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.post(f'{BASE}/projects/{ident}/extensions/os.system/run?client_id=31', headers=HEADERS, json={}).status_code, 400)
        saved = self.client.get(f'{BASE}/projects/{ident}?client_id=31').json['data']
        text = saved['project']['scenes'][0]['tracks']['overlay'][0]['elements'][0]
        self.assertEqual((text['startTime'], text['params']['content'], text['params']['background.enabled']), (int(1.5 * TICKS), 'Compre', True))

        from aicentralv2.creative_media import studio
        with patch.object(studio._POOL, 'submit') as submit:
            queued = self.client.post(f'{BASE}/projects/{ident}/renders?client_id=31', json={'format': 'mp4'}, headers=HEADERS)
        self.assertEqual(queued.status_code, 200, queued.json)
        submit.assert_called_once()
        with self.app().test_request_context():
            task = json.loads((editor._scope('31') / f'task-{queued.json["data"]["id"]}.json').read_text())
        self.assertEqual((task['kind'], task['work']['revision']), ('opencut_render', saved['revision']))
        self.assertEqual([item['id'] for item in task['work']['media']], [asset], 'só as mídias usadas na timeline vão para o worker')
        self.assertEqual(self.client.get(f'{BASE}/renders/{queued.json["data"]["id"]}/content?client_id=31').status_code, 400, 'render não pronto')

    def test_brand_kit_for_title_presets(self):
        with patch('aicentralv2.creative_media.studio._storyboard_brand', return_value={
                'name': 'Conecta', 'primary_color': '#3a0b3d', 'secondary_color': 'azul', 'fonts': [{'family': 'Montserrat'}],
                'logo_url': 'https://externo/logo.png'}):
            brand = self.client.get(f'{BASE}/brand?client_id=31').json['data']
        self.assertEqual((brand['primary'], brand['secondary'], brand['font'], brand['logo_url'], brand['configured']),
                         ('#3a0b3d', '#4c8dff', 'Montserrat', '', True), 'cor inválida cai no padrão; logo só local')
        with patch('aicentralv2.creative_media.studio._storyboard_brand', side_effect=RuntimeError('sem banco')):
            fallback = self.client.get(f'{BASE}/brand?client_id=31').json['data']
        self.assertEqual((fallback['primary'], fallback['configured']), ('#1dbf73', False))

    def test_delivery_loudness(self):
        loud = self.root / 'loud.mp4'
        fixtures.subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(self.voiced), '-af', 'volume=12dB', '-c:v', 'copy', '-c:a', 'aac', str(loud)],
                                check=True, capture_output=True)
        before = editor.normalize_loudness(loud)
        self.assertTrue(before['changed'])
        after = editor.normalize_loudness(loud)
        self.assertFalse(after['changed'], after)
        self.assertLessEqual(abs(after['lufs'] - editor.DELIVERY_LUFS), 1)
        self.assertLessEqual(after['true_peak'], editor.DELIVERY_TRUE_PEAK + .1)
        self.assertIsNone(editor.normalize_loudness(self.silent), 'vídeo sem áudio fica como está')

    def test_timeline_audio_transcription_task(self):
        ident = self.create()
        url = f'{BASE}/projects/{ident}/transcriptions?client_id=31'
        from aicentralv2.creative_media import studio
        with patch.object(studio._POOL, 'submit') as submit:
            queued = self.client.post(url, headers=HEADERS, data={'language': 'pt', 'file': (io.BytesIO(self.sound.read_bytes()), 'timeline.wav')})
            silent = self.client.post(url, headers=HEADERS, data={'file': (io.BytesIO(png_bytes()), 'timeline.wav')})
        self.assertEqual(queued.status_code, 200, queued.json)
        self.assertEqual(silent.status_code, 400)
        submit.assert_called_once()
        with self.app().test_request_context():
            root = editor._scope('31')
            task = json.loads((root / f'task-{queued.json["data"]["id"]}.json').read_text())
        self.assertEqual((task['kind'], task['work']['language']), ('transcribe', 'pt'))
        self.assertTrue(task['work']['source'].endswith('.transcribe.wav'))
        with patch('aicentralv2.creative_media.studio_tasks.transcribe', return_value={'captions': [{'start': 0, 'end': 1, 'text': 'oi'}], 'words': [], 'language': 'pt'}) as whisper, \
                self.app().app_context():
            from aicentralv2.creative_media.studio_tasks import run_task
            run_task(root, task['id'])
        whisper.assert_called_once_with(Path(task['work']['source']), 'pt')
        self.assertFalse(Path(task['work']['source']).exists(), 'o áudio temporário é apagado')
        status = self.client.get(f'/parametros/api/format-lab/studio/tasks/{task["id"]}?client_id=31').json['data']
        self.assertEqual((status['status'], status['result']['captions'][0]['text']), ('ready', 'oi'))

    def test_browser_export_goes_to_brand_library(self):
        ident = self.create()
        url = f'{BASE}/projects/{ident}/exports?client_id=31'
        webm = self.root / 'export.webm'
        if not webm.exists():
            fixtures.subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(self.voiced), '-c:v', 'libvpx-vp9', '-b:v', '200k', '-c:a', 'libopus', str(webm)],
                                    check=True, capture_output=True)
        from aicentralv2.creative_media import studio
        ready = self.client.post(url, headers=HEADERS, data={'name': 'Campanha.mp4', 'file': (io.BytesIO(self.voiced.read_bytes()), 'Campanha.mp4')})
        self.assertEqual((ready.status_code, ready.json['data']['status']), (200, 'ready'), ready.json)
        clip = ready.json['data']['clip']
        self.assertEqual((clip['source'], clip['project_id'], clip['revision'], clip['name']), ('editor', ident, 1, 'Campanha.mp4'))
        library = self.client.get(f'{BASE}/library?client_id=31').json['data']['items']
        self.assertIn(('clip:' + clip['id'].split(':')[1], 'Exportado do editor'), {(row['ref'], row['source']) for row in library})
        with self.client.get(clip['video_url']) as content:
            self.assertEqual(content.status_code, 200)
        with patch.object(studio._POOL, 'submit') as submit:
            queued = self.client.post(url, headers=HEADERS, data={'name': 'Campanha.webm', 'file': (io.BytesIO(webm.read_bytes()), 'Campanha.webm')})
        self.assertEqual((queued.status_code, queued.json['data']['status']), (200, 'queued'), queued.json)
        submit.assert_called_once()
        with self.app().test_request_context():
            root = editor._scope('31')
            task = json.loads((root / f'task-{queued.json["data"]["task_id"]}.json').read_text())
        self.assertEqual((task['kind'], task['work']['origin']), ('import', {'source': 'editor', 'project_id': ident, 'revision': 1}))
        self.assertTrue(Path(task['work']['source']).exists(), 'a tarefa recebe o arquivo para converter')
        with self.app().app_context():
            from aicentralv2.creative_media.studio_tasks import run_task
            run_task(root, task['id'])
        converted = json.loads((root / f'clip-{task["id"]}.json').read_text())
        self.assertEqual((converted['source'], converted['project_id']), ('editor', ident))
        self.assertIn('audio', fixtures.probe(root / f'{task["id"]}.mp4')[1])
        invalid = self.client.post(url, headers=HEADERS, data={'file': (io.BytesIO(b'nao e video'), 'x.mp4')})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(list(root.glob('*.upload')), [], 'nenhum envio temporário fica para trás')
        foreign = self.client.post(f'{BASE}/projects/{ident}/exports?client_id=32', headers=HEADERS,
                                   data={'file': (io.BytesIO(self.voiced.read_bytes()), 'x.mp4')})
        self.assertEqual(foreign.status_code, 400)


if __name__ == '__main__':
    unittest.main()
