from aicentralv2.brand_reliability import canonical_value, evaluate_shadow


def test_canonical_value_normalizes_text_and_unordered_lists():
    assert canonical_value([' CEMIG ', 'Energia']) == canonical_value(['energia', 'cemíg'])


def test_shadow_promotes_only_when_every_gate_passes():
    records = [{
        'brand_id': 29, 'snapshot_id': 1, 'run_status': 'published',
        'field_name': 'name', 'field_category': 'identity', 'value': 'Cemig',
        'status': 'verified', 'confidence': 0.97, 'evidence_count': 2,
    }]
    labels = [{
        'brand_id': 29, 'field_name': 'name', 'field_category': 'identity',
        'expected_status': 'verified', 'expected_value': 'CEMIG',
    }]
    result = evaluate_shadow(records, labels)
    assert result['decision'] == 'promote'
    assert result['metrics']['published_fact_precision'] == 1.0


def test_shadow_holds_on_wrong_value_missing_evidence_and_empty_confidence():
    records = [{
        'brand_id': 29, 'snapshot_id': 1, 'run_status': 'running',
        'field_name': 'contacts', 'field_category': 'presence', 'value': ['12345678901'],
        'status': 'verified', 'confidence': None, 'evidence_count': 0,
    }]
    labels = [{
        'brand_id': 29, 'field_name': 'contacts', 'field_category': 'presence',
        'expected_status': 'invalid', 'expected_value': [],
    }]
    result = evaluate_shadow(records, labels)
    assert result['decision'] == 'hold'
    assert result['counts']['unsafe_publications'] == 1
    assert 'published_fact_precision_below_target' in result['failures']
    assert 'empty_confidence_rate_above_target' in result['failures']


def test_unlabeled_publication_cannot_fake_precision():
    records = [{
        'brand_id': 1, 'snapshot_id': 1, 'run_status': 'partial', 'field_name': 'name',
        'value': 'Marca', 'status': 'verified', 'confidence': 0.9, 'evidence_count': 1,
    }]
    result = evaluate_shadow(records, [])
    assert result['decision'] == 'hold'
    assert 'insufficient_labeled_published_facts' in result['failures']
