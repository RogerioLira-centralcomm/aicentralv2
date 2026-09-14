from aicentralv2.smart_planner.catalog import resume_action, resume_status, score_label
from aicentralv2.smart_planner.references import reference_block
from aicentralv2.smart_planner.helpers import editor_href, plan_href, session_public_token, session_title, text
from aicentralv2.smart_planner.repository import serialize_list_row


def test_text_ignores_dicts():
    assert text({"canais": []}) == ""
    assert text(["Prime Video", "Serasa"]) == "Prime Video, Serasa"


def test_session_title_does_not_dump_campanha_dict():
    title = session_title(
        {"nome_campanha": "", "cliente": ""},
        {"campanha": {"canais": ["serasa"], "verba": "R$ 80 mil"}, "cliente": "BDMG"},
    )
    assert title == "BDMG"
    assert "{" not in title


def test_session_title_prefers_campaign_name():
    assert session_title(
        {"nome_campanha": "Perfil 252"},
        {"campanha": {"canais": []}, "cliente": "BDMG"},
    ) == "Perfil 252"


def test_plan_href_is_stable():
    assert plan_href("abc", "canvas") == "/smart-planner/abc/canvas"
    assert plan_href("abc", "canvas", "pub") == "/smart-planner/p/pub/editar"
    assert plan_href("abc", "conclusao") == "/smart-planner/abc/conclusao"
    assert plan_href("abc", "canais") == "/smart-planner/abc/revisao"
    assert plan_href("abc", "gerar") == "/smart-planner/abc/revisao"
    assert plan_href("", "canvas") == "/smart-planner/"
    assert plan_href("abc", "missing") == "/smart-planner/abc/briefing"
    assert editor_href("sess", "pubX") == "/smart-planner/p/pubX/editar"
    assert editor_href("sess", "pubX", folha=True) == "/smart-planner/p/pubX/editar?folha=1"
    assert session_public_token({
        "dados_detectados": {"public_token": "from-dados"},
        "plan_content": {"share": {"public_token": "from-share"}},
    }) == "from-share"


def test_history_row_links_to_canvas_when_quadro_exists():
    row = serialize_list_row({
        "id": 9,
        "session_token": "tok-canvas",
        "nome_campanha": "",
        "cliente": "Montana Grill",
        "objetivo": "reconhecimento",
        "budget": "R$ 120 mil",
        "prazo": "outubro",
        "briefing_melhorado": "Briefing",
        "user_name": "Apolo Lira",
        "dados_detectados": {
            "plan_mode": "one_page",
            "agencia": "Casa",
            "brand": {"logo_url": "/static/x.png"},
            "campanha": {"canais": ["prime_video"], "praca": "nacional"},
        },
        "plan_content": {"sections": [{"id": "one_page", "cards": [{"type": "strategy"}]}]},
        "updated_at": None,
    })
    assert row["titulo"] == "Montana Grill"
    assert row["agencia"] == "Casa"
    assert row["executivo"] == "Apolo Lira"
    assert row["logo_url"] == "/static/x.png"
    assert row["resume_step"] == "canvas"
    assert row["href"] == "/smart-planner/tok-canvas/canvas"
    assert row["canvas_href"] == "/smart-planner/tok-canvas/canvas"
    assert row["resume_action"] == resume_action("canvas", "one_page")
    assert row["status_label"] == resume_status("canvas", "one_page")
    assert row["tem_quadro"] is True
    assert row["praca"] == "Nacional"


def test_history_row_continues_wizard_without_quadro():
    row = serialize_list_row({
        "id": 3,
        "session_token": "tok-draft",
        "nome_campanha": "",
        "cliente": "",
        "dados_detectados": {"plan_mode": "completo", "campanha": {}},
        "plan_content": {},
        "briefing_melhorado": "",
        "briefing_compilado": "",
    })
    assert row["titulo"] == "Campanha sem nome"
    assert row["resume_step"] == "briefing"
    assert row["href"] == "/smart-planner/tok-draft/briefing"
    assert row["status_label"] == "Em briefing"
    assert row["agencia"] == ""
    assert row["tem_quadro"] is False


def test_history_row_goes_to_revisao_when_briefing_is_ready():
    row = serialize_list_row({
        "id": 4,
        "session_token": "tok-mix",
        "cliente": "BH Airport",
        "briefing_melhorado": "Estacionamento",
        "dados_detectados": {
            "plan_mode": "one_page",
            "campanha": {"canais": ["g1"], "verba": "R$ 40 mil"},
        },
        "plan_content": {},
    })
    assert row["resume_step"] == "revisao"
    assert row["href"] == "/smart-planner/tok-mix/revisao"
    assert row["canvas_href"] == "/smart-planner/tok-mix/canvas"
    assert row["resume_action"] == "Gerar documentos"
    assert row["status_label"] == "Em revisão"
    assert row["custo"] == ""
    assert row["custo_brl"] == 0


def test_resume_copy_follows_plan_mode():
    assert resume_action("canvas") == "Abrir quadro"
    assert resume_action("canvas", "one_page") == "Abrir folha"
    assert resume_status("canvas", "completo") == "Quadro pronto"
    assert resume_status("canvas", "one_page") == "Folha pronta"


def test_score_label_matches_php_scale():
    assert score_label(42)["titulo"] == "Regular"
    assert score_label(90)["titulo"] == "Excelente"
    assert score_label(0)["tom"] == "baixo"


def test_reference_block_keeps_kind_and_label():
    bloco = reference_block("url", "montana.com.br", "Cardápio e praça.")
    assert "Referência — página: montana.com.br" in bloco
    assert "Cardápio e praça." in bloco
