from aicentralv2.cadu_planner import plans


def test_objective_change_marks_the_objective_section():
    plan = {'briefing': {'kpis': 'VTR'}, 'objective': 'awareness', 'advertiser_name': 'Nike', 'campaign_name': None}
    briefing = {'kpis': 'VTR'}
    assert plans._edited_sections(plan, briefing, {'objective': 'consideracao', 'advertiser_name': 'Nike'}) == ['objetivo']
    # Sem a chave no payload, o objetivo salvo não conta como edição.
    assert plans._edited_sections(plan, briefing, {'advertiser_name': 'Nike'}) == []
