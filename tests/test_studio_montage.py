"""Montar na timeline: plano (regras ou diretor) → comandos com área segura, enquadramento e marca impostos no código."""
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import jsonify, request
from PIL import Image

from tests import test_video_studio as fixtures
from tests.test_studio_video_editor import BASE, HEADERS, timeline
from aicentralv2.creative_media import studio_montage as montage
from aicentralv2.creative_media import studio_video_editor as editor


def scenes(tmp):
    rows = {}
    for index, (size, kind) in enumerate([((1280, 720), 'video'), ((1024, 1024), 'image'), ((1080, 1920), 'image')], 1):
        path = Path(tmp) / f's{index}.png'
        Image.new('RGB', size, (40 * index, 90, 160)).save(path)
        rows[f'b{index}'] = {'id': f'a{index}', 'type': kind, 'width': size[0], 'height': size[1], 'duration': 2.0 if kind == 'video' else None, 'path': str(path)}
    return rows


BEATS = [{'id': 'b1', 'purpose': 'hook', 'visual': 'celular', 'spoken': 'Seu negócio cabe na palma da mão.', 'transition': 'cut'},
         {'id': 'b2', 'purpose': 'beat', 'visual': 'telas', 'spoken': 'Gerencie de qualquer tela.', 'transition': 'cross dissolve'},
         {'id': 'b3', 'purpose': 'end', 'visual': 'família', 'spoken': 'Teste grátis por trinta dias.', 'transition': 'cut', 'brand': 'signature'}]


class CompilerTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = montage.package(BEATS, scenes(self.tmp.name), width=1080, height=1920, duration=9,
                                   brand={'name': 'Conecta', 'primary_color': '#3a0b3d', 'secondary_color': '#2ee6b6'})

    def test_framing_fill_keeps_subject_without_borders_and_fit_shows_whole(self):
        scale, dx, dy, subject_y = montage.framing({'width': 1024, 'height': 1024}, 1080, 1920, 1.2, {'x': .2, 'y': .3})
        self.assertAlmostEqual(scale, 1920 / 1080 * 1.2, places=3)
        self.assertEqual((dx, dy), (612.0, 192.0), 'deslocamento limitado: nenhuma borda aparece')
        self.assertAlmostEqual(subject_y, .36, places=2)
        self.assertEqual(montage.framing({'width': 1024, 'height': 1024}, 1080, 1920, 1.0, {'x': .2, 'y': .3}, 'fit')[:3], (1.0, 0.0, 0.0))

    def test_text_moves_away_from_subject(self):
        self.assertEqual(montage._zone('top', .25), 'bottom')
        self.assertEqual(montage._zone('bottom', .75), 'top')
        self.assertEqual(montage._zone('top', .7), 'top')

    def test_rules_plan_compiles_inside_safe_area_and_duration(self):
        plan = montage.rules_plan(self.pkg)
        self.assertEqual([row['fit'] for row in plan['scenes']], ['fill', 'fit', 'fill'], 'vídeo preenche; quadrado em 9:16 entra inteiro')
        commands = montage.compile_plan(plan, self.pkg)
        self.assertEqual(commands[0]['args']['background'], 'blur')
        media = [c['args'] for c in commands if c['op'] == 'add_media']
        self.assertAlmostEqual(sum(m['duration'] for m in media), 9, places=2)
        self.assertLessEqual(media[0]['duration'], 2.0, 'cena de vídeo não passa do vídeo de origem')
        for text in (c['args'] for c in commands if c['op'] == 'add_text'):
            self.assertGreater(text['y'], montage.SAFE_TOP)
            self.assertLess(text['y'], 1 - montage.SAFE_BOTTOM)
        result, _ = editor.apply_commands(timeline('p1'), commands, {a['id']: {'ref': a['id'], 'type': a['type'], 'name': a['id'], 'duration': a['duration']}
                                                                      for a in self.pkg['scenes'].values()})
        self.assertEqual(len(result['scenes'][0]['tracks']['main']['elements']), 3)
        self.assertEqual(result['settings']['background']['type'], 'blur')

    def test_brand_logo_stays_below_reels_header(self):
        logo = {'id': 'logo', 'type': 'image', 'width': 600, 'height': 600, 'path': self.pkg['scenes']['b2']['path']}
        pkg = {**self.pkg, 'logo': logo}
        commands = montage.compile_plan(montage.rules_plan(pkg), pkg)
        index = next(i for i, c in enumerate(commands) if c['op'] == 'add_media' and c['args']['asset_id'] == 'logo')
        scale, position = commands[index]['args']['scale'], commands[index + 1]['args']['params']
        side = 600 * min(1080 / 600, 1920 / 600) * scale
        top = 1920 / 2 + position['transform.positionY'] - side / 2
        right = 1080 / 2 + position['transform.positionX'] + side / 2
        self.assertGreaterEqual(top, 1920 * montage.SAFE_TOP)
        self.assertLessEqual(right, 1080 * .95)
        self.assertEqual(commands[index]['args']['track'], 'overlay')

    def test_director_plan_is_clamped_and_baked_text_is_protected(self):
        raw = {'cenas': [
            {'beat_id': 'b1', 'peso': 9, 'foco': {'x': 2, 'y': -1}, 'zoom': 5, 'movimento': 'explodir', 'texto': 'um dois três quatro cinco seis sete oito nove', 'zona': 'base'},
            {'beat_id': 'b3', 'texto_gravado': True, 'enquadramento': 'preencher', 'zoom': 1.5, 'movimento': 'zoom_in', 'texto': 'Saiba mais'},
            {'beat_id': 'inventada', 'texto': 'x'}]}
        plan = montage.normalize_plan(raw, self.pkg)
        first = plan['scenes'][0]
        self.assertEqual((first['weight'], first['focus'], first['zoom']), (1.6, {'x': 1.0, 'y': 0.0}, 1.6))
        self.assertEqual(first['motion'], 'zoom_in', 'movimento inválido cai na regra')
        self.assertEqual(len(first['text'].split()), montage.MAX_WORDS)
        self.assertEqual(plan['scenes'][1]['beat_id'], 'b2', 'cena ausente do plano vem das regras')
        commands = montage.compile_plan(plan, self.pkg)
        baked = plan['scenes'][2]
        self.assertEqual((baked['fit'], baked['zoom'], baked['motion'], baked['text']), ('fit', 1.0, 'none', ''))
        self.assertNotIn('Saiba mais', [c['args'].get('text') for c in commands if c['op'] == 'add_text'])

    def test_director_receives_one_image_per_scene(self):
        captured = {}

        def fake(messages, **options):
            captured.update(messages=messages, options=options)
            return {'message': {'content': json.dumps({'cenas': [{'beat_id': 'b2', 'texto': 'Gestão em qualquer tela', 'zona': 'topo'}]})},
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        plan, usage = montage.director_plan(self.pkg, text_callable=fake, model='teste/modelo', briefing='App de gestão')
        images = [part for part in captured['messages'][1]['content'] if part['type'] == 'image_url']
        self.assertEqual(len(images), 3)
        self.assertTrue(images[0]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        self.assertEqual((captured['options']['model'], captured['options']['max_tokens']), ('teste/modelo', None))
        self.assertEqual(plan['scenes'][1]['text'], 'Gestão em qualquer tela')
        self.assertEqual(usage['prompt_tokens'], 10)


@unittest.skipUnless(fixtures.shutil.which('ffmpeg') and fixtures.shutil.which('ffprobe'), 'FFmpeg required')
class MontageRouteTest(unittest.TestCase):
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
        for target in ('aicentralv2.creative_media.studio_video_editor._http',):
            patcher = patch(target, return_value=(execute, lambda: request.get_json(silent=True), lambda data: jsonify(success=True, data=data), Mock))
            patcher.start()
            self.addCleanup(patcher.stop)
        images = {}
        for ident, size in (('s1', (1080, 1920)), ('s2', (1024, 1024))):
            path = self.root / f'still-{ident}.png'
            Image.new('RGB', size, (200, 80, 40)).save(path)
            images[ident] = path
        still = patch('aicentralv2.creative_media.studio_video_editor._resolve_still',
                      side_effect=lambda client, ident: (images[ident], 'image', {'name': ident, 'mime': 'image/png'}))
        brand = patch('aicentralv2.creative_media.studio._storyboard_brand', return_value={'name': 'Conecta', 'primary_color': '#3a0b3d'})
        for patcher in (still, brand):
            patcher.start()
            self.addCleanup(patcher.stop)

    def project(self, beats=True):
        from aicentralv2.creative_media import studio_projects
        with self.app().test_request_context():
            root = editor._scope('31')
            document = {'name': 'Campanha', 'aspect_ratio': '9:16', 'duration': 6, 'video_editor': None}
            if beats:
                document.update(scene_ids=['s1', 's2'], script={'beats': [
                    {'id': 's1', 'purpose': 'hook', 'visual': 'família', 'spoken': 'Energia que acompanha você.'},
                    {'id': 's2', 'purpose': 'end', 'visual': 'logo', 'spoken': 'Saiba mais.'}]})
            saved = studio_projects.save(root, document)
        ident = saved['id']
        self.client.put(f'{BASE}/projects/{ident}?client_id=31', json={'expected_revision': 1, 'project': timeline(ident)}, headers=HEADERS)
        return ident

    def test_rules_montage_builds_timeline_from_project_storyboard(self):
        ident = self.project()
        result = self.client.post(f'{BASE}/projects/{ident}/montage?client_id=31', json={'mode': 'rules'}, headers=HEADERS)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['data']['mode'], 'rules')
        saved = self.client.get(f'{BASE}/projects/{ident}?client_id=31').json['data']['project']
        main = saved['scenes'][0]['tracks']['main']['elements']
        self.assertEqual(len(main), 2)
        self.assertEqual(saved['settings']['canvasSize'], {'width': 1080, 'height': 1920})
        media = self.client.get(f'{BASE}/projects/{ident}/media?client_id=31').json['data']['items']
        self.assertEqual(sorted(item['ref'] for item in media), ['still:s1', 'still:s2'], 'cenas vinculadas ao projeto como mídia')
        again = self.client.post(f'{BASE}/projects/{ident}/montage?client_id=31', json={'mode': 'rules'}, headers=HEADERS)
        self.assertEqual(again.status_code, 400, 'não sobrescreve a timeline sem pedir')
        replaced = self.client.post(f'{BASE}/projects/{ident}/montage?client_id=31', json={'mode': 'rules', 'replace': True}, headers=HEADERS)
        self.assertEqual(replaced.status_code, 200, replaced.json)
        media_again = self.client.get(f'{BASE}/projects/{ident}/media?client_id=31').json['data']['items']
        self.assertEqual(len(media_again), 2, 'remontar não duplica as mídias')

    def test_director_failure_falls_back_to_rules(self):
        from aicentralv2.services.openrouter_service import OpenRouterError
        ident = self.project()
        with patch('aicentralv2.creative_media.studio_video_editor._metered_director', return_value=Mock()), \
                patch('aicentralv2.creative_media.studio_montage.director_plan', side_effect=OpenRouterError('fora do ar')):
            result = self.client.post(f'{BASE}/projects/{ident}/montage?client_id=31', json={'mode': 'director'}, headers=HEADERS)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['data']['mode'], 'rules')
        self.assertIn('diretor', result.json['data']['warning'])

    def test_project_without_storyboard_is_explained(self):
        ident = self.project(beats=False)
        result = self.client.post(f'{BASE}/projects/{ident}/montage?client_id=31', json={'mode': 'rules'}, headers=HEADERS)
        self.assertEqual(result.status_code, 400)
        self.assertIn('storyboard', result.json['error'])

    def test_static_ref_stays_inside_static(self):
        with self.app().test_request_context():
            root = editor._scope('31')
            for ref in ('static:/static/../../etc/passwd', 'static:/static/js/mc-cadu-video.js'):
                with self.subTest(ref=ref), self.assertRaises(ValueError):
                    editor.resolve_ref(root, '31', ref)


if __name__ == '__main__':
    unittest.main()
