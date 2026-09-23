from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = ROOT / "aicentralv2/templates/campanhas_pi_lista.html"
out_js = ROOT / "aicentralv2/static/js/campanhas-pi-lista.js"

text = template.read_text(encoding="utf-8")
start = text.index('<script src="https://cdn.jsdelivr.net/npm/chart.js')
i = text.index("<script>", start)
end = text.rindex("</script>")
js = text[i + 8 : end].strip()

marker = "const isDiariosView = "
if marker in js:
    line_end = js.index(";", js.index(marker))
    js = js[: js.index(marker)] + js[line_end + 1 :].lstrip()

js = js.replace("'{{ url_for(\"campanhas_pi_lista\") }}'", "LISTA_URL")
js = js.replace("{{ url_for(\"campanhas_pi_lista\") }}", "LISTA_URL")

header = """/* Campanhas PI lista — page logic */
(function () {
  var cfgEl = document.getElementById('campanhas-lista-config');
  var cfg = cfgEl ? JSON.parse(cfgEl.textContent) : {};
  var isDiariosView = Boolean(cfg.isDiariosView);
  var LISTA_URL = cfg.listaUrl || '/campanhas-pi/lista';

"""
footer = """
  window.aplicarFiltros = aplicarFiltros;
  window.fecharSidebar = fecharSidebar;
  window.switchSidebarTab = switchSidebarTab;
  window.abrirModalEditar = abrirModalEditar;
  window.abrirModalDiarios = abrirModalDiarios;
  window.toggleFlagSort = toggleFlagSort;
  window.selecionarTemplate = selecionarTemplate;
  window.enviarEmail = enviarEmail;
  window.editarCampanhaSidebar = editarCampanhaSidebar;
  window.excluirCampanhaSidebar = excluirCampanhaSidebar;
  window.verCampanhasDoPi = verCampanhasDoPi;
  window.toggleSidebarNovoDiario = toggleSidebarNovoDiario;
  window.salvarSidebarDiario = salvarSidebarDiario;
  window.abrirDiariosDoCampanhaModal = abrirDiariosDoCampanhaModal;
  window.toggleNovoDiario = toggleNovoDiario;
  window.salvarDiario = salvarDiario;
  window.confirmarAtualizarDiariosMassa = confirmarAtualizarDiariosMassa;
})();
"""

out_js.write_text(header + js + footer, encoding="utf-8")
print("Wrote", out_js, "lines", len((header + js + footer).splitlines()))
