from unittest import TestCase

from aicentralv2.creative_brand_analysis import CreativeBrandAnalyzer


class WorkspaceBrandReviewAgentsTest(TestCase):
    def test_failed_provider_attempts_remain_visible_after_fallback_exhaustion(self):
        analyzer = CreativeBrandAnalyzer(
            llm=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('indisponível')),
            model='primary-model', fallback_model='fallback-model',
        )

        with self.assertRaises(RuntimeError) as failure:
            analyzer._json_call([{'role': 'user', 'content': 'JSON'}], model='primary-model',
                                max_tokens=100, temperature=0, timeout=1,
                                stage='teste', retries=0)

        self.assertEqual(len(failure.exception.call_trace), 2)
        self.assertEqual([item['model'] for item in failure.exception.call_trace],
                         ['primary-model', 'fallback-model'])

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

    def test_central_reviewer_receives_both_visual_opinions(self):
        calls = []
        responses = iter([
            {'message': {'content': '{"summary":"ok","findings":[],"concerns":[],"confidence":0.8,"decision":"ready"}'}, 'model': 'reviewer'},
            {'message': {'content': '{"summary":"ok","findings":[],"concerns":[],"confidence":0.8,"decision":"ready"}'}, 'model': 'reviewer'},
            {'message': {'content': '{"summary":"comparado","findings":[],"concerns":[],"confidence":0.8,"decision":"ready","accepted_fields":["color_palette"],"blocked_fields":["logo_url"]}'}, 'model': 'reviewer'},
        ])

        def llm(messages, **_kwargs):
            calls.append(messages)
            return next(responses)

        analyzer = CreativeBrandAnalyzer(llm=llm, model='reviewer')
        analyzer.review_pack({'visual_opinions': [
            {'agent': 'primary_visual_analysis', 'color_palette': [{'hex': '#112233'}]},
            {'agent': 'independent_visual_verifier', 'color_palette': [{'hex': '#112233'}], 'blocked_fields': ['logo_url']},
        ]})

        central_payload = calls[-1][1]['content']
        self.assertIn('primary_visual_analysis', central_payload)
        self.assertIn('independent_visual_verifier', central_payload)

    def test_central_provider_failure_uses_deterministic_evidence_fallback(self):
        calls = {'count': 0}

        def llm(*_args, **_kwargs):
            calls['count'] += 1
            if calls['count'] <= 2:
                return {
                    'message': {'content': '{"summary":"ok","findings":[],"concerns":[],"confidence":0.8,"decision":"ready"}'},
                    'model': 'reviewer',
                }
            raise RuntimeError('provider unavailable')

        analyzer = CreativeBrandAnalyzer(llm=llm, model='reviewer')
        reviews = analyzer.review_pack({
            'brand_summary': 'Uma marca comprovada.',
            'target_audience': 'Público comprovado.',
            'products_services': ['Serviço'],
            'sources': ['https://brand.test'],
            'quality_dimensions': {'identity': .8, 'sources': .8},
        })

        central = reviews[-1]
        self.assertEqual(central['id'], 'revisor_central')
        self.assertEqual(central['status'], 'needs_review')
        self.assertEqual(central['confidence'], .35)
        self.assertEqual(central['accepted_fields'], [])
        self.assertIn('consolidação central indisponível', central['blocked_fields'])
