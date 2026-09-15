import hashlib
import re
from pathlib import Path

from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import login_required, login_required_api
from .catalog import CADU_MEDIA_PLANNING, DIRECTORY_SKILLS, PUBLIC_SKILLS, get_public_skill
from .consultations import consultation_state


bp = Blueprint("cadu_skills", __name__, url_prefix="/skills")


@bp.get("/assets/skills-icon-<int:size>.png")
def skills_icon(size):
    if size not in {32, 64}:
        abort(404)
    asset = Path(__file__).resolve().parents[2] / "output" / "mockups" / "brand-assets" / "icons-2d" / "skills" / f"icon-{size}.png"
    return send_file(asset, mimetype="image/png", max_age=86400)


@bp.get("")
@bp.get("/")
def marketplace():
    return render_template("cadu_skills/marketplace.html", skills=DIRECTORY_SKILLS, featured=CADU_MEDIA_PLANNING)


@bp.get("/<slug>")
def detail(slug):
    skill = get_public_skill(slug)
    if not skill:
        abort(404)
    state = consultation_state(session.get(f"skill_preview_{slug}", 0), is_client=bool(session.get("user_id")))
    return render_template("cadu_skills/detail.html", skill=skill, preview_state=state)


@bp.get("/diretorio/<slug>")
def directory_detail(slug):
    skill = next((item for item in DIRECTORY_SKILLS if item["slug"] == slug), None)
    if not skill:
        abort(404)
    return render_template("cadu_skills/directory_detail.html", skill=skill)


@bp.get("/s/<token>")
def shared_skill(token):
    """URL estável e não enumerável para uma personalização premium publicada."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,96}", token):
        abort(404)
    try:
        from ..db import get_db
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with get_db().cursor() as cursor:
            cursor.execute(
                """
                SELECT c.name, c.context_json, s.permission, s.expires_at,
                       d.name AS base_name, d.summary, d.category
                  FROM cadu_skill_shares s
                  JOIN cadu_skill_customizations c ON c.id = s.customization_id
                  JOIN cadu_skill_versions v ON v.id = c.skill_version_id
                  JOIN cadu_skill_definitions d ON d.id = v.skill_id
                 WHERE s.token_hash = %s AND s.revoked_at IS NULL
                   AND (s.expires_at IS NULL OR s.expires_at > NOW())
                   AND c.status = 'published'
                 LIMIT 1
                """,
                (token_hash,),
            )
            shared = cursor.fetchone()
    except Exception:
        shared = None
    if not shared:
        abort(404)
    return render_template("cadu_skills/shared.html", shared=shared)


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
    skill = get_public_skill(slug)
    if not skill:
        return jsonify({"success": False, "error": "Skill não encontrada."}), 404
    if session.get("user_id"):
        return jsonify({"success": False, "code": "CLIENT_STUDIO", "studio_url": url_for("cadu_skills.studio"), "error": "Use o Studio para acessar sua skill e seus dados exclusivos."}), 409
    key = f"skill_preview_{slug}"
    before = consultation_state(session.get(key, 0))
    if not before["allowed"]:
        return jsonify({"success": False, "code": "FREE_LIMIT", "state": before, "start_url": url_for("cadu_skills.start"), "error": "Você concluiu as três prévias gratuitas desta skill."}), 429
    prompt = str((request.get_json(silent=True) or {}).get("prompt") or "").strip()
    if len(prompt) < 12:
        return jsonify({"success": False, "error": "Conte um pouco mais sobre a campanha."}), 400
    session[key] = before["count"] + 1
    state = consultation_state(session[key])
    return jsonify({
        "success": True,
        "state": state,
        "answer": "Comece definindo objetivo, público, praça, período e verba. Com esses cinco pontos, a skill compara papéis de canal e evita distribuir investimento antes de existir uma tese de mídia.",
        "start_url": url_for("cadu_skills.start"),
    })


@bp.get("/studio")
@login_required
def studio():
    return render_template("cadu_skills/studio.html", skill=CADU_MEDIA_PLANNING)


@bp.post("/api/<slug>/runs")
@login_required_api
def create_run(slug):
    skill = get_public_skill(slug)
    if not skill:
        return jsonify({"success": False, "error": "Skill não encontrada."}), 404
    return jsonify({
        "success": False,
        "code": "CREDITS_NOT_ENABLED",
        "error": "O ledger de créditos ainda não foi ativado. Nenhum crédito foi debitado.",
        "required_credits": skill["credit_cost"],
        "user_id": session.get("user_id"),
    }), 409
