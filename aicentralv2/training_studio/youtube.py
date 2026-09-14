"""YouTube: id, player, legendas ASR e quadros do vídeo."""

from __future__ import annotations

import json
import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import requests


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
WATCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
PLAYER_RE = re.compile(
    r"ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*(?:var|</script>)",
    re.S,
)


def parse_youtube_id(url):
    parsed = urlparse(str(url or "").strip())
    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        return None
    if host.endswith("youtu.be"):
        candidate = parsed.path.strip("/").split("/", 1)[0]
        return candidate if _valid_id(candidate) else None
    query = parse_qs(parsed.query)
    if query.get("v") and _valid_id(query["v"][0]):
        return query["v"][0]
    parts = [item for item in parsed.path.split("/") if item]
    if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
        return parts[1] if _valid_id(parts[1]) else None
    return None


def _valid_id(value):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", str(value or "")))


def fetch_watch(video_id):
    video_id = str(video_id or "")
    session = requests.Session()
    session.headers.update(WATCH_HEADERS)
    session.cookies.set("CONSENT", "YES+cb", domain=".youtube.com")
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    html = session.get(watch_url, timeout=25).text
    player = _player_payload(html)
    details = player.get("videoDetails") or {}
    micro = ((player.get("microformat") or {}).get("playerMicroformatRenderer") or {})
    tracks = (
        (player.get("captions") or {})
        .get("playerCaptionsTracklistRenderer")
        or {}
    ).get("captionTracks") or []
    caption = _pick_caption(tracks)
    thumbnails = (
        ((details.get("thumbnail") or {}).get("thumbnails") or [])
        or ((micro.get("thumbnail") or {}).get("thumbnails") or [])
    )
    best_thumb = ""
    if thumbnails:
        best_thumb = str(sorted(thumbnails, key=lambda item: item.get("width") or 0)[-1].get("url") or "")
    oembed = _oembed(watch_url)
    title = (
        details.get("title")
        or micro.get("title", {}).get("simpleText")
        or oembed.get("title")
        or watch_url
    )
    return {
        "video_id": video_id,
        "url": watch_url,
        "titulo": str(title)[:300],
        "autor": str(details.get("author") or oembed.get("author_name") or ""),
        "descricao": str(details.get("shortDescription") or micro.get("description", {}).get("simpleText") or ""),
        "duracao_s": int(details.get("lengthSeconds") or 0),
        "thumbnail_url": best_thumb or oembed.get("thumbnail_url") or _poster_url(video_id),
        "caption_url": caption.get("baseUrl") or "",
        "caption_lang": caption.get("languageCode") or "",
        "caption_kind": caption.get("kind") or "",
        "storyboard_spec": (
            (player.get("storyboards") or {}).get("playerStoryboardSpecRenderer") or {}
        ).get("spec")
        or "",
        "session": session,
    }


def fetch_captions(caption_url, session=None):
    url = str(caption_url or "").strip()
    if not url:
        return ""
    client = session or requests
    for extra in ({"fmt": "json3"}, {"fmt": "srv3"}, {}):
        try:
            response = client.get(url, params=extra or None, timeout=20, headers=WATCH_HEADERS)
        except requests.RequestException:
            continue
        text = _parse_caption_body(response.text or "")
        if text:
            return text
    return ""


def collect_frame_sources(watch):
    video_id = watch.get("video_id") or ""
    sources = []
    poster = watch.get("thumbnail_url") or _poster_url(video_id)
    if poster:
        sources.append({"label": "Capa", "second": 0, "url": poster, "kind": "poster"})
    for name, label in (("maxresdefault.jpg", "Capa 16:9"), ("sddefault.jpg", "Quadro médio")):
        url = f"https://i.ytimg.com/vi/{video_id}/{name}"
        if url != poster:
            sources.append({"label": label, "second": 0, "url": url, "kind": "poster"})
    sources.extend(storyboard_frame_urls(watch.get("storyboard_spec") or "", limit=6))
    seen = set()
    unique = []
    for item in sources:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)
    return unique[:8]


def storyboard_frame_urls(spec, limit=6):
    level = parse_storyboard_level(spec)
    if not level:
        return []
    frames = []
    step = max(1, int(level["count"] / max(limit, 1)))
    for index in range(0, level["count"], step):
        if len(frames) >= limit:
            break
        sheet, cell = divmod(index, level["per_sheet"])
        col, row = cell % level["cols"], cell // level["cols"]
        frames.append(
            {
                "label": f"{index * level['interval_s']:.0f}s",
                "second": index * level["interval_s"],
                "url": level["sheet_url"](sheet),
                "kind": "storyboard",
                "crop": {
                    "x": col * level["width"],
                    "y": row * level["height"],
                    "w": level["width"],
                    "h": level["height"],
                },
            }
        )
    return frames


def parse_storyboard_level(spec):
    parts = str(spec or "").split("|")
    if len(parts) < 3:
        return None
    base = parts[0]
    chosen = None
    for index, raw in enumerate(parts[1:], start=0):
        fields = raw.split("#")
        if len(fields) < 8:
            continue
        width, height, count, cols, rows = (int(fields[i]) for i in range(5))
        interval_ms = int(fields[5] or 0)
        if interval_ms <= 0 or count < 4:
            continue
        npat = fields[6]
        sigh = fields[7][3:] if fields[7].startswith("rs$") else fields[7]

        def sheet_url(sheet, _base=base, _index=index, _npat=npat, _sigh=sigh):
            name = _npat.replace("$M", str(sheet))
            url = _base.replace("$L", str(_index)).replace("$N", name)
            if "sigh=" not in url:
                url += ("&" if "?" in url else "?") + "sigh=" + _sigh
            return url

        chosen = {
            "width": width,
            "height": height,
            "count": count,
            "cols": cols,
            "rows": rows,
            "per_sheet": cols * rows,
            "interval_s": interval_ms / 1000.0,
            "sheet_url": sheet_url,
        }
    return chosen


def crop_storyboard(content, crop):
    from PIL import Image

    image = Image.open(BytesIO(content or b"")).convert("RGB")
    box = (
        int(crop["x"]),
        int(crop["y"]),
        int(crop["x"]) + int(crop["w"]),
        int(crop["y"]) + int(crop["h"]),
    )
    out = BytesIO()
    image.crop(box).save(out, format="JPEG", quality=88)
    return out.getvalue()


def download_bytes(url, session=None):
    client = session or requests
    response = client.get(
        url,
        timeout=20,
        headers={**WATCH_HEADERS, "Accept": "image/*,*/*"},
    )
    response.raise_for_status()
    return response.content or b""


def _player_payload(html):
    match = PLAYER_RE.search(html or "")
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _pick_caption(tracks):
    scored = []
    for item in tracks:
        if not isinstance(item, dict) or not item.get("baseUrl"):
            continue
        lang = str(item.get("languageCode") or "")
        score = 0
        if lang.startswith("pt"):
            score += 4
        if lang.startswith("en"):
            score += 1
        if item.get("kind") == "asr":
            score += 1
        scored.append((score, item))
    if not scored:
        return {}
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]


def _oembed(url):
    try:
        response = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=12,
            headers=WATCH_HEADERS,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}
    except (requests.RequestException, ValueError):
        return {}


def _poster_url(video_id):
    return f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"


def _parse_caption_body(raw):
    text = (raw or "").strip()
    if not text or text.startswith("<!"):
        return ""
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        chunks = []
        for event in data.get("events") or []:
            segs = event.get("segs") or []
            piece = "".join(str(seg.get("utf8") or "") for seg in segs)
            if piece.strip():
                chunks.append(piece.replace("\n", " ").strip())
        return _clean_caption(" ".join(chunks))
    pieces = re.findall(r"<text[^>]*>(.*?)</text>", text, flags=re.S)
    if pieces:
        cleaned = []
        for piece in pieces:
            piece = re.sub(r"<[^>]+>", "", piece)
            piece = (
                piece.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&#39;", "'")
                .replace("&quot;", '"')
            )
            if piece.strip():
                cleaned.append(piece.strip())
        return _clean_caption(" ".join(cleaned))
    if text.startswith("WEBVTT"):
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and "-->" not in line
            and not line.startswith("WEBVTT")
            and not line.startswith("NOTE")
        ]
        return _clean_caption(" ".join(lines))
    return ""


def _clean_caption(text):
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:20000]
