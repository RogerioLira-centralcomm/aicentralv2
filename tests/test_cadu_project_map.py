import json
from types import SimpleNamespace

from aicentralv2.cadu_workspace.agent_v2 import service
from aicentralv2.cadu_workspace.agent_v2.guardrails import normalize_response
from aicentralv2.cadu_workspace.agent_v2.router import route_request


def build_map(resources, relations=None, project_ref="ci:42"):
    run = {
        "context": SimpleNamespace(project_ref=project_ref),
        "resolved_context": SimpleNamespace(values={
            "projects.list_resources": {
                "resources": resources,
                "relations": relations or [],
                "summary": {"total": len(resources)},
            }
        }),
    }
    return service._project_map_content(run)


def resource(index, kind="file", **values):
    return {
        "id": f"resource-{index}",
        "title": f"Arquivo {index}",
        "source_system": "workspace",
        "source_id": f"file:{index}",
        "resource_type": kind,
        "mime_type": "application/pdf",
        "category": "reference",
        "status": "active",
        "version": 1,
        **values,
    }


def test_project_map_packs_rows_using_the_tallest_group():
    resources = [resource(index) for index in range(8)]
    resources += [resource(100, "artifact", source_system="planner_docs", source_id="doc-1")]
    resources += [resource(200, "report"), resource(300, "image")]

    content = build_map(resources)
    groups = {group["id"]: group for group in content["groups"]}

    assert groups["results"]["y"] >= (
        groups["context"]["y"] + groups["context"]["height"] + 48
    )
    assert groups["creative"]["y"] == groups["results"]["y"]


def test_project_map_exposes_only_real_file_actions():
    content = build_map([
        resource(1),
        resource(2, "artifact", source_system="planner_docs", source_id="doc-2"),
        resource(3, "link", locator="http://insecure.example.test"),
        resource(4, "link", locator="https://docs.google.com/document/d/example"),
    ])
    by_source = {item["source_id"]: item for item in content["resources"]}

    assert by_source["file:1"]["download_url"] == "/workspace/app/projetos/42/fontes/1/download"
    assert by_source["file:1"]["editable_copy_url"].endswith("/editable-copy")
    assert by_source["file:1"]["editor_url"] == ""
    assert by_source["doc-2"]["editor_url"] == "/workspace/docs/doc-2"
    assert by_source["file:3"]["url"] == ""
    assert by_source["file:4"]["url"].startswith("https://")


def test_project_map_recognizes_google_workspace_links():
    content = build_map([
        resource(1, "link", locator="https://docs.google.com/spreadsheets/d/sheet", metadata={}),
        resource(2, "link", locator="https://drive.google.com/file/d/file", metadata={}),
    ])

    assert content["resources"][0]["provider"] == "Google Sheets"
    assert content["resources"][1]["provider"] == "Google Drive"


def test_project_map_payload_is_bounded_and_reports_truncation():
    long_value = "x" * 3000
    resources = [resource(
        index,
        title=long_value,
        source_system=long_value,
        source_id=long_value,
        mime_type=long_value,
        category=long_value,
        status=long_value,
        locator="https://example.test/" + long_value,
    ) for index in range(service.PROJECT_MAP_MAX_RESOURCES + 30)]

    content = build_map(resources)

    assert content["truncated"] is True
    assert content["total_resources"] == len(resources)
    assert content["visible_resources"] == service.PROJECT_MAP_MAX_RESOURCES
    assert len(json.dumps(content, ensure_ascii=False).encode("utf-8")) < 256_000


def test_html_request_creates_an_isolated_preview_artifact():
    route = route_request("Crie uma landing page HTML para esta campanha", has_project=True)

    assert route.action == "create_html"
    assert route.artifact_type == "html"
    assert route.response_mode == "artifact_first"


def test_html_patch_is_bounded_without_losing_its_runtime_parts():
    raw = json.dumps({
        "answer": "Página criada.",
        "artifact_patch": {
            "title": "Landing page",
            "html": "<main>Reserva</main>",
            "css": "main { color: teal; }",
            "js": "document.body.dataset.ready = 'true'",
        },
    })

    response = normalize_response(raw, {"max_questions": 1, "max_next_steps": 2, "max_output_tokens": 1200})

    assert response.artifact_patch["html"] == "<main>Reserva</main>"
    assert response.artifact_patch["css"] == "main { color: teal; }"
    assert response.artifact_patch["js"].startswith("document.body")
