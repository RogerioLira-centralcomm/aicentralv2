from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = ROOT / "aicentralv2/templates/campanhas_pi_lista.html"
text = template.read_text(encoding="utf-8")

# Remove inline script block (keep scripts block wrapper)
start = text.index('<script src="https://cdn.jsdelivr.net/npm/chart.js')
end = text.rindex("</script>") + len("</script>")
replacement = """<script type="application/json" id="campanhas-lista-config">{{ {'isDiariosView': request.args.get('view') == 'diarios', 'listaUrl': url_for('campanhas_pi_lista')} | tojson }}</script>
<script src="{{ url_for('static', filename='js/campanhas-pi-lista.js') }}?v=1"></script>"""
text = text[:start] + replacement + text[end:]

# Remove inline style block
style_start = text.index("<style>", text.index("{% block styles %}"))
style_end = text.index("</style>", style_start) + len("</style>")
styles_block = """<link rel="stylesheet" href="{{ url_for('static', filename='css/campanhas-ui.css') }}?v=3">
<link rel="stylesheet" href="{{ url_for('static', filename='css/pi-operacao.css') }}?v=4">
<link rel="stylesheet" href="{{ url_for('static', filename='css/campanhas-pi-lista.css') }}?v=1">"""
# replace from first link after block styles through </style>
link_start = text.index('<link rel="stylesheet"', text.index("{% block styles %}"))
text = text[:link_start] + styles_block + text[style_end:]

# bump campanhas-ui.js in scripts if still v=2
text = text.replace("campanhas-ui.js') }}?v=2", "campanhas-ui.js') }}?v=3")

template.write_text(text, encoding="utf-8")
print("Patched template")
