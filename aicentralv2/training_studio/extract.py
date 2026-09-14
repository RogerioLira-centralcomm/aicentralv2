"""Importação de URL: página (Firecrawl) ou YouTube (legendas + quadros)."""

import base64
import io
import ipaddress
import re
import socket
from urllib.parse import urlparse

from ..crm_v3_web_scout import _firecrawl_scrape
from .prompts import (
    INTERPRET_VIDEO_SYSTEM,
    SUMMARIZE_URL_SYSTEM,
    SUMMARIZE_VIDEO_SYSTEM,
    wrap_untrusted,
)
from .youtube import (
    collect_frame_sources,
    crop_storyboard,
    download_bytes,
    fetch_captions,
    fetch_watch,
    parse_youtube_id,
)


def validate_public_url(raw):
    value = str(raw or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Informe uma URL http ou https válida.")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("A URL precisa ser pública.")
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443)
        }
    except socket.gaierror as exc:
        raise ValueError("Não foi possível resolver o endereço da página.") from exc
    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("A URL precisa apontar para um endereço público.")
    return value


def ingest_url(url, providers, storage=None):
    safe_url = validate_public_url(url)
    video_id = parse_youtube_id(safe_url)
    if video_id:
        return ingest_youtube(safe_url, video_id, providers, storage)
    return ingest_page(safe_url, providers)


def extract_page(url):
    safe_url = validate_public_url(url)
    data = _firecrawl_scrape(safe_url, formats=["markdown"], timeout_s=40)
    metadata = data.get("metadata") or {}
    markdown = str(data.get("markdown") or data.get("content") or "").strip()
    if not markdown:
        raise ValueError("Não foi possível extrair o conteúdo principal da página.")
    title = (
        metadata.get("title")
        or metadata.get("ogTitle")
        or metadata.get("og:title")
        or safe_url
    )
    return {
        "url": safe_url,
        "titulo": str(title)[:300],
        "texto": markdown[:12000],
    }


def ingest_page(url, providers):
    pipeline = [
        _step("detect", "URL", "ok", "Página web"),
        _step("firecrawl", "Firecrawl", "run", "Markdown da página"),
        _step("gpt", "GPT OpenAI", "wait", "Resumo para a mesa"),
        _step("gemini", "Gemini", "skip", "Só entra em vídeo"),
    ]
    try:
        page = extract_page(url)
    except Exception as exc:
        pipeline[1] = _step("firecrawl", "Firecrawl", "error", str(exc)[:160])
        raise
    pipeline[1] = _step("firecrawl", "Firecrawl", "ok", f"{len(page['texto'])} caracteres")
    summary = summarize_page(providers, page)
    pipeline[2] = _step(
        "gpt",
        "GPT OpenAI",
        "ok",
        summary.get("model") or "resumo",
    )
    return {
        "kind": "page",
        "url": page["url"],
        "titulo": page["titulo"],
        "autor": "",
        "texto": page["texto"],
        "transcript": "",
        "transcript_source": "",
        "descricao": "",
        "resumo": summary.get("content") or "",
        "briefing_html": _page_briefing_html(page["titulo"], summary.get("content") or ""),
        "frames": [],
        "hero_url": "",
        "embed_url": "",
        "duracao_s": 0,
        "pipeline": pipeline,
        "costs": [
            {
                "kind": "resumo_url",
                "model": summary.get("model"),
                "usage": summary.get("usage") or {},
                "cost_usd": summary.get("cost_usd") or 0,
                "provider": summary.get("provider") or "openai",
            }
        ],
    }


def ingest_youtube(url, video_id, providers, storage=None):
    pipeline = [
        _step("detect", "YouTube", "run", video_id),
        _step("legendas", "Legendas", "wait", "ASR do player"),
        _step("firecrawl", "Firecrawl", "wait", "Descrição se faltar fala"),
        _step("quadros", "Quadros", "wait", "Capa e storyboard"),
        _step("gemini", "Gemini", "wait", "Lê os quadros"),
        _step("gpt", "GPT OpenAI", "wait", "Briefing da mesa"),
    ]
    watch = fetch_watch(video_id)
    watch["url"] = url or watch.get("url")
    pipeline[0] = _step(
        "detect",
        "YouTube",
        "ok",
        f"{watch.get('duracao_s') or 0}s · {watch.get('autor') or video_id}",
    )
    transcript = fetch_captions(watch.get("caption_url"), watch.get("session"))
    if transcript:
        pipeline[1] = _step(
            "legendas",
            "Legendas",
            "ok",
            f"{watch.get('caption_lang') or 'pt'} · {len(transcript)} caracteres",
        )
        pipeline[2] = _step("firecrawl", "Firecrawl", "skip", "Legendas bastaram")
        page_text = ""
    else:
        pipeline[1] = _step("legendas", "Legendas", "error", "Player sem faixa utilizável")
        page_text = _youtube_page_markdown(watch.get("url") or url)
        if page_text:
            pipeline[2] = _step("firecrawl", "Firecrawl", "ok", "Descrição e página do vídeo")
        else:
            pipeline[2] = _step(
                "firecrawl",
                "Firecrawl",
                "error",
                "Sem markdown extra; usamos a descrição do player",
            )
    frames = _materialize_frames(watch, storage)
    if frames:
        pipeline[3] = _step("quadros", "Quadros", "ok", f"{len(frames)} imagens")
    else:
        pipeline[3] = _step("quadros", "Quadros", "error", "Só metadados; capa indisponível")
    spoken = transcript or watch.get("descricao") or page_text
    if not spoken:
        raise ValueError("Não foi possível ler fala nem descrição deste vídeo.")
    vision = interpret_video(providers, watch, spoken, frames)
    if vision.get("content"):
        pipeline[4] = _step(
            "gemini",
            "Gemini",
            "ok",
            vision.get("model") or "visão",
        )
    else:
        pipeline[4] = _step("gemini", "Gemini", "error", "Sem interpretação visual")
    briefing = summarize_video(providers, watch, spoken, vision.get("content") or "")
    pipeline[5] = _step("gpt", "GPT OpenAI", "ok", briefing.get("model") or "briefing")
    resumo = (vision.get("content") or briefing.get("content") or "")[:4000]
    costs = []
    if vision.get("model"):
        costs.append(
            {
                "kind": "visao_video",
                "model": vision.get("model"),
                "usage": vision.get("usage") or {},
                "cost_usd": vision.get("cost_usd") or 0,
                "provider": vision.get("provider") or "openrouter",
            }
        )
    costs.append(
        {
            "kind": "resumo_url",
            "model": briefing.get("model"),
            "usage": briefing.get("usage") or {},
            "cost_usd": briefing.get("cost_usd") or 0,
            "provider": briefing.get("provider") or "openai",
        }
    )
    hero = next((item.get("asset_url") for item in frames if item.get("asset_url")), "")
    return {
        "kind": "youtube",
        "url": watch.get("url") or url,
        "titulo": watch.get("titulo") or url,
        "autor": watch.get("autor") or "",
        "texto": spoken[:12000],
        "transcript": transcript,
        "transcript_source": "legendas" if transcript else ("firecrawl" if page_text else "descricao"),
        "descricao": watch.get("descricao") or "",
        "resumo": resumo,
        "interpretacao": vision.get("content") or "",
        "briefing_html": briefing.get("content") or "",
        "frames": frames,
        "hero_url": hero,
        "embed_url": f"https://www.youtube.com/embed/{video_id}",
        "duracao_s": watch.get("duracao_s") or 0,
        "pipeline": pipeline,
        "costs": costs,
    }


def summarize_page(providers, page):
    result = providers.text.complete(
        [
            {"role": "system", "content": SUMMARIZE_URL_SYSTEM},
            {
                "role": "user",
                "content": wrap_untrusted(page.get("url"), page.get("texto")),
            },
        ],
        max_tokens=700,
        temperature=0.2,
    )
    return result


def interpret_video(providers, watch, spoken, frames):
    vision = getattr(providers, "vision", None)
    if vision is None or not frames:
        return {}
    urls = []
    for item in frames[:6]:
        url = item.get("public_url") or item.get("data_url")
        if url and (url.startswith("https://") or url.startswith("data:image/")):
            urls.append(url)
    if not urls:
        return {}
    prompt = (
        "Interprete este vídeo para especialistas em mídia. "
        "Use os quadros e o texto. Não invente número. "
        "Responda em português: tese, o que aparece na tela, "
        "o que serve (ou não) para a Imersão, e 3 frases de briefing.\n\n"
        f"Título: {watch.get('titulo')}\n"
        f"Canal: {watch.get('autor')}\n"
        f"{wrap_untrusted('fala_ou_descricao', (spoken or '')[:8000])}"
    )
    try:
        return vision.interpret(prompt, urls, system=INTERPRET_VIDEO_SYSTEM)
    except Exception:
        return {}


def summarize_video(providers, watch, spoken, interpretation):
    result = providers.text.complete(
        [
            {"role": "system", "content": SUMMARIZE_VIDEO_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Título: {watch.get('titulo')}\n"
                    f"Canal: {watch.get('autor')}\n"
                    f"URL: {watch.get('url')}\n\n"
                    f"{wrap_untrusted('interpretacao', interpretation)}\n\n"
                    f"{wrap_untrusted('fala_ou_descricao', (spoken or '')[:9000])}"
                ),
            },
        ],
        max_tokens=900,
        temperature=0.2,
    )
    result["content"] = _session_html(watch.get("titulo"), result.get("content") or "")
    return result


def extract_pdf_text(content):
    try:
        from PyPDF2 import PdfReader
    except ImportError as exc:
        raise ValueError("Leitura de PDF indisponível neste servidor.") from exc

    reader = PdfReader(io.BytesIO(content or b""))
    pages = []
    for page in reader.pages[:12]:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("Não foi possível ler o texto deste PDF.")
    return text[:16000]


def _materialize_frames(watch, storage):
    frames = []
    session = watch.get("session")
    for source in collect_frame_sources(watch):
        try:
            raw = download_bytes(source["url"], session)
        except Exception:
            continue
        if len(raw) < 4000 and source.get("kind") != "storyboard":
            continue
        payload = raw
        if source.get("crop") and source.get("kind") == "storyboard":
            try:
                payload = crop_storyboard(raw, source["crop"])
            except Exception:
                continue
        asset_url = ""
        if storage is not None:
            try:
                asset_url = storage.save_bytes(payload, "jpg")
            except Exception:
                asset_url = ""
        data_url = "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")
        public_url = source.get("url") if source.get("kind") == "poster" else ""
        frames.append(
            {
                "label": source.get("label") or "Quadro",
                "second": source.get("second") or 0,
                "kind": source.get("kind") or "poster",
                "source_url": source.get("url"),
                "public_url": public_url,
                "data_url": data_url if not public_url else "",
                "asset_url": asset_url or source.get("url"),
            }
        )
        if len(frames) >= 6:
            break
    return frames


def _youtube_page_markdown(url):
    try:
        data = _firecrawl_scrape(url, formats=["markdown"], timeout_s=40)
    except Exception:
        return ""
    return str(data.get("markdown") or data.get("content") or "").strip()[:12000]


def _session_html(title, raw):
    from html import escape as html_escape

    html = str(raw or "").strip()
    if html.startswith("```"):
        html = re.sub(r"^```(?:html)?\s*|\s*```$", "", html, flags=re.I).strip()
    if "ts-page" in html:
        return html
    if "<" not in html:
        paras = "".join(
            f"<p>{html_escape(line.strip())}</p>"
            for line in html.split("\n")
            if line.strip()
        )
        html = paras
    return (
        f'<article class="ts-page" data-layout="split">'
        f'<div class="ts-page-copy"><h2>{html_escape(title or "Fonte")}</h2>{html}</div>'
        f'<figure class="ts-page-art" data-slot="ilustracao"></figure>'
        f"</article>"
    )


def _page_briefing_html(title, summary):
    from html import escape as html_escape

    paras = "".join(
        f"<p>{html_escape(line.strip())}</p>"
        for line in str(summary or "").split("\n")
        if line.strip()
    )
    return (
        f'<article class="ts-page" data-layout="copy">'
        f'<div class="ts-page-copy"><h2>{html_escape(title)}</h2>{paras}</div>'
        f"</article>"
    )


def _step(key, label, status, detail=""):
    return {"key": key, "label": label, "status": status, "detail": detail}

