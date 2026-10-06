from aicentralv2.cadu_public_mcp import usage
from aicentralv2.cadu_workspace.mcp.tools import planner


def test_catalog_projection_never_returns_commercial_values():
    place = {"id": 1, "slug": "aeroporto", "name": "Aeroporto", "city": "Recife", "investment": "R$ 90 mil",
             "gallery": [{"url": "x"}], "extras": {"preco": 10}}
    from flask import Flask

    with Flask(__name__).app_context():
        [projected] = planner._project([place], "places")
    assert projected["name"] == "Aeroporto" and projected["city"] == "Recife"
    assert not {"investment", "gallery", "extras", "preco"} & projected.keys()


def test_catalog_covers_every_planner_source_for_agents():
    assert set(planner._CATALOG_FIELDS) == {"canais", "audiencias", "formatos", "interativos", "portais", "places"}
    for fields in planner._CATALOG_FIELDS.values():
        assert not {"investment", "price", "preco", "cpm", "extras"} & set(fields)


def test_planner_reads_are_free():
    for tool in ("planner.search_catalog", "planner.list_plans", "planner.get_brief", "planner.get_media_plan"):
        assert usage.tool_cost(tool) == 0


def test_records_carry_visuals_and_a_ready_markdown_card():
    from flask import Flask

    app = Flask(__name__)
    app.config["PLANNER_URL"] = "https://planner.example"
    audience = {"id": 9, "name": "Executivos", "description": "Alta renda", "audience": "2 mi",
                "category": "Profissional", "platform": "LinkedIn", "image_url": "/static/images/a.png",
                "platform_logo": "/static/images/linkedin.svg"}
    with app.app_context():
        [item] = planner._project([audience], "audiencias")
    assert item["image_url"] == "https://planner.example/static/images/a.png"
    assert item["cadu_url"] == "https://planner.example/audiencias/9"
    assert item["card"].startswith("![Executivos](https://planner.example/static/images/a.png)")
    assert "[Abrir no Cadu](https://planner.example/audiencias/9)" in item["card"]


def test_item_profile_strips_commercial_keys_caps_lists_and_absolutizes_media():
    from flask import Flask

    app = Flask(__name__)
    app.config["PLANNER_URL"] = "https://planner.example"
    profile = {"name": "Canal", "investimento_minimo": 5000, "lp_data": {"x": 1}, "logo_url": "/static/l.svg",
               "gallery": [f"/static/g{i}.png" for i in range(10)],
               "ad_examples": [{"title": "a", "cpm_venda": 9, "image_url": "/static/a.png"}]}
    with app.app_context():
        clean = planner._clean(profile)
    assert not {"investimento_minimo", "lp_data"} & clean.keys()
    assert clean["logo_url"] == "https://planner.example/static/l.svg"
    assert len(clean["gallery"]) == planner._LIST_LIMIT and clean["gallery"][0].startswith("https://planner.example/")
    assert "cpm_venda" not in clean["ad_examples"][0]
    assert clean["ad_examples"][0]["image_url"] == "https://planner.example/static/a.png"


def test_item_tool_is_free_and_covers_the_same_kinds_as_search():
    assert usage.tool_cost("planner.get_catalog_item") == 0
