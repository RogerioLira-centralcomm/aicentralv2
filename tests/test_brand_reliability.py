from aicentralv2.brand_reliability import ReliabilityThresholds, canonical_value, evaluate_shadow


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
    result = evaluate_shadow(records, labels, thresholds=ReliabilityThresholds(
        field_processing_rate=0, minimum_labeled_published_facts=1, minimum_labeled_brands=1,
    ))
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


def test_real_snapshot_decisions_are_terminal():
    records = [
        {'brand_id': 1, 'run_id': 'a', 'run_status': 'approved', 'field_name': 'name',
         'status': 'partial', 'confidence': 0, 'evidence_count': 0},
        {'brand_id': 2, 'run_id': 'b', 'run_status': 'insufficient_evidence', 'field_name': 'name',
         'status': 'blocked', 'confidence': 0, 'evidence_count': 0},
    ]
    result = evaluate_shadow(records, [])
    assert result['metrics']['run_completion_rate'] == 1.0


def test_processing_rate_counts_missing_contract_fields():
    records = [{'brand_id': 1, 'run_id': 'a', 'run_status': 'approved', 'field_name': 'name',
                'status': 'verified', 'confidence': .9, 'evidence_count': 1}]
    result = evaluate_shadow(records, [])
    assert result['counts']['expected_records'] == 39
    assert result['metrics']['field_processing_rate'] == 1 / 39


def test_unreviewed_candidate_labels_do_not_count_as_ground_truth():
    records = [{'brand_id': 1, 'field_name': 'name', 'status': 'verified',
                'value': 'Marca', 'confidence': .9, 'evidence_count': 1}]
    labels = [{'brand_id': 1, 'field_name': 'name', 'reviewed': False,
               'expected_status': 'verified', 'expected_value': 'Marca'}]
    result = evaluate_shadow(records, labels)
    assert result['counts']['applicable_labels'] == 0
    assert result['metrics']['golden_field_coverage'] == 0
