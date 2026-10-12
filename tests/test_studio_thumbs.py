import io
import tempfile
import unittest
from pathlib import Path

from flask import Flask
from PIL import Image

from aicentralv2.creative_media import studio_thumbs
from aicentralv2.creative_media.studio_thumbs import send_resized, thumb_url_for, with_thumbs

STILL = '/parametros/api/format-lab/swap/still/' + 'a' * 32 + '.png'


class ThumbUrlTests(unittest.TestCase):
    def test_known_families_get_a_reduced_copy(self):
        self.assertEqual(thumb_url_for('/static/uploads/creative_generated/abc.png'), '/media/studio/480/creative_generated/abc.png')
        self.assertEqual(thumb_url_for('/static/uploads/creative_references/ref@base.webp'), '/media/studio/480/creative_references/ref@base.webp')
        self.assertEqual(thumb_url_for(STILL), STILL + '?w=480')
        self.assertEqual(thumb_url_for('/parametros/api/media/assets/42/content'), '/parametros/api/media/assets/42/content?w=480')

    def test_everything_else_is_left_alone(self):
        for value in ('', 'https://cdn.example/x.png', 'data:image/png;base64,AAAA', '/static/uploads/other/x.png',
                      '/static/uploads/creative_generated/clip.mp4', '/static/uploads/creative_generated/../x.png',
                      STILL + '?w=240', '/parametros/api/format-lab/swap/still/' + 'a' * 32 + '.mp4'):
            self.assertEqual(thumb_url_for(value), value, value)

    def test_with_thumbs_only_replaces_a_missing_or_full_size_thumb(self):
        full = '/static/uploads/creative_generated/a.png'
        items = with_thumbs([
            {'id': 1, 'image_url': full, 'thumb_url': full},
            {'id': 2, 'image_url': full},
            {'id': 3, 'asset_url': STILL},
            {'id': 4, 'image_url': full, 'thumb_url': '/static/uploads/creative_generated/own-thumb.png'},
            {'id': 5, 'image_url': 'https://cdn.example/x.png'},
            'not-a-dict',
        ])
        self.assertEqual([item.get('thumb_url') for item in items[:5]], [
            '/media/studio/480/creative_generated/a.png', '/media/studio/480/creative_generated/a.png', STILL + '?w=480',
            '/static/uploads/creative_generated/own-thumb.png', None])
        self.assertEqual(items[5], 'not-a-dict')


class ThumbRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        folder = root / 'app' / 'static' / 'uploads' / 'creative_generated'
        folder.mkdir(parents=True)
        Image.new('RGB', (2400, 1600), (30, 120, 200)).save(folder / 'big.png')
        (folder / 'broken.png').write_bytes(b'not an image')
        self.app = Flask(__name__, root_path=str(root / 'app'), instance_path=str(root / 'instance'))
        self.app.register_blueprint(studio_thumbs.bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_serves_a_small_webp_instead_of_the_original(self):
        response = self.client.get('/media/studio/480/creative_generated/big.png')
        self.assertEqual((response.status_code, response.mimetype), (200, 'image/webp'))
        image = Image.open(io.BytesIO(response.data))
        self.assertLessEqual(max(image.size), 480 * 2)
        self.assertLess(image.width, 2400)
        original = (Path(self.tmp.name) / 'app/static/uploads/creative_generated/big.png').stat().st_size
        self.assertLess(len(response.data), original / 5)

    def test_unsupported_requests_are_refused(self):
        for url in ('/media/studio/500/creative_generated/big.png', '/media/studio/480/other/big.png',
                    '/media/studio/480/creative_generated/missing.png', '/media/studio/480/creative_generated/.hidden'):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_an_unreadable_image_still_shows_at_full_size(self):
        response = self.client.get('/media/studio/480/creative_generated/broken.png')
        self.assertEqual((response.status_code, response.data), (200, b'not an image'))

    def test_send_resized_without_a_width_sends_the_original(self):
        path = Path(self.tmp.name) / 'app/static/uploads/creative_generated/big.png'
        with self.app.test_request_context():
            response = send_resized(path, 'image/png', None)
        self.assertEqual(response.mimetype, 'image/png')
        with self.app.test_request_context():
            self.assertEqual(send_resized(path, 'video/mp4', 480).mimetype, 'video/mp4')


if __name__ == '__main__':
    unittest.main()
