"""Channel cards show a real photo and numbers, never a price or a minimum investment."""
from unittest import TestCase
from unittest.mock import patch

from aicentralv2.cadu_planner import channels
from aicentralv2.cadu_planner.catalog import CLIENT_CHANNEL_KEYS


class ChannelCardTest(TestCase):
    def test_cover_uses_first_real_photo_and_drops_raw_columns(self):
        record = {'id': 1, 'slug': 'spotify', 'name': 'Spotify', 'category': 'Streaming', 'logo_path': '',
                  'imagem_path': '/static/nao-existe.png', 'og_image_path': 'https://cdn.example.com/og.jpg',
                  'imagens': ['https://cdn.example.com/a.jpg'], 'viewability': '86%', 'completion_rate': 0}
        with patch.object(channels, '_channel_logo', return_value=''):
            channels.decorate_logos([record])
        self.assertEqual(record['image_url'], 'https://cdn.example.com/og.jpg')
        for raw in ('imagem_path', 'og_image_path', 'imagens'):
            self.assertNotIn(raw, record)
        self.assertEqual(record['viewability'], 86.0)
        self.assertIsNone(record['completion_rate'])

    def test_channel_without_photo_gets_no_generated_stand_in(self):
        record = {'id': 2, 'slug': 'x', 'name': 'X', 'category': 'Portais', 'logo_path': '', 'imagem_path': None,
                  'og_image_path': None, 'imagens': None}
        with patch.object(channels, '_channel_logo', return_value=''):
            channels.decorate_logos([record])
        self.assertEqual(record['image_url'], '')

    def test_no_commercial_value_reaches_the_client(self):
        for key in ('investimento_minimo', 'lp_data', 'preco', 'cpm', 'custo'):
            self.assertNotIn(key, CLIENT_CHANNEL_KEYS)
        record = {'id': 3, 'slug': 'y', 'name': 'Y', 'category': 'Streaming', 'logo_path': '', 'imagens': []}
        with patch.object(channels, '_channel_logo', return_value=''):
            channels.decorate_logos([record])
        self.assertFalse([key for key in record if any(word in key for word in ('invest', 'preco', 'price', 'cpm', 'custo'))])
