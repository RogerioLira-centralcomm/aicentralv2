"""CRM v3 — Web Scout (crawl mínimo do site do cliente via Firecrawl).

Fase B do plano macro (set/2026): quando o usuário confirma o site em
"Site & logo", disparamos um `POST /v2/scrape` do Firecrawl na home,
extraímos o perfil `branding`, metadata e links (logo canônico do
próprio site — melhor que favicons genéricos para clientes locais),
`<title>`, meta description e links do menu principal. Persistimos em
`cliente_web_info` para renderização na aba "Web" do CRM v3 sem
recustar Firecrawl a cada abertura do cliente.

Escopo desta primeira versão (deliberadamente enxuto):
- 1 request Firecrawl por refresh (só a home).
- Sem estruturação via LLM. Confia no `metadata` que o Firecrawl já
  retorna. Fase C adiciona /crawl + Gemini para sócios, blog etc.
- Cache manual: o usuário clica "Atualizar" quando quer refazer.
  Sem TTL automático (evita gastar crédito sem interação).

Fluxo:
  ┌──────────┐    site_url PATCH    ┌───────────────┐
  │ Frontend │ ───────────────────▶ │ crm_v3_routes │
  └────┬─────┘                       └──────┬────────┘
       │                                    │
       │                    dispara refresh │
       │                                    ▼
       │                       ┌────────────────────┐
       │                       │ crm_v3_web_scout   │
       │                       │ .refresh_web_info  │
       │                       └──────┬─────────────┘
       │                              │
       │                              ▼
       │                     ┌────────────────────┐
       │                     │ Firecrawl /scrape  │
       │                     └──────┬─────────────┘
       │                            │ metadata
       │                            ▼
       │                     ┌────────────────────┐
       │                     │ cliente_web_info   │  (upsert)
       │                     └──────┬─────────────┘
       │                            │
       ▼                            ▼
   GET /web-info ◀───────────── retorna dados

Segurança e observabilidade:
- FIRECRAWL_API_KEY vem de env. Se ausente, marca status='erro' com
  mensagem clara em vez de estourar 500.
- Timeout configurável e uma repetição para falhas transitórias.
- Log estruturado em `aicentral.crm_v3.web_scout` (mesma família dos
  outros módulos).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests

from . import db

logger = logging.getLogger("aicentral.crm_v3.web_scout")

FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_TIMEOUT_S = 45
FIRECRAWL_MAX_ATTEMPTS = 2

_SQL_CREATE_CLIENTE_WEB_INFO = """
CREATE TABLE IF NOT EXISTS cliente_web_info (
    id SERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL UNIQUE
        REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    dominio VARCHAR(255) NOT NULL,
    logo_url TEXT,
    favicon_url TEXT,
    titulo TEXT,
    descricao TEXT,
    menu_links JSONB,
    dados_extras JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'ok',
    erro_mensagem TEXT,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def _ensure_cliente_web_info(conn) -> None:
    """Cria a tabela se a migration SQL ainda não rodou neste ambiente."""
    with conn.cursor() as cur:
        cur.execute(_SQL_CREATE_CLIENTE_WEB_INFO)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cliente_web_info_dominio "
            "ON cliente_web_info (dominio)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cliente_web_info_atualizado_em "
            "ON cliente_web_info (atualizado_em)"
        )
    conn.commit()


def _undefined_table(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return "cliente_web_info" in msg and (
        "does not exist" in msg
        or "não existe" in msg
        or "undefinedtable" in name
    )


def _normalizar_dominio(raw: Optional[str]) -> str:
    """Retorna o apex do domínio (sem protocolo, sem www, sem path)."""
    if not raw:
        return ""
    s = str(raw).strip().lower()
    if "://" in s:
        s = s.split("://", 1)[1]
    if s.startswith("www") and not s.startswith("www."):
        s = "www." + s[3:]
    if s.startswith("www."):
        s = s[4:]
    s = s.split("/")[0].split("?")[0].split("#")[0]
    return s.strip()


def _dominio_para_url(dominio: str) -> str:
    """Monta a URL canônica para scrape. Prefere https + apex."""
    d = _normalizar_dominio(dominio)
    if not d:
        return ""
    return f"https://{d}"


def _host_original(raw: Optional[str]) -> str:
    """Extrai o hostname informado sem apagar o prefixo www."""
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    try:
        parsed = urlparse(value if "://" in value else f"//{value}")
        return (parsed.hostname or "").strip(".")
    except (TypeError, ValueError):
        return ""


def _urls_candidatas(raw: Optional[str]) -> list[str]:
    """Retorna apex/www em ordem, priorizando a forma informada."""
    apex = _normalizar_dominio(raw)
    if not apex:
        return []
    original = _host_original(raw)
    hosts = [f"www.{apex}", apex] if original.startswith("www.") else [apex, f"www.{apex}"]
    return [f"https://{host}" for host in dict.fromkeys(hosts)]


_DNS_ERROR_HINTS = (
    "dns resolution failed",
    "could not resolve host",
    "name or service not known",
    "name resolution",
    "hostname",
    "nxdomain",
)


def _eh_erro_dns(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return any(hint in message for hint in _DNS_ERROR_HINTS)


def _firecrawl_scrape_com_variantes(raw: Optional[str]) -> tuple[Dict[str, Any], str]:
    """Tenta apex e www, usando fallback apenas para falha de DNS."""
    urls = _urls_candidatas(raw)
    if not urls:
        raise RuntimeError("Domínio inválido")
    try:
        return _firecrawl_scrape(urls[0]), urls[0]
    except Exception as first_error:
        if len(urls) < 2 or not _eh_erro_dns(first_error):
            raise
        logger.info("host %s não resolveu; tentando %s", urls[0], urls[1])
        try:
            return _firecrawl_scrape(urls[1]), urls[1]
        except Exception as second_error:
            if _eh_erro_dns(second_error):
                raise RuntimeError(
                    "Não encontramos o domínio. Testamos os endereços com e sem www."
                ) from second_error
            raise RuntimeError(
                "Não foi possível ler o site. Testamos os endereços com e sem www. "
                f"{str(second_error)[:220]}"
            ) from second_error


def _firecrawl_timeout() -> int:
    """Timeout configurável, limitado para não prender workers Flask."""
    raw = os.environ.get("FIRECRAWL_TIMEOUT_S", str(FIRECRAWL_TIMEOUT_S))
    try:
        return max(10, min(int(raw), 120))
    except (TypeError, ValueError):
        return FIRECRAWL_TIMEOUT_S


def _firecrawl_url() -> str:
    """Aceita endpoint completo ou base de API em FIRECRAWL_API_URL."""
    configured = os.environ.get("FIRECRAWL_API_URL", "").strip()
    if not configured:
        return FIRECRAWL_URL
    value = configured.rstrip("/")
    if value.endswith("/scrape"):
        return value
    if value.endswith("/v1") or value.endswith("/v2"):
        return value + "/scrape"
    return value + "/v2/scrape"


def _extrair_menu_links(fc_links: list, dominio: str, limite: int = 8) -> list:
    """Filtra a lista de links do Firecrawl para o menu principal.

    Heurística: mantém apenas links do próprio domínio (mesmo apex),
    remove âncoras (#), remove duplicatas mantendo ordem de primeira
    aparição, e limita a `limite` items (default 8 — cabe no topo da
    aba Web sem scroll). O `label` é o path humanizado quando o
    Firecrawl não devolve texto do link.
    """
    if not isinstance(fc_links, list):
        return []
    apex = _normalizar_dominio(dominio)
    if not apex:
        return []
    visto = set()
    resultado = []
    for item in fc_links:
        # O Firecrawl normalmente retorna strings em `data.links`; também
        # aceitamos dicts para manter compatibilidade entre versões.
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            texto = str(item.get("text") or "").strip()
        else:
            url = str(item or "").strip()
            texto = ""
        if not url or url.startswith("#") or url.startswith("mailto:") or url.startswith("tel:"):
            continue
        # Absolutiza para conseguir extrair o host.
        try:
            parsed = urlparse(url if "://" in url else f"https://{apex}{url}")
        except Exception:
            continue
        host = _normalizar_dominio(parsed.netloc)
        # Aceita apex ou subdomínios diretos (blog.cliente.com.br).
        if host and host != apex and not host.endswith("." + apex):
            continue
        # Dedup pelo path.
        chave = (parsed.path or "/").rstrip("/") or "/"
        if chave in visto:
            continue
        # Ignora a home (path vazio) porque a UI já mostra o site inteiro.
        if chave == "/":
            continue
        visto.add(chave)
        # Label: usa texto do link, ou humaniza o último segmento do path.
        if not texto:
            seg = chave.strip("/").split("/")[-1]
            texto = seg.replace("-", " ").replace("_", " ").title() or chave
        resultado.append({"label": texto[:60], "url": parsed.geturl()})
        if len(resultado) >= limite:
            break
    return resultado


_SOCIAL_PLATFORMS = (
    ("instagram", ("instagram.com",), ()),
    ("linkedin", ("linkedin.com",), ("/company/", "/in/", "/school/")),
    ("youtube", ("youtube.com",), ("/@", "/channel/", "/c/", "/user/")),
    ("tiktok", ("tiktok.com",), ("/@",)),
    ("facebook", ("facebook.com", "fb.com"), ()),
    ("x", ("x.com", "twitter.com"), ()),
)


def _extrair_redes_sociais(fc_links: list, limite: int = 8) -> list:
    """Extrai perfis sociais públicos presentes nos links da página."""
    if not isinstance(fc_links, list):
        return []
    resultado = []
    vistos = set()
    for item in fc_links:
        raw_url = item.get("url") if isinstance(item, dict) else item
        url = str(raw_url or "").strip()
        if not url:
            continue
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith(("http://", "https://")):
            continue
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        host = (parsed.hostname or "").lower()
        path = re.sub(r"/+", "/", parsed.path or "/")
        platform = ""
        for candidate, domains, required_prefixes in _SOCIAL_PLATFORMS:
            if not any(host == domain or host.endswith("." + domain) for domain in domains):
                continue
            if required_prefixes and not path.lower().startswith(required_prefixes):
                break
            platform = candidate
            break
        if not platform:
            continue
        lower_path = path.lower()
        if any(fragment in lower_path for fragment in (
            "/share", "/sharer", "/intent/", "/watch", "/shorts/", "/reel/", "/p/"
        )):
            continue
        normalized = f"https://{host}{path.rstrip('/') or '/'}"
        key = (platform, normalized.lower())
        if key in vistos:
            continue
        vistos.add(key)
        resultado.append({
            "platform": platform,
            "label": {
                "instagram": "Instagram",
                "linkedin": "LinkedIn",
                "youtube": "YouTube",
                "tiktok": "TikTok",
                "facebook": "Facebook",
                "x": "X",
            }[platform],
            "url": normalized,
        })
        if len(resultado) >= limite:
            break
    return resultado


def _firecrawl_scrape(url: str) -> Dict[str, Any]:
    """Chama Firecrawl /v2/scrape e devolve `data` bruto.

    Lança RuntimeError com mensagem amigável em caso de falha (chave
    ausente, HTTP != 2xx, timeout). Timeout, conexão e HTTP 5xx recebem
    somente uma nova tentativa; erros definitivos não gastam créditos.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY não configurada")

    timeout_s = _firecrawl_timeout()
    payload = {
        "url": url,
        # `branding` separa o logo real do og:image promocional.
        # Não pedimos markdown: o CRM não o consome e ele torna o scrape
        # mais lento em sites grandes.
        "formats": ["branding", "links"],
        "onlyMainContent": False,
        "timeout": max(5_000, (timeout_s - 5) * 1_000),
        "maxAge": 3_600_000,
        "storeInCache": True,
    }
    endpoint = _firecrawl_url()
    last_error = None
    for attempt in range(1, FIRECRAWL_MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout_s,
            )
        except requests.Timeout as exc:
            last_error = exc
            logger.warning(
                "Firecrawl timeout tentativa %s/%s para %s",
                attempt, FIRECRAWL_MAX_ATTEMPTS, url,
            )
            if attempt < FIRECRAWL_MAX_ATTEMPTS:
                continue
            raise RuntimeError(
                f"O site demorou mais de {timeout_s}s para responder. Tente novamente."
            ) from exc
        except requests.ConnectionError as exc:
            last_error = exc
            logger.warning(
                "Firecrawl conexão falhou tentativa %s/%s para %s",
                attempt, FIRECRAWL_MAX_ATTEMPTS, url,
            )
            if attempt < FIRECRAWL_MAX_ATTEMPTS:
                continue
            raise RuntimeError("Não foi possível conectar ao Firecrawl. Tente novamente.") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Erro de rede ao acessar Firecrawl: {exc}") from exc

        if resp.status_code // 100 == 2:
            try:
                body = resp.json()
            except ValueError as exc:
                raise RuntimeError("Firecrawl retornou uma resposta inválida") from exc
            if not body.get("success"):
                raise RuntimeError(
                    f"Firecrawl: {body.get('error') or body.get('message') or 'resposta sem success=true'}"
                )
            return body.get("data") or {}

        try:
            error_body = resp.json()
            msg = error_body.get("error") or error_body.get("message")
        except (ValueError, AttributeError):
            msg = None
        msg = str(msg or f"HTTP {resp.status_code}")[:300]
        if resp.status_code >= 500 and attempt < FIRECRAWL_MAX_ATTEMPTS:
            logger.warning(
                "Firecrawl HTTP %s tentativa %s/%s para %s",
                resp.status_code, attempt, FIRECRAWL_MAX_ATTEMPTS, url,
            )
            continue
        if resp.status_code in (401, 403):
            raise RuntimeError("Firecrawl: credencial inválida ou sem permissão")
        if resp.status_code == 402:
            raise RuntimeError("Firecrawl: créditos insuficientes")
        if resp.status_code == 429:
            raise RuntimeError("Firecrawl: limite de requisições atingido. Tente mais tarde.")
        raise RuntimeError(f"Firecrawl: {msg}")

    raise RuntimeError(f"Firecrawl indisponível: {last_error or 'falha desconhecida'}")


def _montar_registro(
    dominio: str,
    fc_data: Dict[str, Any],
    base_url_efetiva: Optional[str] = None,
) -> Dict[str, Any]:
    """Traduz o payload do Firecrawl para o shape da tabela.

    Prioridades de logo (ordem de fallback):
        1. branding.logo / branding.images.logo.
        2. branding.images.ogImage ou metadata.ogImage.
        3. favicon separado para apresentação auxiliar.
    """
    meta = fc_data.get("metadata") or {}
    branding = fc_data.get("branding") or {}
    branding_images = branding.get("images") or {}
    source_url = str(meta.get("sourceURL") or meta.get("url") or "").strip()
    base_url = source_url if source_url.startswith(("http://", "https://")) else ""
    base_url = base_url or base_url_efetiva or _dominio_para_url(dominio)

    logo = (
        branding.get("logo")
        or branding_images.get("logo")
        or ""
    )
    og_image = (
        branding_images.get("ogImage")
        or meta.get("ogImage")
        or meta.get("og:image")
        or meta.get("twitterImage")
        or ""
    )
    favicon = branding_images.get("favicon") or meta.get("favicon") or ""

    titulo = (
        meta.get("ogSiteName")
        or meta.get("og:site_name")
        or meta.get("title")
        or meta.get("ogTitle")
        or ""
    )
    descricao = (
        meta.get("description")
        or meta.get("ogDescription")
        or meta.get("og:description")
        or ""
    )

    links = fc_data.get("links") or []
    menu_links = _extrair_menu_links(links, dominio)
    social_links = _extrair_redes_sociais(links)

    return {
        "logo_url": urljoin(base_url + "/", logo or og_image) if (logo or og_image) else None,
        "favicon_url": urljoin(base_url + "/", favicon) if favicon else None,
        "titulo": (titulo or "").strip()[:255] or None,
        "descricao": (descricao or "").strip() or None,
        "menu_links": menu_links,
        "dados_extras": {
            "social_links": social_links,
            "source_url": base_url,
        },
    }


_LOGO_DIR = Path(__file__).resolve().parent / "static" / "uploads" / "clientes"
_LOGO_MAX_BYTES = 8 * 1024 * 1024
_LOGO_CT_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


def _ext_logo(url: str, content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _LOGO_CT_EXT:
        return _LOGO_CT_EXT[ct]
    path = urlparse(url or "").path.lower()
    m = re.search(r"\.(png|jpe?g|webp|gif|svg|ico)(?:$|\?)", path)
    if m:
        ext = m.group(1)
        return ".jpg" if ext in ("jpg", "jpeg") else f".{ext}"
    return ".png"


def _persistir_logo_cliente(cliente_id, url: Optional[str]) -> Optional[str]:
    """Baixa o logo detectado e grava em static/uploads/clientes."""
    raw = (url or "").strip()
    if not raw:
        return None
    if raw.startswith("/static/uploads/clientes/"):
        return raw
    if not raw.startswith("http://") and not raw.startswith("https://"):
        if raw.startswith("//"):
            raw = "https:" + raw
        else:
            return None
    try:
        resp = requests.get(
            raw,
            timeout=20,
            stream=True,
            headers={"User-Agent": "CentralX-CRM/1.0"},
        )
        if resp.status_code // 100 != 2:
            logger.info("logo download HTTP %s para %s", resp.status_code, raw[:120])
            return None
        content_length = resp.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > _LOGO_MAX_BYTES:
                    logger.info("logo %s excedeu o limite no header", raw[:80])
                    return None
            except (TypeError, ValueError):
                pass
        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].lower()
        if content_type and not (
            content_type.startswith("image/")
            or content_type == "application/octet-stream"
        ):
            logger.info("logo rejeitado por Content-Type %s para %s", content_type, raw[:80])
            return None
        _LOGO_DIR.mkdir(parents=True, exist_ok=True)
        ext = _ext_logo(raw, content_type)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cliente_{int(cliente_id)}_{ts}{ext}"
        filepath = _LOGO_DIR / filename
        total = 0
        try:
            with open(filepath, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > _LOGO_MAX_BYTES:
                        raise ValueError("logo excedeu o limite de tamanho")
                    fh.write(chunk)
        except Exception:
            try:
                filepath.unlink()
            except OSError:
                pass
            raise
        if total < 32:
            try:
                filepath.unlink()
            except OSError:
                pass
            return None
        public = f"/static/uploads/clientes/{filename}"
        logger.info("logo do cliente %s armazenado em %s", cliente_id, public)
        return public
    except Exception as e:
        logger.info("falha ao persistir logo (%s): %s", type(e).__name__, e)
        return None


def _apagar_logo_local(url: Optional[str]) -> None:
    raw = str(url or "")
    marker = "/static/uploads/clientes/"
    if marker not in raw:
        return
    name = raw.split(marker)[-1]
    if not name or "/" in name or ".." in name:
        return
    path = _LOGO_DIR / name
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


# ------------------------------------------------------------------
# CRUD contra `cliente_web_info`
# ------------------------------------------------------------------

def obter_web_info(cliente_id) -> Optional[Dict[str, Any]]:
    """Retorna o registro `cliente_web_info` do cliente, ou None.

    Não faz refresh — só lê. Serializa `menu_links` e `dados_extras`
    já como dict/list (psycopg 3 devolve JSONB nativo). Se a tabela
    ainda não existir (migration não rodada), retorna None em vez de
    propagar — permite o CRM v3 seguir funcionando enquanto o admin
    aplica a migration.
    """
    conn = db.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, id_cliente, dominio, logo_url, favicon_url,
                       titulo, descricao, menu_links, dados_extras,
                       status, erro_mensagem, atualizado_em, criado_em
                FROM cliente_web_info
                WHERE id_cliente = %s
                """,
                (int(cliente_id),),
            )
            row = cur.fetchone()
    except Exception as e:
        # Se a tabela não existe, o Postgres deixa a transação em
        # aborted; sem rollback qualquer query seguinte no request
        # explode com InFailedSqlTransaction (mesmo padrão do
        # crm_v3_repository).
        try:
            conn.rollback()
        except Exception:
            pass
        logger.info("cliente_web_info indisponível (%s): %s", type(e).__name__, e)
        return None
    if not row:
        return None
    return _row_para_dict(row)


def refresh_web_info(cliente_id, dominio: str) -> Dict[str, Any]:
    """Faz scrape do site e faz upsert em `cliente_web_info`.

    Sempre retorna um registro (mesmo em caso de erro): com status='ok'
    e dados populados no sucesso, ou status='erro' + erro_mensagem no
    falha. Isso simplifica o frontend, que só precisa checar `status`.
    """
    d = _normalizar_dominio(dominio)
    if not d:
        return _upsert_erro(cliente_id, dominio or "", "Domínio inválido")

    try:
        fc_data, effective_url = _firecrawl_scrape_com_variantes(dominio)
    except Exception as e:
        logger.warning(
            "refresh_web_info %s (%s) falhou no Firecrawl: %s: %s",
            cliente_id, d, type(e).__name__, e,
        )
        return _upsert_erro(cliente_id, d, str(e))

    payload = _montar_registro(d, fc_data, effective_url)
    anterior = obter_web_info(cliente_id) or {}
    local = _persistir_logo_cliente(cliente_id, payload.get("logo_url"))
    if local:
        antigo = anterior.get("logo_url") or ""
        if antigo and antigo != local:
            _apagar_logo_local(antigo)
        payload["logo_url"] = local
    elif str(anterior.get("logo_url") or "").startswith("/static/uploads/clientes/"):
        payload["logo_url"] = anterior["logo_url"]
    else:
        payload["logo_url"] = None
    return _upsert_ok(cliente_id, d, payload)


def _upsert_ok(cliente_id, dominio: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = db.get_db()
    try:
        return _upsert_ok_once(conn, cliente_id, dominio, payload)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if not _undefined_table(e):
            raise
        _ensure_cliente_web_info(conn)
        return _upsert_ok_once(conn, cliente_id, dominio, payload)


def _upsert_ok_once(conn, cliente_id, dominio: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cliente_web_info (
                id_cliente, dominio,
                logo_url, favicon_url, titulo, descricao,
                menu_links, dados_extras,
                status, erro_mensagem,
                atualizado_em, criado_em
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                'ok', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (id_cliente) DO UPDATE SET
                dominio       = EXCLUDED.dominio,
                logo_url      = EXCLUDED.logo_url,
                favicon_url   = EXCLUDED.favicon_url,
                titulo        = EXCLUDED.titulo,
                descricao     = EXCLUDED.descricao,
                menu_links    = EXCLUDED.menu_links,
                dados_extras  = COALESCE(EXCLUDED.dados_extras, cliente_web_info.dados_extras),
                status        = 'ok',
                erro_mensagem = NULL,
                atualizado_em = CURRENT_TIMESTAMP
            RETURNING id, id_cliente, dominio, logo_url, favicon_url,
                      titulo, descricao, menu_links, dados_extras,
                      status, erro_mensagem, atualizado_em, criado_em
            """,
            (
                int(cliente_id),
                dominio,
                payload.get("logo_url"),
                payload.get("favicon_url"),
                payload.get("titulo"),
                payload.get("descricao"),
                json.dumps(payload.get("menu_links") or []),
                json.dumps(payload.get("dados_extras")) if payload.get("dados_extras") else None,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return _row_para_dict(row)


def _upsert_erro(cliente_id, dominio: str, mensagem: str) -> Dict[str, Any]:
    conn = db.get_db()
    try:
        return _upsert_erro_once(conn, cliente_id, dominio, mensagem)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if not _undefined_table(e):
            raise
        _ensure_cliente_web_info(conn)
        return _upsert_erro_once(conn, cliente_id, dominio, mensagem)


def _upsert_erro_once(conn, cliente_id, dominio: str, mensagem: str) -> Dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cliente_web_info (
                id_cliente, dominio, status, erro_mensagem,
                atualizado_em, criado_em
            ) VALUES (%s, %s, 'erro', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (id_cliente) DO UPDATE SET
                dominio       = EXCLUDED.dominio,
                status        = 'erro',
                erro_mensagem = EXCLUDED.erro_mensagem,
                atualizado_em = CURRENT_TIMESTAMP
            RETURNING id, id_cliente, dominio, logo_url, favicon_url,
                      titulo, descricao, menu_links, dados_extras,
                      status, erro_mensagem, atualizado_em, criado_em
            """,
            (int(cliente_id), dominio, mensagem[:500]),
        )
        row = cur.fetchone()
        conn.commit()
    return _row_para_dict(row)


def _row_para_dict(row) -> Dict[str, Any]:
    """Serializa timestamps e garante JSON-friendly.

    `menu_links` e `dados_extras` já vêm como dict/list do psycopg 3
    (colunas JSONB), então basta encaminhar. `atualizado_em` e
    `criado_em` viram ISO strings para o frontend consumir sem
    conversão.
    """
    if not row:
        return {}
    def _iso(v):
        if v is None:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)
    if not isinstance(row, dict):
        try:
            row = dict(row)
        except Exception:
            return {}
    return {
        "id": row.get("id"),
        "id_cliente": row.get("id_cliente"),
        "dominio": row.get("dominio"),
        "logo_url": row.get("logo_url"),
        "favicon_url": row.get("favicon_url"),
        "titulo": row.get("titulo"),
        "descricao": row.get("descricao"),
        "menu_links": row.get("menu_links") or [],
        "dados_extras": row.get("dados_extras"),
        "status": row.get("status"),
        "erro_mensagem": row.get("erro_mensagem"),
        "atualizado_em": _iso(row.get("atualizado_em")),
        "criado_em": _iso(row.get("criado_em")),
    }
