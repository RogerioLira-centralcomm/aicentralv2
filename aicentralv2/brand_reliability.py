"""Deterministic quality gates for brand-analysis shadow runs.

This module deliberately has no Flask or database dependency so the exact same
rules can be used by tests, offline calibration and the production dashboard.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
import json
import re
import unicodedata
from typing import Any, Iterable


TERMINAL_RUN_STATES = frozenset({'published', 'partial', 'blocked', 'failed_terminal'})
PROCESSED_FIELD_STATES = frozenset({
    'verified', 'probable', 'partial', 'conflicting', 'not_found',
    'not_applicable', 'invalid', 'blocked',
})
PUBLISHABLE_FIELD_STATES = frozenset({'verified'})


def _canonical_scalar(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'\s+', ' ', text).strip().casefold()


def canonical_value(value: Any) -> Any:
    """Normalize values for evaluation without hiding semantic differences."""
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple, set)):
        normalized = [canonical_value(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return str(Decimal(str(value)).normalize())
    if value is None or isinstance(value, bool):
        return value
    return _canonical_scalar(value)


def values_match(actual: Any, expected: Any) -> bool:
    return canonical_value(actual) == canonical_value(expected)


@dataclass(frozen=True)
class ReliabilityThresholds:
    run_completion_rate: float = 0.99
    field_processing_rate: float = 1.0
    published_fact_precision: float = 0.99
    published_provenance_rate: float = 1.0
    unsafe_publication_rate: float = 0.0
    empty_confidence_rate: float = 0.0
    minimum_labeled_published_facts: int = 1


def evaluate_shadow(records: Iterable[dict], labels: Iterable[dict], *,
                    thresholds: ReliabilityThresholds | None = None) -> dict:
    """Compare per-field snapshot rows with reviewed labels and decide rollout.

    Record identity is ``(brand_id, field_name)``. Labels may mark a field as
    non-applicable and may omit ``expected_value`` when only state is reviewed.
    """
    thresholds = thresholds or ReliabilityThresholds()
    records = [dict(item) for item in records]
    labels = [dict(item) for item in labels]
    by_key = {(str(item.get('brand_id')), str(item.get('field_name'))): item for item in records}
    label_by_key = {(str(item.get('brand_id')), str(item.get('field_name'))): item for item in labels}

    run_states: dict[str, str] = {}
    state_counts = Counter()
    empty_confidence = 0
    unsafe_publications = 0
    published_with_provenance = 0
    published = 0
    processed = 0
    applicable = 0
    labeled_published = 0
    correct_published = 0
    differences = []
    category_stats = defaultdict(lambda: Counter(total=0, matched=0, published=0, correct=0))

    for record in records:
        state = str(record.get('status') or '').lower()
        state_counts[state or 'missing'] += 1
        if state in PROCESSED_FIELD_STATES:
            processed += 1
        if record.get('confidence') is None:
            empty_confidence += 1
        run_id = str(record.get('run_id') or record.get('snapshot_id') or record.get('brand_id'))
        run_states[run_id] = str(record.get('run_status') or record.get('decision') or 'partial').lower()
        if state in PUBLISHABLE_FIELD_STATES:
            published += 1
            evidence_count = int(record.get('evidence_count') or 0)
            if evidence_count > 0:
                published_with_provenance += 1
            if float(record.get('confidence') or 0) < 0.85 or evidence_count <= 0:
                unsafe_publications += 1

    for key, label in label_by_key.items():
        if label.get('applicable', True) is False:
            continue
        applicable += 1
        record = by_key.get(key)
        category = str(label.get('field_category') or (record or {}).get('field_category') or 'unknown')
        stats = category_stats[category]
        stats['total'] += 1
        expected_state = str(label.get('expected_status') or '').lower()
        actual_state = str((record or {}).get('status') or 'missing').lower()
        state_matches = not expected_state or actual_state == expected_state
        has_expected_value = 'expected_value' in label
        value_matches = not has_expected_value or values_match((record or {}).get('value'), label.get('expected_value'))
        if state_matches and value_matches:
            stats['matched'] += 1
        else:
            differences.append({
                'brand_id': key[0], 'field_name': key[1], 'category': category,
                'expected_status': expected_state or None, 'actual_status': actual_state,
                'expected_value': label.get('expected_value') if has_expected_value else None,
                'actual_value': (record or {}).get('value'),
            })
        if actual_state in PUBLISHABLE_FIELD_STATES:
            stats['published'] += 1
            labeled_published += 1
            if state_matches and value_matches:
                stats['correct'] += 1
                correct_published += 1

    total_runs = len(run_states)
    completed_runs = sum(state in TERMINAL_RUN_STATES for state in run_states.values())
    total_records = len(records)
    metrics = {
        'run_completion_rate': completed_runs / total_runs if total_runs else 0.0,
        'field_processing_rate': processed / total_records if total_records else 0.0,
        'published_fact_precision': correct_published / labeled_published if labeled_published else 0.0,
        'published_provenance_rate': published_with_provenance / published if published else 0.0,
        'unsafe_publication_rate': unsafe_publications / published if published else 0.0,
        'empty_confidence_rate': empty_confidence / total_records if total_records else 0.0,
        'golden_field_coverage': len(label_by_key) / total_records if total_records else 0.0,
    }
    failures = []
    for name in ('run_completion_rate', 'field_processing_rate', 'published_fact_precision', 'published_provenance_rate'):
        if metrics[name] < getattr(thresholds, name):
            failures.append(f'{name}_below_target')
    for name in ('unsafe_publication_rate', 'empty_confidence_rate'):
        if metrics[name] > getattr(thresholds, name):
            failures.append(f'{name}_above_target')
    if labeled_published < thresholds.minimum_labeled_published_facts:
        failures.append('insufficient_labeled_published_facts')

    return {
        'decision': 'promote' if not failures else 'hold',
        'failures': failures,
        'metrics': metrics,
        'counts': {
            'runs': total_runs, 'completed_runs': completed_runs, 'records': total_records,
            'applicable_labels': applicable, 'published': published,
            'labeled_published': labeled_published, 'correct_published': correct_published,
            'unsafe_publications': unsafe_publications, 'empty_confidence': empty_confidence,
        },
        'states': dict(sorted(state_counts.items())),
        'categories': {
            name: {**dict(stats), 'agreement': stats['matched'] / stats['total'] if stats['total'] else 0.0}
            for name, stats in sorted(category_stats.items())
        },
        'differences': differences,
    }
