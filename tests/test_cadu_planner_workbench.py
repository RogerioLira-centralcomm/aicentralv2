import pytest
from werkzeug.exceptions import BadRequest, Conflict

from aicentralv2.cadu_planner import workbench


def plan(**overrides):
    base = {'id': 'p1', 'title': 'Plano', 'objective': None, 'briefing': {}, 'items': [], 'allocations': [],
            'revision': 3, 'workbench': {}}
    base.update(overrides)
    return base


def proposal(section='pracas', **overrides):
    base = {'id': 'x1', 'section': section, 'status': 'pending', 'base_revision': 3,
            'payload': {'geography': 'BH', 'priority': ['BH', 'SP']}}
    base.update(overrides)
    return base


def test_overview_orders_sections_and_points_to_next_open():
    result = workbench.overview(plan(objective='awareness', briefing={'kpis': 'alcance'}))
    assert [item['key'] for item in result['sections']] == list(workbench.SECTION_KEYS)
    assert result['sections'][1]['state'] == 'editada'
    assert result['next'] == 'briefing'
    assert result['revision'] == 3


def test_pending_proposal_shows_as_proposta():
    result = workbench.overview(plan(), {'pracas': 'x1'})
    pracas = next(item for item in result['sections'] if item['key'] == 'pracas')
    assert pracas['state'] == 'proposta' and pracas['proposal_id'] == 'x1'


def test_accept_applies_payload_and_marks_accepted():
    new_workbench, changes = workbench.apply_proposal(plan(), proposal(), 'accepted', expected_revision=3)
    assert changes == {'pracas': {'geography': 'BH', 'priority': ['BH', 'SP']}}
    assert new_workbench['sections']['pracas']['state'] == 'aceita'


def test_partial_applies_only_chosen_fields_and_marks_edited():
    new_workbench, changes = workbench.apply_proposal(plan(), proposal(), 'partial', ['geography'])
    assert changes == {'pracas': {'geography': 'BH'}}
    assert new_workbench['sections']['pracas']['state'] == 'editada'
    with pytest.raises(BadRequest):
        workbench.apply_proposal(plan(), proposal(), 'partial', [])
    with pytest.raises(BadRequest):
        workbench.apply_proposal(plan(), proposal(), 'partial', ['budget'])


def test_reject_changes_nothing():
    new_workbench, changes = workbench.apply_proposal(plan(), proposal(), 'rejected')
    assert changes == {}
    assert new_workbench['sections']['pracas']['state'] == 'vazia'


def test_user_edited_section_stays_with_the_user():
    edited = plan(workbench=workbench.mark_edited(plan(), 'pracas'))
    new_workbench, _changes = workbench.apply_proposal(edited, proposal(), 'accepted')
    assert new_workbench['sections']['pracas']['state'] == 'editada'


def test_locked_section_never_receives_proposals():
    locked = plan(workbench=workbench.set_locked(plan(), 'pracas', True))
    assert not workbench.can_propose(locked, 'pracas')
    with pytest.raises(Conflict):
        workbench.apply_proposal(locked, proposal(), 'accepted')
    assert workbench.mark_edited(locked, 'pracas')['sections']['pracas']['state'] == 'travada'
    unlocked = workbench.set_locked(locked, 'pracas', False)
    assert unlocked['sections']['pracas']['state'] == 'vazia'


def test_stale_revision_and_decided_proposals_conflict():
    with pytest.raises(Conflict):
        workbench.apply_proposal(plan(), proposal(), 'accepted', expected_revision=2)
    with pytest.raises(Conflict):
        workbench.apply_proposal(plan(), proposal(base_revision=1), 'accepted')
    with pytest.raises(Conflict):
        workbench.apply_proposal(plan(), proposal(status='accepted'), 'accepted')


def test_unknown_section_or_decision_is_rejected():
    with pytest.raises(BadRequest):
        workbench.apply_proposal(plan(), proposal(section='mágica'), 'accepted')
    with pytest.raises(BadRequest):
        workbench.apply_proposal(plan(), proposal(), 'talvez')
