from unittest import TestCase

from aicentralv2.creative_brand_analysis import CreativeBrandAnalyzer


class WorkspaceBrandReviewAgentsTest(TestCase):
    def test_two_gpt_reviews_keep_distinct_evidence_and_expansion_contracts(self):
        responses = iter([
            {'message': {'content': '{"summary":"Fatos confirmados.","findings":["Site oficial"],"concerns":[],"confidence":0.8,"decision":"ready"}'}, 'model': 'reviewer'},
            {'message': {'content': '{"summary":"Posicionamento requer validação.","findings":[],"concerns":["Público inferido"],"confidence":0.5,"decision":"needs_review"}'}, 'model': 'reviewer'},
            {'message': {'content': '{"summary":"Consolidação concluída.","findings":["Perfil consistente"],"concerns":[],"confidence":0.85,"decision":"ready","quality_dimensions":{"identity":0.8}}'}, 'model': 'reviewer'},
        ])
        analyzer = CreativeBrandAnalyzer(llm=lambda *_args, **_kwargs: next(responses), model='reviewer')

        reviews = analyzer.review_pack({'brand_summary': 'Uma marca.', 'asset_candidates': ['not sent']})

        self.assertEqual([item['id'] for item in reviews], ['evidencias', 'ampliacao', 'revisor_central'])
        self.assertEqual(reviews[0]['status'], 'ready')
        self.assertEqual(reviews[1]['status'], 'needs_review')
        self.assertEqual(reviews[1]['status'], 'needs_review')
        self.assertEqual(reviews[2]['quality_dimensions']['identity'], .8)

    def test_review_reports_each_provider_call_for_credit_billing(self):
        responses = iter([
            {'message': {'content': '{"summary":"ok","findings":[],"concerns":[],"confidence":0.8,"decision":"ready"}'}, 'model': 'reviewer', 'usage': {'total_tokens': 120}},
            {'message': {'content': '{"summary":"ok","findings":[],"concerns":[],"confidence":0.8,"decision":"ready"}'}, 'model': 'reviewer', 'usage': {'total_tokens': 121}},
            {'message': {'content': '{"summary":"ok","findings":[],"concerns":[],"confidence":0.8,"decision":"ready"}'}, 'model': 'reviewer', 'usage': {'total_tokens': 123}},
        ])
        billed = []
        analyzer = CreativeBrandAnalyzer(llm=lambda *_args, **_kwargs: next(responses), model='reviewer')

        analyzer.review_pack({'brand_summary': 'Uma marca.'}, billing_callback=lambda *event: billed.append(event))

        self.assertEqual([event[0] for event in billed], [
            'parecer_evidencias', 'parecer_ampliacao', 'revisor_central',
        ])
        self.assertEqual([event[1]['usage']['total_tokens'] for event in billed], [120, 121, 123])

    def test_one_review_module_can_be_refreshed_without_running_the_other_two(self):
        billed = []
        analyzer = CreativeBrandAnalyzer(llm=lambda *_args, **_kwargs: {
            'message': {'content': '{"summary":"Fontes conferidas.","findings":["Site oficial"],"concerns":[],"confidence":0.9,"decision":"ready"}'},
            'model': 'reviewer', 'usage': {'total_tokens': 55},
        }, model='reviewer')

        review = analyzer.review_module({'brand_summary': 'Uma marca.'}, 'evidencias',
                                        billing_callback=lambda *event: billed.append(event))

        self.assertEqual(review['id'], 'evidencias')
        self.assertEqual(review['status'], 'ready')
        self.assertEqual([event[0] for event in billed], ['parecer_evidencias'])

    def test_central_reviewer_can_be_refreshed_from_the_two_saved_opinions(self):
        billed = []
        analyzer = CreativeBrandAnalyzer(llm=lambda *_args, **_kwargs: {
            'message': {'content': '{"summary":"Consolidação segura.","findings":["Fontes coerentes"],"concerns":[],"confidence":0.91,"decision":"ready","quality_dimensions":{"sources":0.9},"accepted_fields":["brand_summary"],"blocked_fields":[]}'},
            'model': 'reviewer', 'usage': {'total_tokens': 77},
        }, model='reviewer')

        review = analyzer.review_module(
            {'brand_summary': 'Uma marca.'}, 'revisor_central',
            prior_reviews=[
                {'id': 'evidencias', 'status': 'ready'},
                {'id': 'ampliacao', 'status': 'ready'},
            ],
            billing_callback=lambda *event: billed.append(event),
        )

        self.assertEqual(review['id'], 'revisor_central')
        self.assertEqual(review['status'], 'ready')
        self.assertEqual(review['quality_dimensions']['sources'], .9)
        self.assertEqual(review['accepted_fields'], ['brand_summary'])
        self.assertEqual([event[0] for event in billed], ['revisor_central'])
