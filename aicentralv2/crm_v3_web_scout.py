"""CRM v3 — Web Scout (crawl mínimo do site do cliente via Firecrawl).

Fase B do plano macro (set/2026): quando o usuário confirma o site em
"Site & logo", disparamos um `POST /v1/scrape` do Firecrawl na home,
extraímos `og:image`/`favicon` (logo canônico do próprio site — muito
melhor que Clearbit ou Google Favicons para clientes locais),
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
- Timeout de 30s no request. Sites lentos não travam o CRM.
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
from urllib.parse import urlparse

import requests

from . import db

logger = logging.getLogger("aicentral.crm_v3.web_scout")

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_TIMEOUT_S = 30


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
        # Firecrawl v1 retorna links como strings simples em `data.links`.
        # Se algum dia mudar para dicts, damos suporte transparente.
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


def _firecrawl_scrape(url: str) -> Dict[str, Any]:
    """Chama Firecrawl /v1/scrape e devolve `data` bruto.

    Lança RuntimeError com mensagem amigável em caso de falha (chave
    ausente, HTTP != 2xx, timeout). O caller decide se persiste com
    status='erro' ou propaga.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY não configurada")

    payload = {
        "url": url,
        # `markdown` habilita o metadata rico (ogImage, favicon, title,
        # description). `links` traz o menu para _extrair_menu_links.
        "formats": ["markdown", "links"],
        # onlyMainContent=false porque queremos o <head> completo (og:*).
        "onlyMainContent": False,
    }
    try:
        resp = requests.post(
            FIRECRAWL_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=FIRECRAWL_TIMEOUT_S,
        )
    except requests.Timeout as e:
        raise RuntimeError(f"Timeout ao acessar Firecrawl ({FIRECRAWL_TIMEOUT_S}s)") from e
    except requests.RequestException as e:
        raise RuntimeError(f"Erro de rede ao acessar Firecrawl: {e}") from e

    if resp.status_code // 100 != 2:
        # Firecrawl devolve JSON com `error` na maioria dos casos.
        try:
            body = resp.json()
            msg = body.get("error") or body.get("message") or f"HTTP {resp.status_code}"
        except Exception:
            msg = f"HTTP {resp.status_code}"
        raise RuntimeError(f"Firecrawl: {msg}")

    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"Firecrawl: {body.get('error') or 'resposta sem success=true'}")
    return body.get("data") or {}


def _montar_registro(dominio: str, fc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Traduz o payload do Firecrawl para o shape da tabela.

    Prioridades de logo (ordem de fallback):
        1. og:image (imagem que o próprio site publica para redes sociais).
        2. metadata.favicon (link rel=icon absoluto).
        3. /favicon.ico do apex (fallback duro).
    """
    meta = fc_data.get("metadata") or {}
    # og:image pode vir como `ogImage` (v1) ou `og:image` (v0). Cobre ambos.
    og_image = (
        meta.get("ogImage")
        or meta.get("og:image")
        or meta.get("twitterImage")
        or ""
    )
    favicon = meta.get("favicon") or ""

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

    menu_links = _extrair_menu_links(fc_data.get("links") or [], dominio)

    return {
        "logo_url": og_image or None,
        "favicon_url": favicon or None,
        "titulo": (titulo or "").strip()[:255] or None,
        "descricao": (descricao or "").strip() or None,
        "menu_links": menu_links,
        "dados_extras": None,  # Reservado para Fase C.
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
    """Baixa o og:image e grava em static/uploads/clientes (igual audiências)."""
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
        _LOGO_DIR.mkdir(parents=True, exist_ok=True)
        ext = _ext_logo(raw, resp.headers.get("Content-Type") or "")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cliente_{int(cliente_id)}_{ts}{ext}"
        filepath = _LOGO_DIR / filename
        total = 0
        with open(filepath, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _LOGO_MAX_BYTES:
                    fh.close()
                    try:
                        filepath.unlink()
                    except OSError:
                        pass
                    logger.info("logo %s excedeu %s bytes", raw[:80], _LOGO_MAX_BYTES)
                    return None
                fh.write(chunk)
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

    url = _dominio_para_url(d)
    try:
        fc_data = _firecrawl_scrape(url)
    except Exception as e:
        logger.warning(
            "refresh_web_info %s (%s) falhou no Firecrawl: %s: %s",
            cliente_id, d, type(e).__name__, e,
        )
        return _upsert_erro(cliente_id, d, str(e))

    payload = _montar_registro(d, fc_data)
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
