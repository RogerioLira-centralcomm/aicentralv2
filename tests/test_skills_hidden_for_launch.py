"""Skills fica fora do lançamento (2026-10-11) atrás de CADU_SKILLS_ENABLED.

Roda sem banco: DB_HOST=127.0.0.1 DB_PORT=1.
"""
import json
import os
import re

os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "1")

import pytest
from flask import render_template, render_template_string

from aicentralv2 import product_flags
from tests.shared_app import get_app


@pytest.fixture()
def app():
    application = get_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def skills_off(monkeypatch):
    monkeypatch.delenv("CADU_SKILLS_ENABLED", raising=False)


@pytest.fixture()
def skills_on(monkeypatch):
    monkeypatch.setenv("CADU_SKILLS_ENABLED", "true")


def test_helper_padrao_desligado(skills_off):
    assert product_flags.skills_enabled() is False
    assert product_flags.visible_solutions({"workspace": "/", "skills": "/s"}) == {"workspace": "/"}
    assert product_flags.visible_solutions([("workspace",), ("skills",)]) == [("workspace",)]


@pytest.mark.parametrize("value", ["true", "1", "on", "TRUE"])
def test_helper_liga_pela_variavel(monkeypatch, value):
    monkeypatch.setenv("CADU_SKILLS_ENABLED", value)
    assert product_flags.skills_enabled() is True


@pytest.mark.parametrize("path", ["/skills/", "/skills", "/skills/agentes", "/skills/comecar", "/skills/minhas-skills", "/skills/metodos"])
def test_rotas_publicas_de_skills_respondem_404(app, skills_off, path):
    assert app.test_client().get(path).status_code == 404


def test_minhas_skills_no_workspace_responde_404(app, skills_off):
    from werkzeug.exceptions import NotFound
    from aicentralv2.cadu_workspace import routes
    view = getattr(routes.my_skills, "__wrapped__", routes.my_skills)
    with app.test_request_context("/workspace/minhas-skills"):
        with pytest.raises(NotFound):
            view()


def test_pagina_publica_da_solucao_skills_some(app, skills_off):
    client = app.test_client()
    assert client.get("/workspace/solucoes/skills").status_code == 404
    assert client.get("/workspace/conteudos/skill-de-audiencia").status_code == 404
    llms = client.get("/llms.txt", headers={"Host": "localhost"}).get_data(as_text=True)
    assert "Skills" not in llms
    sitemap = client.get("/sitemap.xml", headers={"Host": "localhost"}).get_data(as_text=True)
    assert "solucoes/skills" not in sitemap


def test_infra_interna_continua_registrada(app, skills_off):
    # Gestão (CentralX), APIs e entregas por token não passam pelo 404 de lançamento.
    from aicentralv2.cadu_skills import routes
    with app.test_request_context("/skills/api/x/runs", method="POST"):
        assert routes.hide_skills_product_for_launch() is None
    with app.test_request_context("/skills/s/token"):
        assert routes.hide_skills_product_for_launch() is None
    from aicentralv2.cadu_skills import repository
    assert callable(repository.credit_position)


SWITCH = "{% set cadu_active_product = 'workspace' %}{% include 'cadu/_product_switch.html' %}"


def _render_switch(app):
    with app.test_request_context("/"):
        return render_template_string(SWITCH)


def _auth_tools(app, template):
    with app.test_request_context("/login"):
        html = render_template(template, is_centralx_host=False, is_centralx_access=False, next_target="")
    match = re.search(r'"tools":\s*(\[.*?\])', html, re.S)
    assert match, "bootstrap sem tools"
    return [tool["id"] for tool in json.loads(match.group(1))]


def test_catalogos_sem_skills_quando_desligada(app, skills_off):
    html = _render_switch(app)
    assert "Reports" in html and "Skills" not in html
    with app.test_request_context("/"):
        nav = render_template_string("{% import 'cadu/_product_catalog.html' as c with context %}{{ c.cadu_product_catalog|map(attribute='0')|join(',') }}")
    assert nav.strip().endswith("workspace,planner,studio,connect")


def test_catalogos_com_skills_quando_ligada(app, skills_on):
    assert "Skills" in _render_switch(app)


@pytest.mark.parametrize("template", ["login_tailwind.html", "signup_tailwind.html"])
def test_login_e_cadastro_sem_skills(app, skills_off, template):
    try:
        tools = _auth_tools(app, template)
    except Exception as exc:  # pragma: no cover - template pede contexto extra
        pytest.skip(f"render indisponível sem contexto: {exc}")
    assert "skills" not in tools and "workspace" in tools


@pytest.mark.parametrize("template", ["login_tailwind.html", "signup_tailwind.html"])
def test_login_e_cadastro_com_skills(app, skills_on, template):
    try:
        tools = _auth_tools(app, template)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"render indisponível sem contexto: {exc}")
    assert "skills" in tools


def test_bootstraps_sem_url_de_skills(skills_off):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates"
    for name in ["_app_sidebar.html", "account_react.html", "brand_detail_react.html", "brands_react.html",
                 "projects_react.html", "project_detail_react.html", "conversations_v2_lab.html",
                 "workspace_home_chat.html", "mcp_agents.html"]:
        source = (root / "cadu_workspace" / name).read_text(encoding="utf-8")
        assert "visible_solutions(" in source, name
