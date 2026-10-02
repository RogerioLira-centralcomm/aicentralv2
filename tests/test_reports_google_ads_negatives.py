from unittest import TestCase
from unittest.mock import patch

from aicentralv2.cadu_connect import reports_google_ads_negatives as negatives


def neg(id, text, match='EXACT', level='ad_group', campaign='10', group='20', **extra):
    return {'id': id, 'account_id': 1, 'level': level, 'campaign_external_id': campaign, 'ad_group_external_id': group if level == 'ad_group' else None,
            'campaign_name': 'C', 'ad_group_name': 'G', 'keyword_text': text, 'match_type': match, 'attached_campaign_ids': [],
            'shared_set_external_id': None, 'shared_set_name': None, 'removed_at': None, **extra}


def term(text, clicks=10, cost=20, conversions=0, campaign='10', group='20'):
    return {'account_id': 1, 'campaign_external_id': campaign, 'ad_group_external_id': group, 'search_term': text,
            'clicks': clicks, 'cost': cost, 'conversions': conversions}


def score(rows, keywords=(), terms=(), conflicts=()):
    negatives.score_negatives(rows, list(keywords), list(terms), set(conflicts))
    return {row['id']: row for row in rows}


class NegativeScoreTest(TestCase):
    def test_conflict_is_a_certain_removal(self):
        out = score([neg(1, 'gratis', 'BROAD')], conflicts=[1])
        self.assertEqual(('remove', 5), (out[1]['verdict'], out[1]['score']))

    def test_campaign_negative_covers_the_ad_group_duplicate(self):
        out = score([neg(1, 'curso', 'BROAD', level='campaign'), neg(2, 'curso gratis', 'EXACT')])
        self.assertEqual('remove', out[2]['verdict'])
        self.assertEqual(1, out[2]['redundant_with'])
        self.assertEqual('keep', out[1]['verdict'])

    def test_broad_inside_exact_is_not_redundant(self):
        out = score([neg(1, 'curso gratis', 'EXACT', level='campaign'), neg(2, 'curso', 'BROAD')])
        self.assertNotEqual('remove', out[2]['verdict'])

    def test_mutual_duplicates_keep_only_one(self):
        out = score([neg(1, 'emprego'), neg(2, 'emprego')])
        self.assertEqual(['keep', 'remove'], [out[1]['verdict'], out[2]['verdict']])

    def test_other_campaign_does_not_cover(self):
        out = score([neg(1, 'curso', 'BROAD', level='campaign', campaign='99'), neg(2, 'curso')])
        self.assertEqual('keep', out[2]['verdict'])

    def test_blocking_converting_terms_asks_for_review(self):
        out = score([neg(1, 'tarifa social')], terms=[term('tarifa social', conversions=3)])
        self.assertEqual(('review', 25), (out[1]['verdict'], out[1]['score']))

    def test_protecting_budget_scores_high(self):
        out = score([neg(1, 'emprego', 'BROAD')], terms=[term('vaga emprego', clicks=30, cost=80)])
        self.assertEqual(('keep', 85), (out[1]['verdict'], out[1]['score']))

    def test_broad_word_inside_a_keyword_is_reviewed(self):
        keyword = {'account_id': 1, 'campaign_external_id': '10', 'ad_group_external_id': '20', 'keyword_text': 'teste gratis'}
        out = score([neg(1, 'gratis', 'BROAD')], keywords=[keyword])
        self.assertEqual('review', out[1]['verdict'])

    def test_removed_rows_are_skipped_and_proposal_targets_the_level(self):
        rows = [neg(1, 'a', removed_at='2026-09-30'), neg(2, 'lista', level='shared_list', campaign=None, shared_set_external_id='7', shared_set_name='Lista')]
        out = score(rows)
        self.assertNotIn('score', out[1])
        self.assertEqual({'level': 'shared_list', 'shared_set_id': '7'}, out[2]['proposal']['target'])
        self.assertEqual('negative.remove', out[2]['proposal']['op'])


class NegativeReviewTest(TestCase):
    def test_reviews_are_filtered_and_clamped(self):
        rows = [neg(1, 'a'), neg(2, 'b')]
        score(rows)
        reply = '```json\n{"reviews":[{"id":1,"verdict":"remove","confidence":3,"reason":"x"},{"id":2,"verdict":"nope"},{"id":9,"verdict":"keep"}]}\n```'
        with patch.object(negatives, 'chat_completion', return_value={'message': {'content': reply}}):
            out = negatives.review(rows, [], [])
        self.assertEqual({1: {'verdict': 'remove', 'confidence': 1.0, 'reason': 'x'}}, out)

    def test_unreadable_answer_is_an_error(self):
        rows = [neg(1, 'a')]
        score(rows)
        with patch.object(negatives, 'chat_completion', return_value={'message': {'content': 'sem json'}}):
            with self.assertRaises(negatives.ReviewError):
                negatives.review(rows, [], [])
