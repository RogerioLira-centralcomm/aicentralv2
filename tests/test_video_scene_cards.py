from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "aicentralv2/static/js/mc-cadu-video.js").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "aicentralv2/templates/parametros/_mc_video.html").read_text(encoding="utf-8")


def test_roteiro_completo_e_somente_leitura_e_cartoes_existem():
    assert 'id="mcVideoSceneCards"' in TEMPLATE
    assert 'id="mcVideoScript" rows="9" readonly' in TEMPLATE


def test_cotacao_nao_relê_o_texto_livre_por_posicao():
    plan_body = JS.split("function planBody()", 1)[1].split("\n}\n", 1)[0]
    assert "parseScript" not in plan_body
    assert "mcVideoScript" not in plan_body


def test_trocar_imagem_mantem_o_roteiro_da_cena():
    replace = JS.split("function replaceScene(", 1)[1].split("\n}\n", 1)[0]
    assert "beat.id = item.id" in replace


def test_modo_trocar_nao_prende_a_biblioteca_quando_a_cena_some():
    click = JS.split("function onLibraryClick(", 1)[1].split("\n}\n", 1)[0]
    assert "!state.scenes.some((row) => row.id === state.replaceSceneId)" in click


def test_trocar_a_unica_cena_adota_a_proporcao_da_nova_imagem():
    replace = JS.split("function replaceScene(", 1)[1].split("\n}\n", 1)[0]
    assert "adoptSelectedAspect(item)" in replace
