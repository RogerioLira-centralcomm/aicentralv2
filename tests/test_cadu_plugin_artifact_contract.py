"""The requested semantic output must survive plugin and source routing."""

import pytest

from aicentralv2.cadu_workspace.agent_v2.artifact_intent import named_artifact_type
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.agent_v2.guardrails import normalize_response


@pytest.mark.parametrize(("message", "artifact_type"), [
    ("Mostre o plano de mídia salvo como artefato editável", "media_plan"),
    ("Compare estes três investimentos em um cenário editável", "scenario"),
    ("Pesquise o tema e salve os achados em uma pesquisa editável", "research"),
    ("Registre esta decisão como nota curta", "note"),
    ("Crie um resumo executivo editável dos resultados", "executive_summary"),
])
def test_named_artifact_routes_to_its_semantic_type(message, artifact_type):
    assert named_artifact_type(message) == artifact_type
    route = route_request(message, has_project=True)
    assert route.artifact_type == artifact_type
    assert route.response_mode == "artifact_first"


def test_research_artifact_chooses_project_or_web_evidence():
    internal = route_request("Crie uma pesquisa editável dos dados deste projeto", has_project=True)
    external = route_request("Pesquise o mercado e crie uma pesquisa editável", has_project=True)
    assert internal.needs_tools == ("workspace.search_project_content",)
    assert external.needs_tools == ("web.search",)


def test_brand_with_website_does_not_become_a_page_artifact():
    route = route_request("Crie a marca Acme, segmento tecnologia, com site https://acme.com.br")
    assert route.artifact_type is None
    assert route.action == "create_brand"


def test_research_patch_keeps_structured_evidence_and_rejects_unsafe_image():
    response = normalize_response({
        "answer": "Pesquisa pronta.",
        "artifact_patch": {
            "title": "Mercado de café", "summary": "Achados documentados.",
            "tables": [{"title": "Canais", "columns": ["Canal", "Valor"],
                        "rows": [["Busca", "R$ 100"]]}],
            "citations": [{"title": "Fonte oficial", "url": "https://example.com/dados", "excerpt": "Dado lido"}],
            "images": [{"url": "javascript:alert(1)", "alt": "inválida"},
                       {"url": "https://example.com/capa.png", "alt": "Capa"}],
        },
    }, {"mode": "artifact_first", "allow_artifact": True, "artifact_type": "research"})

    patch = response.artifact_patch
    assert patch["tables"][0]["rows"] == [["Busca", "R$ 100"]]
    assert patch["citations"][0]["url"] == "https://example.com/dados"
    assert patch["images"] == [{"url": "https://example.com/capa.png", "alt": "Capa", "caption": ""}]
