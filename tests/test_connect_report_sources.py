import io
from unittest import TestCase, mock
from PIL import Image
from werkzeug.datastructures import FileStorage
from aicentralv2.cadu_connect import report_sources as sources
from flask import Flask
from werkzeug.exceptions import RequestEntityTooLarge


def upload(fmt='PNG'):
    data = io.BytesIO()
    Image.new('RGB', (10, 12), 'white').save(data, format=fmt)
    data.seek(0)
    return FileStorage(stream=data, filename='print.png')


class ReportSourceTests(TestCase):
    def test_report_multipart_is_bounded_before_parsing(self):
        with mock.patch.dict(sources.LIMITS, bytes_per_batch=3):
            oversized = mock.MagicMock(content_length=1024 * 1024 + 4)
            with self.assertRaises(RequestEntityTooLarge):
                sources.bound_multipart_request(oversized)
            oversized.stream.read.assert_not_called()
            streamed = mock.MagicMock(content_length=None, stream=io.BytesIO(b'a' * (1024 * 1024 + 4)))
            with self.assertRaises(RequestEntityTooLarge):
                sources.bound_multipart_request(streamed)

    def test_decodes_supported_images_and_normalizes_png(self):
        for fmt in ('PNG', 'JPEG', 'WEBP'):
            result = sources.prepare_image(upload(fmt))
            self.assertEqual((result['width'], result['height']), (10, 12))
            self.assertEqual(result['mime_type'], 'image/png')
            self.assertTrue(result['image_bytes'].startswith(b'\x89PNG'))

    def test_fake_extension_rejected(self):
        with self.assertRaises(ValueError):
            sources.prepare_image(FileStorage(stream=io.BytesIO(b'<script>alert(1)</script>'), filename='photo.png'))

    def test_unsupported_format_rejected_even_with_png_name(self):
        with self.assertRaises(ValueError):
            sources.prepare_image(upload('GIF'))

    def test_limits_and_hash_are_deterministic(self):
        self.assertEqual(sources.prepare_image(upload())['sha256'], sources.prepare_image(upload())['sha256'])
        with mock.patch.dict(sources.LIMITS, pixels_per_image=10):
            with self.assertRaises(ValueError):
                sources.prepare_image(upload())

    def test_project_access_rechecked_before_serving_source(self):
        app = Flask(__name__)
        selected = {'organization_id': 4, 'client_id': 5}
        with app.test_request_context(), mock.patch.object(sources.context, 'resolve', return_value=selected), mock.patch.object(sources.context, 'inventory', return_value=[]):
            query = mock.Mock(return_value=[{'project_ref': 'projects:9'}])
            from werkzeug.exceptions import NotFound
            with self.assertRaises(NotFound):
                sources.authorized_report(query, 10)
            self.assertEqual(query.call_args.args[1], (10, 4, 5))
