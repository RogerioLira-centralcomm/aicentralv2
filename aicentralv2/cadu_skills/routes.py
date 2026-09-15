import csv
import hashlib
import io
import re
import secrets
import zipfile
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import admin_required, admin_required_api, login_required, login_required_api
from ..services.openrouter_service import OpenRouterError
from .catalog import (
    CADU_MEDIA_PLANNING, CADU_OFFICIAL_SKILLS, CATALOG_SKILLS,
    DEFERRED_SKILLS, DIRECTORY_SKILLS, TOP_SKILLS,
)
from .agents import CADU_AGENTS
from .consultations import consultation_state
from .repository import (
    all_owned_skills, create_share, credit_position, customization_as_skill, customization_markdown, customization_targets,
    finish_run, get_customization, list_customizations, managed_skills, record_event,
    reserve_run, revoke_shares, update_customization_links, update_managed_skill,
)
from .runtime import run_test_skill


bp = Blueprint("cadu_skills", __name__, url_prefix="/skills")


def _actor():
    if not session.get("cadu_skill_actor"):
        session["cadu_skill_actor"] = secrets.token_urlsafe(18)
    return session["cadu_skill_actor"]


def _top_skills():
    return managed_skills(TOP_SKILLS)


def all_cadu_skills():
    return all_owned_skills(CATALOG_SKILLS)


def _skill(slug):
    return next((item for item in all_cadu_skills() if item["slug"] == slug), None)


def _public_url(endpoint, **values):
    base = str(current_app.config.get("SKILLS_URL") or request.url_root).rstrip("/")
    return f"{base}{url_for(endpoint, **values)}"


def _skill_source(skill):
    source = Path(skill.get("path")) if skill and skill.get("path") else None
    return source if source and source.is_file() else None


def _skill_archive(skill):
    source = _skill_source(skill)
    if not source:
        return None
    package = io.BytesIO()
    skill_dir = source.parent
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, Path(skill["slug"]) / path.relative_to(skill_dir))
    return package.getvalue()


def _package_details(skill):
    source = _skill_source(skill)
    if not source:
        return None
    files = []
    datasets = []
    for path in sorted(source.parent.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(source.parent).as_posix()
        size = path.stat().st_size
        files.append({"path": relative, "size": size})
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                rows = sum(1 for _ in reader)
            datasets.append({"name": path.name, "rows": rows, "fields": len(header)})
    archive = _skill_archive(skill) or b""
    return {
        "files": files,
        "datasets": datasets,
        "file_count": len(files),
        "archive_size": len(archive),
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "download_url": _public_url("cadu_skills.download_skill", slug=skill["slug"]),
        "install_url": _public_url("cadu_skills.install_skill", slug=skill["slug"]),
        "instructions_url": _public_url("cadu_skills.install_skill", slug=skill["slug"], format="md"),
        "detail_url": _public_url("cadu_skills.detail", slug=skill["slug"]),
    }


def _shared_record(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,96}", token):
        return None
    try:
        from ..db import get_db
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with get_db().cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.name, c.summary AS custom_summary, c.image_url,
                       c.context_json, c.instructions, c.client_id, c.project_id,
                       s.permission, s.expires_at, d.slug AS base_slug,
                       d.name AS base_name, d.summary, d.category,
                       v.model, v.credit_cost, cli.nome_fantasia AS client_name,
                       p.nome AS project_name
                  FROM cadu_skill_shares s
                  JOIN cadu_skill_customizations c ON c.id = s.customization_id
                  JOIN cadu_skill_versions v ON v.id = c.skill_version_id
                  JOIN cadu_skill_definitions d ON d.id = v.skill_id
             LEFT JOIN tbl_cliente cli ON cli.id_cliente = c.client_id
             LEFT JOIN cadu_projetos p ON p.id = c.project_id
                 WHERE s.token_hash = %s AND s.revoked_at IS NULL
                   AND (s.expires_at IS NULL OR s.expires_at > NOW())
                   AND c.status = 'published' LIMIT 1
                """,
                (token_hash,),
            )
            return cursor.fetchone()
    except Exception:
        return None


@bp.get("/assets/skills-icon-<int:size>.png")
def skills_icon(size):
    if size not in {32, 64}:
        abort(404)
    asset = Path(__file__).resolve().parents[2] / "output" / "mockups" / "brand-assets" / "icons-2d" / "skills" / f"icon-{size}.png"
    return send_file(asset, mimetype="image/png", max_age=86400)


@bp.get("")
@bp.get("/")
def marketplace():
    top = _top_skills()
    top_slugs = {item["slug"] for item in top}
    all_skills = all_cadu_skills()
    official_slugs = {item["slug"] for item in CADU_OFFICIAL_SKILLS}
    official = [item for item in all_skills if item["slug"] in official_slugs]
    owned = [item for item in all_skills if item["slug"] not in top_slugs | official_slugs]
    return render_template(
        "cadu_skills/marketplace.html", top_skills=top,
        official_skills=official, cadu_skills=owned, skills=DEFERRED_SKILLS,
        featured=top[0] if top else CADU_MEDIA_PLANNING,
    )


@bp.get("/<slug>")
def detail(slug):
    skill = _skill(slug)
    if not skill:
        abort(404)
    record_event(slug, "view", actor=_actor(), user_id=session.get("user_id"))
    state = consultation_state(session.get(f"skill_preview_{slug}", 0), is_client=bool(session.get("user_id")))
    return render_template(
        "cadu_skills/detail.html", skill=skill, preview_state=state,
        package=_package_details(skill) if skill.get("installable") else None,
    )


@bp.get("/install/<slug>")
def install_skill(slug):
    skill = _skill(slug)
    package = _package_details(skill) if skill and skill.get("installable") else None
    if not skill or not package:
        abort(404)
    if request.args.get("format") != "md":
        response = current_app.make_response(render_template("cadu_skills/install.html", skill=skill, package=package))
        response.headers.update({
            "Cache-Control": "public, max-age=300",
            "Link": f'<{package["download_url"]}>; rel="alternate"; type="application/zip", <{package["instructions_url"]}>; rel="alternate"; type="text/markdown"',
        })
        return response

    capabilities = "\n".join(f"- {item}" for item in skill.get("capabilities") or ())
    content = f"""---
name: {skill['slug']}
description: {skill.get('description') or skill.get('summary') or ''}
source: {package['detail_url']}
download: {package['download_url']}
sha256: {package['archive_sha256']}
---

# Instalar {skill['name']} em 2 passos

1. Baixe o ZIP: {package['download_url']}
2. Envie o ZIP completo ao seu ambiente GPT/Codex ou Claude e diga: **Instale esta skill.**

O ZIP já contém a pasta `{skill['slug']}`, o `SKILL.md` e todas as referências necessárias. Não envie os arquivos separadamente.

## Para automações

Baixe o arquivo indicado em `download`, valide o SHA-256 e instale o ZIP como uma única skill. Leia `SKILL.md` antes do primeiro uso.

## O que esta skill faz

{capabilities}

## Integridade

- Arquivos: {package['file_count']}
- Tamanho do ZIP: {package['archive_size']} bytes
- SHA-256: `{package['archive_sha256']}`
- Página pública: {package['detail_url']}
"""
    return Response(
        content,
        content_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
            "Content-Disposition": f'inline; filename="{skill["slug"]}-install.md"',
            "Link": f'<{package["download_url"]}>; rel="alternate"; type="application/zip"',
        },
    )


@bp.get("/<slug>/download")
def download_skill(slug):
    skill = _skill(slug)
    archive = _skill_archive(skill) if skill and skill.get("installable") else None
    if not skill or archive is None:
        abort(404)
    record_event(slug, "install", actor=_actor(), user_id=session.get("user_id"))
    return send_file(
        io.BytesIO(archive), mimetype="application/zip", as_attachment=True,
        download_name=f"{skill['slug']}.zip", max_age=0,
    )


@bp.get("/diretorio/<slug>")
def directory_detail(slug):
    if any(item["slug"] == slug for item in TOP_SKILLS):
        return redirect(url_for("cadu_skills.detail", slug=slug))
    skill = next((item for item in DIRECTORY_SKILLS if item["slug"] == slug), None)
    if not skill:
        abort(404)
    return render_template("cadu_skills/directory_detail.html", skill=skill)


@bp.get("/agentes")
def agents():
    return render_template("cadu_skills/agents.html", agents=CADU_AGENTS, skills=all_cadu_skills())


@bp.get("/s/<token>")
def shared_skill(token):
    """URL estável e não enumerável para uma personalização premium publicada."""
    shared = _shared_record(token)
    if not shared:
        abort(404)
    allowed_to_run = bool(
        shared["permission"] == "run" and session.get("user_id") and (
            session.get("is_centralcomm") or int(session.get("cliente_id") or 0) == int(shared["client_id"])
        )
    )
    return render_template(
        "cadu_skills/shared.html", shared=shared, token=token,
        allowed_to_run=allowed_to_run,
    )


@bp.post("/s/<token>/run")
@login_required_api
def shared_skill_run(token):
    shared = _shared_record(token)
    if not shared or shared["permission"] != "run":
        return jsonify({"success": False, "error": "Este link não permite execução."}), 404
    if not session.get("is_centralcomm") and int(session.get("cliente_id") or 0) != int(shared["client_id"]):
        return jsonify({"success": False, "error": "Esta skill pertence a outra organização."}), 403
    prompt = str((request.get_json(silent=True) or {}).get("prompt") or "").strip()
    base = _skill(shared["base_slug"])
    if not base:
        return jsonify({"success": False, "error": "A skill-base não está disponível."}), 409
    skill = customization_as_skill(dict(shared), base)
    try:
        reservation = reserve_run(
            skill, client_id=int(shared["client_id"]), user_id=int(session["user_id"]),
            prompt=prompt, customization_id=int(shared["id"]),
        )
        result = run_test_skill(skill, prompt)
        finish_run(reservation, success=True, result=result)
        return jsonify({
            "success": True, "answer": result["answer"], "charged_credits": reservation["cost"],
            "remaining_credits": max(0, reservation["balance_before"] - reservation["cost"]),
        })
    except ValueError as exc:
        if "reservation" in locals():
            finish_run(reservation, success=False, error_code=type(exc).__name__)
        return jsonify({"success": False, "error": str(exc), "charged_credits": 0}), 409
    except (RuntimeError, OpenRouterError) as exc:
        if "reservation" in locals():
            finish_run(reservation, success=False, error_code=type(exc).__name__)
        return jsonify({"success": False, "error": str(exc), "charged_credits": 0}), 503


@bp.route("/comecar", methods=("GET", "POST"))
def start():
    if session.get("user_id"):
        return redirect(url_for("cadu_skills.studio"))
    submitted = False
    error = ""
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:160]
        email = (request.form.get("email") or "").strip().lower()[:180]
        company = (request.form.get("company") or "").strip()[:180]
        if not name or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            error = "Informe seu nome e um e-mail profissional válido."
        else:
            try:
                from .. import db
                db.criar_lead({
                    "nome": name,
                    "email": email,
                    "empresa": company,
                    "mensagem": "Solicitou acesso ao Cadu Skills após experimentar o marketplace público.",
                    "origem": "cadu-skills",
                    "canal": "site",
                    "interesse": "Cadu Skills e ecossistema CentralX",
                    "fonte": "site",
                    "status": "inbox",
                    "potencial": "alto",
                    "tipo_lead": "cliente",
                })
                submitted = True
            except Exception:
                error = "Não foi possível registrar agora. Tente novamente em alguns minutos."
    return render_template("cadu_skills/start.html", submitted=submitted, error=error)


@bp.post("/api/public/<slug>/preview")
def public_preview(slug):
    skill = _skill(slug)
    if not skill:
        return jsonify({"success": False, "error": "Skill não encontrada."}), 404
    if not skill.get("is_testable", True) or skill.get("status") != "published":
        return jsonify({"success": False, "code": "NOT_TESTABLE", "error": "Esta skill está em revisão e ainda não pode ser testada."}), 409
    key = f"skill_preview_{slug}"
    before = consultation_state(session.get(key, 0), is_client=bool(session.get("user_id")))
    if not before["allowed"]:
        return jsonify({"success": False, "code": "FREE_LIMIT", "state": before, "start_url": url_for("cadu_skills.start"), "error": "Você concluiu as três prévias gratuitas desta skill."}), 429
    prompt = str((request.get_json(silent=True) or {}).get("prompt") or "").strip()
    if len(prompt) < 12:
        return jsonify({"success": False, "error": "Conte um pouco mais sobre a campanha."}), 400
    installed = set(session.get("cadu_test_skills") or ())
    if slug not in installed:
        installed.add(slug)
        session["cadu_test_skills"] = sorted(installed)
        record_event(slug, "install", actor=_actor(), user_id=session.get("user_id"))
    record_event(slug, "run_started", actor=_actor(), user_id=session.get("user_id"))
    try:
        result = run_test_skill(skill, prompt)
    except (ValueError, RuntimeError, OpenRouterError) as exc:
        record_event(slug, "run_failed", actor=_actor(), user_id=session.get("user_id"), metadata={"error": type(exc).__name__})
        return jsonify({"success": False, "error": str(exc)}), 503
    session[key] = before["count"] + 1
    state = consultation_state(session[key], is_client=bool(session.get("user_id")))
    record_event(slug, "run_succeeded", actor=_actor(), user_id=session.get("user_id"), metadata={"model": result.get("model")})
    return jsonify({"success": True, "state": state, "answer": result["answer"], "model": result.get("model"), "start_url": url_for("cadu_skills.start")})


@bp.post("/api/public/<slug>/events")
def public_event(slug):
    if not _skill(slug):
        return jsonify({"success": False}), 404
    event_type = str((request.get_json(silent=True) or {}).get("event") or "")
    if event_type != "copy":
        return jsonify({"success": False}), 400
    return jsonify({"success": record_event(slug, event_type, actor=_actor(), user_id=session.get("user_id"))})


@bp.get("/studio")
@login_required
def studio():
    skills = all_cadu_skills()
    selected = next((item for item in skills if item["slug"] == request.args.get("skill")), skills[0])
    return render_template(
        "cadu_skills/studio.html", skill=selected, skills=skills,
        credit_position=credit_position(int(session.get("cliente_id") or 0)),
    )


@bp.post("/api/<slug>/runs")
@login_required_api
def create_run(slug):
    skill = _skill(slug)
    if not skill:
        return jsonify({"success": False, "error": "Skill não encontrada."}), 404
    prompt = str((request.get_json(silent=True) or {}).get("prompt") or "").strip()
    try:
        reservation = reserve_run(
            skill, client_id=int(session.get("cliente_id") or 0),
            user_id=int(session["user_id"]), prompt=prompt,
        )
    except ValueError as exc:
        return jsonify({"success": False, "code": "CREDITS_UNAVAILABLE", "error": str(exc), "required_credits": skill["credit_cost"]}), 409
    try:
        result = run_test_skill(skill, prompt)
        finish_run(reservation, success=True, result=result)
        record_event(slug, "run_succeeded", actor=_actor(), user_id=session.get("user_id"), metadata={"billed": reservation["cost"]})
        return jsonify({
            "success": True, "answer": result["answer"], "charged_credits": reservation["cost"],
            "remaining_credits": max(0, reservation["balance_before"] - reservation["cost"]),
        })
    except (ValueError, RuntimeError, OpenRouterError) as exc:
        finish_run(reservation, success=False, error_code=type(exc).__name__)
        record_event(slug, "run_failed", actor=_actor(), user_id=session.get("user_id"), metadata={"billed": 0})
        return jsonify({"success": False, "error": str(exc), "charged_credits": 0}), 503


@bp.get("/gestao")
@admin_required
def management():
    rows = all_cadu_skills()
    targets = customization_targets()
    totals = {key: sum(int(item.get(key) or 0) for item in rows) for key in ("views", "copies", "installs", "runs")}
    return render_template(
        "cadu_skills/management.html", skills=rows, totals=totals,
        deferred_count=len(DEFERRED_SKILLS), customizations=list_customizations(),
        clients=targets["clients"], projects=targets["projects"],
    )


@bp.post("/api/gestao/<slug>")
@admin_required_api
def management_update(slug):
    skill = _skill(slug)
    if not skill:
        return jsonify({"success": False, "error": "Skill não encontrada."}), 404
    data = request.get_json(silent=True) or {}
    try:
        payload = {
            "name": str(data.get("name") or skill["name"]).strip()[:180],
            "summary": str(data.get("summary") or skill["summary"]).strip()[:1200],
            "category": str(data.get("category") or skill["category"]).strip()[:100],
            "image_url": str(data.get("image_url") or "").strip()[:1000],
            "display_rank": max(1, min(999, int(data.get("display_rank") or skill.get("rank") or 999))),
            "status": str(data.get("status") or "published") if str(data.get("status") or "published") in {"draft", "published", "archived"} else "draft",
            "is_testable": bool(data.get("is_testable")),
            "model": str(data.get("model") or skill["model"]).strip()[:100],
            "credit_cost": max(1, min(100, int(data.get("credit_cost") or skill["credit_cost"]))),
            "instructions": str(data.get("instructions") or skill["instructions"]).strip()[:30000],
        }
        if not payload["name"] or not payload["summary"] or not payload["instructions"]:
            raise ValueError("Nome, resumo e instruções são obrigatórios.")
        if not update_managed_skill(slug, payload, int(session["user_id"])):
            raise ValueError("Aplique as migrations do Cadu Skills antes de editar.")
        return jsonify({"success": True, "message": "Skill atualizada."})
    except (ValueError, TypeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.get("/gestao/personalizadas/<int:customization_id>/download")
@admin_required
def customization_download(customization_id):
    row = get_customization(customization_id)
    if not row:
        abort(404)
    base = _skill(row["base_slug"])
    if not base:
        abort(409)
    content = customization_markdown(row, customization_as_skill(row, base))
    filename = re.sub(r"[^a-z0-9-]+", "-", str(row["name"]).lower()).strip("-") or "skill-cadu"
    return Response(
        content, mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
    )


@bp.post("/api/gestao/personalizadas/<int:customization_id>/vinculo")
@admin_required_api
def customization_link_targets(customization_id):
    data = request.get_json(silent=True) or {}
    try:
        client_id = int(data.get("client_id") or 0)
        project_id = int(data["project_id"]) if data.get("project_id") else None
        brand_id = int(data["brand_id"]) if data.get("brand_id") else None
        if client_id < 1:
            raise ValueError("Selecione um cliente.")
        if not update_customization_links(
            customization_id, client_id=client_id, project_id=project_id, brand_id=brand_id,
        ):
            return jsonify({"success": False, "error": "Skill personalizada não encontrada."}), 404
        return jsonify({"success": True, "message": "Cliente, projeto e marca atualizados."})
    except (ValueError, TypeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.post("/api/gestao/personalizadas/<int:customization_id>/link")
@admin_required_api
def customization_link(customization_id):
    row = get_customization(customization_id)
    if not row or row.get("status") != "published":
        return jsonify({"success": False, "error": "Publique a skill antes de gerar o link."}), 409
    permission = str((request.get_json(silent=True) or {}).get("permission") or "view")
    token = create_share(customization_id, user_id=int(session["user_id"]), permission=permission)
    public_base = str(current_app.config.get("SKILLS_URL") or request.url_root).rstrip("/")
    return jsonify({
        "success": True,
        "url": f"{public_base}{url_for('cadu_skills.shared_skill', token=token)}",
        "message": "Link não listado criado. Guarde-o: o token não poderá ser recuperado depois.",
    })


@bp.post("/api/gestao/personalizadas/<int:customization_id>/revogar-links")
@admin_required_api
def customization_revoke_links(customization_id):
    if not get_customization(customization_id):
        return jsonify({"success": False, "error": "Skill personalizada não encontrada."}), 404
    count = revoke_shares(customization_id)
    return jsonify({"success": True, "message": f"{count} link(s) revogado(s)."})


@bp.post("/api/gestao/personalizadas/<int:customization_id>/test")
@admin_required_api
def customization_test(customization_id):
    data = request.get_json(silent=True) or {}
    if data.get("confirm_charge") is not True:
        return jsonify({"success": False, "error": "Confirme o uso dos créditos do cliente."}), 400
    row = get_customization(customization_id)
    if not row:
        return jsonify({"success": False, "error": "Skill personalizada não encontrada."}), 404
    base = _skill(row["base_slug"])
    if not base:
        return jsonify({"success": False, "error": "A skill-base não está disponível."}), 409
    skill = customization_as_skill(row, base)
    prompt = str(data.get("prompt") or "").strip()
    try:
        reservation = reserve_run(
            skill, client_id=int(row["client_id"]), user_id=int(session["user_id"]),
            prompt=prompt, customization_id=customization_id,
        )
        result = run_test_skill(skill, prompt)
        finish_run(reservation, success=True, result=result)
        return jsonify({
            "success": True, "answer": result["answer"], "charged_credits": reservation["cost"],
            "remaining_credits": max(0, reservation["balance_before"] - reservation["cost"]),
        })
    except ValueError as exc:
        if "reservation" in locals():
            finish_run(reservation, success=False, error_code=type(exc).__name__)
        return jsonify({"success": False, "error": str(exc), "charged_credits": 0}), 409
    except (RuntimeError, OpenRouterError) as exc:
        if "reservation" in locals():
            finish_run(reservation, success=False, error_code=type(exc).__name__)
        return jsonify({"success": False, "error": str(exc), "charged_credits": 0}), 503
