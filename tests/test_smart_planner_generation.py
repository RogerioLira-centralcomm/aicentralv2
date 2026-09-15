from unittest.mock import patch

from aicentralv2.smart_planner.estimates import calculate_estimates, format_estimates_for_prompt
from aicentralv2.smart_planner.canvas import _card_count, _fill_from_groups, _plain_excerpt, empty_plan
from aicentralv2.smart_planner.generator import (
    _as_plan_markdown,
    _material_hash,
    _mix_law,
    _pack,
    _require_llm,
    _stale_generation,
    _usable_core,
    _usable_page,
    _validate_group_markdown,
    _validate_plan_markdown,
    _validate_page,
    start_generation,
)
from aicentralv2.smart_planner.one_page import cards_from_v2
from aicentralv2.smart_planner.progress import finish_progress, mark_step, progress_view, start_progress
from aicentralv2.smart_planner.skills import decorate_step, generation_steps, load_skill
from aicentralv2.smart_planner.snapshot import build_evidence, build_snapshot


def test_generation_steps_split_one_page_and_completo():
    one = generation_steps("one_page")
    full = generation_steps("completo")
    assert [item["id"] for item in one] == [
        "snapshot", "evidence", "core", "estimates", "one_page", "validate", "images", "publish",
    ]
    assert "full_strategy" not in {item["id"] for item in one}
    assert {item["id"] for item in full} >= {"full_strategy", "full_media", "full_execution", "full_defense", "compose"}
    assert decorate_step(one[4])["label"] == "Página única"
    assert decorate_step(one[0])["kind_label"] == "motor"
    assert decorate_step(one[2])["kind_label"] == "skill"


def test_internal_skills_are_versioned_packages():
    truth = load_skill("planner_truth_v1")
    core = load_skill("planner_strategy_core_v1")
    page = load_skill("planner_one_page_v2")
    assert "premissa" in truth.lower()
    assert "strategy core" in core.lower() or "núcleo" in core.lower()
    assert "defesa" in page.lower()
    assert "mix aprovado" in page.lower()
    assert "gestão de mídia" in page.lower()
    assert load_skill("missing_skill") == ""


def test_group_markdown_contract_requires_expected_chapters_and_rejects_fences():
    valid, errors = _validate_group_markdown(
        "planner_full_media_v2",
        "## Estratégia de mídia\nTexto suficiente para o bloco com contexto operacional e critérios de decisão.\n\n## Mix e investimento\nTabela e leitura que explicam a distribuição aprovada, o papel de cada canal e o fechamento da verba.\n\n## Fases do voo\nDetalhe operacional da cadência, dos marcos de otimização e das dependências de aprovação.",
    )
    assert valid is True
    assert errors == []
    valid, errors = _validate_group_markdown("planner_full_media_v2", "## Estratégia de mídia\n```\nrascunho\n```")
    assert valid is False
    assert any("bloco de código" in error for error in errors)


def test_full_document_quality_rejects_insufficient_chapters():
    failed = _validate_plan_markdown("## Capa\nVersão.")
    assert failed["valid"] is False
    assert "capítulos insuficientes" in failed["errors"][0]
    passed = _validate_plan_markdown("\n\n".join(f"## Capítulo {index}\nTexto." for index in range(8)))
    assert passed["valid"] is True


def test_snapshot_freezes_confirmed_fields():
    row = {
        "id": 123,
        "session_token": "tok-abc",
        "cliente": "COPASA",
        "briefing_melhorado": "Divulgar os canais digitais oficiais da COPASA.",
        "objetivo": "trafego",
        "publico_alvo": "Clientes da RMBH",
        "prazo": "outubro a novembro",
        "budget": "R$ 400 mil",
        "analise_ia": {"falta_completar": ["Confirmar CPM"]},
        "dados_detectados": {
            "campanha": {
                "canais": ["ooh", "google_ads"],
                "canais_verba": {"ooh": 200000, "google_ads": 200000},
                "praca": "geolocalizada",
                "praca_detalhe": "BH e RMBH",
                "periodo": "outubro a novembro",
                "verba": "R$ 400 mil",
            },
            "fonte": {"briefing": "Preciso divulgar o app.", "referencias": []},
        },
    }
    snapshot = build_snapshot(row)
    evidence = build_evidence(snapshot)
    assert snapshot["snapshot_id"].startswith("campaign_123_")
    assert snapshot["client"]["name"] == "COPASA"
    assert snapshot["client"]["confidential"] is False
    assert snapshot["client"]["display_name"] == "COPASA"
    assert snapshot["channels"] == ["ooh", "google_ads"]
    assert "calendar" in snapshot
    assert "mix_progress" in snapshot
    assert snapshot["pending_decisions"] == ["Confirmar CPM"]
    assert evidence["snapshot_id"] == snapshot["snapshot_id"]
    assert evidence["user_briefing"] == "Preciso divulgar o app."


def test_estimates_unavailable_without_media_params():
    result = calculate_estimates({"mix": [{"id": "ooh", "label": "OOH", "amount": 100000}]})
    assert result["status"] == "not_available"
    assert "CPM" in format_estimates_for_prompt(result)


def test_estimates_calculate_cpm_scenarios():
    result = calculate_estimates({
        "mix": [{"id": "ooh", "label": "OOH", "amount": 100000}],
        "media_params": {"ooh": {"cpm": 20, "frequency": 4}},
    })
    assert result["status"] == "available"
    channel = result["channels"][0]
    assert channel["status"] == "system_calculated"
    ref = next(item for item in channel["scenarios"] if item["scenario"] == "referencia")
    assert ref["impressions"] == 5_000_000
    assert ref["reach"] == 1_250_000
    assert "5_000_000" not in format_estimates_for_prompt(result)
    assert "5000000" in format_estimates_for_prompt(result).replace(".", "")


def test_cards_from_v2_keep_four_canvas_types():
    cards = cards_from_v2({
        "thesis": {"statement": "A campanha deve partir da necessidade do cliente."},
        "recommendation": {"summary": "Organizar a mídia por serviço oficial."},
        "challenge": {"body": "Parte dos clientes desconhece os canais digitais."},
        "opportunity": {"body": "Conectar cada demanda ao canal oficial."},
        "creative_expression": {
            "headline": "Resolva de onde estiver",
            "supporting_text": "App e site oficiais.",
            "channel": "ooh",
            "surface": "display",
        },
        "result_estimates": {"status": "not_available", "summary": "Informe CPM"},
        "commercial_defense": {
            "why_this_plan": ["Mais útil que uma divulgação genérica."],
            "closing_statement": "O plano merece aprovação.",
        },
        "benefits": {"audience": ["Facilidade"], "brand": ["Modernização"], "operation": ["Autosserviço"]},
    })
    assert [card["type"] for card in cards] == ["strategy", "creative", "market", "defense"]
    assert "necessidade" in cards[0]["body"]
    assert "Informe CPM" in cards[2]["body"]
    assert "aprovação" in cards[3]["body"]


def test_progress_view_lists_skills_for_the_ui():
    store = {}

    def fake_merge(token, payload):
        store.update(payload)

    def fake_get(token):
        return {"dados_detectados": store}

    with patch("aicentralv2.smart_planner.progress.merge_dados", side_effect=fake_merge), patch(
        "aicentralv2.smart_planner.progress.get_by_token", side_effect=fake_get
    ), patch("aicentralv2.smart_planner.progress._engine", return_value="openai"):
        started = start_progress("tok", "one_page")
        assert started["steps"][0]["state"] == "running"
        assert started["engine"] == "openai"
        marked = mark_step("tok", "core", "running")
        assert marked["step"] == "core"
        assert marked["label"] == "Núcleo estratégico"
        assert marked["steps"][0]["state"] == "done"
        finished = finish_progress("tok", "one_page")
        assert finished["status"] == "done"
        assert finished["percent"] == 100
        view = progress_view({"dados_detectados": store})
        assert view["status"] == "done"
        assert view["steps"][2]["skill"] == "planner_strategy_core_v1"


def test_start_generation_reuses_running_job():
    row = {
        "briefing_melhorado": "Briefing da COPASA.",
        "dados_detectados": {"geracao": {"status": "running", "mode": "one_page"}},
    }
    with patch("aicentralv2.smart_planner.generator.get_by_token", return_value=row):
        result = start_generation("tok", "one_page")
    assert result["started"] is True
    assert result["already"] is True
    assert result["redirect"].endswith("/conclusao")


def test_empty_canvas_fills_from_existing_groups():
    plan = empty_plan({"title": "BDMG", "client": "BDMG"}, "completo")
    assert _card_count(plan) == 0
    filled = _fill_from_groups(plan, {
        "strategy_core": {"central_thesis": "Partir dos serviços institucionais já confirmados do BDMG."},
        "planejamento_grupos": {
            "strategy": "Organizar acessos oficiais.",
            "media": "Sem mix aprovado ainda.",
            "execution": "Confirmar canais e verba.",
            "defense": "Aprovar o recorte institucional.",
        },
    })
    assert _card_count(filled) == 6
    strategy = next(section for section in filled["sections"] if section["id"] == "strategy")
    assert "serviços institucionais" in strategy["cards"][0]["body"]


def test_progress_view_idle_without_generation():
    assert progress_view({}) == {"status": "idle", "steps": [], "percent": 0}


def test_reuses_core_and_page_only_when_briefing_matches():
    digest = _material_hash({"briefing_melhorado": "Divulgar canais digitais da COPASA."})
    assert _usable_core({"central_thesis": "Partir da necessidade do cliente.", "material_hash": digest}, digest)
    assert not _usable_core({"central_thesis": "Partir da necessidade do cliente.", "material_hash": "outro"}, digest)
    assert _usable_page({"thesis": {"statement": "A campanha parte do serviço."}, "material_hash": digest}, digest)
    assert not _usable_page(
        {"thesis": {"statement": "A campanha parte do serviço."}, "material_hash": digest, "strategy_core_id": "old"},
        digest,
        {"id": "new"},
    )


def test_material_hash_changes_when_channels_change():
    row = {
        "briefing_melhorado": "Mesmo briefing.",
        "dados_detectados": {"campanha": {"canais": ["ooh"]}},
    }
    other = {
        "briefing_melhorado": "Mesmo briefing.",
        "dados_detectados": {"campanha": {"canais": ["ooh", "google_ads"]}},
    }
    assert _material_hash(row) != _material_hash(other)


def test_validate_page_requires_client_and_rejects_foreign_channel():
    page = {
        "thesis": {"statement": "A campanha do BDMG parte dos canais oficiais."},
        "recommendation": {"summary": "Organizar a jornada institucional.", "channel_roles": [{"channel": "tiktok"}]},
        "result_estimates": {"status": "available"},
    }
    try:
        _validate_page(page, {"client": {"name": "BDMG"}, "channels": ["ooh"]}, {"status": "not_available"})
    except ValueError as exc:
        assert "canais não aprovados" in str(exc)
    else:
        raise AssertionError("deveria rejeitar canal extra")
    ok = {
        "thesis": {"statement": "A campanha do BDMG parte dos canais oficiais."},
        "recommendation": {"summary": "Organizar a jornada institucional.", "channel_roles": [{"channel": "ooh"}]},
        "result_estimates": {"status": "available"},
    }
    _validate_page(ok, {"client": {"name": "BDMG"}, "channels": ["ooh"]}, {"status": "not_available"})
    assert ok["result_estimates"]["status"] == "not_available"


def test_pack_redacts_confidential_advertiser():
    packed = _pack(
        {
            "client": {"name": "COPASA", "confidential": True, "display_name": "Anunciante"},
            "brand": {"name": "COPASA"},
            "briefing": "A COPASA precisa divulgar o app oficial em Minas.",
        },
        {"briefing": "Material da COPASA.", "user_briefing": "Texto da COPASA."},
        {},
    )
    assert "COPASA" not in packed
    assert "Anunciante" in packed


def test_material_hash_changes_when_confidential_toggles():
    row = {
        "briefing_melhorado": "Divulgar o app.",
        "dados_detectados": {"campanha": {"canais": ["ooh"]}, "anunciante_confidencial": False},
    }
    other = {
        "briefing_melhorado": "Divulgar o app.",
        "dados_detectados": {"campanha": {"canais": ["ooh"]}, "anunciante_confidencial": True},
    }
    assert _material_hash(row) != _material_hash(other)


def test_validate_page_allows_thesis_without_advertiser_name():
    page = {
        "thesis": {"statement": "Partir dos canais oficiais e levar cada demanda ao autosserviço."},
        "recommendation": {"summary": "OOH e portais no recorte de Minas.", "channel_roles": [{"channel": "ooh"}]},
        "result_estimates": {"status": "not_available"},
    }
    _validate_page(page, {"client": {"name": "COPASA"}, "channels": ["ooh"]}, {"status": "not_available"})


def test_validate_page_rejects_meta_thesis_and_confidential_leak():
    meta = {
        "thesis": {"statement": "Este planejamento recomenda OOH e portais para a campanha."},
        "recommendation": {"summary": "Organizar a jornada oficial.", "channel_roles": [{"channel": "ooh"}]},
        "result_estimates": {"status": "not_available"},
    }
    try:
        _validate_page(meta, {"client": {"name": "COPASA"}, "channels": ["ooh"]}, {"status": "not_available"})
    except ValueError as exc:
        assert "planejamento" in str(exc)
    else:
        raise AssertionError("deveria rejeitar tese sobre o planejamento")
    leak = {
        "thesis": {"statement": "A COPASA precisa levar cada demanda ao canal oficial."},
        "recommendation": {"summary": "OOH no recorte mineiro.", "channel_roles": [{"channel": "ooh"}]},
        "result_estimates": {"status": "not_available"},
    }
    try:
        _validate_page(
            leak,
            {"client": {"name": "COPASA", "confidential": True}, "channels": ["ooh"]},
            {"status": "not_available"},
        )
    except ValueError as exc:
        assert "confidencial" in str(exc)
    else:
        raise AssertionError("deveria rejeitar vazamento do nome")


def test_defense_json_becomes_markdown():
    body = _as_plan_markdown('{"why_this_plan": ["Porque parte do BDMG Digital."], "approval_argument": "Aprovar a base."}')
    assert "## Por que este plano" in body
    assert "BDMG Digital" in body


def test_plain_excerpt_strips_headings_and_json():
    assert "Resumo executivo" in _plain_excerpt("## Resumo executivo\nA tese do BDMG permanece institucional.")
    assert "#" not in _plain_excerpt("## Resumo executivo\nA tese do BDMG permanece institucional.")
    assert "BDMG Digital" in _plain_excerpt('{"why_this_plan": ["BDMG Digital"]}')


def test_stale_running_generation_can_restart():
    assert _stale_generation({"status": "running", "updatedAt": "2000-01-01T00:00:00+00:00"})
    assert not _stale_generation({"status": "done", "updatedAt": "2000-01-01T00:00:00+00:00"})
    assert not _stale_generation({"status": "running"})


def test_require_llm_explains_missing_credential():
    with patch("aicentralv2.smart_planner.generator._has_llm", return_value=False):
        try:
            _require_llm("página única")
        except ValueError as exc:
            assert "Integrações" in str(exc)
        else:
            raise AssertionError("deveria exigir credencial")


def _page_with_mix(channel="ooh", roles=None):
    return {
        "thesis": {"statement": "Partir dos canais oficiais e levar cada demanda ao autosserviço."},
        "recommendation": {
            "summary": "OOH no recorte de Minas e busca no serviço oficial.",
            "channel_roles": roles or [{"channel": channel, "role": "Alcance de rua"}],
        },
        "creative_expression": {"channel": channel, "headline": "Resolva de onde estiver"},
        "result_estimates": {"status": "not_available"},
    }


def test_validate_page_rejects_creative_outside_approved_mix():
    snapshot = {
        "client": {"name": "BDMG"},
        "channels": ["ooh", "google_ads"],
        "mix": [
            {"id": "ooh", "label": "OOH / Painéis", "pct": 70},
            {"id": "google_ads", "label": "Google Ads", "pct": 30},
        ],
    }
    try:
        _validate_page(_page_with_mix("google_ads"), snapshot, {"status": "not_available"})
    except ValueError as exc:
        assert "maior peso" in str(exc)
    else:
        raise AssertionError("deveria rejeitar criativo fora do mix")


def test_validate_page_requires_hero_channel_in_roles():
    snapshot = {
        "client": {"name": "BDMG"},
        "channels": ["ooh", "google_ads"],
        "mix": [
            {"id": "ooh", "label": "OOH / Painéis", "pct": 70},
            {"id": "google_ads", "label": "Google Ads", "pct": 30},
        ],
    }
    page = _page_with_mix("ooh", roles=[{"channel": "google_ads", "role": "Busca"}])
    try:
        _validate_page(page, snapshot, {"status": "not_available"})
    except ValueError as exc:
        assert "herói" in str(exc)
    else:
        raise AssertionError("deveria exigir o canal-herói nos papéis")


def test_validate_page_accepts_mix_label_as_hero():
    snapshot = {
        "client": {"name": "BDMG"},
        "channels": ["ooh", "google_ads"],
        "mix": [
            {"id": "google_ads", "label": "Google Ads", "pct": 55},
            {"id": "ooh", "label": "OOH / Painéis", "pct": 45},
        ],
    }
    _validate_page(_page_with_mix("Google Ads"), snapshot, {"status": "not_available"})


def test_pack_exposes_approved_mix_as_law():
    packed = _pack(
        {
            "client": {"name": "BDMG"},
            "mix": [
                {"id": "ooh", "label": "OOH / Painéis", "pct": 60, "amount_label": "R$ 240.000"},
                {"id": "google_ads", "label": "Google Ads", "pct": 40, "amount_label": "R$ 160.000"},
            ],
            "mix_method": "funil",
            "pace": {"how": "Começa menor, solta no meio e no fim."},
        },
        {},
    )
    assert "mix_aprovado" in packed
    assert "OOH / Painéis: 60%" in packed
    assert "lei da mesa" in packed
    law = _mix_law({
        "mix": [{"id": "ooh", "label": "OOH / Painéis", "pct": 60, "amount_label": "R$ 240.000"}],
    })
    assert law["hero"]["id"] == "ooh"
