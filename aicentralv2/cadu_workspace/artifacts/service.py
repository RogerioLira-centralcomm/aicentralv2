"""Artifact persistence with optimistic versioning and tenant scoping."""

import json
import re
from html.parser import HTMLParser
from uuid import uuid4

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from ...db import get_db
from ..agent_v2.contracts import RequestContext
from .catalog import ALLOWED_TYPES, definition


ALLOWED_STATUS = {"draft", "active", "published", "archived"}
_VOID_HTML_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _BalancedFragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        if tag not in _VOID_HTML_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        return None

    def handle_endtag(self, tag):
        if tag in _VOID_HTML_TAGS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.invalid = True
            return
        self.stack.pop()


def _balanced_css(value: str) -> bool:
    cleaned = re.sub(r"/\*.*?\*/", "", str(value or ""), flags=re.S)
    cleaned = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "", cleaned)
    return cleaned.count("{") == cleaned.count("}") and not cleaned.rstrip().endswith(("{", ":", ","))


def _nested_html(value):
    """Recover HTML from legacy/provider envelopes without accepting partial JSON."""
    if isinstance(value, dict):
        patch = value.get("artifact_patch")
        if isinstance(patch, dict) and str(patch.get("html") or "").strip():
            return str(patch["html"]), str(patch.get("css") or ""), str(patch.get("js") or "")
        text = value.get("text")
        if isinstance(text, dict) and str(text.get("content") or "").lstrip().lower().startswith(("<!doctype", "<html")):
            return str(text["content"]), "", ""
        for key in ("structured_output", "output", "data"):
            recovered = _nested_html(value.get(key))
            if recovered:
                return recovered
    return None


def normalize_html_content(value: dict) -> dict:
    content = dict(value)
    html = str(content.get("html") or "").strip()
    if not html:
        serialized = str(content.get("summary") or "").strip().lstrip("\ufeff")
        if serialized.startswith(("{", "```")):
            if serialized.startswith("```json") and serialized.endswith("```"):
                serialized = serialized[7:-3].strip()
            elif serialized.startswith("```") and serialized.endswith("```"):
                serialized = serialized[3:-3].strip()
            try:
                recovered = _nested_html(json.loads(serialized))
            except (TypeError, ValueError):
                recovered = None
            if recovered:
                html, recovered_css, recovered_js = recovered
                content["html"] = html
                content["css"] = str(content.get("css") or recovered_css)
                content["js"] = str(content.get("js") or recovered_js)
                content.pop("summary", None)
    html = str(content.get("html") or "").strip()
    if not html:
        raise BadRequest("A página HTML não possui conteúdo utilizável. Gere novamente o dashboard completo.")
    lowered = html.lower()
    if ((lowered.startswith(("<!doctype", "<html")) and "</html>" not in lowered)
            or ("<style" in lowered and "</style>" not in lowered)
            or ("<script" in lowered and "</script>" not in lowered)):
        raise BadRequest("O HTML está incompleto ou truncado e não foi salvo. Gere novamente a página completa.")
    # The runtime owns the outer document. Accept complete documents from MCP
    # clients, but project only their body/styles/scripts into the canonical contract.
    if lowered.startswith(("<!doctype", "<html")):
        styles = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", html, flags=re.I | re.S)
        scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", html, flags=re.I | re.S)
        body = re.search(r"<body\b[^>]*>(.*?)</body\s*>", html, flags=re.I | re.S)
        if not body:
            raise BadRequest("O documento HTML não contém um corpo completo e não foi salvo.")
        content["html"] = re.sub(
            r"<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>", "", body.group(1),
            flags=re.I | re.S,
        ).strip()
        content["css"] = "\n".join(filter(None, [str(content.get("css") or "").strip(), *styles])).strip()
        content["js"] = "\n".join(filter(None, [str(content.get("js") or "").strip(), *scripts])).strip()
    if not re.search(r"<\s*[a-z][^>]*>", str(content.get("html") or ""), flags=re.I):
        raise BadRequest("A página HTML precisa conter marcação renderizável.")
    fragment = _BalancedFragment()
    fragment.feed(str(content.get("html") or ""))
    fragment.close()
    if fragment.invalid or fragment.stack or not str(content.get("html") or "").rstrip().endswith(">"):
        raise BadRequest("O fragmento HTML está incompleto ou truncado e não foi salvo.")
    if not _balanced_css(str(content.get("css") or "")):
        raise BadRequest("O CSS está incompleto ou truncado e não foi salvo.")
    return content


def _content(value, artifact_type: str) -> dict:
    if not isinstance(value, dict):
        raise BadRequest("O conteúdo do artefato precisa ser estruturado.")
    if artifact_type == "html":
        value = normalize_html_content(value)
    else:
        # A recognized type and a JSON object are not enough to make a useful
        # artifact. Reject title-only/empty drafts before they reach the editor.
        usable_keys = {
            "brief": ("summary", "fields", "sections", "html", "source_markdown", "brand", "campaign"),
            "document": ("summary", "fields", "sections", "html", "content", "source_markdown"),
            "note": ("summary", "fields", "sections", "html", "content", "source_markdown"),
            "executive_summary": ("summary", "fields", "sections", "highlights", "metrics", "kpis", "tables", "html", "source_markdown"),
            "media_plan": ("summary", "fields", "sections", "tables", "channels", "allocations", "rows", "html", "source_markdown"),
            "scenario": ("summary", "fields", "sections", "options", "tables", "html", "source_markdown"),
            "research": ("summary", "fields", "sections", "tables", "citations", "html", "source_markdown"),
            "project_map": ("groups", "resources"),
            "meeting_summary": ("summary", "fields", "sections", "html", "source_markdown"),
            "meeting_agenda": ("summary", "fields", "sections", "html", "source_markdown"),
            "link_reader": ("url",),
        }.get(artifact_type, ())
        def has_value(item):
            if isinstance(item, str):
                return bool(item.strip())
            if isinstance(item, dict):
                return any(has_value(child) for child in item.values())
            if isinstance(item, (list, tuple)):
                return any(has_value(child) for child in item)
            return item is not None

        def has_fields(items):
            if not isinstance(items, list):
                return False
            for field in items:
                if not isinstance(field, dict) or not str(field.get("key") or field.get("title") or "").strip():
                    continue
                field_value = field.get("value")
                if field_value is None:
                    field_value = field.get("content")
                if field_value is None:
                    field_value = field.get("text")
                if has_value(field_value):
                    return True
                if str(field.get("state") or "").lower() in {"missing", "conflicting"}:
                    return True
            return False

        def has_tables(items):
            if not isinstance(items, list):
                return False
            for table in items:
                if not isinstance(table, dict) or not isinstance(table.get("rows"), list):
                    continue
                if any(has_value(row) for row in table["rows"]):
                    return True
            return False

        def has_content_key(key):
            item = value.get(key)
            if key in {"fields", "sections"}:
                return has_fields(item)
            if key == "tables":
                return has_tables(item)
            if key in {"rows", "channels", "allocations", "options", "citations", "highlights"}:
                return has_value(item)
            return has_value(item)

        if not any(key in value and has_content_key(key) for key in usable_keys):
            raise BadRequest("O artefato não tem conteúdo suficiente para ser salvo.")
        if artifact_type in {"brief", "document", "note", "executive_summary", "media_plan",
                             "scenario", "research", "meeting_summary", "meeting_agenda"}:
            fields = value.get("fields", value.get("sections", []))
            if fields is not None and not isinstance(fields, list):
                raise BadRequest("As seções do artefato precisam estar em uma lista.")
            for field in fields or []:
                if not isinstance(field, dict) or not str(field.get("key") or field.get("title") or "").strip():
                    raise BadRequest("Cada seção precisa ter um título e conteúdo estruturado.")
            tables = value.get("tables", [])
            if tables is not None and not isinstance(tables, list):
                raise BadRequest("As tabelas do artefato precisam estar em uma lista.")
            for table in tables or []:
                if not isinstance(table, dict) or not isinstance(table.get("rows", []), list):
                    raise BadRequest("Cada tabela precisa ter linhas estruturadas.")
                if table.get("rows") and not (table.get("columns") or isinstance(table["rows"][0], (list, dict))):
                    raise BadRequest("As linhas da tabela precisam ter cabeçalhos ou chaves identificáveis.")
        if artifact_type == "scenario" and value.get("options") is not None:
            if not isinstance(value["options"], list) or any(not isinstance(item, (str, dict)) for item in value["options"]):
                raise BadRequest("Os cenários precisam estar em uma lista de opções estruturadas.")
        if artifact_type == "link_reader" and not re.match(r"^https://", str(value.get("url") or ""), re.I):
            raise BadRequest("A referência precisa ter uma URL HTTPS válida.")
    size = len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))
    maximum = definition(artifact_type).max_content_bytes
    if size > maximum:
        raise BadRequest(
            f"A entrega possui {size} bytes e excede o limite de {maximum}; "
            "o conteúdo foi recusado integralmente, sem cortes. Divida-o em blocos ou anexos."
        )
    return value


def create_draft(context: RequestContext, artifact_type: str, content: dict, *, title="", conversation_id=None,
                 artifact_id=None) -> dict:
    if artifact_type not in ALLOWED_TYPES:
        raise BadRequest("Tipo de artefato inválido.")
    if context.project_ref:
        _require_project_access(context, str(context.project_ref), write=True)
    content = _content(content, artifact_type)
    artifact_id, version_id = str(artifact_id or uuid4()), str(uuid4())
    title = " ".join(str(title or "").split())[:180] or "Novo artefato"
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id::text,type,project_ref FROM cadu_workspace_artifacts
                            WHERE id=%s AND organization_id=%s AND client_id=%s""",
                        (artifact_id, context.client_id, context.client_id))
            existing = cur.fetchone()
            if existing:
                if existing.get("type") != artifact_type or existing.get("project_ref") != context.project_ref:
                    raise Conflict("O identificador desta entrega já pertence a outro conteúdo.")
                conn.commit()
                return get_artifact(context, artifact_id)
            cur.execute("""INSERT INTO cadu_workspace_artifacts
                (id, organization_id, client_id, project_ref, conversation_id, type, title, status,
                 current_version, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', 1, %s, NOW(), NOW())""",
                (artifact_id, context.client_id, context.client_id, context.project_ref,
                 conversation_id or context.conversation_id, artifact_type, title, context.user_id))
            cur.execute("""INSERT INTO cadu_workspace_artifact_versions
                (id, artifact_id, version, content, change_summary, created_by, created_at)
                VALUES (%s, %s, 1, %s, %s, %s, NOW())""",
                (version_id, artifact_id, Json(content), "Rascunho criado", context.user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if context.project_ref:
        try:
            from ..project_resource_service import notify_change
            notify_change(context.client_id, context.project_ref, "created", source_system="cadu_workspace_artifacts",
                          source_id=artifact_id, actor_id=context.user_id)
        except Exception:
            pass
    artifact = get_artifact(context, artifact_id)
    materialize_artifact(artifact)
    return artifact


def get_artifact(context: RequestContext, artifact_id: str) -> dict:
    with get_db().cursor() as cur:
        cur.execute("""SELECT a.id, a.organization_id, a.client_id, a.project_ref, a.conversation_id, a.type, a.title, a.status,
                              a.current_version, a.created_by, a.created_at, a.updated_at, v.content, v.change_summary
                         FROM cadu_workspace_artifacts a
                         JOIN cadu_workspace_artifact_versions v
                           ON v.artifact_id = a.id AND v.version = a.current_version
                        WHERE a.id = %s AND a.organization_id = %s AND a.client_id = %s""",
                    (str(artifact_id), context.client_id, context.client_id))
        row = cur.fetchone()
    if not row:
        raise NotFound("Artefato indisponível.")
    artifact = dict(row)
    if artifact.get("type") == "html":
        try:
            artifact["content"] = normalize_html_content(artifact.get("content") or {})
        except BadRequest:
            # Keep malformed legacy rows readable by the private UI so it can
            # explain the failure and offer regeneration instead of turning a
            # diagnostic GET into an unrelated transport error.
            pass
    _require_artifact_access(context, artifact)
    artifact["capabilities"] = definition(artifact["type"]).to_dict()
    return artifact


def materialize_artifact(artifact: dict):
    from .workspace import materialize
    return materialize(artifact)


def list_artifacts(context: RequestContext, *, artifact_type=None, status=None, limit=20) -> list[dict]:
    if artifact_type is not None and artifact_type not in ALLOWED_TYPES:
        raise BadRequest("Tipo de artefato inválido.")
    if status is not None and status not in ALLOWED_STATUS:
        raise BadRequest("Status de artefato inválido.")
    limit = min(50, max(1, int(limit or 20)))
    filters = ["a.organization_id = %s", "a.client_id = %s"]
    params = [context.client_id, context.client_id]
    if context.project_ref:
        _require_project_access(context, str(context.project_ref))
        filters.append("a.project_ref = %s")
        params.append(context.project_ref)
    if artifact_type:
        filters.append("a.type = %s")
        params.append(artifact_type)
    if status:
        filters.append("a.status = %s")
        params.append(status)
    params.append(limit)
    with get_db().cursor() as cur:
        cur.execute(f"""SELECT a.id, a.project_ref, a.conversation_id, a.type, a.title, a.status,
                               a.current_version, a.created_by, a.created_at, a.updated_at
                          FROM cadu_workspace_artifacts a
                         WHERE {' AND '.join(filters)}
                      ORDER BY a.updated_at DESC, a.id DESC LIMIT %s""", tuple(params))
        rows = [dict(row) for row in cur.fetchall()]
    visible = []
    for row in rows:
        try:
            _require_artifact_access(context, row)
        except (NotFound, BadRequest):
            continue
        visible.append(row)
    return visible


def list_versions(context: RequestContext, artifact_id: str, *, limit=50) -> list[dict]:
    # Resolve the artifact first so a foreign-tenant ID remains indistinguishable from a missing ID.
    get_artifact(context, artifact_id)
    limit = min(100, max(1, int(limit or 50)))
    with get_db().cursor() as cur:
        cur.execute("""SELECT v.id, v.version, v.change_summary, v.created_by, v.created_at
                         FROM cadu_workspace_artifact_versions v
                        WHERE v.artifact_id = %s
                     ORDER BY v.version DESC LIMIT %s""", (str(artifact_id), limit))
        return [dict(row) for row in cur.fetchall()]


def get_version(context: RequestContext, artifact_id: str, version: int) -> dict:
    get_artifact(context, artifact_id)
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise BadRequest("Versão inválida.")
    with get_db().cursor() as cur:
        cur.execute("""SELECT v.id, v.version, v.content, v.change_summary, v.created_by, v.created_at
                         FROM cadu_workspace_artifact_versions v
                        WHERE v.artifact_id = %s AND v.version = %s""", (str(artifact_id), version))
        row = cur.fetchone()
    if not row:
        raise NotFound("Versão indisponível.")
    return dict(row)


def restore_version(context: RequestContext, artifact_id: str, version: int, *, expected_version: int) -> dict:
    """Create a new current version from an immutable snapshot.

    Published content must be explicitly unpublished first so a restore cannot
    alter a live public URL as a side effect. Archived and read-only resources
    likewise require an explicit lifecycle action before their history changes.
    """
    artifact = get_artifact(context, artifact_id)
    if artifact["status"] == "published":
        raise Conflict("Retire a página da publicação antes de restaurar uma versão.")
    if artifact["status"] == "archived":
        raise Conflict("Reative a entrega antes de restaurar uma versão.")
    if not definition(artifact["type"]).agent_editable:
        raise BadRequest("Este tipo de entrega é uma referência somente para leitura.")
    snapshot = get_version(context, artifact_id, version)
    return patch_artifact(
        context, artifact_id, snapshot["content"], expected_version=expected_version,
        change_summary=f"Versão {int(version)} restaurada",
    )


def patch_artifact(context: RequestContext, artifact_id: str, content: dict, *, expected_version: int,
                   title=None, status=None, change_summary="") -> dict:
    if status not in (None, "archived"):
        raise BadRequest("O estado do artefato deve ser alterado pela ação própria do ciclo de vida.")
    try:
        expected_version = int(expected_version)
    except (TypeError, ValueError):
        raise BadRequest("Informe a versão atual do artefato.")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT current_version,type,status,project_ref,created_by FROM cadu_workspace_artifacts
                            WHERE id = %s AND organization_id = %s AND client_id = %s FOR UPDATE""",
                        (str(artifact_id), context.client_id, context.client_id))
            row = cur.fetchone()
            if not row:
                raise NotFound("Artefato indisponível.")
            artifact = {**row, "id": str(artifact_id)}
            _require_artifact_access(context, artifact, write=True)
            if not definition(row.get("type") or "document").agent_editable:
                raise BadRequest("Este tipo de entrega é uma referência somente para leitura.")
            if row.get("status") in {"published", "archived"}:
                raise Conflict("Retire a publicação ou reative o artefato antes de editá-lo.")
            if status == "archived" and row.get("status") not in {"draft", "active"}:
                raise Conflict("Somente artefatos em rascunho ou ativos podem ser arquivados.")
            content = _content(content, row.get("type") or "document")
            if int(row["current_version"]) != expected_version:
                raise Conflict("O artefato foi alterado. Atualize antes de salvar novamente.")
            next_version = expected_version + 1
            cur.execute("""INSERT INTO cadu_workspace_artifact_versions
                (id, artifact_id, version, content, change_summary, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                (str(uuid4()), str(artifact_id), next_version, Json(content),
                 str(change_summary or "Atualização")[:500], context.user_id))
            cur.execute("""UPDATE cadu_workspace_artifacts
                               SET current_version = %s,
                                   title = COALESCE(%s, title), status = COALESCE(%s, status), updated_at = NOW()
                             WHERE id = %s""",
                        (next_version, " ".join(str(title).split())[:180] if title is not None else None,
                         status, str(artifact_id)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if context.project_ref:
        try:
            from ..project_resource_service import notify_change
            notify_change(context.client_id, context.project_ref, "versioned", source_system="cadu_workspace_artifacts",
                          source_id=str(artifact_id), actor_id=context.user_id)
        except Exception:
            pass
    artifact = get_artifact(context, artifact_id)
    materialize_artifact(artifact)
    return artifact


def attach_to_project(context: RequestContext, artifact_id: str, project_ref: str | None) -> dict:
    """Move an artifact to an authorized project, or return it to the personal space."""
    project_ref = " ".join(str(project_ref or "").split())[:120]
    if project_ref and not project_ref.startswith("ci:"):
        raise BadRequest("Selecione um projeto válido para salvar este documento.")
    # The caller resolves project membership before reaching this service. The
    # artifact lookup still enforces the tenant boundary before any mutation.
    previous = get_artifact(context, artifact_id)
    _require_artifact_access(context, previous, write=True)
    if project_ref:
        _require_project_access(context, project_ref, write=True)
    previous_ref = previous.get("project_ref") or ""
    if previous_ref == project_ref:
        return previous
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE cadu_workspace_artifacts
                              SET project_ref = %s,
                                  status = CASE WHEN %s IS NULL AND status = 'active' THEN 'draft' ELSE status END,
                                  updated_at = NOW()
                            WHERE id = %s AND organization_id = %s AND client_id = %s""",
                        (project_ref or None, project_ref or None, str(artifact_id), context.client_id, context.client_id))
            if cur.rowcount != 1:
                raise NotFound("Artefato indisponível.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    from ..project_resource_service import notify_change
    for changed_ref, event in ((previous_ref, "detached"), (project_ref, "attached")):
        if changed_ref:
            try:
                notify_change(context.client_id, changed_ref, event, source_system="cadu_workspace_artifacts",
                              source_id=str(artifact_id), actor_id=context.user_id)
            except Exception:
                pass
    return get_artifact(context, artifact_id)


class _DocumentText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style"}:
            self.ignored += 1
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "tr", "br", "th", "td"}:
            self.parts.append("\n")
        if tag == "img" and attributes.get("alt"):
            self.parts.append(f" {attributes['alt']} ")
        if tag == "a" and str(attributes.get("href") or "").startswith(("https://", "http://")):
            self.parts.append(f" ({attributes['href']}) ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "tr", "th", "td"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


class _DocumentMarkdown(HTMLParser):
    """Convert the editor's safe rich-text subset to readable Markdown."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0
        self.links = []
        self.list_stack = []
        self.table_head = False
        self.table_cell_count = 0

    def _space(self, count=1):
        value = "\n" * count
        current = self.parts[-1] if self.parts else ""
        if current and not current.endswith(value):
            self.parts.append(value)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style"}:
            self.ignored += 1
            return
        if self.ignored:
            return
        if tag in {"p", "div", "section", "article", "figure", "figcaption"}:
            self._space(2)
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._space(2)
            self.parts.append("#" * int(tag[1]) + " ")
        elif tag == "br":
            self.parts.append("  \n")
        elif tag in {"ul", "ol"}:
            self._space()
            self.list_stack.append({"tag": tag, "count": 0})
        elif tag == "li":
            self._space()
            depth = max(0, len(self.list_stack) - 1)
            if self.list_stack and self.list_stack[-1]["tag"] == "ol":
                self.list_stack[-1]["count"] += 1
                marker = f"{self.list_stack[-1]['count']}. "
            else:
                marker = "- "
            self.parts.append("  " * depth + marker)
        elif tag == "blockquote":
            self._space(2)
            self.parts.append("> ")
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "code":
            self.parts.append("`")
        elif tag == "pre":
            self._space(2)
            self.parts.append("```\n")
        elif tag == "a":
            href = str(attributes.get("href") or "")
            self.links.append(href if href.startswith(("https://", "http://")) else "")
            self.parts.append("[")
        elif tag == "img":
            alt, src = str(attributes.get("alt") or ""), str(attributes.get("src") or "")
            if src.startswith(("https://", "http://")):
                self.parts.append(f"![{alt}]({src})")
            elif alt:
                self.parts.append(alt)
        elif tag == "table":
            self._space(2)
        elif tag == "thead":
            self.table_head = True
        elif tag in {"th", "td"}:
            if self.parts and not self.parts[-1].endswith(("|", " ")):
                self.parts.append(" ")
            self.parts.append("| ")
            self.table_cell_count += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if tag in {"p", "div", "section", "article", "figure", "figcaption", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._space(2 if tag != "li" else 1)
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "code":
            self.parts.append("`")
        elif tag == "pre":
            self._space()
            self.parts.append("```\n")
        elif tag == "a":
            href = self.links.pop() if self.links else ""
            self.parts.append(f"]({href})" if href else "]")
        elif tag == "ul" or tag == "ol":
            if self.list_stack:
                self.list_stack.pop()
            self._space(2)
        elif tag in {"th", "td"}:
            self.parts.append(" ")
        elif tag == "tr":
            self.parts.append("|\n")
            if self.table_head:
                # A separator follows the header row before body rows.
                self.parts.append("|" + " --- |" * max(1, self.table_cell_count) + "\n")
                self.table_head = False
            self.table_cell_count = 0
        elif tag == "table":
            self._space(2)

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)

    def markdown(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip()


def _indexable_text(artifact: dict) -> str:
    content = artifact.get("content") or {}
    source_markdown = str(content.get("source_markdown") or "").strip()
    if source_markdown:
        return source_markdown
    if content.get("html"):
        parser = _DocumentText()
        parser.feed(str(content["html"]))
        return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
    parts = []
    def add(label, value):
        if value is None or isinstance(value, (dict, list, tuple)):
            return
        value = str(value).strip()
        if value:
            parts.append(f"{label}: {value}" if label else value)
    add("Resumo", content.get("summary"))
    for field in content.get("fields") or content.get("sections") or []:
        if isinstance(field, dict):
            state = str(field.get("state") or "").strip()
            add(str(field.get("key") or field.get("title") or "Seção") + (f" [{state}]" if state else ""),
                field.get("value") or field.get("content") or field.get("text"))
            add("Fontes da seção", ", ".join(map(str, field.get("source_ids") or [])))
    for key in ("highlights",):
        for item in content.get(key) or []:
            add("Destaque", item.get("text") or item.get("title") if isinstance(item, dict) else item)
    metrics = content.get("metrics") or content.get("kpis") or {}
    if isinstance(metrics, dict):
        for key, value in metrics.items():
            add(f"Indicador {key}", value)
    tables = list(content.get("tables") or [])
    if not tables and any(content.get(key) for key in ("channels", "allocations", "rows")):
        tables.append({"title": "Distribuição", "columns": content.get("columns") or [],
                      "rows": content.get("channels") or content.get("allocations") or content.get("rows")})
    for table in tables:
        if not isinstance(table, dict):
            continue
        add("Tabela", table.get("title"))
        columns = table.get("columns") or []
        for row in table.get("rows") or []:
            if isinstance(row, dict) and columns:
                keys = [column if isinstance(column, str) else column.get("key") or column.get("name") or column.get("label")
                        for column in columns]
                values = [row.get(key, "") for key in keys]
                labels = [column if isinstance(column, str) else column.get("label") or column.get("name") or column.get("key")
                          for column in columns]
            else:
                values = list(row.values()) if isinstance(row, dict) else row if isinstance(row, list) else [row]
                labels = columns or [f"Coluna {index + 1}" for index in range(len(values))]
            add(" | ".join(str(label) for label in labels), " | ".join(str(value) for value in values))
    for index, option in enumerate(content.get("options") or [], 1):
        if not isinstance(option, dict):
            add(f"Cenário {index}", option)
            continue
        add("Cenário", option.get("title"))
        add("Descrição", option.get("summary") or option.get("description") or option.get("content"))
        for key, value in (option.get("metrics") or {}).items() if isinstance(option.get("metrics"), dict) else []:
            add(f"{option.get('title') or 'Cenário'} — {key}", value)
    for citation in content.get("citations") or []:
        if isinstance(citation, str):
            add("Fonte", citation)
        elif isinstance(citation, dict):
            add("Fonte", " — ".join(str(value) for value in (citation.get("title") or citation.get("source"), citation.get("url")) if value))
            add("Trecho da fonte", citation.get("excerpt"))
    return "\n".join(parts)


def content_markdown(artifact: dict) -> str:
    content = artifact.get("content") if isinstance(artifact.get("content"), dict) else {}
    if content.get("html"):
        parser = _DocumentMarkdown()
        parser.feed(str(content["html"]))
        body = parser.markdown()
        return f"# {artifact.get('title') or 'Documento'}\n\n{body}".strip()
    parts = [f"# {artifact.get('title') or 'Documento'}"]
    if content.get("summary"):
        parts.append(str(content["summary"]).strip())
    for field in content.get("fields") or content.get("sections") or []:
        if not isinstance(field, dict):
            continue
        heading = str(field.get("key") or field.get("title") or "Seção").strip()
        state = str(field.get("state") or "").strip()
        parts.append(f"## {heading}" + (f" ({state})" if state else ""))
        value = field.get("value") or field.get("content") or field.get("text")
        if value:
            parts.append(str(value).strip())
    highlights = content.get("highlights") or []
    if highlights:
        parts.extend(["## Destaques", "\n".join(
            f"- {item.get('text') or item.get('title') or item.get('value') or ''}" if isinstance(item, dict)
            else f"- {item}" for item in highlights)])
    metrics = content.get("metrics") or content.get("kpis") or {}
    if isinstance(metrics, dict) and metrics:
        parts.extend(["## Indicadores", "| Indicador | Valor |", "| --- | --- |"])
        parts.extend(f"| {str(key).replace('|', '\\|')} | {str(value).replace('|', '\\|')} |" for key, value in metrics.items())
    tables = list(content.get("tables") or [])
    if not tables and any(content.get(key) for key in ("channels", "allocations", "rows")):
        tables.append({"title": "Distribuição", "columns": content.get("columns") or [],
                      "rows": content.get("channels") or content.get("allocations") or content.get("rows")})
    for table in tables:
        if not isinstance(table, dict) or not table.get("rows"):
            continue
        columns = table.get("columns") or []
        rows = table["rows"]
        first = rows[0]
        if not columns:
            columns = list(first.keys()) if isinstance(first, dict) else [f"Item {index + 1}" for index in range(len(first))]
        labels = [str(column if isinstance(column, str) else column.get("label") or column.get("name") or column.get("key") or "Coluna")
                  for column in columns]
        keys = [column if isinstance(column, str) else column.get("key") or column.get("name") or column.get("label")
                for column in columns]
        markdown_rows = ["| " + " | ".join(label.replace("|", "\\|") for label in labels) + " |",
                         "| " + " | ".join("---" for _ in labels) + " |"]
        for row in rows:
            values = [row.get(key, "") for key in keys] if isinstance(row, dict) else list(row) if isinstance(row, list) else [row]
            markdown_rows.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", "<br>") for value in values) + " |")
        if table.get("title"):
            parts.append(f"## {table['title']}")
        parts.append("\n".join(markdown_rows))
    for index, option in enumerate(content.get("options") or [], 1):
        if isinstance(option, str):
            parts.extend([f"## Cenário {index}", option])
            continue
        if not isinstance(option, dict):
            continue
        parts.append(f"## {option.get('title') or f'Cenário {index}'}")
        body = option.get("summary") or option.get("description") or option.get("content")
        if body:
            parts.append(str(body).strip())
        if isinstance(option.get("metrics"), dict) and option["metrics"]:
            parts.extend(["| Indicador | Valor |", "| --- | --- |"])
            parts.extend(f"| {key} | {value} |" for key, value in option["metrics"].items())
    citations = content.get("citations") or []
    if citations:
        parts.append("## Fontes")
        for citation in citations:
            if isinstance(citation, str):
                parts.append(f"- {citation}")
            elif isinstance(citation, dict):
                title = citation.get("title") or citation.get("source") or citation.get("url") or "Fonte"
                url = citation.get("url") or citation.get("href") or citation.get("link")
                parts.append(f"- [{title}]({url})" if url else f"- {title}")
                if citation.get("excerpt"):
                    parts.append(f"  {citation['excerpt']}")
    return "\n\n".join(part for part in parts if part and str(part).strip()).strip()


def _require_project_access(context: RequestContext, project_ref: str, *, write=False):
    from ...cadu_family import repository
    if not project_ref or not repository.project_user_can_view(context.client_id, project_ref, context.user_id):
        raise NotFound("Projeto indisponível.")
    if write:
        actor = repository.actor(context.user_id) or {}
        admin = int(actor.get("organization_id") or 0) == context.client_id and repository.account_role(actor) == "admin"
        roles = {item.get("role") for item in repository.project_access(context.client_id, project_ref)
                 if int(item.get("user_id") or 0) == context.user_id}
        if not admin and not roles.intersection({"owner", "admin", "editor"}):
            raise BadRequest("Você não pode alterar materiais neste projeto.")


def _require_artifact_access(context: RequestContext, artifact: dict, *, write=False):
    project_ref = str(artifact.get("project_ref") or "")
    if project_ref:
        _require_project_access(context, project_ref, write=write)
        return
    if int(artifact.get("created_by") or 0) != int(context.user_id or 0):
        raise NotFound("Artefato indisponível.")


def finalize_to_project(context: RequestContext, artifact_id: str, *, expected_version: int,
                        source_format: str | None = None) -> dict:
    """Make the latest approved document the project's sole indexed snapshot."""
    from ...cadu_family import repository
    from ...cadu_skills.repository import charge_project_rag
    from .. import project_index_service, project_knowledge
    from ..project_resource_service import notify_change

    try:
        expected_version = int(expected_version)
    except (TypeError, ValueError) as exc:
        raise BadRequest("Informe a versão atual do documento para finalizar.") from exc
    if expected_version < 1:
        raise BadRequest("Informe uma versão válida do documento.")
    project_ref = str(context.project_ref or "")
    if not project_ref.startswith("ci:"):
        raise BadRequest("Selecione um projeto nativo para finalizar o documento.")
    if not repository.project_user_can_view(context.client_id, project_ref, context.user_id):
        raise NotFound("Projeto indisponível.")
    actor = repository.actor(context.user_id) or {}
    admin = int(actor.get("organization_id") or 0) == context.client_id and repository.account_role(actor) == "admin"
    roles = {item.get("role") for item in repository.project_access(context.client_id, project_ref)
             if int(item.get("user_id") or 0) == context.user_id}
    if not admin and not roles.intersection({"owner", "admin", "editor"}):
        raise BadRequest("Você não pode finalizar documentos neste projeto.")
    artifact = get_artifact(context, artifact_id)
    _require_artifact_access(context, artifact, write=True)
    source_format = str(source_format or ("html" if artifact["type"] == "html" else "md")).lower()
    if source_format not in ({"html"} if artifact["type"] == "html" else {"md", "txt"}):
        raise BadRequest("Formato de arquivo inválido para este documento.")
    if artifact.get("project_ref") not in {None, project_ref}:
        raise BadRequest("O documento pertence a outro projeto.")
    if int(artifact["current_version"]) != int(expected_version):
        raise Conflict("O documento mudou. Reabra a versão recente antes de finalizar.")
    if not definition(artifact["type"]).indexable:
        raise BadRequest("Esta entrega pode permanecer vinculada ao projeto, mas não entra na base textual.")
    source_markdown = str((artifact.get("content") or {}).get("source_markdown") or "")
    text = (source_markdown if source_markdown.strip() else content_markdown(artifact)) \
        if source_format == "md" else _indexable_text(artifact)
    if len(text) < 20:
        raise BadRequest("O documento precisa de conteúdo suficiente para entrar na base do projeto.")
    project_id = project_ref[3:]
    category = {"brief":"brief", "media_plan":"media_plan", "research":"research"}.get(artifact["type"], "other")
    source_name = f"{artifact['title']}.{source_format}"
    connection = get_db()
    with connection.cursor() as cursor:
        cursor.execute("""SELECT id FROM cadu_ci_projeto_arquivos WHERE id_cliente=%s AND projeto_id=%s
                          AND classification_metadata->>'artifact_id'=%s
                          AND classification_metadata->>'artifact_version'=%s
                          AND purpose='knowledge_source' LIMIT 1""",
                       (context.client_id, project_id, str(artifact_id), str(expected_version)))
        already_indexed = cursor.fetchone()
    connection.rollback()
    if already_indexed:
        return {"artifact": artifact, "source_id": int(already_indexed["id"]), "indexed_version": int(expected_version), "already_finalized": True}

    chunks, embedding_tokens, embedding_model = project_knowledge.index(text)
    metadata = {"classifier":"artifact-final-v2", "artifact_id":str(artifact_id),
                "artifact_version":str(expected_version), "created_via":"document_finalization"}
    classification = {"category":category, "status":"manual", "confidence":1.0,
                      "reason":"Versão final confirmada no artefato."}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                           (f"cadu-artifact-index:{context.client_id}:{artifact_id}",))
            cursor.execute("""SELECT current_version FROM cadu_workspace_artifacts
                              WHERE id=%s AND client_id=%s AND organization_id=%s FOR UPDATE""",
                           (str(artifact_id), context.client_id, context.client_id))
            current = cursor.fetchone()
            if not current or int(current["current_version"]) != int(expected_version):
                raise Conflict("O documento mudou durante a indexação. Tente finalizar novamente.")
            cursor.execute("""SELECT id FROM cadu_ci_projeto_arquivos WHERE id_cliente=%s AND projeto_id=%s
                              AND classification_metadata->>'artifact_id'=%s
                              AND classification_metadata->>'artifact_version'=%s
                              AND purpose='knowledge_source' LIMIT 1""",
                           (context.client_id, project_id, str(artifact_id), str(expected_version)))
            duplicate = cursor.fetchone()
            if duplicate:
                connection.commit()
                return {"artifact": get_artifact(context, artifact_id), "source_id": int(duplicate["id"]),
                        "indexed_version": expected_version, "already_finalized": True}
            cursor.execute("""SELECT id FROM cadu_ci_projeto_arquivos WHERE id_cliente=%s AND projeto_id=%s
                              AND classification_metadata->>'artifact_id'=%s
                              AND purpose='knowledge_source' FOR UPDATE""",
                           (context.client_id, project_id, str(artifact_id)))
            previous = [int(row["id"]) for row in cursor.fetchall()]
            charged = charge_project_rag(cursor, client_id=context.client_id, user_id=context.user_id,
                                         project_id=project_id, tokens=embedding_tokens, stage="indexacao",
                                         idempotency_key=f"artifact-final:{artifact_id}:v{expected_version}")
            source_id = project_index_service.persist_indexed_source(
                cursor, project_id=project_id, client_id=context.client_id, user_id=context.user_id,
                name=source_name, mime={"html": "text/html", "md": "text/markdown", "txt": "text/plain"}[source_format],
                size=len(text.encode("utf-8")),
                storage_path=f"workspace://artifact/{artifact_id}/v{expected_version}", source="artifact_final",
                content=text, chunks=chunks, embedding_model=embedding_model, charged_tokens=charged,
                classification=classification, metadata=metadata)
            if previous:
                cursor.execute("DELETE FROM cadu_ci_chunks WHERE id_cliente=%s AND projeto_id=%s AND arquivo_id=ANY(%s)",
                               (context.client_id, project_id, previous))
                cursor.execute("""UPDATE cadu_ci_projeto_arquivos SET purpose='project_attachment',
                                  indexing_status='superseded', updated_at=NOW()
                                  WHERE id_cliente=%s AND projeto_id=%s AND id=ANY(%s)""",
                               (context.client_id, project_id, previous))
                cursor.execute("""UPDATE cadu_ci_projetos
                                  SET total_arquivos=GREATEST(COALESCE(total_arquivos,0)-%s,0), updated_at=NOW()
                                  WHERE id=%s AND id_cliente=%s""",
                               (len(previous), project_id, context.client_id))
            cursor.execute("""UPDATE cadu_workspace_artifacts
                              SET project_ref=%s,
                                  status=CASE WHEN status IN ('draft', 'archived') THEN 'active' ELSE status END,
                                  updated_at=NOW()
                              WHERE id=%s AND client_id=%s AND organization_id=%s""",
                           (project_ref, str(artifact_id), context.client_id, context.client_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    try:
        notify_change(context.client_id, project_ref, "indexed", source_system="cadu_workspace_artifacts",
                      source_id=str(artifact_id), actor_id=context.user_id)
    except Exception:
        pass
    return {"artifact": get_artifact(context, artifact_id), "source_id": source_id,
            "indexed_version": int(expected_version), "already_finalized": False}


def publish_artifact(context: RequestContext, artifact_id: str) -> dict:
    """Make an HTML artifact available through its opaque public UUID URL."""
    artifact = get_artifact(context, artifact_id)
    _require_artifact_access(context, artifact, write=True)
    if artifact.get("type") != "html":
        raise BadRequest("Somente artefatos HTML podem ser publicados como página pública.")
    # Legacy rows may predate strict creation/update validation. Never expose a
    # public URL for an empty, serialized or visibly truncated document.
    _content(artifact.get("content"), "html")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE cadu_workspace_artifacts
                              SET status = 'published', updated_at = NOW()
                            WHERE id = %s AND organization_id = %s AND client_id = %s""",
                        (str(artifact_id), context.client_id, context.client_id))
            if cur.rowcount != 1:
                raise NotFound("Artefato indisponível.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_artifact(context, artifact_id)


def unpublish_artifact(context: RequestContext, artifact_id: str) -> dict:
    """Revoke the public URL while keeping the HTML artifact and its versions."""
    artifact = get_artifact(context, artifact_id)
    _require_artifact_access(context, artifact, write=True)
    if artifact.get("type") != "html":
        raise BadRequest("Somente artefatos HTML podem ser retirados da publicação.")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE cadu_workspace_artifacts
                              SET status = 'draft', updated_at = NOW()
                            WHERE id = %s AND organization_id = %s AND client_id = %s""",
                        (str(artifact_id), context.client_id, context.client_id))
            if cur.rowcount != 1:
                raise NotFound("Artefato indisponível.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_artifact(context, artifact_id)


def get_public_artifact(artifact_id: str) -> dict:
    """Read only published HTML; intentionally has no session or tenant input."""
    with get_db().cursor() as cur:
        cur.execute("""SELECT a.id, a.type, a.title, a.status, a.current_version,
                              a.created_at, a.updated_at, v.content
                         FROM cadu_workspace_artifacts a
                         JOIN cadu_workspace_artifact_versions v
                           ON v.artifact_id = a.id AND v.version = a.current_version
                        WHERE a.id = %s AND a.type = 'html' AND a.status = 'published'""",
                    (str(artifact_id),))
        row = cur.fetchone()
    if not row:
        raise NotFound("Página pública indisponível.")
    return dict(row)
