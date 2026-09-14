"""Quebra uma fonte importada em sessões que o instrutor consegue organizar."""

from html import escape as html_escape
import re

from .content.markup import art_slot, page


LARGE_SECONDS = 360
LARGE_CHARS = 1800
MAX_FRAME_SESSIONS = 4


def is_large_import(payload):
    payload = payload or {}
    transcript = str(payload.get("transcript") or "")
    briefing = str(payload.get("briefing_html") or "")
    frames = payload.get("frame_urls") or payload.get("frames") or []
    headings = len(re.findall(r"<h2\b", briefing, flags=re.I))
    return (
        int(payload.get("duracao_s") or 0) >= LARGE_SECONDS
        or len(transcript) >= LARGE_CHARS
        or headings >= 2
        or len(frames) >= 4
    )


def preview_import_plan(payload, frame_urls=None):
    return [
        {"titulo": item["titulo"], "tipo": item.get("tipo") or "fonte"}
        for item in build_import_sessions(payload, frame_urls)
    ]


def build_import_sessions(payload, frame_urls=None):
    payload = payload or {}
    title = str(payload.get("titulo") or "Fonte importada").strip()[:160] or "Fonte importada"
    briefing = str(payload.get("briefing_html") or "").strip()
    transcript = str(payload.get("transcript") or payload.get("descricao") or "").strip()
    frames = [
        url
        for url in (frame_urls if frame_urls is not None else _frame_urls(payload))
        if url
    ]
    hero = frames[0] if frames else str(payload.get("hero_url") or "")
    if not is_large_import({**payload, "frame_urls": frames}):
        return [
            {
                "titulo": title,
                "tipo": "fonte",
                "conteudo_html": _title_slide(title, payload) + _roteiro_block(title, briefing, hero),
                "notas_instrutor": _notes(payload, "Uma sessão. Separe palco e fala se crescer."),
            }
        ]
    sessions = [
        {
            "titulo": title,
            "tipo": "fonte",
            "conteudo_html": _title_slide(title, payload) + _roteiro_block(title, briefing, hero),
            "notas_instrutor": _notes(payload, "Tese da fonte. Palco na primeira página."),
        }
    ]
    if len(frames) >= 2:
        sessions.append(
            {
                "titulo": f"{title} · quadros",
                "tipo": "fonte",
                "conteudo_html": "".join(
                    _frame_slide(title, url, index)
                    for index, url in enumerate(frames[:MAX_FRAME_SESSIONS], start=1)
                ),
                "notas_instrutor": {
                    "tese": "Quadros da fonte, um por palco.",
                    "pergunta": "Qual quadro entra no primeiro minuto?",
                    "nao_repetir": "Não usar os quatro no mesmo slide.",
                },
            }
        )
    if len(transcript) >= LARGE_CHARS:
        sessions.append(
            {
                "titulo": f"{title} · fala",
                "tipo": "fonte",
                "conteudo_html": _transcript_roteiro(title, transcript),
                "notas_instrutor": {
                    "tese": "Fala bruta para o instrutor recortar.",
                    "pergunta": "O que vira palco e o que fica nota?",
                    "nao_repetir": "Não projetar a transcrição inteira.",
                },
            }
        )
    return sessions


def _frame_urls(payload):
    urls = []
    for item in payload.get("frames") or []:
        if isinstance(item, str):
            urls.append(item)
            continue
        url = (item or {}).get("asset_url") or (item or {}).get("source_url")
        if url:
            urls.append(url)
    return urls


def _title_slide(title, payload):
    lede = (
        str(payload.get("autor") or "").strip()
        or "Fonte importada para a mesa."
    )
    mins = int(payload.get("duracao_s") or 0)
    if mins:
        lede = f"{lede} · {max(1, round(mins / 60))} min"
    copy = f"<h2>{html_escape(title)}</h2><p>{html_escape(lede)}</p>"
    return page("title", copy).replace(
        'data-layout="title"',
        'data-layout="title" data-surface="slide"',
        1,
    )


def _roteiro_block(title, briefing, hero):
    html = briefing or f"<h2>{html_escape(title)}</h2><p>Sem briefing. Recorte a fala.</p>"
    if "ts-page" in html:
        html = html.replace('data-layout="', 'data-surface="roteiro" data-layout="', 1)
        if hero and "ts-page-art" in html and "<img" not in html:
            html = html.replace(
                '<figure class="ts-page-art" data-slot="ilustracao"></figure>',
                f'<figure class="ts-page-art" data-slot="ilustracao">'
                f'<img src="{html_escape(hero, quote=True)}" alt=""></figure>',
                1,
            )
        return html
    art = ""
    if hero:
        art = (
            f'<figure class="ts-page-art" data-slot="ilustracao">'
            f'<img src="{html_escape(hero, quote=True)}" alt=""></figure>'
        )
    return page("split" if art else "copy", html, art).replace(
        'data-layout="',
        'data-surface="roteiro" data-layout="',
        1,
    )


def _frame_slide(title, url, index):
    copy = f"<h2>{html_escape(title)}</h2><p>Quadro {index} da fonte.</p>"
    art = (
        f'<figure class="ts-page-art" data-slot="ilustracao">'
        f'<img src="{html_escape(url, quote=True)}" alt=""></figure>'
    )
    return page("split", copy, art).replace(
        'data-layout="split"',
        'data-layout="split" data-surface="slide"',
        1,
    )


def _transcript_roteiro(title, transcript):
    chunks = _split_text(transcript, 900)
    parts = []
    for index, chunk in enumerate(chunks[:6], start=1):
        paras = "".join(
            f"<p>{html_escape(piece.strip())}</p>"
            for piece in re.split(r"\n{2,}", chunk)
            if piece.strip()
        )
        copy = f"<h2>{html_escape(title)} · fala {index}</h2>{paras}"
        parts.append(
            page("copy", copy).replace(
                'data-layout="copy"',
                'data-layout="copy" data-surface="roteiro"',
                1,
            )
        )
    return "".join(parts)


def _split_text(text, size):
    text = re.sub(r"\s+", " ", text or "").strip()
    chunks = []
    while text:
        chunks.append(text[:size])
        text = text[size:].lstrip()
    return chunks


def _notes(payload, tese):
    return {
        "tese": tese,
        "pergunta": "O que entra no palco e o que fica no roteiro?",
        "nao_repetir": str(payload.get("url") or ""),
    }
