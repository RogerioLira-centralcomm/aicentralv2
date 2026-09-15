import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest import TestCase

from scripts.preserve_cadu_legacy import preserve


class LegacyPreservationTest(TestCase):
    def test_snapshot_routes_redactions_exclusions_and_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'legacy'
            source.mkdir()
            (source / '.htaccess').write_text('RewriteRule ^chat-v2/?$ chat-cadu-dify.php [L,QSA]\n')
            (source / 'chat.php').write_text("<?php $api_key = 'example-secret-value'; include 'input.php';")
            (source / 'input.php').write_text('<textarea></textarea>')
            (source / '.env').write_text('PASSWORD=not-for-copy')
            (source / 'uploads').mkdir()
            (source / 'uploads/private.txt').write_text('private upload')
            (source / 'link.php').symlink_to(source / 'input.php')
            destination = root / 'snapshot'
            with contextlib.redirect_stdout(io.StringIO()):
                preserve(source, destination)
            manifest = json.loads((destination / 'manifest.json').read_text())
            self.assertEqual(len(manifest['routes']), 1)
            saved = (destination / 'source/chat.php.reference').read_text()
            self.assertNotIn('example-secret-value', saved)
            self.assertIn('input.php', saved)
            self.assertFalse((destination / 'source/.env.reference').exists())
            self.assertFalse((destination / 'source/uploads').exists())
            self.assertFalse((destination / 'source/link.php.reference').exists())
            self.assertIn('example-secret-value', (source / 'chat.php').read_text())
            with self.assertRaises(FileExistsError):
                preserve(source, destination)

    def test_rejects_destination_inside_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            with self.assertRaises(ValueError):
                preserve(source, source / 'snapshot')
