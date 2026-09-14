"""Persistência PostgreSQL do Studio de Treinamentos."""

from contextlib import contextmanager
from decimal import Decimal

from psycopg.types.json import Json

from .schema import ensure_schema, seed_imersao


class TrainingNotFoundError(LookupError):
    pass


class TrainingConflictError(ValueError):
    pass


def _money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _serialize(row):
    if not row:
        return row
    data = dict(row)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
    return data


class TrainingStudioRepository:
    def __init__(self, connection=None):
        self._connection = connection
        self._ready = False

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from .. import db

        return db.get_db()

    def ready(self, created_by=None):
        if not self._ready:
            ensure_schema(self.conn)
            self._ready = True
        return seed_imersao(self.conn, created_by=created_by)

    @contextmanager
    def _write(self):
        try:
            with self.conn.cursor() as cursor:
                yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def get_treinamento(self, treinamento_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, titulo, descricao, slug, guia_estilo, created_by, created_at
                  FROM cx_treinamentos
                 WHERE id = %s
                """,
                (treinamento_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Treinamento não encontrado.")
        return _serialize(row)

    def update_treinamento(self, treinamento_id, data):
        fields = []
        values = []
        if "titulo" in data:
            fields.append("titulo = %s")
            values.append(str(data.get("titulo") or "").strip()[:200])
        if "descricao" in data:
            fields.append("descricao = %s")
            values.append(str(data.get("descricao") or "").strip())
        if "guia_estilo" in data:
            fields.append("guia_estilo = %s")
            values.append(Json(data.get("guia_estilo") or {}))
        if not fields:
            return self.get_treinamento(treinamento_id)
        values.append(treinamento_id)
        with self._write() as cursor:
            cursor.execute(
                f"UPDATE cx_treinamentos SET {', '.join(fields)} WHERE id = %s",
                values,
            )
            if cursor.rowcount == 0:
                raise TrainingNotFoundError("Treinamento não encontrado.")
        return self.get_treinamento(treinamento_id)

    def get_sessao(self, sessao_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.treinamento_id, s.slug, s.titulo, s.conteudo_html,
                       s.ordem, s.horario_inicio, s.horario_fim, s.facilitadores,
                       s.tipo, s.origem, s.notas_instrutor, s.palco_json,
                       s.importacao_id, s.created_at, s.updated_at,
                       t.titulo AS treinamento_titulo,
                       t.descricao AS treinamento_descricao,
                       t.guia_estilo
                  FROM cx_treinamento_sessoes s
                  JOIN cx_treinamentos t ON t.id = s.treinamento_id
                 WHERE s.id = %s
                """,
                (sessao_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Sessão não encontrada.")
        data = _serialize(row)
        data["fontes"] = self.list_fontes(sessao_id)
        data["imagens"] = self.list_imagens(sessao_id)
        data["consumo"] = self.consumo(sessao_id)
        data["facilitadores"] = list(data.get("facilitadores") or [])
        data["notas_instrutor"] = dict(data.get("notas_instrutor") or {})
        data["palco_json"] = list(data.get("palco_json") or [])
        if data.get("importacao_id"):
            data["importacao"] = self.get_importacao(data["importacao_id"])
        return data

    def list_sessoes(self, treinamento_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, treinamento_id, slug, titulo, ordem, horario_inicio,
                       horario_fim, facilitadores, tipo, origem, importacao_id,
                       notas_instrutor, updated_at
                  FROM cx_treinamento_sessoes
                 WHERE treinamento_id = %s
                 ORDER BY ordem, id
                """,
                (treinamento_id,),
            )
            rows = []
            for row in cursor.fetchall():
                item = _serialize(row)
                item["facilitadores"] = list(item.get("facilitadores") or [])
                item["notas_instrutor"] = dict(item.get("notas_instrutor") or {})
                rows.append(item)
        return rows

    def get_sessao_by_slug(self, treinamento_id, slug):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM cx_treinamento_sessoes
                 WHERE treinamento_id = %s AND slug = %s
                """,
                (treinamento_id, slug),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Sessão não encontrada.")
        return self.get_sessao(row["id"])

    def update_sessao(self, sessao_id, data):
        fields = ["updated_at = NOW()"]
        values = []
        if "titulo" in data:
            fields.append("titulo = %s")
            values.append(str(data.get("titulo") or "").strip()[:200] or "Sessão")
        if "conteudo_html" in data:
            html = str(data.get("conteudo_html") or "")
            fields.append("conteudo_html = %s")
            values.append(html)
            fields.append("palco_json = %s")
            values.append(Json(_palco_json(html, {"titulo": data.get("titulo")})))
        if "palco_json" in data:
            fields.append("palco_json = %s")
            values.append(Json(data.get("palco_json") or []))
        if "importacao_id" in data:
            fields.append("importacao_id = %s")
            values.append(data.get("importacao_id") or None)
        if "origem" in data:
            fields.append("origem = %s")
            values.append(str(data.get("origem") or "extra")[:20])
        if "notas_instrutor" in data:
            fields.append("notas_instrutor = %s")
            values.append(Json(data.get("notas_instrutor") or {}))
        if "ordem" in data:
            fields.append("ordem = %s")
            values.append(int(data.get("ordem") or 0))
        if "horario_inicio" in data:
            fields.append("horario_inicio = %s")
            values.append(str(data.get("horario_inicio") or "")[:5] or None)
        if "horario_fim" in data:
            fields.append("horario_fim = %s")
            values.append(str(data.get("horario_fim") or "")[:5] or None)
        if "tipo" in data:
            fields.append("tipo = %s")
            values.append(str(data.get("tipo") or "bloco")[:20])
        values.append(sessao_id)
        with self._write() as cursor:
            cursor.execute(
                f"UPDATE cx_treinamento_sessoes SET {', '.join(fields)} WHERE id = %s",
                values,
            )
            if cursor.rowcount == 0:
                raise TrainingNotFoundError("Sessão não encontrada.")
        return self.get_sessao(sessao_id)

    def create_sessao(self, treinamento_id, data):
        from .agenda import SESSIONS

        titulo = str(data.get("titulo") or "").strip()[:200] or "Sessão"
        slug = str(data.get("slug") or "").strip()[:80]
        if not slug:
            slug = _slugify(titulo)
        after = str(data.get("apos_slug") or "").strip()
        official = [item["slug"] for item in SESSIONS]
        ordem = len(official) + 1
        existing = self.list_sessoes(treinamento_id)
        if after:
            for index, item in enumerate(existing):
                if item.get("slug") == after:
                    ordem = int(item.get("ordem") or index) + 1
                    break
        else:
            ordem = max((int(item.get("ordem") or 0) for item in existing), default=0) + 1
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_treinamento_sessoes
                   SET ordem = ordem + 1
                 WHERE treinamento_id = %s AND ordem >= %s
                """,
                (treinamento_id, ordem),
            )
            html = str(data.get("conteudo_html") or "")
            origem = str(data.get("origem") or ("fonte" if data.get("tipo") == "fonte" else "extra"))[:20]
            cursor.execute(
                """
                INSERT INTO cx_treinamento_sessoes (
                    treinamento_id, slug, titulo, conteudo_html, ordem,
                    horario_inicio, horario_fim, facilitadores, tipo,
                    origem, importacao_id, notas_instrutor, palco_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    treinamento_id,
                    _unique_slug(cursor, treinamento_id, slug),
                    titulo,
                    html,
                    ordem,
                    str(data.get("horario_inicio") or "")[:5] or None,
                    str(data.get("horario_fim") or "")[:5] or None,
                    list(data.get("facilitadores") or []),
                    str(data.get("tipo") or "bloco")[:20],
                    origem,
                    data.get("importacao_id") or None,
                    Json(data.get("notas_instrutor") or {}),
                    Json(data.get("palco_json") or _palco_json(html, {"titulo": titulo})),
                ),
            )
            sessao_id = cursor.fetchone()["id"]
        return self.get_sessao(sessao_id)

    def list_fontes(self, sessao_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sessao_id, url, titulo, resumo, incluido_no_contexto,
                       importacao_id, kind, payload, created_at
                  FROM cx_treinamento_fontes
                 WHERE sessao_id = %s
                 ORDER BY created_at DESC, id DESC
                """,
                (sessao_id,),
            )
            return [_serialize(row) for row in cursor.fetchall()]

    def add_fonte(self, sessao_id, url, titulo, resumo, *, kind="page", importacao_id=None, payload=None):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_fontes (
                    sessao_id, url, titulo, resumo, kind, importacao_id, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, sessao_id, url, titulo, resumo, incluido_no_contexto,
                          importacao_id, kind, payload, created_at
                """,
                (
                    sessao_id,
                    url,
                    (titulo or "")[:300],
                    resumo or "",
                    str(kind or "page")[:20],
                    importacao_id,
                    Json(payload or {}),
                ),
            )
            return _serialize(cursor.fetchone())

    def ensure_fonte(
        self,
        sessao_id,
        url,
        titulo,
        resumo,
        incluido=False,
        *,
        kind="page",
        importacao_id=None,
        payload=None,
    ):
        url = str(url or "").strip()
        if not url:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM cx_treinamento_fontes
                 WHERE sessao_id = %s AND url = %s
                """,
                (sessao_id, url),
            )
            row = cursor.fetchone()
        if row:
            if incluido:
                return self.apply_fonte(sessao_id, row["id"])
            for item in self.list_fontes(sessao_id):
                if item["id"] == row["id"]:
                    return item
            return None
        fonte = self.add_fonte(
            sessao_id,
            url,
            titulo,
            resumo,
            kind=kind,
            importacao_id=importacao_id,
            payload=payload,
        )
        if incluido:
            return self.apply_fonte(sessao_id, fonte["id"])
        return fonte

    def apply_fonte(self, sessao_id, fonte_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_treinamento_fontes
                   SET incluido_no_contexto = TRUE
                 WHERE id = %s AND sessao_id = %s
                RETURNING id, sessao_id, url, titulo, resumo, incluido_no_contexto,
                          importacao_id, kind, payload, created_at
                """,
                (fonte_id, sessao_id),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Fonte não encontrada.")
        return _serialize(row)

    def context_fontes(self, sessao_id):
        return [item for item in self.list_fontes(sessao_id) if item.get("incluido_no_contexto")]

    def list_imagens(self, sessao_id, limit=24):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sessao_id, asset_url, thumb_url, prompt, kind,
                       importacao_id, meta, created_at
                  FROM cx_treinamento_imagens
                 WHERE sessao_id = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (sessao_id, int(limit)),
            )
            return [_serialize(row) for row in cursor.fetchall()]

    def add_imagem(
        self,
        sessao_id,
        asset_url,
        prompt,
        thumb_url=None,
        *,
        kind="gerada",
        importacao_id=None,
        meta=None,
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_imagens (
                    sessao_id, asset_url, thumb_url, prompt, kind, importacao_id, meta
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, sessao_id, asset_url, thumb_url, prompt, kind,
                          importacao_id, meta, created_at
                """,
                (
                    sessao_id,
                    asset_url,
                    thumb_url or asset_url,
                    prompt or "",
                    str(kind or "gerada")[:20],
                    importacao_id,
                    Json(meta or {}),
                ),
            )
            return _serialize(cursor.fetchone())

    def add_importacao(self, treinamento_id, sessao_id, data):
        data = data or {}
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_importacoes (
                    treinamento_id, sessao_id, kind, url, video_id, titulo, autor,
                    duracao_s, transcript, transcript_source, descricao,
                    interpretacao, briefing_html, texto, pipeline, frames, costs,
                    hero_url, embed_url, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    treinamento_id,
                    sessao_id,
                    str(data.get("kind") or "page")[:20],
                    data.get("url") or "",
                    (data.get("video_id") or "")[:20] or None,
                    (data.get("titulo") or "")[:300],
                    (data.get("autor") or "")[:200],
                    int(data.get("duracao_s") or 0),
                    data.get("transcript") or "",
                    str(data.get("transcript_source") or "")[:40],
                    data.get("descricao") or "",
                    data.get("interpretacao") or data.get("resumo") or "",
                    data.get("briefing_html") or "",
                    data.get("texto") or "",
                    Json(data.get("pipeline") or []),
                    Json(data.get("frames") or []),
                    Json(data.get("costs") or []),
                    data.get("hero_url") or "",
                    data.get("embed_url") or "",
                    str(data.get("status") or "ingested")[:20],
                ),
            )
            return _hydrate_importacao(cursor.fetchone())

    def update_importacao(self, importacao_id, data):
        if not importacao_id:
            return None
        fields = []
        values = []
        if "status" in data:
            fields.append("status = %s")
            values.append(str(data.get("status") or "ingested")[:20])
        if "applied_mode" in data:
            fields.append("applied_mode = %s")
            values.append(str(data.get("applied_mode") or "")[:20] or None)
        if data.get("applied"):
            fields.append("applied_at = NOW()")
        if "sessao_id" in data:
            fields.append("sessao_id = %s")
            values.append(data.get("sessao_id") or None)
        if not fields:
            return self.get_importacao(importacao_id)
        values.append(importacao_id)
        with self._write() as cursor:
            cursor.execute(
                f"UPDATE cx_treinamento_importacoes SET {', '.join(fields)} WHERE id = %s",
                values,
            )
        return self.get_importacao(importacao_id)

    def get_importacao(self, importacao_id):
        if not importacao_id:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_treinamento_importacoes WHERE id = %s",
                (importacao_id,),
            )
            row = cursor.fetchone()
        return _hydrate_importacao(row)

    def list_importacoes(self, treinamento_id, limit=20):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, treinamento_id, sessao_id, kind, url, video_id, titulo,
                       autor, duracao_s, transcript_source, hero_url, embed_url,
                       status, applied_mode, applied_at, created_at
                  FROM cx_treinamento_importacoes
                 WHERE treinamento_id = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (treinamento_id, int(limit)),
            )
            return [_serialize(row) for row in cursor.fetchall()]

    def add_agent_message(
        self,
        sessao_id,
        role,
        content,
        tool_used=None,
        display=None,
        *,
        surface=None,
        selection=None,
        importacao_id=None,
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_agent_mensagens (
                    sessao_id, role, content, tool_used, display_payload,
                    surface, selection, importacao_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, sessao_id, role, content, tool_used, display_payload,
                          surface, selection, importacao_id, created_at
                """,
                (
                    sessao_id,
                    role,
                    content or "",
                    tool_used,
                    Json(display or {}),
                    (surface or (display or {}).get("surface") or "")[:20] or None,
                    (selection or "")[:4000],
                    importacao_id or (display or {}).get("importacao_id"),
                ),
            )
            return _serialize(cursor.fetchone())

    def list_agent_messages(self, sessao_id, limit=40):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sessao_id, role, content, tool_used, display_payload,
                       surface, selection, importacao_id, created_at
                  FROM cx_treinamento_agent_mensagens
                 WHERE sessao_id = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (sessao_id, int(limit)),
            )
            rows = [_serialize(row) for row in cursor.fetchall()]
        rows.reverse()
        return rows

    def add_ledger(self, treinamento_id, sessao_id, kind, model, usage, cost_usd, cost_brl, rate, source, provider="openai"):
        usage = usage or {}
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_ai_ledger (
                    treinamento_id, sessao_id, kind, provider, model,
                    prompt_tokens, completion_tokens,
                    cost_usd, cost_brl, usd_brl_rate, usd_brl_source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    treinamento_id,
                    sessao_id,
                    kind,
                    str(provider or "openai")[:40],
                    model,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    Decimal(str(_money(cost_usd))),
                    Decimal(str(_money(cost_brl))),
                    Decimal(str(_money(rate))) if rate else None,
                    source,
                ),
            )
            return cursor.fetchone()["id"]

    def consumo(self, sessao_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0) AS cost_usd,
                       COALESCE(SUM(cost_brl), 0) AS cost_brl
                  FROM cx_treinamento_ai_ledger
                 WHERE sessao_id = %s
                """,
                (sessao_id,),
            )
            totals = _serialize(cursor.fetchone()) or {"cost_usd": 0, "cost_brl": 0}
            cursor.execute(
                """
                SELECT kind,
                       COALESCE(SUM(cost_usd), 0) AS cost_usd,
                       COALESCE(SUM(cost_brl), 0) AS cost_brl
                  FROM cx_treinamento_ai_ledger
                 WHERE sessao_id = %s
                 GROUP BY kind
                """,
                (sessao_id,),
            )
            by_kind = {
                row["kind"]: {
                    "cost_usd": _money(row["cost_usd"]),
                    "cost_brl": _money(row["cost_brl"]),
                }
                for row in cursor.fetchall()
            }
        return {
            "cost_usd": _money(totals.get("cost_usd")),
            "cost_brl": _money(totals.get("cost_brl")),
            "by_kind": by_kind,
        }

    def consumo_treinamento(self, treinamento_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0) AS cost_usd,
                       COALESCE(SUM(cost_brl), 0) AS cost_brl
                  FROM cx_treinamento_ai_ledger
                 WHERE treinamento_id = %s
                """,
                (treinamento_id,),
            )
            totals = _serialize(cursor.fetchone()) or {"cost_usd": 0, "cost_brl": 0}
        return {
            "cost_usd": _money(totals.get("cost_usd")),
            "cost_brl": _money(totals.get("cost_brl")),
            "by_kind": {},
        }


def _hydrate_importacao(row):
    if not row:
        return None
    data = _serialize(row)
    data["pipeline"] = list(data.get("pipeline") or [])
    data["frames"] = list(data.get("frames") or [])
    data["costs"] = list(data.get("costs") or [])
    return data


def _palco_json(html, sessao=None):
    from .slides.live import slides_payload

    return slides_payload(html, sessao)


def _slugify(value):
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:80] or "sessao"


def _unique_slug(cursor, treinamento_id, slug):
    base = slug or "sessao"
    candidate = base
    index = 2
    while True:
        cursor.execute(
            """
            SELECT 1 FROM cx_treinamento_sessoes
             WHERE treinamento_id = %s AND slug = %s
            """,
            (treinamento_id, candidate),
        )
        if cursor.fetchone() is None:
            return candidate
        candidate = f"{base}-{index}"[:80]
        index += 1
