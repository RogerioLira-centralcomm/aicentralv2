from pathlib import Path

template = Path(__file__).resolve().parents[1] / "aicentralv2/templates/campanhas_pi_lista.html"
text = template.read_text(encoding="utf-8")
marker = '{% block scripts %}'
start = text.index(marker)
chart = text.index('<script src="https://cdn.jsdelivr.net/npm/chart.js', start)
end = text.rindex("</script>") + len("</script>")
new_scripts = """{% block scripts %}
<script src="{{ url_for('static', filename='js/campanhas-ui.js') }}?v=3"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script type="application/json" id="campanhas-lista-config">{{ {'isDiariosView': request.args.get('view') == 'diarios', 'listaUrl': url_for('campanhas_pi_lista')} | tojson }}</script>
<script src="{{ url_for('static', filename='js/campanhas-pi-lista.js') }}?v=1"></script>
{% endblock %}
"""
text = text[:start] + new_scripts
if not text.endswith("\n"):
    text += "\n"
template.write_text(text, encoding="utf-8")
print("Stripped inline script")
