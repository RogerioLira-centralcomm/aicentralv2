"""Gerador modular: snapshot → núcleo → one page → plano por grupos."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone

from . import canvas as canvas_mod
from . import planner
from . import one_page
from .ai import chat_json, chat_text
from .brand import brand_prompt_block
from .catalog import CHANNEL_CATALOG, PLAN_MODES, PRIMARY_FORMATS
from .cost import bound_session
from .estimates import calculate_estimates, format_estimates_for_prompt
from .helpers import (
    as_bool,
    as_dict,
    as_list,
    client_display_name,
    extract_json,
    name_leaks_in,
    normalize_markdown,
    plan_mode_of,
    redact_advertiser,
    text,
    thesis_is_meta,
)
from .progress import finish_progress, mark_step, start_progress
from .repository import get_by_token, merge_dados, update_session
from .skills import load_skill, skill_role
from .snapshot import build_evidence, build_snapshot

logger = logging.getLogger(__name__)

FINAL_REVIEW_PROMPT = """Você é o revisor final de um planejamento de mídia brasileiro.
Audite o material recebido contra as evidências e a configuração da campanha.
Procure apenas: canal inventado, verba ou percentual divergente, repetição, texto prolixo, afirmação sem fonte, KPI inventado,
vazamento de anunciante confidencial, texto sobre imagem que não deveria estar no documento e linguagem comercial indevida.
Não pesquise na internet. Não complete lacunas por plausibilidade.
Quando houver OOH ou Places, o documento não pode fazer afirmações de preço, cotação, mínimo comercial, compra de mídia,
negociação, fornecedor, ponto, raio, circuito, inventário, disponibilidade comercial ou promessa de veiculação. Pode conter
investimento total, divisão percentual, público, segmentação, papel estratégico e defesa do plano. Apps e sites de Places
só podem aparecer como contexto de audiência digital observado no catálogo.
Essa restrição vale para afirmações comerciais sobre compra de mídia. Não trate como infração expressões de público ou
categoria, como "intenção de compra", "compras de imóveis" ou "jornada de compra". Se encontrar uma afirmação comercial
indevida, remova ou reescreva o trecho no campo `corrected`; não devolva apenas a reprovação.
Remova introduções genéricas, conclusões duplicadas, listas que repetem parágrafos e seções sem decisão útil.
Preserve a tese, o schema e os títulos obrigatórios. Escreva em português direto, com uma ideia por parágrafo.
Devolva apenas JSON: {"approved": true|false, "issues": [], "corrected": null ou o documento corrigido}.
Se houver problema, corrija somente o necessário e preserve o schema ou os títulos das seções.
"""

GROUP_CONTRACTS = {
    "planner_full_strategy_v2": ("Resumo executivo", "Framework de indicadores", "Estratégia de comunicação"),
    "planner_full_media_v2": ("Estratégia de mídia", "Mix e investimento", "Fases do voo"),
    "planner_full_execution_v1": ("Direção criativa", "Mensuração", "Riscos e dependências"),
    "planner_commercial_defense_v1": ("Por que este plano",),
}


def start_generation(token: str, mode: str | None = None) -> dict:
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    briefing = text(row.get("briefing_melhorado") or row.get("briefing_compilado"))
    if not briefing:
        raise ValueError("Processe o briefing antes de gerar o plano.")
    dados = as_dict(row.get("dados_detectados"))
    chosen = (mode or plan_mode_of(dados) or "one_page").strip().lower()
    if chosen not in PLAN_MODES:
        chosen = "one_page"
    geracao = as_dict(dados.get("geracao"))
    if text(geracao.get("status")) == "running" and not _stale_generation(geracao):
        return {
            "started": True,
            "already": True,
            "mode": text(geracao.get("mode")) or chosen,
            "redirect": f"/smart-planner/{token}/conclusao",
        }
    start_progress(token, chosen)
    _spawn_generation(token, chosen)
    return {
        "started": True,
        "mode": chosen,
        "redirect": f"/smart-planner/{token}/conclusao",
    }


def run_generation(token: str, mode: str | None = None, *, progress_started: bool = False) -> dict:
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    briefing = text(row.get("briefing_melhorado") or row.get("briefing_compilado"))
    if not briefing:
        raise ValueError("Processe o briefing antes de gerar o plano.")
    dados = as_dict(row.get("dados_detectados"))
    chosen = (mode or plan_mode_of(dados) or "one_page").strip().lower()
    if chosen not in PLAN_MODES:
        chosen = "one_page"
    if not progress_started:
        start_progress(token, chosen)
    try:
        with bound_session(token):
            return _run(token, chosen)
    except Exception as exc:
        mark_step(
            token,
            as_dict(as_dict((get_by_token(token) or {}).get("dados_detectados")).get("geracao")).get("step") or "core",
            "error",
            str(exc),
        )
        raise


def _spawn_generation(token: str, mode: str) -> None:
    from flask import current_app, has_app_context

    if not has_app_context():
        run_generation(token, mode, progress_started=True)
        return

    app = current_app._get_current_object()

    def runner():
        with app.app_context():
            try:
                run_generation(token, mode, progress_started=True)
            except Exception:
                logger.exception("Geração Smart Planner falhou: %s", token)
            finally:
                try:
                    from ..db import close_db

                    close_db()
                except Exception:
                    pass

    threading.Thread(target=runner, daemon=True, name=f"sp-gen-{token[:12]}").start()


def _run(token: str, mode: str) -> dict:
    row = get_by_token(token)
    dados = as_dict(row.get("dados_detectados"))
    material_hash = _material_hash(row)

    mark_step(token, "snapshot", "running")
    snapshot = build_snapshot(row, dados)
    snapshot["material_hash"] = material_hash
    merge_dados(token, {"snapshot": snapshot, "plan_mode": mode, "material_hash": material_hash})
    mark_step(token, "snapshot", "done")

    mark_step(token, "evidence", "running")
    evidence = build_evidence(snapshot)
    merge_dados(token, {"evidence": evidence})
    mark_step(token, "evidence", "done")

    market_research = text(dados.get("market_research"))
    if not market_research and _has_llm():
        mark_step(token, "market", "running")
        market_research = planner.research_market(
            text(snapshot.get("briefing")),
            as_dict(dados.get("campanha")),
            as_dict(snapshot.get("brand")),
            apoio=text(snapshot.get("user_briefing")),
        )
        merge_dados(token, {"market_research": market_research})
        snapshot["market_research"] = market_research
        evidence["market_research"] = market_research
        merge_dados(token, {"evidence": evidence})
        mark_step(token, "market", "done")
    else:
        mark_step(token, "market", "skipped")

    core = as_dict(dados.get("strategy_core"))
    if _usable_core(core, material_hash):
        mark_step(token, "core", "skipped")
    else:
        _require_llm("núcleo estratégico")
        mark_step(token, "core", "running")
        core = _strategy_core(snapshot, evidence)
        core["material_hash"] = material_hash
        merge_dados(token, {"strategy_core": core, "strategy_core_id": text(core.get("id"))})
        mark_step(token, "core", "done")

    mark_step(token, "estimates", "running")
    estimates = calculate_estimates(snapshot)
    merge_dados(token, {"estimates": estimates})
    mark_step(token, "estimates", "done")

    page = as_dict(dados.get("one_page_v2"))
    folha = as_dict(dados.get("folha"))
    if _usable_page(page, material_hash, core) and as_list(folha.get("sections")):
        mark_step(token, "one_page", "skipped")
    else:
        _require_llm("página única")
        mark_step(token, "one_page", "running")
        page = _one_page_v2(snapshot, evidence, core, estimates)
        page = _review_page(page, snapshot, estimates)
        page["creative_plan"] = _creative_plan(page, snapshot)
        page["material_hash"] = material_hash
        folha = _materialize_folha(token, snapshot, page, core)
        merge_dados(token, {"one_page_v2": page, "folha": folha})
        mark_step(token, "one_page", "done")

    if not as_list(page.get("creative_plan")):
        page["creative_plan"] = _creative_plan(page, snapshot)
        merge_dados(token, {"one_page_v2": page})

    mark_step(token, "validate", "running")
    _validate_page(page, snapshot, estimates)
    mark_step(token, "validate", "done")

    if mode == "one_page":
        mark_step(token, "publish", "running")
        _publish_folha(token, folha)
        finish_progress(token, mode)
        return {"folha": folha, "strategy_core": core, "estimates": estimates, "planejamento": ""}

    groups = as_dict(dados.get("planejamento_grupos"))
    if (
        text(dados.get("material_hash")) == material_hash
        and all(text(groups.get(key)) for key in ("strategy", "media", "execution", "defense"))
    ):
        mark_step(token, "full_strategy", "skipped")
        mark_step(token, "full_media", "skipped")
        mark_step(token, "full_execution", "skipped")
        mark_step(token, "full_defense", "skipped")
        strategy_md = text(groups.get("strategy"))
        media_md = text(groups.get("media"))
        execution_md = text(groups.get("execution"))
        defense_md = _as_plan_markdown(text(groups.get("defense")))
    else:
        _require_llm("plano completo")
        mark_step(token, "full_strategy", "running")
        strategy_md = _group_markdown("planner_full_strategy_v2", snapshot, evidence, core, page, estimates, folha)
        mark_step(token, "full_media", "running")
        media_md = _group_markdown("planner_full_media_v2", snapshot, evidence, core, page, estimates, folha)
        mark_step(token, "full_execution", "running")
        execution_md = _group_markdown("planner_full_execution_v1", snapshot, evidence, core, page, estimates, folha)
        mark_step(token, "full_defense", "running")
        defense_md = _as_plan_markdown(
            _group_markdown("planner_commercial_defense_v1", snapshot, evidence, core, page, estimates, folha)
        )

    cover = _cover_markdown(snapshot, core)
    final = normalize_markdown("\n\n".join(part for part in (cover, strategy_md, media_md, execution_md, defense_md) if part))
    final = _review_document(final, snapshot, page, estimates)
    final = _repair_channel_policy_text(final, snapshot)
    _validate_channel_policy(final, snapshot)
    quality = _validate_plan_markdown(final)
    if not quality["valid"]:
        raise ValueError("O documento completo não passou na validação editorial: " + "; ".join(quality["errors"]))
    merge_dados(token, {
        "planejamento": final,
        "planning_quality": quality,
        "planejamento_grupos": {
            "strategy": strategy_md,
            "media": media_md,
            "execution": execution_md,
            "defense": defense_md,
        },
    })

    mark_step(token, "compose", "running")
    canvas_mod.generate_canvas(token)
    if _has_llm():
        consistency = _consistency_check(snapshot, core, page, final)
        merge_dados(token, {"consistency": consistency})
    mark_step(token, "compose", "done")
    mark_step(token, "publish", "running")
    finish_progress(token, mode)
    return {
        "folha": folha,
        "strategy_core": core,
        "estimates": estimates,
        "planejamento": final,
    }


def _redact_pack(payload: dict, name: str) -> dict:
    data = dict(payload or {})
    for key in ("briefing", "user_briefing"):
        if text(data.get(key)):
            data[key] = redact_advertiser(text(data.get(key)), name)
    sources = []
    for item in as_list(data.get("sources")):
        row = dict(as_dict(item))
        if text(row.get("notas")):
            row["notas"] = redact_advertiser(text(row.get("notas")), name)
        sources.append(row)
    if sources:
        data["sources"] = sources
    return data


def _review_page(page: dict, snapshot: dict, estimates: dict) -> dict:
    if not _has_llm() or not isinstance(page, dict):
        return page
    try:
        result = chat_json(
            FINAL_REVIEW_PROMPT,
            json.dumps({
                "kind": "one_page",
                "evidence": {
                    "briefing": text(snapshot.get("briefing"))[:7000],
                    "campaign": as_dict(snapshot.get("campaign")),
                    "brand": as_dict(snapshot.get("brand")),
                    "objective": as_dict(snapshot.get("objective")),
                    "budget": as_dict(snapshot.get("budget")),
                    "mix": as_list(snapshot.get("mix")),
                    "places": as_list(snapshot.get("places")),
                    "ooh_inventory": as_dict(snapshot.get("ooh_inventory")),
                    "conteudo_capturado_apoio": text(snapshot.get("conteudo_capturado"))[:12000],
                    "pace": as_dict(snapshot.get("pace")),
                    "estimates": estimates,
                },
                "document": page,
            }, ensure_ascii=False, default=str)[:24000],
            role="final_review",
            max_tokens=2200,
        )
        corrected = as_dict(result.get("corrected"))
        return corrected if corrected else page
    except Exception:
        logger.warning("Revisor final da página única indisponível", exc_info=True)
        return page


def _review_document(document: str, snapshot: dict, page: dict, estimates: dict) -> str:
    if not _has_llm() or not document:
        return document
    try:
        result = chat_json(
            FINAL_REVIEW_PROMPT,
            json.dumps({
                "kind": "full_plan",
                "evidence": {
                    "briefing": text(snapshot.get("briefing"))[:7000],
                    "campaign": as_dict(snapshot.get("campaign")),
                    "objective": as_dict(snapshot.get("objective")),
                    "budget": as_dict(snapshot.get("budget")),
                    "mix": as_list(snapshot.get("mix")),
                    "places": as_list(snapshot.get("places")),
                    "ooh_inventory": as_dict(snapshot.get("ooh_inventory")),
                    "conteudo_capturado_apoio": text(snapshot.get("conteudo_capturado"))[:12000],
                    "pace": as_dict(snapshot.get("pace")),
                    "estimates": estimates,
                },
                "page_decision": page,
                "document": document[:30000],
            }, ensure_ascii=False, default=str)[:42000],
            role="final_review",
            max_tokens=3200,
        )
        corrected = text(result.get("corrected"))
        return normalize_markdown(corrected) if corrected else document
    except Exception:
        logger.warning("Revisor final do planejamento indisponível", exc_info=True)
        return document


def _mix_law(snapshot: dict) -> dict:
    mix = [as_dict(row) for row in as_list((snapshot or {}).get("mix")) if as_dict(row).get("id") or as_dict(row).get("label")]
    if not mix:
        return {}
    ranked = sorted(mix, key=lambda row: int(row.get("pct") or 0), reverse=True)
    hero = ranked[0] if ranked else {}
    lines = []
    for row in ranked:
        label = text(row.get("label") or row.get("id"))
        pct = row.get("pct")
        group = text(row.get("group") or (CHANNEL_CATALOG.get(text(row.get("id"))) or {}).get("group"))
        amount = "" if group in {"ooh", "places"} else text(row.get("amount_label"))
        bit = f"{label}: {pct}%" if pct is not None and pct != "" else label
        if amount:
            bit += f" · {amount}"
        lines.append(bit)
    pace = as_dict((snapshot or {}).get("pace"))
    return {
        "lei": "O mix abaixo é lei da mesa. channel_roles e criativo só com estes canais. O criativo vai no canal de maior peso. why_this_mix cita a divisão percentual e o investimento total, nunca cotação por OOH ou Place.",
        "hero": {
            "id": text(hero.get("id")),
            "label": text(hero.get("label") or hero.get("id")),
            "pct": hero.get("pct"),
            "amount_label": text(hero.get("amount_label")),
        },
        "channels": lines,
        "voo": text(pace.get("how")),
        "method": text((snapshot or {}).get("mix_method")),
    }


def _places_law(snapshot: dict) -> dict:
    rows = [as_dict(item) for item in as_list((snapshot or {}).get("places")) if as_dict(item).get("slug")]
    if not rows:
        return {}
    lines = []
    for place in rows:
        title = text(place.get("title") or place.get("slug"))
        metrics = as_dict(place.get("metrics"))
        digital = []
        for point in as_list(place.get("points")):
            row = as_dict(point)
            digital.extend(text(item) for item in as_list(row.get("apps")) + as_list(row.get("portals")) if text(item))
        digital_note = f" · ambientes digitais observados: {', '.join(sorted(set(digital))[:8])}" if digital else ""
        lines.append(f"{title} · audiência consolidada: {text(metrics.get('addressable')) or text(metrics.get('four_weeks')) or 'não informada'}{digital_note}")
    interativos = as_dict((snapshot or {}).get("interativos"))
    formats = [text(item) for item in as_list(interativos.get("formats")) if text(item)]
    return {
        "lei": (
            "Só estes ambientes e suas audiências consolidadas. Apps e sites observados no catálogo podem ser usados como contexto de audiência digital, nunca como promessa de compra ou inventário. Não cite preço, mínimo comercial, ponto, raio ou fornecedor. "
            "Se o catálogo trouxer sinal explícito, separe Places digital (apps e geolocalização) de Places OOH (presença física); sem sinal, use apenas ambiente Place. "
            "Interativos não são Places — só no portal-herói se interativos estiver no mix."
        ),
        "places": lines,
        "multi": len(rows) > 1,
        "interativos": formats,
    }


def _pack(snapshot: dict, evidence: dict, core: dict | None = None, estimates: dict | None = None, extra: dict | None = None) -> str:
    snap = dict(snapshot or {})
    client = dict(as_dict(snap.get("client")))
    secret = text(client.get("name"))
    if client.get("confidential"):
        display = client_display_name(client)
        client["name"] = display
        client["display_name"] = display
        snap["client"] = client
        brand = dict(as_dict(snap.get("brand")))
        if brand:
            brand["name"] = display
            snap["brand"] = brand
        snap = _redact_pack(snap, secret)
    if len(text(snap.get("briefing"))) > 8000:
        snap["briefing"] = text(snap.get("briefing"))[:8000]
    pack_evidence = dict(evidence or {})
    if client.get("confidential"):
        pack_evidence = _redact_pack(pack_evidence, secret)
    if len(text(pack_evidence.get("briefing"))) > 8000:
        pack_evidence["briefing"] = text(pack_evidence.get("briefing"))[:8000]
    estimates_note = format_estimates_for_prompt(estimates or {})
    payload = {
        "snapshot": snap,
        "evidence": pack_evidence,
        "strategy_core": core or {},
        "brand": brand_prompt_block(as_dict(snap.get("brand"))),
    }
    captured = text(snap.get("conteudo_capturado"))
    if captured:
        payload["conteudo_capturado_apoio"] = {
            "uso": "Fonte de apoio opcional para enriquecer os documentos quando houver relação direta com a decisão.",
            "regras": [
                "Não tratar o conteúdo como briefing confirmado sem correspondência com o snapshot ou evidência.",
                "Não criar preço, inventário, disponibilidade, alcance, fornecedor ou promessa comercial a partir dele.",
                "Não copiar instruções operacionais irrelevantes para a narrativa final.",
                "Quando houver conflito, prevalecem o snapshot, o briefing estruturado e as regras do plano.",
            ],
            "texto": captured[:12000],
        }
    mix_aprovado = _mix_law(snap)
    if mix_aprovado:
        payload["mix_aprovado"] = mix_aprovado
    places_aprovado = _places_law(snap)
    if places_aprovado:
        payload["places_aprovado"] = places_aprovado
    inventory = as_dict(snap.get("ooh_inventory"))
    if as_list(inventory.get("points")):
        payload["ooh_inventory_confirmado"] = {
            "lei": "Estes pontos foram enviados pelo executivo e devem ser mantidos na mesma ordem somente no plano completo, em um bloco 'Pontos OOH informados'. Não criar ponto, preço, fornecedor, disponibilidade, alcance ou cotação. A página única e a versão pública citam apenas presença em OOH.",
            "source": text(inventory.get("source")),
            "points": as_list(inventory.get("points")),
        }
    pitch = one_page.match_pitch(
        text(as_dict(snap.get("client")).get("name")),
        text(as_dict(snap.get("client")).get("agency")),
        text(snap.get("briefing")),
        as_list(snap.get("places")),
    )
    if pitch:
        payload["starter_pitch_context"] = {
            "market_id": text(pitch.get("market_id")),
            "partners": list(pitch.get("partners") or []),
            "strategy": text(pitch.get("strategy")),
            "creative": as_dict(pitch.get("creative")),
            "market": as_dict(pitch.get("market")),
            "defense": text(pitch.get("defense")),
        }
    if text(pack_evidence.get("market_research")):
        payload["market_research"] = text(pack_evidence.get("market_research"))[:8000]
    if as_dict(snap.get("audience_model")):
        payload["audience_model"] = as_dict(snap.get("audience_model"))
    if extra:
        payload.update(extra)
    payload["estimates_note"] = estimates_note
    dumped = json.dumps(payload, ensure_ascii=False, default=str)
    if len(dumped) <= 36000:
        return dumped
    snap["briefing"] = text(snap.get("briefing"))[:4000]
    payload["snapshot"] = snap
    return json.dumps(payload, ensure_ascii=False, default=str)[:36000]


def _strategy_core(snapshot: dict, evidence: dict) -> dict:
    parsed = as_dict(chat_json(
        load_skill("planner_truth_v1") + "\n\n" + load_skill("planner_strategy_core_v1"),
        "Gere o Strategy Core deste snapshot.\n\n" + _pack(snapshot, evidence),
        role=skill_role("planner_strategy_core_v1"),
    ))
    parsed["id"] = "strategy_" + text(snapshot.get("snapshot_id"))
    parsed["snapshot_id"] = text(snapshot.get("snapshot_id"))
    return parsed


def _one_page_v2(snapshot: dict, evidence: dict, core: dict, estimates: dict) -> dict:
    system = "\n\n".join((
        load_skill("planner_truth_v1"),
        load_skill("planner_estimation_v1"),
        load_skill("planner_one_page_v2"),
    ))
    parsed = as_dict(chat_json(
        system,
        "Sintetize o núcleo neste One Page. Não invente tese nova. "
        "A verba só pode aparecer se estiver confirmada no snapshot; caso contrário, omita qualquer menção financeira. "
        "A direção visual deve trazer uma persona e, quando houver evidência, o lugar/contexto da campanha.\n\n"
        + _pack(snapshot, evidence, core, estimates),
        role=skill_role("planner_one_page_v2"),
    ))
    parsed.setdefault("visual_direction", _visual_direction_fallback(snapshot))
    parsed["visual_direction"] = {
        **_visual_direction_fallback(snapshot),
        **as_dict(parsed.get("visual_direction")),
    }
    parsed["audience_model"] = {
        **_audience_model_fallback(snapshot),
        **as_dict(parsed.get("audience_model")),
    }
    parsed["visual_data"] = as_list(parsed.get("visual_data")) or _visual_data_fallback(snapshot)
    _apply_no_budget_policy(parsed, snapshot)
    parsed.setdefault("result_estimates", {})
    parsed["result_estimates"].setdefault("status", estimates.get("status"))
    if not text(as_dict(parsed.get("result_estimates")).get("summary")):
        parsed["result_estimates"]["summary"] = format_estimates_for_prompt(estimates)
    parsed["snapshot_id"] = text(snapshot.get("snapshot_id"))
    parsed["strategy_core_id"] = text(core.get("id"))
    return parsed


def _visual_direction_fallback(snapshot: dict) -> dict:
    snap = as_dict(snapshot)
    geography = as_dict(snap.get("geography"))
    place = text(geography.get("detail") or geography.get("praca"))
    audiences = as_list(snap.get("audiences"))
    audience = text(audiences[0] if audiences else "")
    return {
        "persona_name": "Pessoa em situação de decisão",
        "persona_description": audience or "Pessoa representativa do público confirmado no briefing.",
        "place_scene": place,
        "persona_image_prompt": (
            "Foto editorial documental de uma pessoa representativa do público descrito no briefing, "
            + (audience or "em uma situação cotidiana ligada ao objetivo da campanha")
            + ". Sem texto, logo ou aparência de banco de imagens."
        ),
        "place_image_prompt": (
            "Foto editorial realista do contexto de campanha em " + place + ", sem texto, logo ou ponto turístico inventado."
            if place else ""
        ),
    }


def _audience_model_fallback(snapshot: dict) -> dict:
    snap = as_dict(snapshot)
    audiences = as_list(snap.get("audiences"))
    audience = text(audiences[0] if audiences else "")
    geography = as_dict(snap.get("geography"))
    return {
        "segments": [{
            "label": "Público informado no briefing",
            "description": audience or "Público descrito no briefing.",
            "status": "briefing" if audience else "a_validar",
        }],
        "faixa_etaria": {"value": None, "status": "a_validar"},
        "genero": {"value": None, "status": "a_validar"},
        "classe_social": {"value": None, "status": "a_validar"},
        "regiao": text(geography.get("praca") or geography.get("detail")),
        "bairro": "",
        "universo_estimado": {"value": None, "unit": "pessoas", "status": "a_validar", "source": ""},
        "impacto_estimado": {"value": None, "unit": "pessoas", "status": "a_validar", "source": ""},
        "source_note": "Estimativas demográficas só entram com fonte pública ou base aprovada.",
    }


def _visual_data_fallback(snapshot: dict) -> list[dict]:
    snap = as_dict(snapshot)
    mix = [as_dict(item) for item in as_list(snap.get("mix")) if as_dict(item).get("label")]
    return [
        {"id": "universe", "label": "Universo demográfico", "value": "", "status": "a_validar"},
        {"id": "impact", "label": "Impacto estimado", "value": "", "status": "a_validar"},
        {"id": "ecosystem", "label": "Ecossistema de mídia", "value": f"{len(mix)} canais" if mix else "", "status": "briefing" if mix else "a_validar"},
        {"id": "evidence", "label": "Base da leitura", "value": "Briefing + pesquisa", "status": "briefing"},
    ]


def _apply_no_budget_policy(page: dict, snapshot: dict) -> None:
    budget = as_dict(as_dict(snapshot).get("budget"))
    has_budget = bool(text(budget.get("raw"))) or any(
        as_dict(row).get("amount") not in (None, "", 0)
        for row in as_list(as_dict(snapshot).get("mix"))
    )
    if has_budget:
        return
    page["result_estimates"] = {
        "status": "not_available",
        "summary": "Base comercial ainda em definição nesta fase.",
    }
    blocked = re.compile(r"(?:R\$\s*[\d.,]+|\bverba\b|\borçamento\b|\binvestimento\b|\bbudget\b)", re.I)

    def clean(value):
        if isinstance(value, str):
            parts = re.split(r"(?<=[.!?])\s+", value)
            return " ".join(part for part in parts if not blocked.search(part)).strip()
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        return value

    for key, value in list(page.items()):
        if key != "result_estimates":
            page[key] = clean(value)


def _materialize_folha(token: str, snapshot: dict, page: dict, core: dict) -> dict:
    row = get_by_token(token)
    dados = as_dict(row.get("dados_detectados"))
    meta = canvas_mod._row_meta(row, dados)
    client_info = as_dict(snapshot.get("client"))
    confidential = bool(client_info.get("confidential"))
    client = client_display_name(client_info, name=text(client_info.get("name") or meta.get("client")))
    agency = text(client_info.get("agency") or meta.get("agency"))
    branding = one_page.resolve_branding(
        client if not confidential else "",
        agency,
        text(dados.get("presenter_brand")) or "centralcomm",
        [],
        cliente_id=None if confidential else dados.get("cliente_id"),
        agencia_id=dados.get("agencia_id"),
        brand={} if confidential else as_dict(dados.get("brand")),
    )
    if confidential:
        branding["client"] = {
            "id": None,
            "name": client,
            "logo_url": "",
            "source": "confidential",
        }
    theme = one_page.theme_for_snapshot(client, agency, text(snapshot.get("briefing")), snapshot)
    share = one_page.share_payload(text(dados.get("public_token")), client)
    media = one_page.build_media_board(
        snapshot.get("mix"),
        method=text(snapshot.get("mix_method")),
        pace=snapshot.get("pace"),
        roles=as_dict(page.get("recommendation")).get("channel_roles"),
        calendar=snapshot.get("calendar"),
    )
    plan = one_page.assemble_from_v2(
        {**meta, "client": client, "agency": agency, "presenter": branding["presenter"]["id"]},
        branding,
        theme,
        share,
        page,
        core,
        snapshot.get("snapshot_id"),
        snapshot=snapshot,
        media=media,
    )
    plan["visual_direction"] = as_dict(page.get("visual_direction"))
    plan["audience_model"] = as_dict(page.get("audience_model"))
    plan["visual_data"] = as_list(page.get("visual_data"))
    merge_dados(token, {
        "presenter_brand": plan["meta"]["presenter"],
        "public_token": plan["share"]["public_token"],
    })
    return plan


def _channel_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text(value).strip().lower()).strip("_")


def _channel_tokens(*values) -> set[str]:
    tokens = set()
    for value in values:
        raw = text(value).strip()
        if not raw:
            continue
        tokens.add(raw.lower())
        token = _channel_token(raw)
        if token:
            tokens.add(token)
    return tokens


def _mix_rows(snapshot: dict) -> list[dict]:
    rows = []
    for item in as_list((snapshot or {}).get("mix")):
        row = as_dict(item)
        if text(row.get("id") or row.get("label")):
            rows.append(row)
    return rows


def _approved_tokens(snapshot: dict) -> set[str]:
    tokens = set()
    for item in as_list((snapshot or {}).get("channels")):
        tokens |= _channel_tokens(item)
    for row in _mix_rows(snapshot):
        tokens |= _channel_tokens(row.get("id"), row.get("label"))
    for place in as_list((snapshot or {}).get("places")):
        row = as_dict(place)
        tokens |= _channel_tokens(row.get("slug"), row.get("title"), "places")
    return tokens


def _hero_rows(mix: list[dict]) -> list[dict]:
    scored = [(int(row.get("pct") or 0), row) for row in mix]
    top = max((pct for pct, _row in scored), default=0)
    if top <= 0:
        return []
    return [row for pct, row in scored if pct == top]


def _matches_mix(value: str, rows: list[dict]) -> bool:
    tokens = _channel_tokens(value)
    for row in rows:
        if tokens & _channel_tokens(row.get("id"), row.get("label")):
            return True
    return False


def _creative_plan(page: dict, snapshot: dict) -> list[dict]:
    """Normaliza uma única recomendação de formato por canal.

    O modelo pode sugerir o formato, mas o catálogo é a autoridade. A
    quantidade é uma recomendação de entregáveis, não um lote de imagens.
    """
    roles = as_list(as_dict(page.get("recommendation")).get("channel_roles"))
    months = max(1, len(as_list(as_dict(snapshot.get("pace")).get("months"))))
    out = []
    for mix in _mix_rows(snapshot):
        channel_id = text(mix.get("id"))
        if not channel_id:
            continue
        proposed = next(
            (as_dict(item) for item in roles if _channel_tokens(as_dict(item).get("channel")) & _channel_tokens(channel_id, mix.get("label"))),
            {},
        )
        primary = dict(PRIMARY_FORMATS.get(channel_id) or {
            "id": "static_landscape",
            "label": "Imagem horizontal",
            "surface": "display",
        })
        pct = max(0, int(mix.get("pct") or 0))
        # One concept plus enough refreshes for longer or heavier flights.
        variations = min(5, max(1, months + (1 if pct >= 30 else 0)))
        out.append({
            "channel_id": channel_id,
            "channel": text(mix.get("label")) or text((CHANNEL_CATALOG.get(channel_id) or {}).get("label")) or channel_id,
            "role": text(proposed.get("role") or proposed.get("description") or mix.get("role")),
            "primary_format_id": primary["id"],
            "primary_format": primary["label"],
            "surface": primary.get("surface") or "display",
            "duration_seconds": primary.get("duration_seconds"),
            "format_rationale": text(proposed.get("format_rationale")) or "Formato principal compatível com o canal; especificação comercial confirmada na operação.",
            "deliverables": {
                "concepts": 1,
                "variations": variations,
                "final_files": variations,
                "status": "recommended",
                "rationale": f"Recomendação provisória para {months} mês(es) e {pct}% do mix; confirmar capacidade e necessidade de renovação.",
            },
            "smart_planner_media": "static_concept_image",
        })
    return out


def _validate_page(page: dict, snapshot: dict, estimates: dict) -> None:
    repaired = _repair_channel_policy_payload(page, snapshot)
    if repaired != page:
        page.clear()
        page.update(repaired)
    thesis = text(as_dict(page.get("thesis")).get("statement"))
    if len(thesis) < 20:
        raise ValueError("A tese da página única voltou vazia. Gere novamente.")
    rec = text(as_dict(page.get("recommendation")).get("summary"))
    if len(rec) < 12:
        raise ValueError("A recomendação da página única voltou vazia. Gere novamente.")
    client_info = as_dict((snapshot or {}).get("client"))
    client = text(client_info.get("name"))
    blob = json.dumps(page or {}, ensure_ascii=False, default=str)
    _validate_channel_policy(blob, snapshot)
    if thesis_is_meta(thesis):
        raise ValueError("A tese fala do planejamento, não do anunciante. Gere novamente.")
    if client_info.get("confidential") and name_leaks_in(client, blob):
        raise ValueError("A tese vazou o nome confidencial do anunciante. Gere novamente.")
    mix = _mix_rows(snapshot)
    approved = _approved_tokens(snapshot)
    extras = []
    roles = as_list(as_dict(page.get("recommendation")).get("channel_roles"))
    for item in roles:
        channel = text(as_dict(item).get("channel") or as_dict(item).get("id"))
        if not channel or channel.lower() in {"a definir", "definir"}:
            continue
        if approved and not (_channel_tokens(channel) & approved):
            extras.append(channel)
    if extras:
        raise ValueError("A página única usou canais não aprovados: " + ", ".join(extras[:4]))
    heroes = _hero_rows(mix)
    if heroes:
        creative_channel = text(as_dict(page.get("creative_expression")).get("channel"))
        if not _matches_mix(creative_channel, heroes):
            raise ValueError("O criativo precisa estar no canal de maior peso do mix.")
        if not any(_matches_mix(text(as_dict(item).get("channel") or as_dict(item).get("id")), heroes) for item in roles):
            raise ValueError("Os papéis de canal precisam incluir o canal-herói do mix.")
    result = as_dict(page.get("result_estimates"))
    if result.get("status") == "available" and as_dict(estimates).get("status") != "available":
        page["result_estimates"]["status"] = "not_available"
        page["result_estimates"]["summary"] = format_estimates_for_prompt(estimates)
    creative_plan = as_list(page.get("creative_plan"))
    channel_ids = [text(as_dict(item).get("channel_id")) for item in creative_plan]
    if len(channel_ids) != len(set(channel_ids)) or any(not item for item in channel_ids):
        raise ValueError("Cada canal precisa ter exatamente uma recomendação criativa.")
    for item in creative_plan:
        row = as_dict(item)
        expected = PRIMARY_FORMATS.get(text(row.get("channel_id")))
        if expected and text(row.get("primary_format_id")) != text(expected.get("id")):
            raise ValueError("O formato principal não corresponde ao catálogo do canal.")


def _validate_channel_policy(content: str, snapshot: dict) -> None:
    rows = _mix_rows(snapshot)
    protected = any(
        text(row.get("id")).lower() == "places"
        or text(row.get("group") or (CHANNEL_CATALOG.get(text(row.get("id"))) or {}).get("group")).lower() == "ooh"
        for row in rows
    )
    if not protected:
        return
    violations = _channel_policy_violations(content, snapshot)
    if violations:
        raise ValueError("O documento contém uma afirmação comercial indevida para OOH/Places: " + violations[0][:140])


def _channel_policy_violations(content: str, snapshot: dict) -> list[str]:
    rows = _mix_rows(snapshot)
    protected = any(
        text(row.get("id")).lower() == "places"
        or text(row.get("group") or (CHANNEL_CATALOG.get(text(row.get("id"))) or {}).get("group")).lower() == "ooh"
        for row in rows
    )
    if not protected:
        return []
    value = text(content)
    # A política protege contra promessas comerciais, não contra vocabulário de
    # audiência. "Compras de imóveis" e "intenção de compra" são contexto válido.
    direct_claim = re.compile(
        r"\b(compra\s+(?:de\s+)?(?:invent[aá]rio|m[ií]dia|ponto[s]?|espa[cç]o[s]?|circuito[s]?)|"
        r"compra\s+garantida|garantia\s+de\s+compra|comprar\s+(?:m[ií]dia|invent[aá]rio|ponto[s]?)|"
        r"veicula[cç][aã]o\s+garantida|disponibilidade\s+(?:comercial\s+)?garantida)\b",
        re.I,
    )
    channel_claim = re.compile(
        r"\b(?:ooh|dooh|places?|pain[eé]is?)\b.{0,120}\b(?:pre[cç]o(?:s)?|cota[cç][aã]o|"
        r"m[ií]nimo comercial|fornecedor|negocia[cç][aã]o|disponibilidade comercial|acesso ao invent[aá]rio)\b|"
        r"\b(?:pre[cç]o(?:s)?|cota[cç][aã]o|m[ií]nimo comercial|fornecedor|negocia[cç][aã]o|"
        r"disponibilidade comercial|acesso ao invent[aá]rio)\b.{0,120}\b(?:ooh|dooh|places?|pain[eé]is?)\b",
        re.I | re.S,
    )
    denial = re.compile(r"\b(?:sem|n[aã]o|nunca|jamais)\b.{0,55}$", re.I | re.S)
    violations = []
    for matcher in (direct_claim, channel_claim):
        for match in matcher.finditer(value):
            prefix = value[max(0, match.start() - 60):match.start()]
            if denial.search(prefix):
                continue
            violations.append(match.group(0))
    return violations


def _repair_channel_policy_text(content: str, snapshot: dict) -> str:
    value = text(content)
    if not value or not _channel_policy_violations(value, snapshot):
        return value
    replacement = "A execução de OOH/Places será definida no planejamento da rede."
    lines = value.splitlines()
    repaired = []
    for line in lines:
        if _channel_policy_violations(line, snapshot):
            prefix = ""
            stripped = line.lstrip()
            if stripped.startswith("- "):
                prefix = "- "
            elif re.match(r"^\d+\.\s", stripped):
                prefix = re.match(r"^\d+\.\s", stripped).group(0)
            repaired.append(prefix + replacement)
        else:
            repaired.append(line)
    result = normalize_markdown("\n".join(repaired))
    if _channel_policy_violations(result, snapshot):
        logger.warning("Política OOH/Places ainda encontrou trecho após reparo; aplicando texto seguro.")
        return replacement
    return result


def _repair_channel_policy_payload(value, snapshot: dict):
    if isinstance(value, dict):
        return {key: _repair_channel_policy_payload(item, snapshot) for key, item in value.items()}
    if isinstance(value, list):
        return [_repair_channel_policy_payload(item, snapshot) for item in value]
    if isinstance(value, str):
        return _repair_channel_policy_text(value, snapshot)
    return value


def _group_markdown(
    skill: str,
    snapshot: dict,
    evidence: dict,
    core: dict,
    page: dict,
    estimates: dict,
    folha: dict,
) -> str:
    system = load_skill("planner_truth_v1") + "\n\n" + load_skill(skill)
    user = (
        "Aprofunde a estratégia aprovada em markdown. Não altere tese, verba, canais ou período.\n\n"
        + _pack(
            snapshot,
            evidence,
            core,
            estimates,
            extra={"one_page": page, "pagina_unica": canvas_mod.folha_text(folha)},
        )
    )
    errors = []
    for attempt in range(2):
        retry = "" if not attempt else "\n\nA versão anterior falhou na estrutura. Use exatamente os títulos solicitados, sem bloco de código e sem comentários."
        raw = chat_text(system, user + retry, role=skill_role(skill), timeout=120)
        candidate = normalize_markdown(raw)
        valid, errors = _validate_group_markdown(skill, candidate)
        if valid:
            return candidate
    raise ValueError(f"O grupo {skill} não passou na validação editorial: {'; '.join(errors)}")


def _validate_group_markdown(skill: str, markdown: str) -> tuple[bool, list[str]]:
    """Reject malformed LLM chapters before they reach a public document."""
    value = normalize_markdown(markdown)
    headings = re.findall(r"(?m)^##\s+(.+?)\s*$", value)
    expected = GROUP_CONTRACTS.get(skill, ())
    errors = []
    if "```" in value:
        errors.append("bloco de código não permitido")
    if not headings:
        errors.append("sem capítulos de nível ##")
    missing = [title for title in expected if title.lower() not in {item.lower() for item in headings}]
    if missing:
        errors.append("faltam capítulos: " + ", ".join(missing))
    if len(value.strip()) < 160:
        errors.append("conteúdo insuficiente")
    return not errors, errors


def _validate_plan_markdown(markdown: str) -> dict:
    value = normalize_markdown(markdown)
    headings = re.findall(r"(?m)^##\s+(.+?)\s*$", value)
    errors = []
    if "```" in value:
        errors.append("há bloco de código não renderizável")
    if len(headings) < 8:
        errors.append("documento com capítulos insuficientes")
    return {"valid": not errors, "errors": errors, "chapter_count": len(headings), "validated_at": datetime.now(timezone.utc).isoformat()}


def _consistency_check(snapshot: dict, core: dict, page: dict, planejamento: str) -> dict:
    parsed = as_dict(chat_json(
        load_skill("planner_truth_v1") + "\n\n" + load_skill("planner_consistency_v1"),
        _pack(
            snapshot,
            {"briefing": text((snapshot or {}).get("briefing")), "user_briefing": text((snapshot or {}).get("user_briefing"))},
            core,
            extra={"one_page": page, "planejamento": (planejamento or "")[:20000]},
        ),
        role=skill_role("planner_consistency_v1"),
    ))
    parsed.setdefault("consistent", False)
    parsed.setdefault("conflicts", [])
    parsed.setdefault("warnings", [])
    return parsed


def _cover_markdown(snapshot: dict, core: dict) -> str:
    client = as_dict(snapshot.get("client"))
    campaign = as_dict(snapshot.get("campaign"))
    return "\n".join((
        "## Capa e controle da versão",
        f"Anunciante: {client_display_name(client) or 'A definir'}",
        f"Campanha: {text(campaign.get('name')) or 'A definir'}",
        f"Período: {text(as_dict(snapshot.get('period')).get('raw')) or 'A definir'}",
        f"Praça: {text(as_dict(snapshot.get('geography')).get('praca')) or 'A definir'}",
        f"Verba: {text(as_dict(snapshot.get('budget')).get('raw')) or 'A definir'}",
        f"Snapshot: {text(snapshot.get('snapshot_id'))}",
        f"Tese: {text(core.get('central_thesis'))}",
    ))


def _material_hash(row: dict) -> str:
    dados = as_dict((row or {}).get("dados_detectados"))
    campanha = as_dict(dados.get("campanha"))
    payload = {
        "briefing": text((row or {}).get("briefing_melhorado") or (row or {}).get("briefing_compilado")),
        "canais": as_list(campanha.get("canais") or dados.get("canais")),
        "verba": campanha.get("canais_verba") or campanha.get("verba") or (row or {}).get("budget"),
        "praca": campanha.get("praca") or dados.get("praca"),
        "periodo": campanha.get("periodo") or (row or {}).get("prazo"),
        "objetivo": (row or {}).get("objetivo") or dados.get("objetivo") or campanha.get("objetivo"),
        "media_params": dados.get("media_params") or campanha.get("media_params"),
        "anunciante_confidencial": as_bool(dados.get("anunciante_confidencial")),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _usable_core(core: dict, material_hash: str) -> bool:
    data = as_dict(core)
    return text(data.get("material_hash")) == material_hash and len(text(data.get("central_thesis"))) >= 20


def _usable_page(page: dict, material_hash: str, core: dict | None = None) -> bool:
    data = as_dict(page)
    thesis = text(as_dict(data.get("thesis")).get("statement"))
    if text(data.get("material_hash")) != material_hash or len(thesis) < 20:
        return False
    core_id = text(as_dict(core).get("id"))
    if core_id:
        return text(data.get("strategy_core_id")) == core_id
    return True


def _stale_generation(geracao: dict, *, minutes: int = 15) -> bool:
    if text(as_dict(geracao).get("status")) != "running":
        return False
    raw = text(as_dict(geracao).get("updatedAt"))
    if not raw:
        return False
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when > timedelta(minutes=minutes)


def _as_plan_markdown(raw: str) -> str:
    cleaned = normalize_markdown(raw)
    parsed = extract_json(cleaned)
    if not isinstance(parsed, dict):
        return cleaned
    lines = []
    mapping = (
        ("why_this_plan", "Por que este plano"),
        ("why_this_mix", "Por que este mix"),
        ("expected_benefits", "Benefícios defendíveis"),
        ("approval_argument", "Argumento de aprovação"),
    )
    for key, title in mapping:
        value = parsed.get(key)
        if isinstance(value, list) and value:
            lines.append("## " + title + "\n" + "\n".join(f"- {text(item)}" for item in value if text(item)))
        elif text(value):
            lines.append("## " + title + "\n" + text(value))
    for item in as_list(parsed.get("objections")):
        row = as_dict(item)
        if text(row.get("objection")):
            lines.append(f"### {text(row.get('objection'))}\n{text(row.get('response'))}")
    return normalize_markdown("\n\n".join(lines)) or cleaned


def _has_llm() -> bool:
    try:
        from ..services.openrouter_service import resolve_api_key, resolve_openai_api_key
        return bool(resolve_openai_api_key() or resolve_api_key())
    except Exception:
        return False


def _require_llm(etapa: str) -> None:
    if _has_llm():
        return
    raise ValueError(
        f"Não há credencial de IA para gerar o {etapa}. "
        "Configure a OpenAI nativa ou o OpenRouter em Parâmetros → Integrações."
    )


def _publish_folha(token: str, folha: dict) -> None:
    update_session(token, {
        "plan_content": folha,
        "schema_version": 3,
        "canvas_layout": {
            "mode": "one_page",
            "generatedAt": (folha.get("meta") or {}).get("updatedAt"),
            "presenter": (folha.get("meta") or {}).get("presenter"),
        },
    })
