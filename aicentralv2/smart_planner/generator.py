"""Gerador modular: snapshot → núcleo → one page → plano por grupos."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from . import canvas as canvas_mod
from . import one_page
from .ai import chat_json, chat_text
from .brand import brand_prompt_block
from .catalog import PLAN_MODES
from .cost import bound_session
from .estimates import calculate_estimates, format_estimates_for_prompt
from .helpers import as_dict, as_list, extract_json, normalize_markdown, plan_mode_of, text
from .images import apply_sheet_art
from .progress import finish_progress, mark_step, start_progress
from .repository import get_by_token, merge_dados, update_session
from .skills import load_skill, skill_role
from .snapshot import build_evidence, build_snapshot

logger = logging.getLogger(__name__)


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
        page["material_hash"] = material_hash
        folha = _materialize_folha(token, snapshot, page, core)
        merge_dados(token, {"one_page_v2": page, "folha": folha})
        mark_step(token, "one_page", "done")

    mark_step(token, "validate", "running")
    _validate_page(page, snapshot, estimates)
    mark_step(token, "validate", "done")

    if _has_image_provider():
        mark_step(token, "images", "running")
        try:
            folha = apply_sheet_art(folha)
            merge_dados(token, {"folha": folha})
            mark_step(token, "images", "done")
        except Exception:
            logger.exception("Imagem da folha falhou; o texto segue.")
            mark_step(token, "images", "skipped")
    else:
        mark_step(token, "images", "skipped")

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
    merge_dados(token, {
        "planejamento": final,
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


def _pack(snapshot: dict, evidence: dict, core: dict | None = None, estimates: dict | None = None, extra: dict | None = None) -> str:
    snap = dict(snapshot or {})
    if len(text(snap.get("briefing"))) > 8000:
        snap["briefing"] = text(snap.get("briefing"))[:8000]
    pack_evidence = dict(evidence or {})
    if len(text(pack_evidence.get("briefing"))) > 8000:
        pack_evidence["briefing"] = text(pack_evidence.get("briefing"))[:8000]
    estimates_note = format_estimates_for_prompt(estimates or {})
    payload = {
        "snapshot": snap,
        "evidence": pack_evidence,
        "strategy_core": core or {},
        "brand": brand_prompt_block(as_dict((snapshot or {}).get("brand"))),
    }
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
        "Sintetize o núcleo neste One Page. Não invente tese nova.\n\n" + _pack(snapshot, evidence, core, estimates),
        role=skill_role("planner_one_page_v2"),
    ))
    parsed.setdefault("result_estimates", {})
    parsed["result_estimates"].setdefault("status", estimates.get("status"))
    if not text(as_dict(parsed.get("result_estimates")).get("summary")):
        parsed["result_estimates"]["summary"] = format_estimates_for_prompt(estimates)
    parsed["snapshot_id"] = text(snapshot.get("snapshot_id"))
    parsed["strategy_core_id"] = text(core.get("id"))
    return parsed


def _materialize_folha(token: str, snapshot: dict, page: dict, core: dict) -> dict:
    row = get_by_token(token)
    dados = as_dict(row.get("dados_detectados"))
    meta = canvas_mod._row_meta(row, dados)
    client = text((snapshot.get("client") or {}).get("name") or meta.get("client"))
    agency = text((snapshot.get("client") or {}).get("agency") or meta.get("agency"))
    branding = one_page.resolve_branding(
        client,
        agency,
        text(dados.get("presenter_brand")) or "centralcomm",
        [],
        cliente_id=dados.get("cliente_id"),
        agencia_id=dados.get("agencia_id"),
        brand=as_dict(dados.get("brand")),
    )
    theme = one_page.compose_theme(client, agency, text(snapshot.get("briefing")), None)
    share = one_page.share_payload(text(dados.get("public_token")), client)
    plan = one_page.assemble_from_v2(
        {**meta, "client": client, "agency": agency, "presenter": branding["presenter"]["id"]},
        branding,
        theme,
        share,
        page,
        core,
        snapshot.get("snapshot_id"),
    )
    merge_dados(token, {
        "presenter_brand": plan["meta"]["presenter"],
        "public_token": plan["share"]["public_token"],
    })
    return plan


def _validate_page(page: dict, snapshot: dict, estimates: dict) -> None:
    thesis = text(as_dict(page.get("thesis")).get("statement"))
    if len(thesis) < 20:
        raise ValueError("A tese da página única voltou vazia. Gere novamente.")
    rec = text(as_dict(page.get("recommendation")).get("summary"))
    if len(rec) < 12:
        raise ValueError("A recomendação da página única voltou vazia. Gere novamente.")
    client = text(as_dict((snapshot or {}).get("client")).get("name"))
    if client and client.lower() not in f"{thesis} {rec}".lower():
        raise ValueError("A tese não nomeia o anunciante. Gere novamente.")
    approved = {text(item) for item in as_list((snapshot or {}).get("channels")) if text(item)}
    mix_ids = {text(as_dict(row).get("id")) for row in as_list((snapshot or {}).get("mix")) if text(as_dict(row).get("id"))}
    extras = []
    for item in as_list(as_dict(page.get("recommendation")).get("channel_roles")):
        channel = text(as_dict(item).get("channel") or as_dict(item).get("id"))
        if not channel or channel.lower() in {"a definir", "definir"}:
            continue
        if approved and channel not in approved and channel not in mix_ids:
            extras.append(channel)
    if extras:
        raise ValueError("A página única usou canais não aprovados: " + ", ".join(extras[:4]))
    result = as_dict(page.get("result_estimates"))
    if result.get("status") == "available" and as_dict(estimates).get("status") != "available":
        page["result_estimates"]["status"] = "not_available"
        page["result_estimates"]["summary"] = format_estimates_for_prompt(estimates)


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
    raw = chat_text(system, user, role=skill_role(skill), timeout=120)
    return normalize_markdown(raw)


def _consistency_check(snapshot: dict, core: dict, page: dict, planejamento: str) -> dict:
    parsed = as_dict(chat_json(
        load_skill("planner_truth_v1") + "\n\n" + load_skill("planner_consistency_v1"),
        json.dumps(
            {
                "snapshot": snapshot,
                "strategy_core": core,
                "one_page": page,
                "planejamento": (planejamento or "")[:20000],
            },
            ensure_ascii=False,
            default=str,
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
        f"Cliente: {text(client.get('name')) or 'A definir'}",
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


def _has_image_provider() -> bool:
    return _has_llm()


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
