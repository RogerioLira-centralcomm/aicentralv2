from aicentralv2.cadu_planner.docs import markdown_to_safe_html
from aicentralv2.cadu_workspace.agent_v2.guardrails import _clean_editor_html


def test_plan_table_survives_chat_to_document_conversion():
    source = "| Etapa | Verba | Decisão |\n|---|---:|---|\n| Topo | R$ 800 | **Descoberta** |"
    html = markdown_to_safe_html(source)
    assert '<table>' in html
    assert '<th scope="col">Etapa</th>' in html
    assert '<td>R$ 800</td>' in html
    assert '<strong>Descoberta</strong>' in html
    assert '<p>|---|---:|---|</p>' not in html
    assert '<table>' in _clean_editor_html(html)
    assert '<th scope="col">Etapa</th>' in _clean_editor_html(html)
