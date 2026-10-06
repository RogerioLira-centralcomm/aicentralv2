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


class ReachSplitTest(TestCase):
    def test_number_leads_and_sentence_is_never_a_figure(self):
        self.assertEqual(channels.split_reach('+20M usuários BR'), ('+20M', 'usuários BR'))
        self.assertEqual(channels.split_reach('+150M pageviews/mês'), ('+150M', 'pageviews/mês'))
        self.assertEqual(channels.split_reach('Mensurável por campanha no Brasil'), ('', 'Mensurável por campanha no Brasil'))
        self.assertEqual(channels.split_reach('24 horas no ar'), ('', '24 horas no ar'))
        self.assertEqual(channels.split_reach(None), ('', ''))

    def test_decorate_exposes_figure_and_keeps_sentence_out_of_it(self):
        number = {'id': 1, 'slug': 'a', 'name': 'A', 'category': 'Streaming', 'logo_path': '', 'imagens': [], 'audience': '+50M ouvintes'}
        phrase = {'id': 2, 'slug': 'b', 'name': 'B', 'category': 'Programática', 'logo_path': '', 'imagens': [], 'audience': 'Mensurável por campanha'}
        with patch.object(channels, '_channel_logo', return_value=''):
            channels.decorate_logos([number, phrase])
        self.assertEqual((number['reach_figure'], number['reach_unit']), ('+50M', 'ouvintes'))
        self.assertEqual(phrase['reach_figure'], '')
        self.assertNotIn('reach_unit', phrase)


class MeasurableTest(TestCase):
    def test_measurable_comes_from_a_real_measurement_value_and_raw_column_is_dropped(self):
        rows = [
            {'id': 1, 'slug': 'a', 'name': 'A', 'category': 'X', 'logo_path': '', 'imagens': [], 'medicao': ['Pixel', 'Brand lift']},
            {'id': 2, 'slug': 'b', 'name': 'B', 'category': 'X', 'logo_path': '', 'imagens': [], 'medicao': 'Não informado'},
            {'id': 3, 'slug': 'c', 'name': 'C', 'category': 'X', 'logo_path': '', 'imagens': [], 'medicao': []},
        ]
        with patch.object(channels, '_channel_logo', return_value=''):
            channels.decorate_logos(rows)
        self.assertEqual([row['measurable'] for row in rows], [True, False, False])
        self.assertTrue(all('medicao' not in row for row in rows))


class PlacesNoValueTest(TestCase):
    def test_place_projection_carries_no_investment(self):
        from aicentralv2.cadu_planner import places
        row = {'id': 1, 'slug': 's', 'title': 'T', 'investment': {'label': 'R$ 10 mil a R$ 20 mil'}, 'metrics': {}, 'media': {}, 'points': []}
        self.assertNotIn('investment', places._serialize(row))


class StudioCoverTest(TestCase):
    def test_studio_cover_is_used_only_when_there_is_no_real_photo_and_is_flagged(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'spotify.webp').write_bytes(b'x')
            (Path(folder) / 'spotify-b.webp').write_bytes(b'x')
            with patch.object(channels, '_CAPAS_DIR', Path(folder)):
                self.assertEqual(channels.capa_urls('spotify'), ['/static/images/canais/capas/spotify.webp', '/static/images/canais/capas/spotify-b.webp'])
                self.assertEqual(channels.cover_url({'slug': 'spotify'}), '/static/images/canais/capas/spotify.webp')
                self.assertTrue(channels.cover_is_illustration({'slug': 'spotify'}))
                self.assertEqual(channels.cover_url({'slug': 'netflix'}), '')
                self.assertFalse(channels.cover_is_illustration({'slug': 'netflix'}))
                self.assertEqual(channels.capa_urls('../etc/passwd'), [])
                real = {'slug': 'spotify', 'imagens': ['https://cdn.example.com/real.jpg']}
                self.assertEqual(channels.cover_url(real), 'https://cdn.example.com/real.jpg')
                self.assertFalse(channels.cover_is_illustration(real))


class RetiredAndHiddenChannelsTest(TestCase):
    def test_constants_hide_portals_and_retire_waze(self):
        from aicentralv2.cadu_family import repository
        self.assertIn('Portais', repository.HIDDEN_CHANNEL_CATEGORIES)
        self.assertIn('waze', repository.RETIRED_CHANNEL_SLUGS)

    def test_detail_of_retired_channel_is_not_found(self):
        from werkzeug.exceptions import NotFound
        row = {'id': 22, 'slug': 'waze', 'name': 'Waze', 'categoria': 'Mobilidade', 'logo_path': '', 'imagem_path': None,
               'og_image_path': None, 'imagens': []}
        with patch.object(channels, '_rows', return_value=[row]):
            with self.assertRaises(NotFound):
                channels.detail(22)

    def test_a_portal_channel_cannot_be_newly_added_but_others_can(self):
        from werkzeug.exceptions import BadRequest
        from aicentralv2.cadu_planner import catalog
        with self.assertRaises(BadRequest):
            catalog.ensure_channel_listed('canais', {'category': 'Portais'})
        catalog.ensure_channel_listed('canais', {'category': 'Streaming'})
        catalog.ensure_channel_listed('portais', {'category': 'Portais'})

    def test_waze_migration_is_registered_for_deploy(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        self.assertIn('deactivate_canal_waze.sql', (root / 'migrations' / 'ORDER.txt').read_text())
        sql = (root / 'migrations' / 'deactivate_canal_waze.sql').read_text()
        self.assertIn("slug = 'waze'", sql)
        self.assertNotIn('DELETE', sql.upper())
