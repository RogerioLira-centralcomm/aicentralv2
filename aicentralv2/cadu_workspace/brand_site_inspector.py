"""Safe, bounded inspection of official brand websites and logo candidates."""

from html.parser import HTMLParser
from ipaddress import ip_address
import socket
from urllib.parse import urljoin, urlparse

import requests
from werkzeug.exceptions import BadRequest


MAX_HTML_BYTES = 512_000
MAX_REDIRECTS = 5
MAX_LOGO_CANDIDATES = 4
REQUEST_TIMEOUT = (3, 5)


def normalize_public_url(value: str, *, label: str = "site") -> str:
    raw = str(value or "").strip()[:2000]
    if raw and not raw.lower().startswith(("http://", "https://")):
        if ":" in raw.split("/", 1)[0]:
            raise BadRequest(f"Informe uma URL http ou https válida para {label}.")
        raw = "https://" + raw.lstrip("/")
    parsed = urlparse(raw)
    if not raw or parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BadRequest(f"Informe uma URL http ou https válida para {label}.")
    if parsed.username or parsed.password:
        raise BadRequest(f"A URL de {label} não pode conter credenciais.")
    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or default_port, type=socket.SOCK_STREAM)}
    except (OSError, socket.gaierror) as exc:
        raise BadRequest(f"Não foi possível localizar o endereço de {label}.") from exc
    if not addresses or any(not ip_address(value).is_global for value in addresses):
        raise BadRequest(f"O endereço de {label} precisa ser público.")
    return parsed.geturl()


class _BrandHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._inside_title = False
        self.candidates = []

    def handle_starttag(self, tag, attrs):
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        if tag.lower() == "title":
            self._inside_title = True
        if tag.lower() == "link" and values.get("href"):
            rel = values.get("rel", "").lower()
            if "icon" in rel:
                self.candidates.append((values["href"], "site_icon", 0.72))
        if tag.lower() == "meta":
            prop = (values.get("property") or values.get("name") or "").lower()
            if prop in {"og:image", "twitter:image"} and values.get("content"):
                self.candidates.append((values["content"], prop.replace(":", "_"), 0.45))
        if tag.lower() == "img" and values.get("src"):
            signal = " ".join(values.get(key, "") for key in ("alt", "class", "id", "src")).lower()
            if any(word in signal for word in ("logo", "marca", "brand")):
                self.candidates.append((values["src"], "page_logo", 0.9))

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data):
        if self._inside_title and len(self.title) < 300:
            self.title += data


def _request(url: str, *, accept: str, session=None):
    client = session or requests.Session()
    if session is None:
        client.trust_env = False
    current = normalize_public_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        response = client.get(current, headers={"Accept": accept, "User-Agent": "CentralX-BrandInspector/1.0"},
                              timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("Location"):
            response.close()
            current = normalize_public_url(urljoin(current, response.headers["Location"]))
            continue
        return response, current
    raise BadRequest("O endereço excedeu o limite seguro de redirecionamentos.")


def _validate_logo(url: str, *, site_host: str = "", session=None) -> dict:
    try:
        response, final_url = _request(url, accept="image/*,*/*;q=0.2", session=session)
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        sample = next(response.iter_content(16_384), b"")[:16_384]
        signature = (sample.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"\x00\x00\x01\x00"))
                     or (len(sample) >= 12 and sample[8:12] == b"WEBP")
                     or b"<svg" in sample[:2048].lower())
        valid = 200 <= response.status_code < 400 and content_type.startswith("image/") and signature
        response.close()
        host = (urlparse(final_url).hostname or "").lower()
        same_domain = bool(site_host and (host == site_host or host.endswith("." + site_host) or site_host.endswith("." + host)))
        return {"url": final_url, "reachable": 200 <= response.status_code < 400,
                "valid_image": valid, "content_type": content_type, "status_code": response.status_code,
                "same_domain": same_domain}
    except (BadRequest, requests.RequestException) as exc:
        return {"url": str(url or ""), "reachable": False, "valid_image": False, "error": str(exc)}


def inspect_brand_site(website_url: str, *, logo_url: str = "", session=None) -> dict:
    normalized = normalize_public_url(website_url, label="site oficial")
    client = session or requests.Session()
    if session is None:
        client.trust_env = False
    try:
        response, final_url = _request(normalized, accept="text/html,application/xhtml+xml", session=client)
        status = int(response.status_code)
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        body = b""
        if 200 <= status < 400 and (not content_type or "html" in content_type):
            for chunk in response.iter_content(16_384):
                body += chunk
                if len(body) >= MAX_HTML_BYTES:
                    body = body[:MAX_HTML_BYTES]
                    break
        response.close()
    except requests.RequestException as exc:
        return {"website_url": normalized, "reachable": False, "ready_for_analysis": False,
                "logo_candidates": [], "warnings": ["O site não respondeu à inspeção."], "error": str(exc)}

    parser = _BrandHTMLParser()
    if body:
        parser.feed(body.decode("utf-8", errors="replace"))
    site_host = (urlparse(final_url).hostname or "").lower()
    candidates = []
    seen = set()
    attempted = 0
    for candidate, source, confidence in sorted(parser.candidates, key=lambda item: item[2], reverse=True):
        absolute = urljoin(final_url, candidate)
        if absolute in seen:
            continue
        if attempted >= MAX_LOGO_CANDIDATES:
            break
        seen.add(absolute)
        attempted += 1
        check = _validate_logo(absolute, site_host=site_host, session=client)
        if check.get("valid_image"):
            candidates.append({**check, "source": source, "confidence": confidence})
    explicit_logo = _validate_logo(logo_url, site_host=site_host, session=client) if str(logo_url or "").strip() else None
    warnings = []
    if not (200 <= status < 400):
        warnings.append(f"O site respondeu com HTTP {status}.")
    if content_type and "html" not in content_type:
        warnings.append("O endereço não retornou uma página HTML.")
    if explicit_logo and not explicit_logo.get("valid_image"):
        warnings.append("O link informado para a logo não retornou uma imagem válida.")
    if not explicit_logo and not candidates:
        warnings.append("Nenhuma logo verificável foi encontrada automaticamente; ela poderá ser enviada depois.")
    reachable = 200 <= status < 400
    return {"website_url": normalized, "final_url": final_url, "host": site_host,
            "reachable": reachable, "status_code": status, "content_type": content_type,
            "title": " ".join(parser.title.split())[:300], "ready_for_analysis": reachable and "html" in content_type,
            "explicit_logo": explicit_logo, "logo_candidates": candidates, "suggested_logo_url":
            ((explicit_logo or {}).get("url") if (explicit_logo or {}).get("valid_image") else
             (candidates[0]["url"] if candidates else "")), "warnings": warnings}
