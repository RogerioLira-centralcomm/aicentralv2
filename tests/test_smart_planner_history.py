from aicentralv2.smart_planner.catalog import resume_action
from aicentralv2.smart_planner.helpers import plan_href, session_title, text
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
    assert plan_href("", "canvas") == "/smart-planner/"
    assert plan_href("abc", "missing") == "/smart-planner/abc/briefing"


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
        "dados_detectados": {
            "plan_mode": "one_page",
            "campanha": {"canais": ["prime_video"], "praca": "nacional"},
        },
        "plan_content": {"sections": [{"id": "one_page", "cards": [{"type": "strategy"}]}]},
        "updated_at": None,
    })
    assert row["titulo"] == "Montana Grill"
    assert row["resume_step"] == "canvas"
    assert row["href"] == "/smart-planner/tok-canvas/canvas"
    assert row["canvas_href"] == "/smart-planner/tok-canvas/canvas"
    assert row["resume_action"] == resume_action("canvas")
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
    assert row["tem_quadro"] is False


def test_history_row_goes_to_gerar_when_mix_is_ready():
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
    assert row["resume_step"] == "gerar"
    assert row["href"] == "/smart-planner/tok-mix/gerar"
    assert row["canvas_href"] == "/smart-planner/tok-mix/canvas"
    assert row["custo"] == ""
    assert row["custo_brl"] == 0
