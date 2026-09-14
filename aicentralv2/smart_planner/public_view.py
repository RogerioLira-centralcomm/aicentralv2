"""Documento público do Smart Planner — só folha e plano, marca Centralcomm."""

from __future__ import annotations

import re

from .helpers import as_bool, as_dict, as_list, normalize_markdown, plan_mode_of, session_title, text
from .share import HOUSE, public_sheet_url

BOARD_IDS = ("context", "strategy", "media", "execution")
SHEET_TYPES = ("strategy", "creative", "market", "defense")


def _cards(plan: dict) -> list[dict]:
    out = []
    for section in as_list((plan or {}).get("sections")):
        for card in as_list(as_dict(section).get("cards")):
            item = as_dict(card)
            if text(item.get("body") or item.get("title") or item.get("image_url") or item.get("stat")):
                out.append(item)
    return out


def _is_board(plan: dict) -> bool:
    ids = {text(as_dict(section).get("id")) for section in as_list((plan or {}).get("sections"))}
    return bool(ids & set(BOARD_IDS))


def _sheet_cards(plan: dict) -> dict:
    found = {}
    for card in _cards(plan):
        kind = text(card.get("type"))
        if kind in SHEET_TYPES and kind not in found:
            found[kind] = card
    return found


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.count("|") >= 2


def _is_sep_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells if cell)


def _blocks(raw: str) -> list[dict]:
    lines = raw.replace("\r\n", "\n").split("\n")
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_table_row(line):
            rows = []
            while i < len(lines) and _is_table_row(lines[i]):
                cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not _is_sep_row(cells):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append({"type": "table", "head": rows[0], "rows": rows[1:]})
            continue
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ")):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            if items:
                blocks.append({"type": "ul", "items": items})
            continue
        if stripped:
            chunk = [stripped]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip() or nxt.startswith("##") or _is_table_row(nxt) or nxt.strip().startswith(("- ", "* ")):
                    break
                chunk.append(nxt.strip())
                i += 1
            blocks.append({"type": "p", "text": " ".join(chunk)})
            continue
        i += 1
    return blocks


def plan_chapters(markdown: str) -> list[dict]:
    body = normalize_markdown(markdown).strip()
    if not body:
        return []
    chapters: list[dict] = []
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            if current:
                chapters.append(current)
            current = {"title": line[3:].strip(), "blocks": []}
            continue
        if current is None:
            current = {"title": "", "blocks": []}
        current.setdefault("_lines", []).append(line)
    if current:
        chapters.append(current)
    out = []
    for chapter in chapters:
        blocks = _blocks("\n".join(chapter.pop("_lines", [])))
        if chapter["title"] or blocks:
            out.append({"title": chapter["title"], "blocks": blocks})
    return out


def public_view(row: dict) -> dict:
    dados = as_dict(row.get("dados_detectados"))
    plan = as_dict(row.get("plan_content"))
    share = as_dict(plan.get("share") or as_dict(as_dict(dados.get("folha")).get("share")))
    token = text(share.get("public_token") or dados.get("public_token"))
    url = text(share.get("url")) or public_sheet_url(token)
    folha = as_dict(dados.get("folha"))
    if not _cards(folha) and plan and not _is_board(plan):
        folha = plan
    sheet = _sheet_cards(folha)
    board = plan if _is_board(plan) else {}
    board_sections = []
    for section in as_list(board.get("sections")):
        item = as_dict(section)
        cards = [as_dict(card) for card in as_list(item.get("cards")) if text(as_dict(card).get("body") or as_dict(card).get("title"))]
        if cards:
            board_sections.append({"id": text(item.get("id")), "title": text(item.get("title") or item.get("id")), "cards": cards})
    chapters = plan_chapters(text(dados.get("planejamento")))
    branding = as_dict(folha.get("branding") or board.get("branding"))
    meta = as_dict(folha.get("meta") or board.get("meta"))
    campanha = as_dict(dados.get("campanha"))
    title = session_title(row, dados)
    confidential = as_bool(dados.get("anunciante_confidencial"))
    raw_client = text(meta.get("client") or row.get("cliente") or dados.get("cliente") or campanha.get("cliente"))
    client = "Confidencial" if confidential else raw_client
    facts = [
        item
        for item in (
            ("Anunciante", client),
            ("Campanha", text(meta.get("campaign") or row.get("nome_campanha") or dados.get("nome_campanha"))),
            ("Verba", text(meta.get("budget") or row.get("budget") or campanha.get("verba") or dados.get("verba"))),
            ("Praça", text(meta.get("market") or campanha.get("praca"))),
            ("Período", text(meta.get("period") or row.get("prazo") or campanha.get("periodo") or dados.get("periodo"))),
            ("Objetivo", text(meta.get("objective") or row.get("objetivo") or campanha.get("objetivo"))),
        )
        if item[1] and item[1] != title
    ]
    tem_folha = bool(sheet)
    tem_completo = bool(chapters or board_sections)
    return {
        "house": HOUSE,
        "title": title,
        "client": client,
        "mode": plan_mode_of(dados, "one_page"),
        "facts": facts,
        "branding": branding,
        "sheet": sheet,
        "tem_folha": tem_folha,
        "tem_completo": tem_completo,
        "chapters": chapters,
        "board": board_sections,
        "share_url": url,
        "public_token": token,
        "default_tab": "folha" if tem_folha or not tem_completo else "plano",
    }
