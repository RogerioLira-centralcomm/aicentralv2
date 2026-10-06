from aicentralv2.cadu_public_mcp import usage
from aicentralv2.cadu_workspace.mcp.tools import planner


def test_catalog_projection_never_returns_commercial_values():
    place = {"id": 1, "slug": "aeroporto", "name": "Aeroporto", "city": "Recife", "investment": "R$ 90 mil",
             "gallery": [{"url": "x"}], "extras": {"preco": 10}}
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
