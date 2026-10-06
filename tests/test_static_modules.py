import json
import re
from pathlib import Path

from aicentralv2.static_modules import import_map_tag, module_import_map

ROOT = Path(__file__).resolve().parents[1]


def _site(tmp_path):
    js = tmp_path / "js" / "app"
    js.mkdir(parents=True)
    (tmp_path / "js" / "entry.js").write_text("import { a } from './app/a.js?v=2';\nimport {\n  b,\n} from \"./app/b.js\";\nconst c = import('./app/c.js');\n")
    (js / "a.js").write_text("import { b } from './b.js';\nexport const a = b;\n")
    (js / "b.js").write_text("export const b = 1;\n")
    (js / "c.js").write_text("export default 3;\n")
    return tmp_path


def test_import_map_covers_the_whole_relative_import_graph_once(tmp_path):
    mapping = module_import_map(str(_site(tmp_path)), "js/entry.js")
    assert {"/static/js/entry.js", "/static/js/app/a.js", "/static/js/app/b.js", "/static/js/app/c.js"} <= set(mapping)
    # ./a.js?v=2 (query antiga) aponta para o mesmo módulo com hash, sem criar uma segunda instância
    assert mapping["/static/js/app/a.js?v=2"] == mapping["/static/js/app/a.js"]
    assert all(re.search(r"\?v=[0-9a-f]{10}$", url) for url in mapping.values())


def test_changing_a_module_changes_only_its_own_url(tmp_path):
    site = _site(tmp_path)
    before = module_import_map(str(site), "js/entry.js")
    (site / "js" / "app" / "b.js").write_text("export const b = 2;\n")
    after = module_import_map(str(site), "js/entry.js")
    assert after["/static/js/app/b.js"] != before["/static/js/app/b.js"]
    assert after["/static/js/app/c.js"] == before["/static/js/app/c.js"]


def test_tag_is_valid_json_and_cannot_close_the_script(tmp_path):
    tag = str(import_map_tag(str(_site(tmp_path)), "js/entry.js"))
    body = tag.removeprefix('<script type="importmap">').removesuffix("</script>")
    assert "</" not in body
    assert "imports" in json.loads(body)


def test_video_desks_load_the_import_map_before_the_module_script():
    for name in ("cadu_studio/desk.html", "parametros/modelagem_desk.html"):
        html = (ROOT / "aicentralv2" / "templates" / name).read_text()
        assert "module_import_map(mc_page_js)" in html, name
        assert html.index("module_import_map(mc_page_js)") < html.index("static_fingerprint(mc_page_js)"), name
