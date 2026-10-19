"""Página única v4: contexto confirmado/lacunas, uma chamada só e guarda de números."""

import json

from aicentralv2.smart_planner import generator
from aicentralv2.smart_planner.generator import (
    _guard_page_numbers,
    _one_page_payload,
    _one_page_prompt_version,
    _one_page_v4,
    _usable_page,
)
from aicentralv2.smart_planner.skills import load_skill

SNAPSHOT = {
    "snapshot_id": "campaign_1_r1",
    "client": {"name": "Marca Sigilosa", "agency": "Agência X", "confidential": False},
    "campaign": {"name": "Lançamento"},
    "objective": {"id": "vendas", "label": "Vendas"},
    "audiences": ["Jovens 18-24 da capital"],
    "geography": {"praca": "São Paulo"},
    "period": {"raw": "mar a mai 2027"},
    "budget": {"raw": "R$ 300.000"},
    "kpis": ["CTR", "Vendas"],
    "channels": ["youtube", "meta_ads", "ooh"],
    "mix": [
        {"id": "meta_ads", "label": "Meta Ads", "pct": 30, "amount": 90000, "amount_label": "R$ 90.000"},
        {"id": "youtube", "label": "YouTube", "pct": 50, "amount": 150000, "amount_label": "R$ 150.000"},
        {"id": "ooh", "label": "OOH / Painéis", "pct": 20, "amount": 60000, "amount_label": "R$ 60.000"},
    ],
    "pace": {"labels": ["mar/27"], "keys": ["2027-03"], "allocation": {"2027-03": 100000}, "how": "Começa menor."},
    "briefing": "A Marca Sigilosa quer vender o novo tênis para jovens.",
    "market_research": "- 41% dos jovens compram pelo celular (Pesquisa Fictícia, https://exemplo.org/pesquisa, 2026).",
    "sources": [],
}


def test_payload_separates_confirmed_from_gaps_and_ranks_hero():
    payload = _one_page_payload(SNAPSHOT, {}, {"status": "not_available"})
    confirmed = payload["confirmado"]
    assert confirmed["mix_heroi"] == "YouTube"
    assert [item["canal"] for item in confirmed["mix"]] == ["YouTube", "Meta Ads", "OOH / Painéis"]
    ooh = next(item for item in confirmed["mix"] if item["canal_id"] == "ooh")
    assert "investimento" not in ooh and ooh["percentual"] == 20
    assert payload["lacunas"] == []


def test_payload_lists_gaps_without_budget_or_split():
    snap = {**SNAPSHOT, "budget": {"raw": ""}, "kpis": [], "mix": [{"id": "youtube", "label": "YouTube"}]}
    gaps = _one_page_payload(snap, {}, {})["lacunas"]
    assert "KPIs não definido no plano" in gaps
    assert any(item.startswith("verba não informada") for item in gaps)
    assert "divisão do mix entre canais ainda não definida" in gaps


def test_payload_redacts_confidential_advertiser():
    snap = {**SNAPSHOT, "client": {**SNAPSHOT["client"], "confidential": True}}
    dumped = json.dumps(_one_page_payload(snap, {}, {}), ensure_ascii=False)
    assert "Marca Sigilosa" not in dumped


def test_guard_drops_invented_numbers_and_keeps_mix_numbers():
    payload = _one_page_payload(SNAPSHOT, {}, {})
    page = {
        "recommendation": {"summary": "YouTube leva 50% da verba para abrir a conversa. A campanha vai atingir 3.500.000 pessoas."},
        "market_evidence": {"stat": "77%", "source": "Instituto Inventado", "insight": "Jovens decidem rápido."},
    }
    removed = _guard_page_numbers(page, payload)
    assert page["recommendation"]["summary"] == "YouTube leva 50% da verba para abrir a conversa."
    assert page["market_evidence"]["stat"] == ""
    assert page["market_evidence"]["status"] == "omitted"
    assert len(removed) >= 2


def test_guard_keeps_market_stat_with_source_from_context():
    payload = _one_page_payload(SNAPSHOT, {}, {})
    page = {"market_evidence": {
        "stat": "41%", "source": "Pesquisa Fictícia", "source_url": "https://exemplo.org/pesquisa",
        "insight": "41% dos jovens compram pelo celular.",
    }}
    _guard_page_numbers(page, payload)
    assert page["market_evidence"]["stat"] == "41%"
    assert page["market_evidence"]["source_url"] == "https://exemplo.org/pesquisa"


def test_one_page_v4_is_a_single_call_and_derives_core(monkeypatch):
    calls = []
    answer = {
        "nucleo": {"media_objective": "Converter quem já considera a marca.", "risks": ["Criativo único cansar."]},
        "pagina": {
            "challenge": {"title": "Atenção curta", "body": "Jovens trocam de marca rápido."},
            "opportunity": {"title": "Vídeo abre a conversa", "body": "O lançamento pede demonstração."},
            "thesis": {"statement": "O tênis precisa ser visto em uso antes de ser comparado no preço."},
            "recommendation": {
                "summary": "Vídeo apresenta, social converte e OOH lembra na rua.",
                "audience": "Jovens de 18 a 24 anos da capital.",
                "channel_roles": [{"channel": "YouTube", "role": "alcance"}, {"channel": "Meta Ads", "role": "acao"}],
            },
            "creative_expression": {"channel": "YouTube", "headline": "Corre que é novo"},
            "commercial_defense": {"why_this_plan": ["Mostra o produto em uso."]},
        },
    }

    def fake_chat_json(system, user, **kwargs):
        calls.append((system, user))
        return answer

    monkeypatch.setattr(generator, "chat_json", fake_chat_json)
    page, core = _one_page_v4(SNAPSHOT, {}, {"status": "not_available"}, "hash-1")
    assert len(calls) == 1
    assert "planner_one_page_v4" in calls[0][0]
    assert json.loads(calls[0][1].split("CONTEXTO:\n", 1)[1])["confirmado"]["mix_heroi"] == "YouTube"
    assert core["central_thesis"].startswith("O tênis precisa")
    assert core["media_objective"] == "Converter quem já considera a marca."
    assert core["material_hash"] == "hash-1"
    assert page["strategy_core_id"] == core["id"]
    assert page["prompt_version"] == _one_page_prompt_version()
    assert _usable_page({**page, "material_hash": "hash-1"}, "hash-1", core)


def test_engine_switch_falls_back_to_v3(monkeypatch):
    monkeypatch.setenv("SMART_PLANNER_ONE_PAGE_ENGINE", "v3")
    assert generator._one_page_engine() == "v3"
    assert ":" not in _one_page_prompt_version()
    monkeypatch.setenv("SMART_PLANNER_ONE_PAGE_ENGINE", "qualquer")
    assert generator._one_page_engine() == "v4"


def test_v4_prompt_keeps_contract_keys_the_public_page_reads():
    prompt = load_skill("planner_one_page_v4")
    for key in ("challenge", "opportunity", "thesis", "creative_expression", "market_evidence",
                "media_narrative", "commercial_defense", "benefits", "journey", "outputs", "confirmado", "lacunas"):
        assert key in prompt


def test_blank_template_items_are_dropped():
    cleaned = generator._drop_blank_items({"pending_decisions": [""], "outputs": [{"name": "", "description": ""}, {"name": "Leads"}]})
    assert cleaned == {"pending_decisions": [], "outputs": [{"name": "Leads"}]}


def test_guard_keeps_sum_of_mix_shares():
    payload = _one_page_payload(SNAPSHOT, {}, {})
    page = {"commercial_defense": {"why_this_mix": ["YouTube e Meta Ads somam 80% do mix."]}}
    _guard_page_numbers(page, payload)
    assert page["commercial_defense"]["why_this_mix"] == ["YouTube e Meta Ads somam 80% do mix."]


def test_guard_rejects_source_only_named_in_briefing():
    snap = {**SNAPSHOT, "briefing": "Usar dados do IBGE quando possível.", "market_research": ""}
    payload = _one_page_payload(snap, {}, {})
    page = {"market_evidence": {"stat": "IBGE", "source": "IBGE", "insight": "Jovens compram online."}}
    _guard_page_numbers(page, payload)
    assert page["market_evidence"]["status"] == "omitted"
    assert page["market_evidence"]["source"] == ""


def test_repair_maps_channel_alias_to_mix_row():
    page = {
        "recommendation": {"channel_roles": [{"channel": "YouTube"}, {"channel": "Instagram", "function": "Converte."}]},
        "creative_expression": {"channel": "YouTube"},
    }
    generator._repair_page_channels(page, SNAPSHOT)
    roles = page["recommendation"]["channel_roles"]
    assert [role["channel"] for role in roles] == ["YouTube", "Meta Ads"]
    assert roles[1]["function"] == "Converte."


def test_repair_drops_alias_that_duplicates_existing_role():
    page = {
        "recommendation": {"channel_roles": [{"channel": "YouTube"}, {"channel": "Meta Ads"}, {"channel": "Instagram"}]},
        "creative_expression": {"channel": "YouTube"},
    }
    generator._repair_page_channels(page, SNAPSHOT)
    assert [role["channel"] for role in page["recommendation"]["channel_roles"]] == ["YouTube", "Meta Ads"]
