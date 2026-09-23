from io import BytesIO
from unittest import TestCase

from werkzeug.datastructures import FileStorage

from aicentralv2.creative_brand_analysis import (
    CreativeBrandAnalyzer,
    _confidence_from_provenance,
    _deterministic_central_review,
    _field_provenance,
    _image_parts,
    _public_contact_records,
    _upload_manifest,
    _validated_public_contacts,
)


class WorkspaceBrandReviewAgentsTest(TestCase):
    def test_missing_provider_confidence_is_derived_from_sourced_provenance(self):
        analysis = {
            'brand_summary': 'Marca comprovada.',
            'target_audience': 'Público comprovado.',
            'color_palette': [{'hex': '#123456'}],
            'sources': ['https://brand.test', 'https://brand.test/about'],
        }
        provenance = _field_provenance({
            'brand_summary': {
                'source_urls': ['https://brand.test/about'],
                'evidence_status': 'verified',
            },
            'target_audience': {
                'source_urls': ['https://brand.test'],
                'evidence_status': 'verified',
            },
            'color_palette': {
                'source_urls': ['https://brand.test'],
                'evidence_status': 'partial',
            },
        }, {}, analysis)

        confidence = _confidence_from_provenance(provenance, analysis)

        self.assertGreaterEqual(confidence['identity'], .85)
        self.assertGreaterEqual(confidence['audience'], .85)
        self.assertGreater(confidence['visual'], 0)
        self.assertLess(confidence['visual'], .85)

    def test_invalid_optional_image_does_not_abort_valid_images(self):
        invalid = FileStorage(stream=BytesIO(b'not an image'), filename='notes.txt', content_type='text/plain')
        valid = FileStorage(stream=BytesIO(b'png bytes'), filename='logo.png', content_type='image/png')

        parts = _image_parts([invalid, valid])
        manifest = _upload_manifest([invalid, valid])

        self.assertEqual(len(parts), 1)
        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]['filename'], 'logo.png')
        self.assertEqual(manifest[0]['image_index'], 0)

    def test_contact_extraction_rejects_unformatted_numeric_identifiers(self):
        contacts, _addresses = _public_contact_records([{
            'url': 'https://brand.test/atendimento',
            'content': 'Central de atendimento 4095675861. Telefone (31) 3219-8000.',
        }])

        self.assertEqual([item['value'] for item in contacts], ['(31) 3219-8000'])

    def test_final_contact_gate_rejects_truncated_toll_free_number(self):
        records = [
            {'type': 'phone', 'label': 'Central de atendimento', 'value': '0800 2121',
             'source_url': 'https://example.com/contato', 'excerpt': 'Central de atendimento 0800 2121 211'},
            {'type': 'phone', 'label': 'Central de atendimento', 'value': '0800 2121 211',
             'source_url': 'https://example.com/contato', 'excerpt': 'Central de atendimento 0800 2121 211'},
        ]

        self.assertEqual([item['value'] for item in _validated_public_contacts(records)], ['0800 2121 211'])

    def test_final_contact_gate_keeps_traceable_short_service_code(self):
        records = [{
            'type': 'phone', 'label': 'Fale com a Cemig', 'value': '116',
            'source_url': 'https://www.cemig.com.br/atendimento', 'excerpt': 'FALE COM A CEMIG 116',
        }]

        self.assertEqual(_validated_public_contacts(records)[0]['value'], '116')

    def test_final_contact_gate_accepts_brazilian_number_with_country_code(self):
        records = [{
            'type': 'phone', 'label': 'WhatsApp', 'value': '+55 (31) 99876-5432',
            'source_url': 'https://example.com/contato',
            'excerpt': 'Fale pelo WhatsApp +55 (31) 99876-5432',
        }]

        self.assertEqual(_validated_public_contacts(records)[0]['value'], '+55 (31) 99876-5432')

    def test_deterministic_central_fallback_preserves_only_consensus(self):
        common = ['brand_summary', 'target_audience', 'products_services']
        result = _deterministic_central_review([
            {'status': 'ready', 'confidence': .82, 'accepted_fields': [*common, 'proof_points'], 'blocked_fields': []},
            {'status': 'ready', 'confidence': .88, 'accepted_fields': [*common, 'differentiators'], 'blocked_fields': []},
        ], {'quality_dimensions': {'identity': .9}})

        self.assertEqual(result['decision'], 'ready')
        self.assertEqual(result['confidence'], .85)
        self.assertEqual(result['accepted_fields'], sorted(common))
        self.assertNotIn('consolidação central indisponível', result['blocked_fields'])

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
