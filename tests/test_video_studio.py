"""Real FFmpeg regression coverage for studio uploads, trim and sound export."""
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from flask import Blueprint, Flask, jsonify, request

from aicentralv2.creative_media.studio import normalize_edit, probe, render_clip, register_studio_routes
from aicentralv2.creative_media.planner import build_plan
from aicentralv2.creative_media.transcode import mix_voiceover
from aicentralv2.creative_format_lab.swap_session import normalize_video_project


class ProjectTest(unittest.TestCase):
    def test_sound_default_preserves_explicit_silence(self):
        self.assertEqual(normalize_video_project({})['audio']['mode'], 'ambient')
        self.assertEqual(normalize_video_project({'audio': {'mode': 'silence'}})['audio']['mode'], 'silence')

    def test_roundtrip_and_invalid_numbers(self):
        edit = normalize_edit({'start': 1, 'end': 5, 'speed': .5, 'original_volume': 0, 'sound_volume': .4, 'loop': True})
        self.assertEqual(normalize_video_project({'edit': edit})['edit'], edit)
        self.assertEqual(normalize_edit({'start': float('nan'), 'end': -5, 'sound_volume': 500})['start'], 0)
        self.assertEqual(normalize_edit({'sound_volume': 500})['sound_volume'], 1)
        self.assertEqual(edit['speed'], .5)
        self.assertEqual(normalize_edit({'speed': 20})['speed'], 4)

    def test_workspace_spend_roundtrip_is_bounded_and_sanitized(self):
        project = normalize_video_project({'spend': {'events': [{
            'id': 'video:job-1', 'kind': 'video', 'label': 'Geração 8s',
            'amount_brl': 12.34, 'amount_usd': 2.1, 'status': 'confirmed',
            'created_at': '2026-09-14T20:00:00Z',
        }]}})
        self.assertEqual(project['spend']['events'][0]['amount_brl'], 12.34)
        self.assertEqual(project['spend']['events'][0]['status'], 'confirmed')

    def test_single_image_project_preserves_seedance_mode_and_four_seconds(self):
        project = normalize_video_project({'generation_mode': 'single_image', 'duration': 4})
        self.assertEqual(project['generation_mode'], 'single_image')
        self.assertEqual(project['duration'], 4)

    def test_single_image_vertical_output_and_native_audio_contract(self):
        plan = build_plan({
            'source': {'mode': 'flattened_still', 'base_id': 'scene-1'},
            'duration': 4,
            'quality': 'production',
            'aspect_ratio': '9:16',
            'audio': {'mode': 'ambient'},
        })
        self.assertEqual(plan['size'], '720x1280')
        self.assertEqual(plan['aspect_ratio'], '9:16')
        self.assertTrue(plan['generate_audio'])
        self.assertIsNone(plan['seed'])

    def test_audio_composition_supports_narration_music_and_ambience(self):
        plan = build_plan({
            'audio': {
                'enabled': True,
                'ambience': True,
                'ambience_note': 'som discreto de loja',
                'narration_mode': 'guided',
                'prompt': 'voz brasileira apresenta a oferta visível',
                'music_enabled': True,
                'music_note': 'eletrônica moderna e discreta',
            },
        })
        self.assertTrue(plan['generate_audio'])
        self.assertEqual(plan['audio_mode'], 'voice')
        self.assertIn('Keep it below narration', plan['prompt'])
        self.assertIn('som discreto de loja', plan['prompt'])

    def test_exact_voiceover_does_not_create_duplicate_native_speech(self):
        plan = build_plan({
            'audio': {
                'enabled': True,
                'ambience': False,
                'narration_mode': 'voiceover',
                'script': 'Conheça agora a nossa oferta.',
                'music_enabled': True,
                'music_note': 'institucional leve',
            },
        })
        self.assertTrue(plan['generate_audio'])
        self.assertIn('No native speech', plan['prompt'])
        self.assertIn('background music bed', plan['prompt'])

    def test_audio_composition_roundtrips_and_silence_disables_layers(self):
        project = normalize_video_project({'audio': {
            'enabled': False,
            'ambience': True,
            'narration_mode': 'guided',
            'music_enabled': True,
        }})
        self.assertEqual(project['audio']['mode'], 'silence')
        self.assertFalse(project['audio']['ambience'])
        self.assertEqual(project['audio']['narration_mode'], 'none')
        self.assertFalse(project['audio']['music_enabled'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class MediaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.silent = cls.root / 'silent.mp4'
        cls.voiced = cls.root / 'voiced.mp4'
        cls.voice = cls.root / 'voice.wav'
        cls.sound = cls.root / 'sound.wav'
        def ff(*args):
            subprocess.run(['ffmpeg', '-y', '-v', 'error', *args], check=True, capture_output=True)
        ff('-f', 'lavfi', '-i', 'color=c=blue:s=128x72:d=2.4:r=24', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.silent))
        ff('-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.6', str(cls.voice))
        ff('-f', 'lavfi', '-i', 'sine=frequency=880:duration=3', str(cls.sound))
        ff('-i', str(cls.silent), '-i', str(cls.sound), '-map', '0:v', '-map', '1:a', '-shortest', '-c:v', 'copy', '-c:a', 'aac', str(cls.voiced))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_voiceover_preserves_video_length_with_and_without_original_audio(self):
        for source in (self.silent, self.voiced):
            with self.subTest(source=source.name):
                output = self.root / f'mixed-{source.name}'
                output.write_bytes(mix_voiceover(source.read_bytes(), self.voice.read_bytes()))
                duration, streams = probe(output)
                self.assertIn('audio', streams)
                self.assertAlmostEqual(duration, 2.4, delta=.15)

    def test_trim_mix_and_silence(self):
        output = self.root / 'trim.mp4'
        render_clip(self.silent, output, normalize_edit({'start': .4, 'end': 1.6, 'fade_in': .1, 'fade_out': .2}), self.sound)
        duration, streams = probe(output)
        self.assertAlmostEqual(duration, 1.2, delta=.15)
        self.assertIn('audio', streams)
        render_clip(self.voiced, output, normalize_edit({'original_volume': 0}))
        self.assertNotIn('audio', probe(output)[1])

    def test_loop_and_invalid_range(self):
        output = self.root / 'loop.mp4'
        render_clip(self.silent, output, normalize_edit({'loop': True, 'sound_offset': .2}), self.voice)
        self.assertAlmostEqual(probe(output)[0], 2.4, delta=.15)
        with self.assertRaises(ValueError):
            render_clip(self.silent, output, normalize_edit({'start': 2, 'end': 1}))

    def test_visual_effects_are_in_exported_frames(self):
        output = self.root / 'effects.mp4'
        render_clip(self.silent, output, normalize_edit({'grayscale': True, 'flip': True, 'video_fade_in': .2, 'video_fade_out': .2}))
        result = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0.5', '-i', str(output), '-vf', 'scale=1:1', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
        pixel = list(result.stdout[:3])
        self.assertEqual(len(pixel), 3)
        self.assertLessEqual(max(pixel) - min(pixel), 2)
        self.assertAlmostEqual(probe(output)[0], 2.4, delta=.15)

    def test_speed_changes_export_duration_and_keeps_audio(self):
        output = self.root / 'speed.mp4'
        render_clip(self.voiced, output, normalize_edit({'speed': 2}))
        duration, streams = probe(output)
        self.assertAlmostEqual(duration, 1.2, delta=.18)
        self.assertIn('audio', streams)

    def test_export_routes_are_idempotent_and_brand_scoped(self):
        from aicentralv2.creative_media import studio
        app = self.app()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_type='admin', trocr_csrf_token='test-token')
        service = Mock()
        service.load_format_lab_swap_library.return_value = {'items': [{'id': 'clip-test', 'video_url': '/parametros/api/media/assets/asset-test/content'}]}
        service.serve_media_asset.return_value = (self.silent, 'video/mp4')
        def execute(fn):
            try:
                return fn()
            except ValueError as error:
                return jsonify(success=False, error=str(error)), 400
        http = (execute, lambda: request.get_json(), lambda data: jsonify(success=True, data=data), lambda: service)
        data = {'client_id': 20, 'clip_id': 'clip-test', 'request_id': 'a'*32, 'edit': {'start': .4, 'end': 1.4}}
        url = '/parametros/api/format-lab/studio/exports'
        headers = {'X-Trocr-CSRF-Token': 'test-token'}
        with patch('aicentralv2.creative_format_lab.swap_routes._http', return_value=http), patch.object(studio._POOL, 'submit', side_effect=lambda fn,*args: fn(*args)) as submit:
            response = client.post(url, json=data, headers=headers)
            self.assertEqual(response.status_code, 200, response.json)
            again = client.post(url, json=data, headers=headers)
            self.assertEqual(again.json['data']['status'], 'ready')
            self.assertEqual(submit.call_count, 1)
            status = client.get(url + '/' + 'a'*32 + '?client_id=20')
            self.assertEqual(status.json['data']['status'], 'ready')
            self.assertEqual(client.get(url + '/' + 'a'*32 + '/content?client_id=20').status_code, 200)
            self.assertEqual(client.get(url + '/' + 'a'*32 + '/content?client_id=21').status_code, 400)
            self.assertEqual(client.post(url, json={**data, 'clip_id': 'other-brand'}, headers=headers).status_code, 400)

    def app(self):
        app = Flask(__name__, instance_path=str(self.root / 'instance'))
        app.secret_key = 'test-only'
        app.config['MEDIA_WORKER_MODE'] = 'thread'
        bp = Blueprint('studio_test', __name__, url_prefix='/parametros')
        register_studio_routes(bp)
        app.register_blueprint(bp)
        return app

    def test_private_upload_library_and_cross_brand_lookup(self):
        app = self.app()
        client = app.test_client()
        url = '/parametros/api/format-lab/studio/sounds'
        self.assertEqual(client.get(url + '?client_id=10').status_code, 401)
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_type='admin', trocr_csrf_token='test-token')
        self.assertEqual(client.post(url).status_code, 403)
        def execute(fn):
            try:
                return fn()
            except ValueError as error:
                return jsonify(success=False, error=str(error)), 400
        http = (execute, lambda: request.get_json(), lambda data: jsonify(success=True, data=data), None)
        with patch('aicentralv2.creative_format_lab.swap_routes._http', return_value=http):
            result = client.post(url, data={'client_id': '10', 'file': (io.BytesIO(self.sound.read_bytes()), 'trilha.wav')}, headers={'X-Trocr-CSRF-Token': 'test-token'})
            self.assertEqual(result.status_code, 200, result.json)
            row = result.json['data']
            self.assertEqual(client.get(row['url']).status_code, 200)
            self.assertTrue(row['waveform'])
            self.assertLessEqual(len(row['waveform']), 96)
            self.assertEqual(client.get(row['url'].replace('client_id=10', 'client_id=11')).status_code, 400)
            library = client.get(url + '?client_id=10').json['data']['items']
            self.assertTrue(any(item['id'] == row['id'] for item in library))
            bad = client.post(url, data={'client_id': '10', 'file': (io.BytesIO(b'not media'), 'bad.mp3')}, headers={'X-Trocr-CSRF-Token': 'test-token'})
            self.assertEqual(bad.status_code, 400)

class SeedancePanelTest(unittest.TestCase):
    def test_capabilities_match_backend_limits(self):
        from aicentralv2.creative_media import settings
        app = Flask(__name__)
        app.secret_key = 'test'
        bp = Blueprint('capabilities_test', __name__)
        register_studio_routes(bp)
        app.register_blueprint(bp)
        client = app.test_client()
        url = '/api/format-lab/studio/capabilities'
        self.assertEqual(client.get(url).status_code, 401)
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_type='admin')
        data = client.get(url).json['data']
        self.assertEqual(data['model'], settings.MODEL)
        self.assertEqual(data['durations'], [d for d in settings.DURATIONS if d <= settings.MAX_DURATION])
        self.assertIn('ambient', data['audio_modes'])
        self.assertEqual(data['qualities']['production'], settings.PRODUCTION_RESOLUTION)

    def test_seed_roundtrip_and_provider_payload(self):
        from aicentralv2.creative_media.planner import build_plan
        from aicentralv2.services.openrouter_service import build_video_payload
        for seed in (0, 42, 2147483647):
            project = normalize_video_project({'seed': seed})
            plan = build_plan({'seed': project['seed'], 'audio': {'mode': 'ambient'}})
            payload = build_video_payload('test', seed=plan['seed'], generate_audio=plan['generate_audio'])
            self.assertEqual(payload['seed'], seed)
            self.assertTrue(payload['generate_audio'])
        for seed in (-1, '42', 1.5, True, 2147483648):
            with self.assertRaises(ValueError):
                build_plan({'seed': seed})


if __name__ == '__main__':
    unittest.main()
