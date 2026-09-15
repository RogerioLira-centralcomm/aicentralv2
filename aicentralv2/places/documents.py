"""Documentos comerciais persistentes para Places.

O conteúdo é sempre composto a partir de um snapshot do Place. Assim uma proposta
baixada no futuro continua sendo a mesma que foi revisada pelo comercial.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from html import escape
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from psycopg.types.json import Json
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ..db import get_db
from ..services.openrouter_service import OpenRouterError, chat_completion
from .repository import PlaceNotFound, get_by_id
from .schema import public_view, text

DOCUMENT_TYPES = {"proposal_deck", "technical_sheet"}
DOCUMENT_MODEL = os.getenv("PLACES_DOCUMENT_MODEL", "openai/gpt-5-nano")


def _row(row):
    return dict(row) if row else None


def _slug(*parts: str) -> str:
    raw = "-".join(text(part) for part in parts if text(part))
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower() or "centralcomm"


def _now_label(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def filename(document: dict, place: dict) -> str:
    return "%s.pdf" % _slug(
        document.get("agency_name") or "CentralComm",
        document.get("campaign_name"),
        place.get("slug") or place.get("title"),
        _now_label(place.get("created_at")),
        "v%s" % document.get("version", 1),
    )


def _source_snapshot(place: dict) -> dict:
    view = public_view(place)
    metrics = dict(view.get("metrics") or {})
    for key, metric in list(metrics.items()):
        if isinstance(metric, dict) and metric.get("source_status") == "to_validate":
            metrics[key] = {**metric, "value": None, "label": ""}
    investment = dict(view.get("investment") or {})
    if investment.get("source_status") == "to_validate":
        investment["value"], investment["label"] = None, ""
    points = []
    for item in view.get("points") or []:
        point = dict(item)
        if point.get("reach_status") == "to_validate": point["reach"] = ""
        if "validar" in text(point.get("note")).lower(): point["note"] = ""
        points.append(point)
    return {
        "place_id": view.get("id"), "slug": view.get("slug"), "title": view.get("title"),
        "city_label": view.get("city_label"), "type_label": view.get("type_label"),
        "subtitle": view.get("subtitle"), "metrics": metrics, "points": points,
        "target_audience": view.get("target_audience"), "investment": investment,
        "planning": view.get("planning"), "inventory": view.get("inventory"), "defense": view.get("defense"),
        "offer": view.get("offer"), "media": view.get("media"), "methodology": view.get("methodology"),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def _content(snapshot: dict, instruction: str = "") -> dict:
    points = snapshot.get("points") or []
    first = points[0] if points else {}
    investment = (snapshot.get("investment") or {}).get("label") or "Sob consulta"
    defense = snapshot.get("defense") or {}
    planning = snapshot.get("planning") or {}
    return {
        "title": snapshot.get("title") or "Place",
        "subtitle": snapshot.get("subtitle") or "Recorte comercial para campanhas de mídia.",
        "summary": defense.get("lead") or (snapshot.get("offer") or {}).get("lead") or "Oportunidade de presença contextual no celular.",
        "slides": [
            {"title": "Oportunidade", "body": defense.get("body") or snapshot.get("subtitle") or ""},
            {"title": "Público e evidências", "body": " · ".join(snapshot.get("target_audience") or []) or "Dados sob validação comercial."},
            {"title": "Ponto comercial", "body": first.get("name") or "Ponto a confirmar"},
            {"title": "Plano de presença", "body": " · ".join(planning.get("channels") or []) or "Mix definido após validação de inventário."},
            {"title": "Investimento", "body": investment},
        ],
        "instruction": text(instruction),
    }


def _quality(snapshot: dict) -> dict:
    warnings = []
    if not (snapshot.get("points") or []): warnings.append("Inclua ao menos um ponto comercial antes de enviar a proposta.")
    if not (snapshot.get("media") or {}).get("hero_url"): warnings.append("A proposta será exportada sem foto principal aprovada.")
    if not (snapshot.get("investment") or {}).get("label"): warnings.append("Investimento será mostrado como sob consulta.")
    return {"ok": not warnings, "warnings": warnings, "reviewed_at": datetime.now(timezone.utc).isoformat()}


def _agent_content(snapshot: dict, instruction: str, fallback: dict) -> tuple[dict, str]:
    """Refina a narrativa, nunca os dados. Falha silenciosa preserva o rascunho seguro."""
    compact = {
        "title": snapshot.get("title"), "city": snapshot.get("city_label"), "subtitle": snapshot.get("subtitle"),
        "audience": snapshot.get("target_audience"), "points": [{"name": row.get("name"), "formats": row.get("formats"), "reach": row.get("reach")} for row in snapshot.get("points") or []],
        "investment": (snapshot.get("investment") or {}).get("label"), "channels": (snapshot.get("planning") or {}).get("channels"),
        "defense": snapshot.get("defense"), "offer": snapshot.get("offer"),
    }
    messages = [
        {"role": "system", "content": "Você é o revisor comercial do CentralComm Places. Escreva somente uma narrativa curta em português. Não crie, altere ou complete números, alcances, preços, fontes, canais ou inventário. Responda JSON: {summary:string, slides:[{title:string,body:string}]}, com no máximo 5 slides."},
        {"role": "user", "content": "Dados aprovados do Place:\n%s\nOrientação comercial: %s" % (json.dumps(compact, ensure_ascii=False), instruction or "Seja objetivo e claro.")},
    ]
    try:
        response = chat_completion(messages, model=DOCUMENT_MODEL, max_tokens=900, temperature=0.2, response_format={"type": "json_object"}, timeout=45)
        raw = (response.get("message") or {}).get("content") or "{}"
        parsed = json.loads(raw if isinstance(raw, str) else "{}")
        slides = parsed.get("slides") if isinstance(parsed.get("slides"), list) else []
        cleaned = [{"title": text(item.get("title")), "body": text(item.get("body"))} for item in slides if isinstance(item, dict) and text(item.get("title"))][:5]
        if cleaned:
            result = dict(fallback); result["summary"] = text(parsed.get("summary")) or fallback["summary"]; result["slides"] = cleaned
            return result, response.get("model") or DOCUMENT_MODEL
    except (OpenRouterError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return fallback, "fallback"


def _latest(place_id: int, document_type: str) -> dict | None:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""SELECT * FROM cx_place_documents WHERE place_id=%s AND document_type=%s
                       ORDER BY version DESC LIMIT 1""", (place_id, document_type))
        return _row(cur.fetchone())


def list_documents(place_id: int) -> list[dict]:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM cx_place_documents WHERE place_id=%s ORDER BY document_type, version DESC", (place_id,))
        return [_row(item) for item in (cur.fetchall() or [])]


def save_document(place_id: int, document_type: str, data: dict, user_id: int | None = None) -> dict:
    if document_type not in DOCUMENT_TYPES: raise ValueError("Tipo de documento inválido.")
    place = get_by_id(place_id)
    current = _latest(place_id, document_type)
    # Nunca alteramos uma versão já exportada: a edição abre a próxima versão.
    version = (int(current["version"]) + 1) if current and current.get("status") == "exported" else int((current or {}).get("version") or 1)
    snapshot = _source_snapshot(place)
    instruction = text(data.get("agent_instruction"))
    content, model = _agent_content(snapshot, instruction, _content(snapshot, instruction))
    quality = _quality(snapshot)
    quality["model"] = model
    values = {
        "place_id": place_id, "document_type": document_type, "agency_name": text(data.get("agency_name")) or None,
        "campaign_name": text(data.get("campaign_name")) or None, "brand_name": text(data.get("brand_name")) or "CentralComm",
        "version": version, "status": "reviewed" if data.get("review") else "draft", "agent_instruction": instruction,
        "content": Json(content), "quality_report": Json(quality), "source_snapshot": Json(snapshot), "user_id": user_id,
    }
    conn = get_db()
    with conn.cursor() as cur:
        if current and current.get("status") != "exported":
            cur.execute("""UPDATE cx_place_documents SET agency_name=%(agency_name)s, campaign_name=%(campaign_name)s,
                brand_name=%(brand_name)s, status=%(status)s, agent_instruction=%(agent_instruction)s,
                content=%(content)s, quality_report=%(quality_report)s, source_snapshot=%(source_snapshot)s,
                updated_by=%(user_id)s, updated_at=now() WHERE id=%s RETURNING *""", {**values, "id": current["id"]})
        else:
            cur.execute("""INSERT INTO cx_place_documents (place_id, document_type, agency_name, campaign_name, brand_name,
                version, status, agent_instruction, content, quality_report, source_snapshot, created_by, updated_by)
                VALUES (%(place_id)s,%(document_type)s,%(agency_name)s,%(campaign_name)s,%(brand_name)s,%(version)s,%(status)s,
                %(agent_instruction)s,%(content)s,%(quality_report)s,%(source_snapshot)s,%(user_id)s,%(user_id)s) RETURNING *""", values)
        result = _row(cur.fetchone())
    conn.commit()
    return result


def _line(c, value, x, y, max_width, font="Helvetica", size=16, leading=22, color=HexColor("#141414")):
    c.setFillColor(color); c.setFont(font, size)
    words, line = str(value or "").split(), ""
    for word in words:
        candidate = (line + " " + word).strip()
        if stringWidth(candidate, font, size) > max_width and line:
            c.drawString(x, y, line); y -= leading; line = word
        else: line = candidate
    if line: c.drawString(x, y, line); y -= leading
    return y


def _deck_html(document: dict, place: dict) -> str:
    """Deck em páginas HTML 16:9; a fonte do PDF comercial segue a skill Slides."""
    content = document.get("content") or {}; snapshot = document.get("source_snapshot") or {}
    slides = [{"title": content.get("title"), "body": content.get("subtitle")},
              {"title": content.get("summary"), "body": "Place: %s" % snapshot.get("city_label", "")}] + list(content.get("slides") or [])
    pages = "".join(
        "<section class='slide'><header>%s</header><main><h1>%s</h1><p>%s</p></main><footer>%s · v%s · %s</footer></section>" % (
            escape(str(document.get("brand_name") or "CentralComm")), escape(str(item.get("title") or "")),
            escape(str(item.get("body") or "")), escape(str(place.get("title") or "Place")),
            int(document.get("version") or 1), index + 1,
        ) for index, item in enumerate(slides)
    )
    return """<!doctype html><html><head><meta charset='utf-8'><style>
      @page { size: 10in 5.625in; margin: 0; } * { box-sizing: border-box; }
      body { margin: 0; font-family: Arial, sans-serif; color: #141414; }
      .slide { width: 960px; height: 540px; position: relative; padding: 42px 52px; background: #f7f8fa; page-break-after: always; border-left: 18px solid #1e4d4f; }
      header { color: #1e4d4f; font-size: 13px; font-weight: 700; } main { margin-top: 82px; max-width: 760px; }
      h1 { margin: 0 0 22px; font-size: 42px; line-height: 1.08; letter-spacing: -1.4px; } p { margin: 0; color: #334155; font-size: 23px; line-height: 1.38; }
      footer { position: absolute; right: 52px; bottom: 28px; color: #1e4d4f; font-size: 11px; }
    </style></head><body>""" + pages + "</body></html>"


def _deck_pdf_html(document: dict, place: dict) -> tuple[bytes, int] | None:
    try:
        from ..creative_html_compose import _browser_instance
        browser = _browser_instance(); page = browser.new_page(viewport={"width": 960, "height": 540})
        try:
            page.set_content(_deck_html(document, place), wait_until="load", timeout=15000)
            return page.pdf(width="10in", height="5.625in", print_background=True), len((document.get("content") or {}).get("slides") or []) + 2
        finally:
            page.close()
    except Exception:
        return None


def _pdf(document: dict, place: dict) -> tuple[bytes, int]:
    technical = document["document_type"] == "technical_sheet"
    if not technical:
        html_result = _deck_pdf_html(document, place)
        if html_result:
            return html_result
    size = A4 if technical else (960, 540)  # 16:9 deck, em pontos.
    buffer = BytesIO(); c = canvas.Canvas(buffer, pagesize=size); width, height = size
    content = document.get("content") or {}; snapshot = document.get("source_snapshot") or {}
    if technical:
        c.setFillColor(HexColor("#1E4D4F")); c.rect(0, height-70, width, 70, fill=1, stroke=0)
        c.setFillColor(white); c.setFont("Helvetica-Bold", 22); c.drawString(42, height-43, content.get("title") or "Ficha técnica")
        y = height-110
        for title, body in [("Contexto", content.get("subtitle")), ("Defesa", content.get("summary")), ("Pontos", " · ".join(item.get("name", "") for item in snapshot.get("points") or [])), ("Público", " · ".join(snapshot.get("target_audience") or [])), ("Investimento", (snapshot.get("investment") or {}).get("label") or "Sob consulta"), ("Premissa", (snapshot.get("methodology") or {}).get("body"))]:
            c.setFillColor(HexColor("#1E4D4F")); c.setFont("Helvetica-Bold", 12); c.drawString(42, y, title); y -= 20
            y = _line(c, body, 42, y, width-84, size=10, leading=14); y -= 14
            if y < 70: c.showPage(); y = height-60
        pages = 1
    else:
        slides = [{"title": content.get("title"), "body": content.get("subtitle")}, {"title": content.get("summary"), "body": "Place: %s" % snapshot.get("city_label", "")}] + list(content.get("slides") or [])
        for index, slide in enumerate(slides):
            c.setFillColor(HexColor("#F7F8FA")); c.rect(0, 0, width, height, fill=1, stroke=0)
            c.setFillColor(HexColor("#1E4D4F")); c.rect(0, 0, 18, height, fill=1, stroke=0)
            c.setFillColor(HexColor("#1E4D4F")); c.setFont("Helvetica-Bold", 10); c.drawString(52, height-42, document.get("brand_name") or "CentralComm")
            y = height-140; y = _line(c, slide.get("title"), 52, y, width-104, font="Helvetica-Bold", size=32, leading=39, color=HexColor("#141414")); y -= 22
            _line(c, slide.get("body"), 52, y, width-104, size=18, leading=27, color=HexColor("#334155"))
            c.setFillColor(HexColor("#1E4D4F")); c.setFont("Helvetica", 9); c.drawRightString(width-52, 30, "%s · v%s · %s" % (place.get("title"), document.get("version"), index+1))
            c.showPage()
        pages = len(slides)
    c.save(); return buffer.getvalue(), pages


def export_document(document_id: int, user_id: int | None = None) -> tuple[dict, bytes]:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM cx_place_documents WHERE id=%s", (document_id,)); document = _row(cur.fetchone())
    if not document: raise PlaceNotFound("Documento não encontrado.")
    place = get_by_id(int(document["place_id"]))
    artifact, pages = _pdf(document, place); digest = hashlib.sha256(artifact).hexdigest(); name = filename(document, place)
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO cx_place_document_exports (document_id, filename, content_hash, page_count, artifact, created_by)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (document_id, content_hash) DO UPDATE SET created_at=now()
            RETURNING id, document_id, filename, content_hash, page_count, mime_type, created_at""", (document_id, name, digest, pages, artifact, user_id))
        exported = _row(cur.fetchone())
        cur.execute("UPDATE cx_place_documents SET status='exported', updated_by=%s, updated_at=now() WHERE id=%s", (user_id, document_id))
    conn.commit(); return exported, artifact


def get_export(export_id: int) -> dict | None:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM cx_place_document_exports WHERE id=%s", (export_id,))
        return _row(cur.fetchone())
