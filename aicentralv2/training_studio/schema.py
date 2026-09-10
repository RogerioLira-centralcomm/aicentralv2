"""DDL e seed do Studio de Treinamentos."""

from psycopg.types.json import Json

from .agenda import SESSIONS, session_html

IMMERSAO_SLUG = "imersao-midias-complexas"

DEFAULT_STYLE_GUIDE = {
    "palette": [
        {"hex": "#071422", "name": "navy", "usage": "fundo"},
        {"hex": "#5EEAD4", "name": "menta", "usage": "destaque"},
        {"hex": "#F8FAFC", "name": "off-white", "usage": "texto e superfícies"},
    ],
    "tone": (
        "fotografia corporativa premium + ilustração flat minimalista, "
        "paleta navy/menta, sem ruído visual"
    ),
    "brands": ["MediaHacks Training", "Centralcomm Media Hub"],
    "motto": "Pessoas · Mídia · Resultados",
    "event": {
        "title": "Imersão em Mídias Complexas",
        "date": "28 de setembro",
        "speakers": [
            {"name": "Alexandre Borges", "role": "CEO"},
            {"name": "Apolo Lira", "role": "Co-CEO"},
            {"name": "Max III", "role": "Formatos e métricas"},
            {"name": "Lucas Facchini", "role": "Formatos interativos"},
        ],
    },
    "visual_reference": (
        "arte do convite: fundo dark, logos no topo, retratos oficiais, "
        "tipografia branca condensada e acento menta"
    ),
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cx_treinamentos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    descricao TEXT,
    slug VARCHAR(80) UNIQUE,
    guia_estilo JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cx_treinamento_sessoes (
    id BIGSERIAL PRIMARY KEY,
    treinamento_id INTEGER NOT NULL REFERENCES cx_treinamentos(id) ON DELETE CASCADE,
    titulo VARCHAR(200) NOT NULL DEFAULT 'Sessão',
    conteudo_html TEXT NOT NULL DEFAULT '',
    -- FUTURO: slides JSONB (quebra automática do texto corrido)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_sessoes_treino
    ON cx_treinamento_sessoes (treinamento_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_fontes (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    titulo VARCHAR(300),
    resumo TEXT NOT NULL DEFAULT '',
    incluido_no_contexto BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_fontes_sessao
    ON cx_treinamento_fontes (sessao_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_imagens (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    asset_url TEXT NOT NULL,
    thumb_url TEXT,
    prompt TEXT NOT NULL DEFAULT '',
    -- FUTURO: posicao JSONB / slide_id para drag-and-drop no canvas
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_imagens_sessao
    ON cx_treinamento_imagens (sessao_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_agent_mensagens (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL DEFAULT '',
    tool_used VARCHAR(40),
    display_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_agent_msgs
    ON cx_treinamento_agent_mensagens (sessao_id, created_at, id);

CREATE TABLE IF NOT EXISTS cx_treinamento_ai_ledger (
    id BIGSERIAL PRIMARY KEY,
    treinamento_id INTEGER NOT NULL REFERENCES cx_treinamentos(id) ON DELETE CASCADE,
    sessao_id BIGINT REFERENCES cx_treinamento_sessoes(id) ON DELETE SET NULL,
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('texto', 'pesquisa', 'imagem', 'resumo_url')),
    provider VARCHAR(40) NOT NULL DEFAULT 'openrouter',
    model VARCHAR(120),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    cost_brl NUMERIC(12,2) NOT NULL DEFAULT 0,
    usd_brl_rate NUMERIC(10,4),
    usd_brl_source VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_ai_ledger_sessao
    ON cx_treinamento_ai_ledger (sessao_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_ai_ledger_treino
    ON cx_treinamento_ai_ledger (treinamento_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_treinamento_planos (
    id BIGSERIAL PRIMARY KEY,
    sessao_id BIGINT NOT NULL REFERENCES cx_treinamento_sessoes(id) ON DELETE CASCADE,
    marca VARCHAR(160) NOT NULL,
    briefing TEXT NOT NULL DEFAULT '',
    budget_brl NUMERIC(14,2) NOT NULL DEFAULT 0,
    plano JSONB NOT NULL DEFAULT '{}'::jsonb,
    analise JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- FUTURO: motor de forecast (alcance, atenção, frequência, risco)
    previsao_impacto JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_treinamento_planos_sessao
    ON cx_treinamento_planos (sessao_id, created_at DESC);
"""

SCHEMA_PATCH_SQL = """
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS slug VARCHAR(80);
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS ordem INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS horario_inicio VARCHAR(5);
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS horario_fim VARCHAR(5);
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS facilitadores TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE cx_treinamento_sessoes ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) NOT NULL DEFAULT 'bloco';
CREATE UNIQUE INDEX IF NOT EXISTS idx_cx_treinamento_sessoes_slug
    ON cx_treinamento_sessoes (treinamento_id, slug) WHERE slug IS NOT NULL;
"""


_SCHEMA_READY = False


def ensure_schema(conn):
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    statements = [item.strip() for item in SCHEMA_SQL.split(";") if item.strip()]
    patches = [item.strip() for item in SCHEMA_PATCH_SQL.split(";") if item.strip()]
    with conn.cursor() as cursor:
        for statement in statements + patches:
            cursor.execute(statement)
    conn.commit()
    _SCHEMA_READY = True


def seed_imersao(conn, created_by=None):
    try:
        return _seed_imersao(conn, created_by)
    except Exception:
        conn.rollback()
        if created_by is None:
            raise
        return _seed_imersao(conn, None)


def _seed_imersao(conn, created_by=None):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM cx_treinamentos WHERE slug = %s",
            (IMMERSAO_SLUG,),
        )
        row = cursor.fetchone()
        if row:
            treinamento_id = row["id"]
        else:
            cursor.execute(
                """
                INSERT INTO cx_treinamentos (
                    titulo, descricao, slug, guia_estilo, created_by
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    "Imersão em Mídias Complexas",
                    (
                        "Evento de treinamento MediaHacks + Centralcomm Media Hub. "
                        "28 de setembro, com Alexandre Borges (CEO) e Apolo Lira (Co-CEO)."
                    ),
                    IMMERSAO_SLUG,
                    Json(DEFAULT_STYLE_GUIDE),
                    created_by,
                ),
            )
            treinamento_id = cursor.fetchone()["id"]
        sessao_id = _upsert_agenda(cursor, treinamento_id)
    conn.commit()
    return treinamento_id, sessao_id


def _upsert_agenda(cursor, treinamento_id):
    first_id = None
    for item in SESSIONS:
        cursor.execute(
            """
            SELECT id, conteudo_html FROM cx_treinamento_sessoes
             WHERE treinamento_id = %s AND slug = %s
            """,
            (treinamento_id, item["slug"]),
        )
        row = cursor.fetchone()
        html = session_html(item)
        if row:
            sessao_id = row["id"]
            if not (row.get("conteudo_html") or "").strip():
                cursor.execute(
                    """
                    UPDATE cx_treinamento_sessoes
                       SET titulo = %s, ordem = %s, horario_inicio = %s,
                           horario_fim = %s, facilitadores = %s, tipo = %s,
                           conteudo_html = %s, updated_at = NOW()
                     WHERE id = %s
                    """,
                    (
                        item["titulo"],
                        item["ordem"],
                        item["horario_inicio"],
                        item["horario_fim"],
                        item["facilitadores"],
                        item["tipo"],
                        html,
                        sessao_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE cx_treinamento_sessoes
                       SET titulo = %s, ordem = %s, horario_inicio = %s,
                           horario_fim = %s, facilitadores = %s, tipo = %s,
                           updated_at = NOW()
                     WHERE id = %s
                    """,
                    (
                        item["titulo"],
                        item["ordem"],
                        item["horario_inicio"],
                        item["horario_fim"],
                        item["facilitadores"],
                        item["tipo"],
                        sessao_id,
                    ),
                )
        else:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_sessoes (
                    treinamento_id, slug, titulo, conteudo_html, ordem,
                    horario_inicio, horario_fim, facilitadores, tipo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    treinamento_id,
                    item["slug"],
                    item["titulo"],
                    html,
                    item["ordem"],
                    item["horario_inicio"],
                    item["horario_fim"],
                    item["facilitadores"],
                    item["tipo"],
                ),
            )
            sessao_id = cursor.fetchone()["id"]
        if first_id is None:
            first_id = sessao_id
    cursor.execute(
        """
        DELETE FROM cx_treinamento_sessoes
         WHERE treinamento_id = %s
           AND (slug IS NULL OR slug = '')
           AND COALESCE(conteudo_html, '') = ''
        """,
        (treinamento_id,),
    )
    return first_id
