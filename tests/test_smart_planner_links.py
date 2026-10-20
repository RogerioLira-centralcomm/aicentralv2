from aicentralv2.smart_planner import links
from aicentralv2.smart_planner.share import friendly_token, is_friendly


def test_friendly_token_uses_plan_name_with_hyphens_and_short_suffix():
    token = friendly_token("Educação Financeira CAIXA - Proteja seu Orçamento")
    assert token.startswith("educacao-financeira-caixa-proteja-seu-orcamento-")
    assert is_friendly(token) and len(token.rsplit("-", 1)[1]) == 4
    assert friendly_token("Animale Black Friday", confidential=True).startswith("plano-de-midia-")
    assert not is_friendly("d6F0ge3mTNsx2A")


def test_ensure_friendly_renames_once_and_keeps_old_token_as_alias(monkeypatch):
    saved = {}
    monkeypatch.setattr(links, "update_session", lambda token, fields: saved.update(fields))
    row = {"session_token": "s1", "cliente": "Caixa",
           "dados_detectados": {"public_token": "d6F0ge3mTNsx2A", "folha": {"meta": {"title": "Educação Financeira CAIXA"}, "share": {"public_token": "d6F0ge3mTNsx2A"}}},
           "plan_content": {"share": {"public_token": "d6F0ge3mTNsx2A"}}}
    new = links.ensure_friendly(row)
    assert new.startswith("educacao-financeira-caixa-")
    dados = saved["dados_detectados"]
    assert dados["public_token"] == new and dados["public_token_aliases"] == ["d6F0ge3mTNsx2A"]
    assert dados["folha"]["share"]["public_token"] == new and saved["plan_content"]["share"]["public_token"] == new
    saved.clear()
    assert links.ensure_friendly({"dados_detectados": {"public_token": new}}) == new and not saved


def test_old_link_redirects_to_the_friendly_one(monkeypatch):
    from flask import Flask

    from aicentralv2.smart_planner import routes

    monkeypatch.setattr(links, "ensure_friendly", lambda row: "caixa-plano-abcd")
    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/smart-planner")
    with app.test_request_context("/smart-planner/p/OLD/proposta?paleta=neutra"):
        response = routes._canonical_redirect("OLD", {}, "smart_planner.publico_proposta")
    assert response.status_code == 301
    assert response.location.endswith("/smart-planner/p/caixa-plano-abcd/proposta?paleta=neutra")
