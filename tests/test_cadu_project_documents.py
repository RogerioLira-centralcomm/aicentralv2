from aicentralv2.cadu_planner.docs import markdown_to_safe_html


def test_chat_plan_markdown_is_converted_without_preserving_html():
    html = markdown_to_safe_html('# Plano\n\n- Alcance\n- **Conversão**\n\n<script>alert(1)</script>')
    assert '<h2>Plano</h2>' in html
    assert '<ul><li>Alcance</li><li><strong>Conversão</strong></li></ul>' in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '<script>' not in html
