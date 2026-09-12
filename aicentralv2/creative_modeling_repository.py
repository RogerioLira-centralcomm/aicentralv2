"""Persistência PostgreSQL da Modelagem de Criativos."""

from contextlib import contextmanager
from decimal import Decimal

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Json

from .creative_construct_params import ENGINE_CONSTRUCT
from .creative_format_geometry import resolve_scene_count, scene_count_for_format
from .creative_modeling_prompts import build_inherited_scene_prompt

HOUSE_CRM_CLIENT_ID = 174

_CONCEPT_FORMATS = (
    "video-linear-15",
    "video-cta-15",
    "video-qr-15",
    "ctv-video-linear-30",
    "ctv-video-cta",
    "ctv-video-qr",
)
_CONCEPT_INTENTS = (
    "create",
    "reconstruct",
    "adapt",
    "refine",
    "html",
    "vary",
)
_CONCEPT_STATUSES = ("draft", "concept", "review", "ready", "handed_off")
_CONCEPT_SCENE_STATUSES = ("draft", "concept", "review", "ready", "failed")
_CONCEPT_PASS_KINDS = ("create", "refine", "implement", "validate", "patch")
_CONCEPT_RELATIONAL_KEYS = {
    "id",
    "campaign_id",
    "client_id",
    "format",
    "format_key",
    "variant",
    "intent",
    "status",
    "campaign_slug",
    "duration",
    "duration_seconds",
    "scene_count",
    "adapter",
    "platform_label",
    "objective",
    "knobs",
    "spec",
    "qa",
    "quote",
    "brand",
    "brand_dna",
    "brand_snapshot",
    "spent_usd",
    "scenes",
    "storyboard",
    "passes",
    "references",
    "created_by",
    "created_at",
    "updated_at",
    "handed_off_at",
}


def _concept_format_key(value):
    key = str(value or "").strip()
    return key if key in _CONCEPT_FORMATS else "video-linear-15"


def _concept_variant(value):
    letter = str(value or "A").strip().upper()[:1]
    return letter if letter in {"A", "B", "C", "D"} else "A"


def _concept_intent(value):
    intent = str(value or "create").strip().lower()
    return intent if intent in _CONCEPT_INTENTS else "create"


def _concept_status(value):
    status = str(value or "draft").strip().lower()
    return status if status in _CONCEPT_STATUSES else "draft"


def _concept_scene_status(value, fallback="draft"):
    status = str(value or fallback).strip().lower()
    return status if status in _CONCEPT_SCENE_STATUSES else fallback


def _concept_scene_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 4
    return 5 if count == 5 else 4


def _concept_scene_key(value, position):
    raw = str(value or "").strip()
    if raw in {"scene_01", "scene_02", "scene_03", "scene_04", "scene_05"}:
        return raw
    digits = "".join(character for character in raw if character.isdigit())
    if digits:
        number = int(digits)
        if 1 <= number <= 5:
            return f"scene_{number:02d}"
    if 1 <= int(position) <= 5:
        return f"scene_{int(position):02d}"
    return "scene_01"


def _concept_pass_kind(value):
    kind = str(value or "").strip().lower()
    aliases = {
        "conceito": "create",
        "storyboard": "create",
        "melhor roteiro": "refine",
        "html": "implement",
        "gerar": "implement",
        "qa": "validate",
    }
    kind = aliases.get(kind, kind)
    return kind if kind in _CONCEPT_PASS_KINDS else "create"


def _json_object(value):
    return value if isinstance(value, dict) else {}


def _json_list(value):
    return [item for item in value] if isinstance(value, list) else []


def _optional_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _concept_spent(session):
    if session.get("spent_usd") not in (None, ""):
        amount = _optional_number(session.get("spent_usd"))
        if amount is not None:
            return amount
    cost = session.get("cost") if isinstance(session.get("cost"), dict) else {}
    for key in ("spent_usd", "cost_usd", "estimated_cost_usd"):
        amount = _optional_number(cost.get(key))
        if amount is not None:
            return amount
    quote = session.get("quote") if isinstance(session.get("quote"), dict) else {}
    for key in ("spent_usd", "cost_usd", "estimated_cost_usd"):
        amount = _optional_number(quote.get(key))
        if amount is not None:
            return amount
    return 0


def _concept_scene_items(session):
    for key in ("scenes", "storyboard", "cards"):
        items = session.get(key)
        if isinstance(items, list) and items:
            return [item for item in items if isinstance(item, dict)]
    return []


def _concept_reference_items(session):
    items = []
    seen = set()
    brand = session.get("brand") if isinstance(session.get("brand"), dict) else {}
    for source, role in (
        (session.get("references"), "reference"),
        (session.get("images"), "user"),
        (brand.get("assets"), None),
    ):
        for index, item in enumerate(_json_list(source), start=1):
            if isinstance(item, str):
                url = item
                item_role = role or "reference"
            elif isinstance(item, dict):
                url = item.get("asset_url") or item.get("url") or ""
                item_role = item.get("role") or role or "reference"
            else:
                continue
            url = str(url or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            if item_role not in {"user", "logo", "reference"}:
                item_role = "reference"
            items.append({
                "role": item_role,
                "asset_url": url,
                "position": min(index, 8),
            })
    return items[:8]


class CreativeNotFoundError(LookupError):
    pass


class CreativeConflictError(ValueError):
    pass


def json_revision_clause(column):
    return (
        "COALESCE(CASE WHEN {col} #>> '{{design_system_ads,revision}}' ~ '^[0-9]+$' "
        "THEN ({col} #>> '{{design_system_ads,revision}}')::int ELSE 0 END, 0)"
    ).format(col=column)


def design_system_ads_document(payload):
    """Documento Ads a gravar no path JSONB. Não é o brand_profile inteiro."""
    data = payload if isinstance(payload, dict) else {}
    nested = data.get("design_system_ads")
    if isinstance(nested, dict):
        return nested
    if data.get("framework") == "design-system-ads" or data.get("tokens"):
        return data
    return {}


def revision_where_clause(column, table):
    """Coluna gerada nas tabelas canônicas; path JSONB nos probes."""
    if table in {"cx_clients", "cx_campaigns"}:
        return "design_system_ads_revision"
    return json_revision_clause(column)


def jsonb_set_ads_sql(column, table, *, extra_set=""):
    clause = revision_where_clause(column, table)
    extra = f", {extra_set}" if extra_set else ""
    return f"""
        UPDATE {table}
           SET {column} = jsonb_set(
                 COALESCE({column}, '{{}}'::jsonb),
                 '{{design_system_ads}}',
                 %s::jsonb
               ){extra}
         WHERE id = %s
           AND {clause} = %s
        RETURNING id
    """


def jsonb_merge_neighbors_sql(column, table, *, extra_set=""):
    """Atualiza chaves vizinhas sem tocar design_system_ads."""
    extra = f", {extra_set}" if extra_set else ""
    return f"""
        UPDATE {table}
           SET {column} = COALESCE({column}, '{{}}'::jsonb)
             || (%s::jsonb - 'design_system_ads'){extra}
         WHERE id = %s
        RETURNING id
    """


def _house_crm_client_id(cursor):
    cursor.execute(
        """
        SELECT id_cliente
          FROM tbl_cliente
         WHERE id_cliente = %s AND status = TRUE
        """,
        (HOUSE_CRM_CLIENT_ID,),
    )
    row = cursor.fetchone()
    return row["id_cliente"] if row else None


def _resolve_cx_client_id(cursor, client_source, source_client_id):
    if client_source == "crm":
        cursor.execute(
            """
            SELECT id_cliente,
                   COALESCE(
                       nome_fantasia, razao_social,
                       'Cliente #' || id_cliente::text
                   ) AS name
              FROM tbl_cliente
             WHERE id_cliente = %s AND status = TRUE
            """,
            (source_client_id,),
        )
        crm_client = cursor.fetchone()
        if not crm_client:
            raise CreativeNotFoundError("Cliente do CRM não encontrado.")
        cursor.execute(
            """
            SELECT id
              FROM cx_clients
             WHERE crm_client_id = %s
             ORDER BY id
             LIMIT 1
            """,
            (source_client_id,),
        )
        existing = cursor.fetchone()
        if existing:
            return existing["id"]
        cursor.execute(
            """
            INSERT INTO cx_clients (
                crm_client_id, name, brand_profile,
                analysis_metadata, price_policy
            )
            VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'hide_price')
            RETURNING id
            """,
            (source_client_id, crm_client["name"]),
        )
        return cursor.fetchone()["id"]
    cursor.execute(
        """
        SELECT id, crm_client_id
          FROM cx_clients
         WHERE id = %s
        """,
        (source_client_id,),
    )
    client = cursor.fetchone()
    if not client:
        raise CreativeNotFoundError("Perfil de marca não encontrado.")
    if not client.get("crm_client_id"):
        house = _house_crm_client_id(cursor)
        if house:
            cursor.execute(
                """
                UPDATE cx_clients
                   SET crm_client_id = %s
                 WHERE id = %s AND crm_client_id IS NULL
                """,
                (house, client["id"]),
            )
    return client["id"]


class CreativeModelingRepository:
    def __init__(self, connection=None):
        self._connection = connection

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from . import db

        return db.get_db()

    @contextmanager
    def _write(self):
        try:
            with self.conn.cursor() as cursor:
                yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def list_formats(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.id, f.slug, f.name_pt, f.name_en, f.mechanic,
                       f.media_type, f.engine, f.aspect_ratio, f.default_size,
                       f.safe_area, f.responsive_rules,
                       f.background_guidance, f.foreground_guidance,
                       f.max_reference_variants,
                       f.layers, f.required_fields, f.optional_fields,
                       f.forbidden_elements, f.use_cases_by_market, f.status,
                       f.placement_spec, f.behavior_spec,
                       f.default_viewer_profile_id,
                       COALESCE(cat.slug, 'programatica') AS category,
                       ch.slug AS channel, ch.name AS channel_name,
                       ch.screen_context_template, ch.partner_primary_color,
                       ch.partner_secondary_color, ch.brand_guidelines,
                       COALESCE(
                           (SELECT jsonb_agg(to_jsonb(ref) ORDER BY ref.slot)
                              FROM cx_format_references ref
                             WHERE ref.format_template_id = f.id
                               AND ref.status = 'approved'),
                           '[]'::jsonb
                       ) AS references
                  FROM cx_format_templates f
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_format_categories cat ON cat.id = ch.category_id
                 WHERE f.is_active = TRUE
                 ORDER BY COALESCE(cat.slug, 'programatica'), f.name_pt
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_viewer_profiles(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, name, viewer_kind, source_url, logo_asset_ref,
                       palette, shell_spec, disclaimer
                  FROM cx_creative_viewer_profiles
                 WHERE is_active = TRUE
                 ORDER BY viewer_kind, name
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_viewer_profile(self, profile_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, name, viewer_kind, source_url, logo_asset_ref,
                       palette, shell_spec, disclaimer
                  FROM cx_creative_viewer_profiles
                 WHERE id = %s AND is_active = TRUE
                """,
                (profile_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Ambiente de mídia não encontrado.")
        return dict(row)

    def get_format(self, format_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.*, COALESCE(cat.slug, 'programatica') AS category,
                       ch.slug AS channel, ch.name AS channel_name,
                       ch.screen_context_template, ch.partner_primary_color,
                       ch.partner_secondary_color, ch.brand_guidelines
                  FROM cx_format_templates f
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_format_categories cat ON cat.id = ch.category_id
                 WHERE f.id = %s AND f.is_active = TRUE
                """,
                (format_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Formato não encontrado.")
        return dict(row)

    def update_format_modeling(self, format_id, data):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_templates
                   SET safe_area = %s,
                       responsive_rules = %s,
                       background_guidance = %s,
                       foreground_guidance = %s,
                       placement_spec = %s,
                       behavior_spec = %s,
                       default_viewer_profile_id = %s
                 WHERE id = %s
                RETURNING id
                """,
                (
                    Json(data.get("safe_area") or {}),
                    data.get("responsive_rules"),
                    data.get("background_guidance"),
                    data.get("foreground_guidance"),
                    Json(data.get("placement_spec") or {}),
                    Json(data.get("behavior_spec") or {}),
                    data.get("default_viewer_profile_id"),
                    format_id,
                ),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Formato não encontrado.")

    def list_clients(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, sector, tone_of_voice, logo_url,
                       logo_upload_path, primary_color, secondary_color,
                       website_url, brand_profile, analysis_metadata,
                       price_policy, created_at
                  FROM cx_clients
                 ORDER BY created_at DESC, id DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_campaign_clients(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT cx.id AS profile_id, crm.id_cliente AS crm_client_id,
                       'crm:' || crm.id_cliente::text AS selection_key,
                       'crm' AS source,
                       'ready' AS profile_status,
                       COALESCE(
                           crm.nome_fantasia, crm.razao_social,
                           'Cliente #' || crm.id_cliente::text
                       )
                           AS name,
                       cx.sector, cx.tone_of_voice, cx.logo_url,
                       cx.logo_upload_path, cx.primary_color,
                       cx.secondary_color, cx.website_url,
                       COALESCE(cx.brand_profile, '{}'::jsonb) AS brand_profile,
                       COALESCE(cx.analysis_metadata, '{}'::jsonb)
                           AS analysis_metadata,
                       COALESCE(cx.price_policy, 'hide_price') AS price_policy
                  FROM tbl_cliente crm
                  JOIN LATERAL (
                      SELECT id, sector, tone_of_voice, logo_url,
                             logo_upload_path, primary_color, secondary_color,
                             website_url, brand_profile, analysis_metadata,
                             price_policy
                        FROM cx_clients
                       WHERE crm_client_id = crm.id_cliente
                       ORDER BY id
                       LIMIT 1
                  ) cx ON TRUE
                 WHERE crm.status = TRUE
                UNION ALL
                SELECT cx.id AS profile_id, cx.crm_client_id,
                       'profile:' || cx.id::text AS selection_key,
                       'creative' AS source, 'ready' AS profile_status,
                       cx.name, cx.sector, cx.tone_of_voice, cx.logo_url,
                       cx.logo_upload_path, cx.primary_color,
                       cx.secondary_color, cx.website_url,
                       cx.brand_profile, cx.analysis_metadata, cx.price_policy
                  FROM cx_clients cx
                 ORDER BY name
                """
            )
            rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["house"] = row.get("crm_client_id") == HOUSE_CRM_CLIENT_ID
        return rows

    def get_client(self, client_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, sector, tone_of_voice, logo_url,
                       logo_upload_path, primary_color, secondary_color,
                       website_url, brand_profile, analysis_metadata,
                       price_policy, created_at
                  FROM cx_clients
                 WHERE id = %s
                """,
                (client_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Cliente não encontrado.")
        return dict(row)

    def create_client(self, data):
        with self._write() as cursor:
            crm_client_id = data.get("crm_client_id") or _house_crm_client_id(cursor)
            cursor.execute(
                """
                INSERT INTO cx_clients (
                    crm_client_id, name, sector, tone_of_voice, logo_url,
                    primary_color, secondary_color, website_url, brand_profile,
                    analysis_metadata, price_policy
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    crm_client_id,
                    data["name"],
                    data.get("sector"),
                    data.get("tone_of_voice"),
                    data.get("logo_url"),
                    data.get("primary_color"),
                    data.get("secondary_color"),
                    data.get("website_url"),
                    Json(data.get("brand_profile") or {}),
                    Json(data.get("analysis_metadata") or {}),
                    data["price_policy"],
                ),
            )
            return cursor.fetchone()["id"]

    def list_client_brand_assets(self, client_id, approved_only=True):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, client_id, role, source_kind, source_url, page_url,
                           asset_path, mime_type, width, height, sha256, score,
                           status, is_primary, metadata, created_at
                      FROM cx_client_brand_assets
                     WHERE client_id = %s
                       AND (%s = FALSE OR status = 'approved')
                     ORDER BY CASE role
                                  WHEN 'creative' THEN 0
                                  WHEN 'logo' THEN 1
                                  ELSE 2
                              END,
                              is_primary DESC,
                              score DESC NULLS LAST, id DESC
                    """,
                    (client_id, approved_only),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            try:
                self.conn.rollback()
            except Exception:
                pass
            if "cx_client_brand_assets" in str(exc):
                return []
            raise

    def add_client_brand_asset(self, client_id, data):
        with self._write() as cursor:
            if data.get("is_primary") and data.get("role") == "logo":
                cursor.execute(
                    """
                    UPDATE cx_client_brand_assets
                       SET is_primary = FALSE, updated_at = NOW()
                     WHERE client_id = %s AND role = 'logo'
                    """,
                    (client_id,),
                )
            cursor.execute(
                """
                INSERT INTO cx_client_brand_assets (
                    client_id, role, source_kind, source_url, page_url,
                    asset_path, mime_type, width, height, sha256, score,
                    status, is_primary, metadata
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (
                    client_id,
                    data["role"],
                    data.get("source_kind") or "website",
                    data.get("source_url"),
                    data.get("page_url"),
                    data.get("asset_path"),
                    data.get("mime_type"),
                    data.get("width"),
                    data.get("height"),
                    data.get("sha256"),
                    data.get("score"),
                    data.get("status") or "approved",
                    bool(data.get("is_primary")),
                    Json(data.get("metadata") or {}),
                ),
            )
            row = cursor.fetchone()
            if row:
                return row["id"]
            if data.get("sha256"):
                cursor.execute(
                    """
                    SELECT id
                      FROM cx_client_brand_assets
                     WHERE client_id = %s AND sha256 = %s
                    """,
                    (client_id, data["sha256"]),
                )
                existing = cursor.fetchone()
                return existing["id"] if existing else None
            return None

    def find_client_brand_asset_by_hash(self, client_id, sha256):
        if not sha256:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, asset_path, role
                  FROM cx_client_brand_assets
                 WHERE client_id = %s AND sha256 = %s
                """,
                (client_id, sha256),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def set_primary_client_brand_asset(self, client_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id, asset_path
                  FROM cx_client_brand_assets
                 WHERE id = %s AND client_id = %s
                   AND role = 'logo' AND status = 'approved'
                """,
                (asset_id, client_id),
            )
            asset = cursor.fetchone()
            if not asset:
                raise CreativeNotFoundError("Logo aprovado não encontrado.")
            cursor.execute(
                """
                UPDATE cx_client_brand_assets
                   SET is_primary = (id = %s), updated_at = NOW()
                 WHERE client_id = %s AND role = 'logo'
                """,
                (asset_id, client_id),
            )
            if asset.get("asset_path"):
                cursor.execute(
                    "UPDATE cx_clients SET logo_upload_path = %s WHERE id = %s",
                    (asset["asset_path"], client_id),
                )
            return dict(asset)

    def update_client(self, client_id, data):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_clients
                   SET name = %s,
                       sector = %s,
                       tone_of_voice = %s,
                       logo_url = %s,
                       primary_color = %s,
                       secondary_color = %s,
                       website_url = %s,
                       brand_profile = %s,
                       analysis_metadata = %s,
                       price_policy = %s
                 WHERE id = %s
                RETURNING id
                """,
                (
                    data["name"],
                    data.get("sector"),
                    data.get("tone_of_voice"),
                    data.get("logo_url"),
                    data.get("primary_color"),
                    data.get("secondary_color"),
                    data.get("website_url"),
                    Json(data.get("brand_profile") or {}),
                    Json(data.get("analysis_metadata") or {}),
                    data["price_policy"],
                    client_id,
                ),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Cliente não encontrado.")
            return client_id

    def update_client_brand_profile(self, client_id, brand_profile):
        """Mescla chaves vizinhas. Não substitui design_system_ads."""
        with self._write() as cursor:
            cursor.execute(
                jsonb_merge_neighbors_sql("brand_profile", "cx_clients"),
                (Json(brand_profile or {}), client_id),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Cliente não encontrado.")

    def update_client_design_system_ads(self, client_id, system):
        """Grava só o path canônico. Sem WHERE de revisão."""
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_clients
                   SET brand_profile = jsonb_set(
                         COALESCE(brand_profile, '{}'::jsonb),
                         '{design_system_ads}',
                         %s::jsonb
                       )
                 WHERE id = %s
                RETURNING id
                """,
                (Json(design_system_ads_document(system)), client_id),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Cliente não encontrado.")

    def update_client_brand_profile_cas(self, client_id, brand_profile, expected_revision):
        expected = max(0, int(expected_revision or 0))
        payload = design_system_ads_document(brand_profile)
        with self._write() as cursor:
            cursor.execute(
                jsonb_set_ads_sql("brand_profile", "cx_clients"),
                (Json(payload), client_id, expected),
            )
            if cursor.fetchone():
                return
            cursor.execute("SELECT id FROM cx_clients WHERE id = %s", (client_id,))
            if not cursor.fetchone():
                raise CreativeNotFoundError("Cliente não encontrado.")
            from .design_system_ads.revision import BRAND_CONFLICT

            raise CreativeConflictError(BRAND_CONFLICT)

    def delete_client_brand_asset(self, client_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                DELETE FROM cx_client_brand_assets
                 WHERE id = %s AND client_id = %s
                RETURNING asset_path, is_primary, role
                """,
                (asset_id, client_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Referência da marca não encontrada.")
            if row.get("is_primary"):
                cursor.execute(
                    "UPDATE cx_clients SET logo_upload_path = NULL WHERE id = %s",
                    (client_id,),
                )
            return dict(row)

    def set_client_logo(self, client_id, public_path):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_clients
                   SET logo_upload_path = %s
                 WHERE id = %s
                RETURNING logo_upload_path
                """,
                (public_path, client_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Cliente não encontrado.")

    def delete_client(self, client_id):
        try:
            with self._write() as cursor:
                cursor.execute(
                    "DELETE FROM cx_clients WHERE id = %s RETURNING id",
                    (client_id,),
                )
                if not cursor.fetchone():
                    raise CreativeNotFoundError("Cliente não encontrado.")
        except ForeignKeyViolation as exc:
            raise CreativeConflictError(
                "Cliente vinculado a campanhas não pode ser removido."
            ) from exc

    def create_campaign_with_variation_a(self, data):
        with self._write() as cursor:
            client_id = _resolve_cx_client_id(
                cursor,
                data.get("client_source", "creative"),
                data["client_id"],
            )

            first_step = data["first_step"]
            cursor.execute(
                """
                SELECT id, engine
                  FROM cx_format_templates
                 WHERE id = %s AND is_active = TRUE
                """,
                (first_step["format_template_id"],),
            )
            format_row = cursor.fetchone()
            if not format_row:
                raise CreativeNotFoundError("Formato inicial não encontrado.")
            cursor.execute(
                """
                INSERT INTO cx_campaigns (
                    client_id, name, objective, campaign_text, cta_text,
                    show_price, budget_usd, creative_brief
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    client_id,
                    data["name"],
                    data.get("objective"),
                    data.get("campaign_text"),
                    data.get("cta_text"),
                    data.get("show_price", False),
                    data.get("budget_usd", 0),
                    Json(data.get("creative_brief") or {}),
                ),
            )
            campaign_id = cursor.fetchone()["id"]
            cursor.execute(
                """
                INSERT INTO cx_campaign_variations (campaign_id, label)
                VALUES (%s, 'A')
                RETURNING id
                """,
                (campaign_id,),
            )
            variation_id = cursor.fetchone()["id"]
            cursor.execute(
                """
                INSERT INTO cx_variation_steps (
                    variation_id, position, format_template_id,
                    mockup, scene_description, engine
                )
                VALUES (%s, 1, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    variation_id,
                    format_row["id"],
                    first_step["mockup"],
                    first_step.get("scene_description"),
                    format_row["engine"],
                ),
            )
            step_id = cursor.fetchone()["id"]
        return {
            "id": campaign_id,
            "variation_id": variation_id,
            "step_id": step_id,
        }

    def create_campaign_with_productions(self, data):
        """Cria campanha, uma produção por formato e suas cenas atomicamente."""
        with self._write() as cursor:
            client_id = _resolve_cx_client_id(
                cursor,
                data.get("client_source", "creative"),
                data["client_id"],
            )

            format_ids = [item["format_template_id"] for item in data["productions"]]
            cursor.execute(
                """
                SELECT id, slug, mechanic, media_type, behavior_spec
                  FROM cx_format_templates
                 WHERE id = ANY(%s) AND is_active = TRUE
                """,
                (format_ids,),
            )
            formats = {row["id"]: dict(row) for row in cursor.fetchall()}
            if set(format_ids) != set(formats):
                raise CreativeNotFoundError(
                    "Um ou mais formatos não foram encontrados."
                )
            if any(row["media_type"] == "video" for row in formats.values()):
                raise CreativeConflictError(
                    "Vídeo está indisponível para novas produções."
                )

            cursor.execute(
                """
                INSERT INTO cx_campaigns (
                    client_id, name, objective, campaign_text, cta_text,
                    show_price, budget_usd, creative_brief
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    client_id,
                    data["name"],
                    data.get("objective"),
                    data.get("campaign_text"),
                    data.get("cta_text"),
                    data.get("show_price", False),
                    data.get("budget_usd", 0),
                    Json(data.get("creative_brief") or {}),
                ),
            )
            campaign_id = cursor.fetchone()["id"]
            productions = []
            for requested in data["productions"]:
                format_id = requested["format_template_id"]
                format_row = formats[format_id]
                requested_count = resolve_scene_count(
                    requested.get("scene_count"),
                    default=None,
                )
                descriptions = requested.get("scene_descriptions") or []
                if requested_count:
                    scene_count = requested_count
                elif len(descriptions) in (1, 4, 6, 8):
                    scene_count = len(descriptions)
                else:
                    scene_count = scene_count_for_format(format_row)
                unlock_all = (
                    ((data.get("creative_brief") or {}).get("construct_path") or {}).get("engine")
                    == ENGINE_CONSTRUCT
                )
                cursor.execute(
                    """
                    INSERT INTO cx_creative_productions (
                        campaign_id, format_template_id
                    )
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (campaign_id, format_id),
                )
                production_id = cursor.fetchone()["id"]
                descriptions = requested.get("scene_descriptions") or []
                scene_prompts = requested.get("scene_prompts") or []
                approve_prompts = bool(requested.get("approve_prompts"))
                visual_bible = (
                    (data.get("creative_brief") or {}).get("visual_bible")
                )
                scene_ids = []
                for position in range(1, scene_count + 1):
                    description = (
                        descriptions[position - 1]
                        if position <= len(descriptions)
                        else data.get("campaign_text")
                    )
                    prepared = (
                        scene_prompts[position - 1]
                        if position <= len(scene_prompts)
                        else ""
                    )
                    scene_prompt = prepared or build_inherited_scene_prompt(
                        visual_bible,
                        description,
                        data.get("cta_text"),
                        position,
                    )
                    prompt_status = (
                        "approved" if approve_prompts and prepared else "draft"
                    )
                    cursor.execute(
                        """
                        INSERT INTO cx_creative_scenes (
                            production_id, position, description, prompt,
                            prompt_status, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            production_id,
                            position,
                            description,
                            scene_prompt,
                            prompt_status,
                            "ready" if position == 1 or unlock_all else "blocked",
                        ),
                    )
                    scene_ids.append(cursor.fetchone()["id"])
                productions.append(
                    {
                        "id": production_id,
                        "format_template_id": format_id,
                        "scene_ids": scene_ids,
                    }
                )
        return {"id": campaign_id, "productions": productions}

    def get_production(self, production_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.campaign_id, p.format_template_id, p.status,
                       p.selected_asset_id, p.created_at, p.updated_at,
                       c.name AS campaign_name, f.slug AS format_slug,
                       f.name_pt AS format_name, f.mechanic, f.media_type,
                       f.aspect_ratio, f.default_size, f.placement_spec,
                       f.behavior_spec
                  FROM cx_creative_productions p
                  JOIN cx_campaigns c ON c.id = p.campaign_id
                  JOIN cx_format_templates f ON f.id = p.format_template_id
                 WHERE p.id = %s
                """,
                (production_id,),
            )
            production = cursor.fetchone()
            if not production:
                raise CreativeNotFoundError("Produção não encontrada.")
            cursor.execute(
                """
                SELECT s.id, s.production_id, p.format_template_id,
                       s.position, s.description, s.prompt,
                       s.prompt AS rendered_prompt, s.prompt_status,
                       s.status, s.approved_asset_id, s.preview_asset_id,
                       s.created_at, s.updated_at,
                       COALESCE(
                           (
                               SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at)
                                 FROM cx_generated_assets a
                                WHERE a.scene_id = s.id
                           ),
                           '[]'::jsonb
                       ) AS assets
                  FROM cx_creative_scenes s
                  JOIN cx_creative_productions p ON p.id = s.production_id
                 WHERE s.production_id = %s
                 ORDER BY s.position
                """,
                (production_id,),
            )
            result = dict(production)
            result["scenes"] = [dict(row) for row in cursor.fetchall()]
            return result

    def get_scene_context(self, scene_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.production_id, s.position, s.description,
                       s.prompt, s.prompt_status, s.status, p.campaign_id,
                       p.format_template_id, p.status AS production_status,
                       (
                           SELECT COUNT(*)::integer
                             FROM cx_creative_scenes sequence_scene
                            WHERE sequence_scene.production_id = s.production_id
                       ) AS scene_count,
                       c.name AS campaign_name, c.objective, c.campaign_text,
                       c.cta_text, c.show_price, c.creative_brief,
                       (
                           SELECT jsonb_agg(
                               jsonb_build_object(
                                   'position', sequence_scene.position,
                                   'description', sequence_scene.description
                               )
                               ORDER BY sequence_scene.position
                           )
                             FROM cx_creative_scenes sequence_scene
                            WHERE sequence_scene.production_id = s.production_id
                       ) AS storyboard,
                       (
                           SELECT previous_asset.asset_url
                             FROM cx_creative_scenes previous_scene
                             JOIN cx_generated_assets previous_asset
                               ON previous_asset.id = previous_scene.approved_asset_id
                            WHERE previous_scene.production_id = s.production_id
                              AND previous_scene.position < s.position
                            ORDER BY previous_scene.position DESC
                            LIMIT 1
                       ) AS previous_approved_asset_url,
                       (
                           SELECT first_scene.prompt
                             FROM cx_creative_scenes first_scene
                            WHERE first_scene.production_id = s.production_id
                              AND first_scene.position = 1
                       ) AS master_prompt,
                       (
                           SELECT first_scene.prompt_status
                             FROM cx_creative_scenes first_scene
                            WHERE first_scene.production_id = s.production_id
                              AND first_scene.position = 1
                       ) AS master_prompt_status,
                       cl.id AS client_id,
                       cl.name AS client_name, cl.sector AS client_sector,
                       cl.tone_of_voice, cl.logo_url, cl.logo_upload_path,
                       cl.primary_color, cl.secondary_color, cl.brand_profile,
                       f.slug AS format_slug,
                       f.name_pt AS format_name, f.mechanic, f.media_type,
                       f.engine, f.aspect_ratio, f.default_size, f.safe_area,
                       f.background_guidance, f.foreground_guidance,
                       f.layers, f.forbidden_elements, f.placement_spec,
                       f.behavior_spec, ch.name AS channel_name
                  FROM cx_creative_scenes s
                  JOIN cx_creative_productions p ON p.id = s.production_id
                  JOIN cx_campaigns c ON c.id = p.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                  JOIN cx_format_templates f ON f.id = p.format_template_id
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE s.id = %s
                """,
                (scene_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Cena não encontrada.")
        return dict(row)

    def update_scene_prompt(self, scene_id, prompt, status):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_creative_scenes
                   SET prompt = %s, prompt_status = %s, updated_at = NOW()
                 WHERE id = %s
                   AND status IN (
                       'ready', 'failed', 'blocked', 'review', 'approved'
                   )
                RETURNING id, prompt, prompt AS rendered_prompt, prompt_status
                """,
                (prompt, status, scene_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeConflictError(
                    "Cena não está disponível para editar a direção."
                )
            return dict(row)

    def list_campaigns(self, limit=50):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.name, c.client_id, cl.name AS client,
                       c.objective, c.campaign_text, c.cta_text, c.show_price,
                       c.status, c.budget_usd, c.reserved_usd, c.spent_usd,
                       (c.budget_usd - c.reserved_usd - c.spent_usd) AS balance_usd,
                       c.created_at, c.creative_brief,
                       COALESCE(c.creative_brief->>'flow_kind', 'model') AS flow_kind,
                       COUNT(v.id)::integer AS variation_count
                  FROM cx_campaigns c
                  JOIN cx_clients cl ON cl.id = c.client_id
                  LEFT JOIN cx_campaign_variations v ON v.campaign_id = c.id
                 GROUP BY c.id, cl.name, c.creative_brief
                 ORDER BY c.created_at DESC, c.id DESC
                 LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_latest_campaign_for_client(self, client_id):
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, client_id, name
                  FROM cx_campaigns
                 WHERE client_id = %s
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (client_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "creative_brief": {},
            "client": {"id": row["client_id"]},
        }

    def create_mesa_campaign(self, client_id, name, objective="Mesa de formato"):
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            raise CreativeNotFoundError("Perfil de marca não encontrado.")
        title = str(name or f"Mesa de Formato — {client_id}")[:200]
        try:
            return self._insert_mesa_campaign(client_id, title, objective, True)
        except CreativeNotFoundError:
            raise
        except Exception:
            return self._insert_mesa_campaign(client_id, title, objective, False)

    def _insert_mesa_campaign(self, client_id, name, objective, with_brief):
        with self._write() as cursor:
            cursor.execute("SELECT id FROM cx_clients WHERE id = %s", (client_id,))
            if not cursor.fetchone():
                raise CreativeNotFoundError("Perfil de marca não encontrado.")
            if with_brief:
                cursor.execute(
                    """
                    INSERT INTO cx_campaigns (
                        client_id, name, objective, campaign_text, cta_text,
                        show_price, budget_usd, creative_brief
                    )
                    VALUES (%s, %s, %s, '', '', FALSE, 5, %s)
                    RETURNING id
                    """,
                    (client_id, name, objective, Json({"format_lab": {"source": "mesa"}})),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO cx_campaigns (
                        client_id, name, objective, campaign_text, cta_text,
                        show_price, budget_usd
                    )
                    VALUES (%s, %s, %s, '', '', FALSE, 5)
                    RETURNING id
                    """,
                    (client_id, name, objective),
                )
            return {"id": cursor.fetchone()["id"]}

    def first_active_format_template_id(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                  FROM cx_format_templates
                 WHERE is_active = TRUE
                 ORDER BY id
                 LIMIT 1
                """
            )
            row = cursor.fetchone()
        return row["id"] if row else None

    def get_campaign(self, campaign_id, productions=True):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.name, c.client_id, c.objective,
                       c.campaign_text, c.cta_text, c.show_price,
                       c.creative_brief, c.status,
                       c.budget_usd, c.reserved_usd, c.spent_usd,
                       (c.budget_usd - c.reserved_usd - c.spent_usd) AS balance_usd,
                       c.created_at, cl.name AS client_name,
                       cl.sector AS client_sector,
                       cl.tone_of_voice AS client_tone_of_voice,
                       cl.logo_url AS client_logo_url,
                       cl.logo_upload_path AS client_logo_upload_path,
                       cl.primary_color AS client_primary_color,
                       cl.secondary_color AS client_secondary_color,
                       cl.website_url AS client_website_url,
                       cl.brand_profile AS client_brand_profile,
                       cl.price_policy AS client_price_policy
                  FROM cx_campaigns c
                  JOIN cx_clients cl ON cl.id = c.client_id
                 WHERE c.id = %s
                """,
                (campaign_id,),
            )
            campaign = cursor.fetchone()
            if not campaign:
                raise CreativeNotFoundError("Campanha não encontrada.")
            cursor.execute(
                """
                SELECT id, campaign_id, label, notes, created_at
                  FROM cx_campaign_variations
                 WHERE campaign_id = %s
                 ORDER BY label
                """,
                (campaign_id,),
            )
            variations = [dict(row) for row in cursor.fetchall()]
            variation_ids = [row["id"] for row in variations]
            steps_by_variation = {variation_id: [] for variation_id in variation_ids}
            if variation_ids:
                cursor.execute(
                    """
                    SELECT s.id, s.variation_id, s.position,
                           s.format_template_id, s.mockup,
                           s.scene_description, s.rendered_prompt, s.engine,
                           s.prompt_status, s.script_text, s.script_status,
                           s.asset_url, s.asset_status, s.created_at,
                           f.slug AS format_slug, f.name_pt AS format_name,
                           f.media_type, f.aspect_ratio, f.default_size,
                           COALESCE(
                               (SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at DESC)
                                  FROM cx_generated_assets a
                                 WHERE a.step_id = s.id),
                               '[]'::jsonb
                           ) AS assets
                      FROM cx_variation_steps s
                      JOIN cx_format_templates f ON f.id = s.format_template_id
                     WHERE s.variation_id = ANY(%s)
                     ORDER BY s.variation_id, s.position
                    """,
                    (variation_ids,),
                )
                for row in cursor.fetchall():
                    step = dict(row)
                    steps_by_variation[step["variation_id"]].append(step)

        result = dict(campaign)
        result["client"] = {
            "id": result.pop("client_id"),
            "name": result.pop("client_name"),
            "sector": result.pop("client_sector"),
            "tone_of_voice": result.pop("client_tone_of_voice"),
            "logo_url": result.pop("client_logo_url"),
            "logo_upload_path": result.pop("client_logo_upload_path"),
            "primary_color": result.pop("client_primary_color"),
            "secondary_color": result.pop("client_secondary_color"),
            "website_url": result.pop("client_website_url"),
            "brand_profile": result.pop("client_brand_profile") or {},
            "price_policy": result.pop("client_price_policy"),
        }
        for variation in variations:
            variation["steps"] = steps_by_variation[variation["id"]]
        result["variations"] = variations
        if not productions:
            result["productions"] = []
            result["production"] = None
            return result
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                  FROM cx_creative_productions
                 WHERE campaign_id = %s
                 ORDER BY created_at, id
                """,
                (campaign_id,),
            )
            production_ids = [row["id"] for row in cursor.fetchall()]
        result["productions"] = [
            self.get_production(production_id) for production_id in production_ids
        ]
        result["production"] = (
            result["productions"][0] if result["productions"] else None
        )
        return result

    def update_campaign_bancada(self, campaign_id, brief, name=None):
        """Mescla o brief vizinho. Não substitui design_system_ads."""
        extra = "name = %s" if name else ""
        params = (
            (Json(brief or {}), name, campaign_id)
            if name
            else (Json(brief or {}), campaign_id)
        )
        with self._write() as cursor:
            cursor.execute(
                jsonb_merge_neighbors_sql(
                    "creative_brief", "cx_campaigns", extra_set=extra
                ),
                params,
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Campanha não encontrada.")

    def update_campaign_design_system_ads(self, campaign_id, system, name=None):
        extra = "name = %s" if name else ""
        payload = Json(design_system_ads_document(system))
        params = (payload, name, campaign_id) if name else (payload, campaign_id)
        with self._write() as cursor:
            cursor.execute(
                f"""
                UPDATE cx_campaigns
                   SET creative_brief = jsonb_set(
                         COALESCE(creative_brief, '{{}}'::jsonb),
                         '{{design_system_ads}}',
                         %s::jsonb
                       ){', name = %s' if name else ''}
                 WHERE id = %s
                RETURNING id
                """,
                params,
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Campanha não encontrada.")

    def update_campaign_bancada_cas(self, campaign_id, brief, expected_revision, name=None):
        expected = max(0, int(expected_revision or 0))
        payload = Json(design_system_ads_document(brief))
        extra = "name = %s" if name else ""
        params = (payload, name, campaign_id, expected) if name else (payload, campaign_id, expected)
        with self._write() as cursor:
            cursor.execute(
                jsonb_set_ads_sql("creative_brief", "cx_campaigns", extra_set=extra),
                params,
            )
            if cursor.fetchone():
                return
            cursor.execute("SELECT id FROM cx_campaigns WHERE id = %s", (campaign_id,))
            if not cursor.fetchone():
                raise CreativeNotFoundError("Campanha não encontrada.")
            from .design_system_ads.revision import CAMPAIGN_CONFLICT

            raise CreativeConflictError(CAMPAIGN_CONFLICT)

    def create_variation(self, campaign_id, notes=None):
        labels = ("A", "B", "C", "D")
        try:
            with self._write() as cursor:
                cursor.execute(
                    "SELECT id FROM cx_campaigns WHERE id = %s FOR UPDATE",
                    (campaign_id,),
                )
                if not cursor.fetchone():
                    raise CreativeNotFoundError("Campanha não encontrada.")
                cursor.execute(
                    """
                    SELECT label
                      FROM cx_campaign_variations
                     WHERE campaign_id = %s
                     ORDER BY label
                    """,
                    (campaign_id,),
                )
                used = {row["label"] for row in cursor.fetchall()}
                label = next((item for item in labels if item not in used), None)
                if not label:
                    raise CreativeConflictError(
                        "A campanha já possui o máximo de 4 variações."
                    )
                cursor.execute(
                    """
                    INSERT INTO cx_campaign_variations (
                        campaign_id, label, notes
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id, label
                    """,
                    (campaign_id, label, notes),
                )
                return dict(cursor.fetchone())
        except UniqueViolation as exc:
            raise CreativeConflictError(
                "Não foi possível reservar a próxima variação."
            ) from exc

    def save_variation(self, variation_id, notes, steps):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id
                  FROM cx_campaign_variations
                 WHERE id = %s
                 FOR UPDATE
                """,
                (variation_id,),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Variação não encontrada.")

            cursor.execute(
                """
                SELECT id, format_template_id, mockup, scene_description
                  FROM cx_variation_steps
                 WHERE variation_id = %s
                """,
                (variation_id,),
            )
            existing = {row["id"]: dict(row) for row in cursor.fetchall()}
            incoming_ids = {step["id"] for step in steps if step.get("id")}
            invalid_ids = incoming_ids - set(existing)
            if invalid_ids:
                raise CreativeConflictError(
                    "Um ou mais steps não pertencem à variação."
                )

            format_ids = sorted({step["format_template_id"] for step in steps})
            formats = {}
            if format_ids:
                cursor.execute(
                    """
                    SELECT id, engine
                      FROM cx_format_templates
                     WHERE id = ANY(%s) AND is_active = TRUE
                    """,
                    (format_ids,),
                )
                formats = {row["id"]: row["engine"] for row in cursor.fetchall()}
            if set(format_ids) != set(formats):
                raise CreativeNotFoundError(
                    "Um ou mais formatos não foram encontrados."
                )

            cursor.execute(
                "UPDATE cx_campaign_variations SET notes = %s WHERE id = %s",
                (notes, variation_id),
            )
            cursor.execute(
                """
                UPDATE cx_variation_steps
                   SET position = position + 1000
                 WHERE variation_id = %s
                """,
                (variation_id,),
            )
            if existing:
                omitted = set(existing) - incoming_ids
                if omitted:
                    cursor.execute(
                        "DELETE FROM cx_variation_steps WHERE id = ANY(%s)",
                        (sorted(omitted),),
                    )

            saved = []
            for position, step in enumerate(steps, start=1):
                format_id = step["format_template_id"]
                values = (
                    position,
                    format_id,
                    step["mockup"],
                    step.get("scene_description"),
                    formats[format_id],
                )
                step_id = step.get("id")
                if step_id:
                    before = existing[step_id]
                    changed = (
                        before["format_template_id"] != format_id
                        or before["mockup"] != step["mockup"]
                        or (before.get("scene_description") or "")
                        != (step.get("scene_description") or "")
                    )
                    cursor.execute(
                        """
                        UPDATE cx_variation_steps
                           SET position = %s,
                               format_template_id = %s,
                               mockup = %s,
                               scene_description = %s,
                               engine = %s,
                               rendered_prompt = CASE
                                   WHEN %s THEN NULL ELSE rendered_prompt
                               END,
                               asset_status = CASE
                                   WHEN %s THEN 'pending' ELSE asset_status
                               END
                         WHERE id = %s
                        RETURNING id, position
                        """,
                        values + (changed, changed, step_id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO cx_variation_steps (
                            variation_id, position, format_template_id,
                            mockup, scene_description, engine
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id, position
                        """,
                        (variation_id,) + values,
                    )
                saved.append(dict(cursor.fetchone()))
            return saved

    def delete_variation(self, variation_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT campaign_id
                  FROM cx_campaign_variations
                 WHERE id = %s
                """,
                (variation_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Variação não encontrada.")
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                  FROM cx_campaign_variations
                 WHERE campaign_id = %s
                """,
                (row["campaign_id"],),
            )
            if cursor.fetchone()["total"] <= 1:
                raise CreativeConflictError(
                    "A campanha precisa manter ao menos uma variação."
                )
            cursor.execute(
                "DELETE FROM cx_campaign_variations WHERE id = %s",
                (variation_id,),
            )

    def get_variation_context(self, variation_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.label, v.notes, c.id AS campaign_id,
                       c.name AS campaign_name, c.objective,
                       c.campaign_text, c.cta_text, c.show_price,
                       c.budget_usd, c.reserved_usd, c.spent_usd,
                       cl.id AS client_id,
                       cl.name AS client_name, cl.sector AS client_sector,
                       cl.tone_of_voice, cl.logo_url, cl.logo_upload_path,
                       cl.primary_color, cl.secondary_color,
                       cl.website_url, cl.brand_profile
                  FROM cx_campaign_variations v
                  JOIN cx_campaigns c ON c.id = v.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                 WHERE v.id = %s
                """,
                (variation_id,),
            )
            variation = cursor.fetchone()
            if not variation:
                raise CreativeNotFoundError("Variação não encontrada.")
            cursor.execute(
                """
                SELECT s.id, s.position, s.mockup, s.scene_description,
                       s.rendered_prompt, s.prompt_status, s.script_text,
                       s.script_status,
                       f.id AS format_template_id, f.slug AS format_slug,
                       f.name_pt AS format_name, f.mechanic, f.media_type,
                       f.engine, f.layers, f.forbidden_elements,
                       f.aspect_ratio, f.default_size, f.safe_area,
                       f.responsive_rules, f.background_guidance,
                       f.foreground_guidance,
                       ch.name AS channel_name, ch.screen_context_template,
                       ch.partner_primary_color, ch.partner_secondary_color,
                       ch.brand_guidelines
                  FROM cx_variation_steps s
                  JOIN cx_format_templates f ON f.id = s.format_template_id
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE s.variation_id = %s
                 ORDER BY s.position
                """,
                (variation_id,),
            )
            result = dict(variation)
            result["steps"] = [dict(row) for row in cursor.fetchall()]
            return result

    def get_step_context(self, step_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT variation_id FROM cx_variation_steps WHERE id = %s",
                (step_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Step não encontrado.")
        context = self.get_variation_context(row["variation_id"])
        step = next(item for item in context["steps"] if item["id"] == step_id)
        context["step"] = step
        return context

    def save_rendered_prompts(self, prompts):
        with self._write() as cursor:
            for item in prompts:
                cursor.execute(
                    """
                    UPDATE cx_variation_steps
                       SET rendered_prompt = %s, prompt_status = 'generated',
                           asset_status = 'pending'
                     WHERE id = %s
                    """,
                    (item["prompt"], item["step_id"]),
                )

    def update_step_prompt(self, step_id, prompt, status="reviewed"):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_variation_steps
                   SET rendered_prompt = %s, prompt_status = %s
                 WHERE id = %s
                RETURNING id, rendered_prompt, prompt_status
                """,
                (prompt, status, step_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Step não encontrado.")
            return dict(row)

    def update_step_script(self, step_id, script_text, status="reviewed"):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_variation_steps
                   SET script_text = %s, script_status = %s
                 WHERE id = %s
                RETURNING id, script_text, script_status
                """,
                (script_text, status, step_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Step não encontrado.")
            return dict(row)

    def create_generation_job(
        self,
        campaign_id,
        step_id,
        format_template_id,
        job_type,
        provider,
        model,
        estimated_cost_usd,
        prompt=None,
        script_text=None,
        request_payload=None,
        created_by=None,
        scene_id=None,
        reserve_scene=False,
        allow_existing_scene=False,
        concept_session_id=None,
    ):
        estimate = Decimal(str(estimated_cost_usd or 0))
        with self._write() as cursor:
            if scene_id is not None:
                cursor.execute(
                    """
                    SELECT s.id, s.position, s.status, p.status AS production_status,
                           c.creative_brief
                      FROM cx_creative_scenes s
                      JOIN cx_creative_productions p ON p.id = s.production_id
                      JOIN cx_campaigns c ON c.id = p.campaign_id
                     WHERE s.id = %s
                     FOR UPDATE OF s, p
                    """,
                    (scene_id,),
                )
                scene = cursor.fetchone()
                if not scene:
                    raise CreativeNotFoundError("Cena não encontrada.")
                if scene["production_status"] != "active":
                    raise CreativeConflictError("Produção não está ativa.")
                prompt_job = job_type == "prompt"
                brief = scene.get("creative_brief") if isinstance(scene.get("creative_brief"), dict) else {}
                construct_engine = ((brief.get("construct_path") or {}).get("engine"))
                if not prompt_job and construct_engine != ENGINE_CONSTRUCT:
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS pending_previous
                          FROM cx_creative_scenes current_scene
                          JOIN cx_creative_scenes previous
                            ON previous.production_id = current_scene.production_id
                           AND previous.position < current_scene.position
                         WHERE current_scene.id = %s
                           AND previous.status <> 'approved'
                        """,
                        (scene_id,),
                    )
                    if cursor.fetchone()["pending_previous"]:
                        raise CreativeConflictError(
                            "A cena anterior precisa ser aprovada primeiro."
                        )
                if prompt_job:
                    allowed_status = (
                        "ready",
                        "failed",
                        "blocked",
                        "review",
                        "approved",
                    )
                elif allow_existing_scene:
                    allowed_status = ("ready", "failed", "review", "approved")
                else:
                    allowed_status = ("ready", "failed")
                if scene["status"] not in allowed_status:
                    raise CreativeConflictError(
                        "Cena não está disponível para geração."
                    )
            cursor.execute(
                """
                SELECT budget_usd, reserved_usd, spent_usd
                  FROM cx_campaigns
                 WHERE id = %s
                 FOR UPDATE
                """,
                (campaign_id,),
            )
            campaign = cursor.fetchone()
            if not campaign:
                raise CreativeNotFoundError("Campanha não encontrada.")
            balance = (
                campaign["budget_usd"]
                - campaign["reserved_usd"]
                - campaign["spent_usd"]
            )
            if estimate > balance:
                raise CreativeConflictError(
                    f"Saldo insuficiente. Disponível: US$ {balance:.4f}."
                )
            cursor.execute(
                """
                INSERT INTO cx_generation_jobs (
                    campaign_id, step_id, scene_id, format_template_id, job_type,
                    provider, model, status, prompt, script_text,
                    request_payload, estimated_cost_usd, created_by,
                    concept_session_id
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, 'queued',
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    campaign_id,
                    step_id,
                    scene_id,
                    format_template_id,
                    job_type,
                    provider,
                    model,
                    prompt,
                    script_text,
                    Json(request_payload or {}),
                    estimate,
                    created_by,
                    concept_session_id,
                ),
            )
            job_id = cursor.fetchone()["id"]
            if scene_id is not None and reserve_scene:
                if allow_existing_scene:
                    cursor.execute(
                        """
                        UPDATE cx_creative_scenes
                           SET status = 'generating', updated_at = NOW()
                         WHERE id = %s
                        """,
                        (scene_id,),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE cx_creative_scenes
                           SET status = 'generating', prompt = %s, updated_at = NOW()
                         WHERE id = %s
                        """,
                        (prompt, scene_id),
                    )
            cursor.execute(
                """
                UPDATE cx_campaigns
                   SET reserved_usd = reserved_usd + %s
                 WHERE id = %s
                """,
                (estimate, campaign_id),
            )
            cursor.execute(
                """
                INSERT INTO cx_generation_cost_ledger (
                    campaign_id, job_id, entry_type, amount_usd
                )
                VALUES (%s, %s, 'reservation', %s)
                """,
                (campaign_id, job_id, estimate),
            )
            return job_id

    def mark_job_generating(self, job_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_generation_jobs
                   SET status = 'generating', updated_at = NOW()
                 WHERE id = %s AND status = 'queued'
                RETURNING id
                """,
                (job_id,),
            )
            if not cursor.fetchone():
                raise CreativeConflictError("Job não está disponível para execução.")

    def complete_generation_job(
        self, job_id, actual_cost_usd, response_metadata, status="done"
    ):
        actual = Decimal(str(actual_cost_usd or 0))
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id, campaign_id, estimated_cost_usd, status
                  FROM cx_generation_jobs
                 WHERE id = %s
                 FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if not job:
                raise CreativeNotFoundError("Job não encontrado.")
            if job["status"] in ("done", "failed", "ready_for_higgsfield"):
                raise CreativeConflictError("Job já foi finalizado.")
            cursor.execute(
                """
                UPDATE cx_campaigns
                   SET reserved_usd = GREATEST(0, reserved_usd - %s),
                       spent_usd = spent_usd + %s
                 WHERE id = %s
                """,
                (job["estimated_cost_usd"], actual, job["campaign_id"]),
            )
            cursor.execute(
                """
                UPDATE cx_generation_jobs
                   SET status = %s, actual_cost_usd = %s,
                       response_metadata = %s, updated_at = NOW()
                 WHERE id = %s
                """,
                (status, actual, Json(response_metadata or {}), job_id),
            )
            cursor.executemany(
                """
                INSERT INTO cx_generation_cost_ledger (
                    campaign_id, job_id, entry_type, amount_usd
                )
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        job["campaign_id"],
                        job_id,
                        "release",
                        job["estimated_cost_usd"],
                    ),
                    (job["campaign_id"], job_id, "charge", actual),
                ],
            )

    def fail_generation_job(self, job_id, error_message):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT campaign_id, estimated_cost_usd, status, scene_id, job_type
                  FROM cx_generation_jobs
                 WHERE id = %s
                 FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if not job:
                raise CreativeNotFoundError("Job não encontrado.")
            if job["status"] in ("done", "failed", "ready_for_higgsfield"):
                return
            cursor.execute(
                """
                UPDATE cx_campaigns
                   SET reserved_usd = GREATEST(0, reserved_usd - %s)
                 WHERE id = %s
                """,
                (job["estimated_cost_usd"], job["campaign_id"]),
            )
            cursor.execute(
                """
                UPDATE cx_generation_jobs
                   SET status = 'failed', error_message = %s, updated_at = NOW()
                 WHERE id = %s
                """,
                (str(error_message)[:4000], job_id),
            )
            if job.get("scene_id") and job.get("job_type") == "image":
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'failed', updated_at = NOW()
                     WHERE id = %s AND status = 'generating'
                    """,
                    (job["scene_id"],),
                )
            cursor.execute(
                """
                INSERT INTO cx_generation_cost_ledger (
                    campaign_id, job_id, entry_type, amount_usd
                )
                VALUES (%s, %s, 'release', %s)
                """,
                (job["campaign_id"], job_id, job["estimated_cost_usd"]),
            )

    def add_job_reference(self, job_id, reference):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(MAX(position), 0) + 1 AS next_position
                  FROM cx_generation_references
                 WHERE job_id = %s
                """,
                (job_id,),
            )
            position = cursor.fetchone()["next_position"]
            if position > 2:
                raise CreativeConflictError(
                    "Cada geração aceita no máximo duas referências."
                )
            cursor.execute(
                """
                INSERT INTO cx_generation_references (
                    job_id, position, asset_path, original_name, mime_type
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, position
                """,
                (
                    job_id,
                    position,
                    reference["asset_path"],
                    reference.get("original_name"),
                    reference.get("mime_type"),
                ),
            )
            return dict(cursor.fetchone())

    def add_generated_asset(
        self, job_id, step_id, asset_type, asset_url, metadata=None, scene_id=None
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_generated_assets (
                    job_id, step_id, scene_id, asset_type, asset_url,
                    metadata, position
                )
                SELECT %s, %s, %s, %s, %s, %s,
                       COALESCE(MAX(a.position), 0) + 1
                  FROM cx_generation_jobs target
                  LEFT JOIN cx_generation_jobs sibling
                    ON sibling.campaign_id = target.campaign_id
                  LEFT JOIN cx_generated_assets a ON a.job_id = sibling.id
                 WHERE target.id = %s
                 GROUP BY target.id
                RETURNING id, asset_url, status, position
                """,
                (
                    job_id,
                    step_id,
                    scene_id,
                    asset_type,
                    asset_url,
                    Json(metadata or {}),
                    job_id,
                ),
            )
            asset = dict(cursor.fetchone())
            if step_id:
                cursor.execute(
                    """
                    UPDATE cx_variation_steps
                       SET asset_url = %s, asset_status = 'done'
                     WHERE id = %s
                    """,
                    (asset_url, step_id),
                )
            if scene_id:
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'review', updated_at = NOW()
                     WHERE id = %s
                    """,
                    (scene_id,),
                )
            return asset

    def review_scene_asset(self, scene_id, asset_id, status):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.production_id, s.status AS scene_status,
                       a.id AS asset_id
                  FROM cx_creative_scenes s
                  JOIN cx_generated_assets a
                    ON a.scene_id = s.id AND a.id = %s
                 WHERE s.id = %s
                 FOR UPDATE OF s, a
                """,
                (asset_id, scene_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset da cena não encontrado.")
            if row["scene_status"] != "review":
                raise CreativeConflictError("Cena não está aguardando revisão.")
            if status == "approved":
                cursor.execute(
                    """
                    UPDATE cx_generated_assets
                       SET status = CASE
                           WHEN id = %s THEN 'approved' ELSE 'rejected'
                       END
                     WHERE scene_id = %s
                    """,
                    (asset_id, scene_id),
                )
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'approved', approved_asset_id = %s,
                           preview_asset_id = %s,
                           updated_at = NOW()
                     WHERE id = %s
                    RETURNING position
                    """,
                    (asset_id, asset_id, scene_id),
                )
                position = cursor.fetchone()["position"]
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'ready', updated_at = NOW()
                     WHERE production_id = %s AND position = %s
                       AND status = 'blocked'
                    """,
                    (row["production_id"], position + 1),
                )
                cursor.execute(
                    """
                    UPDATE cx_creative_productions p
                       SET status = CASE
                               WHEN NOT EXISTS (
                                   SELECT 1
                                     FROM cx_creative_scenes s
                                    WHERE s.production_id = p.id
                                      AND s.status <> 'approved'
                               ) THEN 'completed'
                               ELSE 'active'
                           END,
                           updated_at = NOW()
                     WHERE p.id = %s
                    """,
                    (row["production_id"],),
                )
            else:
                cursor.execute(
                    "UPDATE cx_generated_assets SET status = 'rejected' WHERE id = %s",
                    (asset_id,),
                )
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'ready', approved_asset_id = NULL,
                           updated_at = NOW()
                     WHERE id = %s
                    """,
                    (scene_id,),
                )
            return {
                "scene_id": scene_id,
                "asset_id": asset_id,
                "status": status,
            }

    def set_scene_preview_asset(self, scene_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                 WHERE a.id = %s AND a.scene_id = %s AND a.status = 'approved'
                """,
                (asset_id, scene_id),
            )
            if not cursor.fetchone():
                raise CreativeConflictError(
                    "Escolha um asset aprovado desta cena."
                )
            cursor.execute(
                """
                UPDATE cx_creative_scenes
                   SET preview_asset_id = %s, updated_at = NOW()
                 WHERE id = %s
                RETURNING id, preview_asset_id
                """,
                (asset_id, scene_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Cena não encontrada.")
            return dict(row)

    def select_production_asset(self, production_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                  JOIN cx_creative_scenes s ON s.id = a.scene_id
                 WHERE a.id = %s
                   AND s.production_id = %s
                   AND a.status = 'approved'
                """,
                (asset_id, production_id),
            )
            if not cursor.fetchone():
                raise CreativeConflictError(
                    "Escolha um asset aprovado desta produção."
                )
            cursor.execute(
                """
                UPDATE cx_creative_productions
                   SET selected_asset_id = %s, updated_at = NOW()
                 WHERE id = %s
                RETURNING id, selected_asset_id
                """,
                (asset_id, production_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Produção não encontrada.")
            return dict(row)

    def get_assets(self, asset_ids, approved_only=True):
        ids = sorted({_id for _id in asset_ids})
        if not ids:
            return []
        with self.conn.cursor() as cursor:
            query = """
                SELECT a.id, a.job_id, a.step_id, a.scene_id,
                       a.asset_type, a.asset_url,
                       a.status, a.metadata, j.campaign_id,
                       j.prompt AS job_prompt,
                       COALESCE(j.format_template_id, s.format_template_id)
                           AS format_template_id,
                       f.aspect_ratio, f.media_type, f.mechanic
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                 WHERE a.id = ANY(%s)
            """
            if approved_only:
                query += " AND a.status = 'approved'"
            cursor.execute(query, (ids,))
            rows = {row["id"]: dict(row) for row in cursor.fetchall()}
        return [rows[_id] for _id in asset_ids if _id in rows]

    def set_asset_status(self, asset_id, status):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_generated_assets
                   SET status = %s
                 WHERE id = %s
                RETURNING id, job_id, step_id, asset_url, asset_type, status
                """,
                (status, asset_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset não encontrado.")
            if row.get("step_id"):
                cursor.execute(
                    """
                    UPDATE cx_variation_steps
                       SET asset_status = %s
                     WHERE id = %s
                    """,
                    (status, row["step_id"]),
                )
            return dict(row)

    def link_video_assets(self, job_id, assets):
        with self._write() as cursor:
            for position, asset in enumerate(assets, start=1):
                cursor.execute(
                    """
                    INSERT INTO cx_video_input_assets (job_id, position, asset_id)
                    VALUES (%s, %s, %s)
                    """,
                    (job_id, position, asset["id"]),
                )

    def list_generation_jobs(self, campaign_id=None, limit=100):
        params = []
        where = ""
        if campaign_id:
            where = "WHERE j.campaign_id = %s"
            params.append(campaign_id)
        params.append(limit)
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT j.*, c.name AS campaign_name,
                       v.label AS variation_label, s.position AS step_position,
                       f.name_pt AS format_name,
                       COALESCE(
                           (SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at)
                              FROM cx_generated_assets a WHERE a.job_id = j.id),
                           '[]'::jsonb
                       ) AS assets
                  FROM cx_generation_jobs j
                  JOIN cx_campaigns c ON c.id = j.campaign_id
                  LEFT JOIN cx_variation_steps s ON s.id = j.step_id
                  LEFT JOIN cx_campaign_variations v ON v.id = s.variation_id
                  LEFT JOIN cx_format_templates f ON f.id = j.format_template_id
                  {where}
                 ORDER BY j.created_at DESC
                 LIMIT %s
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_format_modeling_job(
        self,
        format_template_id,
        client_id,
        parent_job_id,
        slot,
        reference_type,
        model,
        prompt,
        input_references,
        estimated_cost_usd,
        refinement_instruction=None,
        created_by=None,
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_format_modeling_jobs (
                    format_template_id, client_id, parent_job_id, slot,
                    reference_type, model, prompt, refinement_instruction,
                    input_references, estimated_cost_usd, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    format_template_id,
                    client_id,
                    parent_job_id,
                    slot,
                    reference_type,
                    model,
                    prompt,
                    refinement_instruction,
                    Json(input_references or []),
                    Decimal(str(estimated_cost_usd or 0)),
                    created_by,
                ),
            )
            return cursor.fetchone()["id"]

    def mark_format_modeling_job_generating(self, job_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'generating', updated_at = NOW()
                 WHERE id = %s AND status = 'queued'
                RETURNING id
                """,
                (job_id,),
            )
            if not cursor.fetchone():
                raise CreativeConflictError("Job de modelagem indisponível.")

    def complete_format_modeling_job(
        self, job_id, asset_url, actual_cost_usd, response_metadata
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'review', asset_url = %s,
                       actual_cost_usd = %s, response_metadata = %s,
                       updated_at = NOW()
                 WHERE id = %s AND status = 'generating'
                RETURNING id, format_template_id, client_id, parent_job_id,
                          slot, reference_type, model, status, prompt,
                          refinement_instruction, input_references, asset_url,
                          estimated_cost_usd, actual_cost_usd,
                          response_metadata, created_at, updated_at
                """,
                (
                    asset_url,
                    Decimal(str(actual_cost_usd or 0)),
                    Json(response_metadata or {}),
                    job_id,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeConflictError("Job de modelagem não está gerando.")
            return dict(row)

    def fail_format_modeling_job(self, job_id, error_message):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'failed', error_message = %s, updated_at = NOW()
                 WHERE id = %s AND status IN ('queued', 'generating')
                """,
                (str(error_message)[:4000], job_id),
            )

    def get_format_modeling_job(self, job_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT j.*, f.name_pt AS format_name, f.aspect_ratio,
                       f.default_size, f.placement_spec, f.behavior_spec,
                       c.name AS client_name, c.logo_url, c.logo_upload_path,
                       c.primary_color, c.secondary_color, c.tone_of_voice
                  FROM cx_format_modeling_jobs j
                  JOIN cx_format_templates f ON f.id = j.format_template_id
                  LEFT JOIN cx_clients c ON c.id = j.client_id
                 WHERE j.id = %s
                """,
                (job_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Job de modelagem não encontrado.")
        return dict(row)

    def list_format_modeling_jobs(self, format_template_id, limit=40):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT j.id, j.format_template_id, j.client_id, j.parent_job_id,
                       j.slot, j.reference_type, j.model, j.status, j.prompt,
                       j.refinement_instruction, j.asset_url,
                       j.estimated_cost_usd, j.actual_cost_usd, j.error_message,
                       j.created_at, j.updated_at, c.name AS client_name
                  FROM cx_format_modeling_jobs j
                  LEFT JOIN cx_clients c ON c.id = j.client_id
                 WHERE j.format_template_id = %s
                   AND j.status <> 'archived'
                 ORDER BY j.created_at DESC, j.id DESC
                 LIMIT %s
                """,
                (format_template_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def approve_format_modeling_job(self, job_id, slot):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id, format_template_id, reference_type, prompt, asset_url
                  FROM cx_format_modeling_jobs
                 WHERE id = %s AND status IN ('review', 'approved')
                 FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if not job or not job.get("asset_url"):
                raise CreativeConflictError("Gere o mockup antes de aprová-lo.")
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = CASE WHEN id = %s THEN 'approved' ELSE status END,
                       slot = CASE WHEN id = %s THEN %s ELSE slot END,
                       updated_at = NOW()
                 WHERE id = %s
                """,
                (job_id, job_id, slot, job_id),
            )
            cursor.execute(
                """
                INSERT INTO cx_format_references (
                    format_template_id, slot, reference_type, prompt, asset_url,
                    status, source_modeling_job_id
                )
                VALUES (%s, %s, %s, %s, %s, 'approved', %s)
                ON CONFLICT (format_template_id, slot) DO UPDATE SET
                    reference_type = EXCLUDED.reference_type,
                    prompt = EXCLUDED.prompt,
                    asset_url = EXCLUDED.asset_url,
                    status = 'approved',
                    source_job_id = NULL,
                    source_modeling_job_id = EXCLUDED.source_modeling_job_id,
                    created_at = NOW()
                RETURNING id, slot, asset_url, status
                """,
                (
                    job["format_template_id"],
                    slot,
                    job["reference_type"],
                    job["prompt"],
                    job["asset_url"],
                    job_id,
                ),
            )
            return dict(cursor.fetchone())

    def archive_format_modeling_job(self, job_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'archived', updated_at = NOW()
                 WHERE id = %s AND status <> 'approved'
                RETURNING id, asset_url, input_references
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeConflictError(
                    "Referências aprovadas devem ser substituídas antes de arquivar."
                )
            return dict(row)

    def upsert_format_reference(
        self, format_template_id, slot, reference_type, prompt, asset_url, job_id
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_format_references (
                    format_template_id, slot, reference_type, prompt,
                    asset_url, status, source_job_id
                )
                VALUES (%s, %s, %s, %s, %s, 'approved', %s)
                ON CONFLICT (format_template_id, slot) DO UPDATE SET
                    reference_type = EXCLUDED.reference_type,
                    prompt = EXCLUDED.prompt,
                    asset_url = EXCLUDED.asset_url,
                    status = 'approved',
                    source_job_id = EXCLUDED.source_job_id,
                    created_at = NOW()
                RETURNING id, slot
                """,
                (
                    format_template_id,
                    slot,
                    reference_type,
                    prompt,
                    asset_url,
                    job_id,
                ),
            )
            return dict(cursor.fetchone())

    def list_campaign_assets(self, campaign_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.job_id, a.step_id, a.scene_id,
                       a.asset_type, a.asset_url,
                       a.position, a.title, a.caption, a.status, a.metadata,
                       j.campaign_id, j.prompt, j.script_text, j.model,
                       j.actual_cost_usd, j.created_at,
                       scene.production_id, scene.position AS scene_position,
                       v.label AS variation_label, s.position AS step_position,
                       f.id AS format_template_id, f.name_pt AS format_name,
                       f.mechanic, f.media_type, f.aspect_ratio, f.default_size,
                       f.placement_spec, f.default_viewer_profile_id,
                       ch.name AS channel_name
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_creative_scenes scene ON scene.id = a.scene_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_campaign_variations v ON v.id = s.variation_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE j.campaign_id = %s
                 ORDER BY a.position, a.created_at, a.id
                """,
                (campaign_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def reorder_campaign_assets(self, campaign_id, asset_ids):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                 WHERE j.campaign_id = %s
                 FOR UPDATE
                """,
                (campaign_id,),
            )
            available = {row["id"] for row in cursor.fetchall()}
            if set(asset_ids) != available or len(asset_ids) != len(available):
                raise CreativeConflictError(
                    "A ordenação deve conter todos os assets da campanha uma vez."
                )
            cursor.execute(
                """
                UPDATE cx_generated_assets a
                   SET position = position + 1000
                  FROM cx_generation_jobs j
                 WHERE a.job_id = j.id AND j.campaign_id = %s
                """,
                (campaign_id,),
            )
            for position, asset_id in enumerate(asset_ids, start=1):
                cursor.execute(
                    """
                    UPDATE cx_generated_assets
                       SET position = %s
                     WHERE id = %s
                    """,
                    (position, asset_id),
                )

    def delete_campaign_asset(self, campaign_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                DELETE FROM cx_generated_assets a
                 USING cx_generation_jobs j
                 WHERE a.id = %s
                   AND a.job_id = j.id
                   AND j.campaign_id = %s
                RETURNING a.asset_url
                """,
                (asset_id, campaign_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset não encontrado na campanha.")
            return row["asset_url"]

    def update_campaign_asset(self, campaign_id, asset_id, title, caption):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_generated_assets a
                   SET title = %s, caption = %s
                  FROM cx_generation_jobs j
                 WHERE a.id = %s
                   AND a.job_id = j.id
                   AND j.campaign_id = %s
                RETURNING a.id, a.title, a.caption
                """,
                (title, caption, asset_id, campaign_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset não encontrado na campanha.")
            return dict(row)

    def create_public_collection(
        self, campaign_id, token, title, description, asset_ids,
        viewer_profiles, created_by
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id FROM cx_campaigns WHERE id = %s FOR UPDATE
                """,
                (campaign_id,),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Campanha não encontrada.")
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                 WHERE j.campaign_id = %s AND a.id = ANY(%s)
                """,
                (campaign_id, asset_ids),
            )
            found = {row["id"] for row in cursor.fetchall()}
            if found != set(asset_ids):
                raise CreativeConflictError(
                    "Um ou mais assets não pertencem à campanha."
                )
            cursor.execute(
                """
                INSERT INTO cx_public_creative_collections (
                    campaign_id, token, title, description, created_by
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, token
                """,
                (campaign_id, token, title, description, created_by),
            )
            collection = dict(cursor.fetchone())
            for position, asset_id in enumerate(asset_ids, start=1):
                cursor.execute(
                    """
                    INSERT INTO cx_public_collection_assets (
                        collection_id, asset_id, position, viewer_profile_id
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        collection["id"], asset_id, position,
                        viewer_profiles.get(asset_id),
                    ),
                )
            return collection

    def list_public_collections(self, campaign_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.campaign_id, c.token, c.title, c.description,
                       c.is_active, c.created_at, c.revoked_at,
                       COUNT(a.asset_id)::integer AS asset_count
                  FROM cx_public_creative_collections c
                  LEFT JOIN cx_public_collection_assets a
                    ON a.collection_id = c.id
                 WHERE c.campaign_id = %s
                 GROUP BY c.id
                 ORDER BY c.created_at DESC
                """,
                (campaign_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def revoke_public_collection(self, campaign_id, collection_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_public_creative_collections
                   SET is_active = FALSE, revoked_at = NOW()
                 WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                RETURNING id
                """,
                (collection_id, campaign_id),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Link público ativo não encontrado.")

    def get_public_collection(self, token):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT pc.id, pc.campaign_id, pc.title, pc.description,
                       pc.created_at, c.name AS campaign_name,
                       cl.id AS client_id, cl.name AS client_name, cl.logo_url,
                       cl.logo_upload_path, cl.primary_color, cl.secondary_color
                  FROM cx_public_creative_collections pc
                  JOIN cx_campaigns c ON c.id = pc.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                 WHERE pc.token = %s AND pc.is_active = TRUE
                """,
                (token,),
            )
            collection = cursor.fetchone()
            if not collection:
                raise CreativeNotFoundError("Apresentação não encontrada ou revogada.")
            cursor.execute(
                """
                SELECT a.id, a.asset_type, a.asset_url, a.title, a.caption,
                       a.status, ca.position, j.prompt, j.script_text,
                       f.slug AS format_slug, f.name_pt AS format_name,
                       f.mechanic, f.media_type,
                       f.aspect_ratio, f.default_size,
                       f.placement_spec, f.behavior_spec,
                       ch.slug AS channel_slug, ch.name AS channel_name,
                       v.label AS variation_label, s.position AS step_position,
                       vp.id AS viewer_profile_id, vp.slug AS viewer_slug,
                       vp.name AS viewer_name, vp.viewer_kind,
                       vp.logo_asset_ref AS viewer_logo_asset_ref,
                       vp.palette AS viewer_palette,
                       vp.shell_spec AS viewer_shell_spec,
                       vp.disclaimer AS viewer_disclaimer,
                       COALESCE(
                           (
                               SELECT jsonb_agg(
                                   jsonb_build_object(
                                       'id', frame.id,
                                       'position', frame.position,
                                       'title', frame.title,
                                       'asset_type', frame.asset_type
                                   )
                                   ORDER BY frame.position
                               )
                                 FROM (
                                     SELECT DISTINCT ON (sibling_scene.position)
                                            sibling_asset.id,
                                            sibling_scene.position,
                                            sibling_asset.title,
                                            sibling_asset.asset_type,
                                            sibling_asset.created_at
                                       FROM cx_creative_scenes selected_scene
                                       JOIN cx_creative_scenes sibling_scene
                                         ON sibling_scene.production_id =
                                            selected_scene.production_id
                                       JOIN cx_generation_jobs sibling_job
                                         ON sibling_job.scene_id = sibling_scene.id
                                       JOIN cx_generated_assets sibling_asset
                                         ON sibling_asset.job_id = sibling_job.id
                                      WHERE selected_scene.id = j.scene_id
                                        AND sibling_asset.status = 'approved'
                                      ORDER BY sibling_scene.position,
                                               sibling_asset.created_at DESC
                                 ) frame
                           ),
                           jsonb_build_array(
                               jsonb_build_object(
                                   'id', a.id,
                                   'position', COALESCE(s.position, 1),
                                   'title', a.title,
                                   'asset_type', a.asset_type
                               )
                           )
                       ) AS carousel_assets
                  FROM cx_public_collection_assets ca
                  JOIN cx_generated_assets a ON a.id = ca.asset_id
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_campaign_variations v ON v.id = s.variation_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_creative_viewer_profiles vp
                    ON vp.id = COALESCE(
                        ca.viewer_profile_id,
                        f.default_viewer_profile_id,
                        (
                            SELECT fallback.id
                              FROM cx_creative_viewer_profiles fallback
                             WHERE fallback.slug = CASE
                                 WHEN f.placement_spec->>'context' = 'tv'
                                 THEN 'netflix'
                                 ELSE 'g1'
                             END
                               AND fallback.is_active = TRUE
                             LIMIT 1
                        )
                    )
                 WHERE ca.collection_id = %s
                 ORDER BY ca.position
                """,
                (collection["id"],),
            )
            result = dict(collection)
            result["assets"] = [dict(row) for row in cursor.fetchall()]
            return result

    def list_client_public_nav(self, client_id):
        if not client_id:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT pc.token, pc.title, pc.created_at,
                       c.name AS campaign_name,
                       cl.id AS client_id, cl.name AS client_name,
                       cl.logo_url, cl.logo_upload_path,
                       COALESCE(vp.slug, ch.slug, 'portal') AS viewer_slug,
                       COALESCE(vp.name, ch.name, 'Canal') AS viewer_name,
                       COALESCE(vp.viewer_kind, 'portal') AS viewer_kind,
                       vp.logo_asset_ref AS viewer_logo,
                       ch.name AS channel_name,
                       COUNT(ca.asset_id)::integer AS asset_count
                  FROM cx_public_creative_collections pc
                  JOIN cx_campaigns c ON c.id = pc.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                  JOIN cx_public_collection_assets ca
                    ON ca.collection_id = pc.id
                  JOIN cx_generated_assets a ON a.id = ca.asset_id
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_creative_viewer_profiles vp
                    ON vp.id = COALESCE(
                        ca.viewer_profile_id,
                        f.default_viewer_profile_id
                    )
                 WHERE cl.id = %s AND pc.is_active = TRUE
                 GROUP BY pc.token, pc.title, pc.created_at, c.name,
                          cl.id, cl.name, cl.logo_url, cl.logo_upload_path,
                          vp.slug, vp.name, vp.viewer_kind, vp.logo_asset_ref,
                          ch.slug, ch.name
                 ORDER BY c.name, pc.created_at DESC, viewer_name
                """,
                (client_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_public_collection_asset(self, token, asset_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.asset_url, a.asset_type
                  FROM cx_public_creative_collections pc
                  JOIN cx_generated_assets a ON a.id = %s
                 WHERE pc.token = %s
                   AND pc.is_active = TRUE
                   AND EXISTS (
                       SELECT 1
                         FROM cx_public_collection_assets ca
                         JOIN cx_generated_assets selected_asset
                           ON selected_asset.id = ca.asset_id
                         JOIN cx_generation_jobs selected_job
                           ON selected_job.id = selected_asset.job_id
                         LEFT JOIN cx_creative_scenes selected_scene
                           ON selected_scene.id = selected_job.scene_id
                         JOIN cx_generation_jobs requested_job
                           ON requested_job.id = a.job_id
                         LEFT JOIN cx_creative_scenes requested_scene
                           ON requested_scene.id = requested_job.scene_id
                        WHERE ca.collection_id = pc.id
                          AND (
                              ca.asset_id = a.id
                              OR (
                                  a.status = 'approved'
                                  AND selected_scene.production_id IS NOT NULL
                                  AND selected_scene.production_id =
                                      requested_scene.production_id
                              )
                          )
                   )
                """,
                (asset_id, token),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError(
                    "Mídia não encontrada ou apresentação revogada."
                )
            return dict(row)

    def _compose_variation_row(self, row):
        if not row:
            return None
        data = dict(row)
        data["params"] = data.get("params") or {}
        data["adjust_schema"] = data.get("adjust_schema") or {}
        return data

    def get_compose_variation(self, variation_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.template_id, v.name, v.params, v.status,
                       v.approve_count, v.reject_count, v.preview_asset_url,
                       t.slug AS template_slug, t.kind, t.family, t.html_key,
                       t.adjust_schema
                  FROM cx_compose_variations v
                  JOIN cx_compose_templates t ON t.id = v.template_id
                 WHERE v.id = %s
                """,
                (variation_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Variação da biblioteca não encontrada.")
            return self._compose_variation_row(row)

    def list_brand_visual_systems(self, client_id=None):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, client_id, name, tokens, status
                  FROM cx_brand_visual_systems
                 WHERE status <> 'archived'
                   AND (%s IS NULL OR client_id IS NULL OR client_id = %s)
                 ORDER BY
                    CASE WHEN client_id = %s THEN 0 ELSE 1 END,
                    id DESC
                """,
                (client_id, client_id, client_id),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_design_system_ads(self, client_id):
        try:
            rows = self.list_brand_visual_systems(client_id)
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return None
        for row in rows:
            if str(row.get("client_id") or "") != str(client_id or ""):
                continue
            tokens = row.get("tokens") if isinstance(row.get("tokens"), dict) else {}
            if tokens.get("framework") == "design-system-ads":
                return row
            if row.get("name") in {"Design System Ads", "CentralComm Ads"}:
                return row
        return None

    def upsert_design_system_ads(self, client_id, system):
        """Projeção de `cx_brand_visual_systems`. Canônico: brand_profile.

        Corre depois do CAS. Falha não desfaz o documento canônico.
        Revisão atrasada não sobrescreve a projeção.
        """
        from .design_system_ads.revision import projection_is_stale

        payload = system if isinstance(system, dict) else {}
        name = str(payload.get("name") or "Design System Ads")[:160]
        status = str(payload.get("status") or "draft")
        if status not in {"draft", "approved", "archived"}:
            status = "draft"
        existing = self.get_design_system_ads(client_id)
        if existing and projection_is_stale(
            (existing.get("tokens") or {}), payload
        ):
            return existing.get("id")
        try:
            with self._write() as cursor:
                if existing:
                    cursor.execute(
                        """
                        UPDATE cx_brand_visual_systems
                           SET name = %s,
                               tokens = %s,
                               status = %s,
                               updated_at = NOW()
                         WHERE id = %s
                        RETURNING id
                        """,
                        (name, Json(payload), status, existing["id"]),
                    )
                    row = cursor.fetchone()
                    return row["id"] if row else existing["id"]
                cursor.execute(
                    """
                    INSERT INTO cx_brand_visual_systems (client_id, name, tokens, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (client_id, name, Json(payload), status),
                )
                return cursor.fetchone()["id"]
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return None

    def list_compose_templates(self, family=None):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, visual_system_id, format_template_id, slug, name,
                       kind, family, html_key, adjust_schema
                  FROM cx_compose_templates
                 WHERE %s IS NULL OR family = %s
                 ORDER BY family, id
                """,
                (family, family),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_compose_variations(self, family=None, client_id=None):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.template_id, v.name, v.params, v.status,
                       v.approve_count, v.reject_count, v.preview_asset_url,
                       t.slug AS template_slug, t.kind, t.family, t.html_key,
                       t.adjust_schema
                  FROM cx_compose_variations v
                  JOIN cx_compose_templates t ON t.id = v.template_id
                 WHERE (%s IS NULL OR t.family = %s)
                   AND v.status <> 'archived'
                 ORDER BY
                    CASE v.status WHEN 'approved' THEN 0 ELSE 1 END,
                    v.approve_count DESC,
                    v.id DESC
                """,
                (family, family),
            )
            return [self._compose_variation_row(row) for row in cursor.fetchall()]

    def suggest_compose_variation(self, family, client_id=None):
        rows = self.list_compose_variations(family=family, client_id=client_id)
        return rows[0] if rows else None

    def record_compose_feedback(self, variation_id, campaign_id, asset_id, verdict):
        from .creative_compose_library import next_variation_status

        if verdict not in {"approved", "rejected"}:
            raise ValueError("Veredito da variação deve ser approved ou rejected.")
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id, approve_count, reject_count, status
                  FROM cx_compose_variations
                 WHERE id = %s
                 FOR UPDATE
                """,
                (variation_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Variação da biblioteca não encontrada.")
            approved = int(row["approve_count"] or 0) + (
                1 if verdict == "approved" else 0
            )
            rejected = int(row["reject_count"] or 0) + (
                1 if verdict == "rejected" else 0
            )
            status = next_variation_status(approved, rejected, row["status"])
            cursor.execute(
                """
                INSERT INTO cx_compose_feedback (
                    variation_id, campaign_id, asset_id, verdict
                )
                VALUES (%s, %s, %s, %s)
                """,
                (variation_id, campaign_id, asset_id, verdict),
            )
            cursor.execute(
                """
                UPDATE cx_compose_variations
                   SET approve_count = %s,
                       reject_count = %s,
                       status = %s,
                       updated_at = NOW()
                 WHERE id = %s
                RETURNING id, template_id, name, params, status,
                          approve_count, reject_count, preview_asset_url
                """,
                (approved, rejected, status, variation_id),
            )
            updated = dict(cursor.fetchone())
            updated["params"] = updated.get("params") or {}
            return updated

    def create_compose_variation(self, template_id, name, params, status="experimental"):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_compose_variations (
                    template_id, name, params, status
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id, template_id, name, params, status,
                          approve_count, reject_count, preview_asset_url
                """,
                (template_id, name, Json(params or {}), status),
            )
            row = dict(cursor.fetchone())
            row["params"] = row.get("params") or {}
            return row

    def upsert_concept_session(self, session, created_by=None):
        session = dict(session or {})
        session_id = str(session.get("id") or "").strip()
        if not session_id:
            raise CreativeConflictError("Sessão de conceito sem id.")
        try:
            campaign_id = int(session.get("campaign_id"))
            client_id = int(session.get("client_id"))
        except (TypeError, ValueError):
            raise CreativeConflictError("Sessão de conceito sem campanha ou cliente.")
        knobs = _json_object(session.get("knobs"))
        campaign = session.get("campaign") if isinstance(session.get("campaign"), dict) else {}
        brand = session.get("brand") if isinstance(session.get("brand"), dict) else {}
        brand_snapshot = session.get("brand_snapshot")
        brand_snapshot = brand_snapshot if isinstance(brand_snapshot, dict) else {
            **brand,
            "brand_dna": session.get("brand_dna") or brand.get("brand_dna"),
            "brand_name": session.get("brand_name") or brand.get("name"),
        }
        payload = {
            key: value
            for key, value in session.items()
            if key not in _CONCEPT_RELATIONAL_KEYS
        }
        format_key = _concept_format_key(
            session.get("format") or session.get("format_key")
        )
        status = _concept_status(session.get("status"))
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_concept_sessions (
                    id, campaign_id, client_id, format_key, variant, intent,
                    status, campaign_slug, duration_seconds, scene_count,
                    adapter, platform_label, objective, knobs, spec,
                    brand_snapshot, qa, quote, payload, spent_usd, created_by,
                    handed_off_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, 15, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'handed_off' THEN NOW() ELSE NULL END
                )
                ON CONFLICT (id) DO UPDATE SET
                    campaign_id = EXCLUDED.campaign_id,
                    client_id = EXCLUDED.client_id,
                    format_key = EXCLUDED.format_key,
                    variant = EXCLUDED.variant,
                    intent = EXCLUDED.intent,
                    status = EXCLUDED.status,
                    campaign_slug = EXCLUDED.campaign_slug,
                    scene_count = EXCLUDED.scene_count,
                    adapter = EXCLUDED.adapter,
                    platform_label = EXCLUDED.platform_label,
                    objective = EXCLUDED.objective,
                    knobs = EXCLUDED.knobs,
                    spec = EXCLUDED.spec,
                    brand_snapshot = EXCLUDED.brand_snapshot,
                    qa = EXCLUDED.qa,
                    quote = EXCLUDED.quote,
                    payload = EXCLUDED.payload,
                    spent_usd = EXCLUDED.spent_usd,
                    updated_at = NOW(),
                    handed_off_at = CASE
                        WHEN EXCLUDED.status = 'handed_off'
                        THEN COALESCE(cx_concept_sessions.handed_off_at, NOW())
                        ELSE cx_concept_sessions.handed_off_at
                    END
                """,
                (
                    session_id,
                    campaign_id,
                    client_id,
                    format_key,
                    _concept_variant(session.get("variant")),
                    _concept_intent(session.get("intent")),
                    status,
                    str(
                        session.get("campaign_slug")
                        or campaign.get("slug")
                        or ""
                    ) or None,
                    _concept_scene_count(
                        session.get("scene_count") or knobs.get("scene_count")
                    ),
                    session.get("adapter"),
                    session.get("platform_label"),
                    session.get("objective")
                    or knobs.get("objective")
                    or campaign.get("objective"),
                    Json(knobs),
                    Json(_json_object(session.get("spec"))),
                    Json(brand_snapshot),
                    Json(_json_object(session.get("qa"))),
                    Json(_json_object(session.get("quote") or session.get("cost"))),
                    Json(payload),
                    _concept_spent(session),
                    created_by or session.get("created_by"),
                    status,
                ),
            )
            self._replace_concept_scenes(cursor, session_id, session)
            self._replace_concept_passes(cursor, session_id, session)
            self._replace_concept_references(cursor, session_id, session)
        return self.get_concept_session(session_id)

    def get_concept_session(self, session_id):
        session_id = str(session_id or "").strip()
        if not session_id:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, campaign_id, client_id, format_key, variant, intent,
                       status, campaign_slug, duration_seconds, scene_count,
                       adapter, platform_label, objective, knobs, spec,
                       brand_snapshot, qa, quote, payload, spent_usd,
                       created_by, created_at, updated_at, handed_off_at
                  FROM cx_concept_sessions
                 WHERE id = %s
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                """
                SELECT id, scene_key, position, purpose, role, headline,
                       support, cta, tip, set_note, action_note, timecode,
                       duration_seconds, image_prompt, html, render_url,
                       layers, status
                  FROM cx_concept_scenes
                 WHERE session_id = %s
                 ORDER BY position
                """,
                (session_id,),
            )
            scene_rows = [dict(item) for item in cursor.fetchall()]
            scene_ids = [item["id"] for item in scene_rows]
            layers_by_scene = {}
            if scene_ids:
                cursor.execute(
                    """
                    SELECT scene_id, layer_key, layer_type, x, y, w, h, z,
                           text_value, css_value
                      FROM cx_concept_layers
                     WHERE scene_id = ANY(%s)
                     ORDER BY scene_id, z NULLS LAST, id
                    """,
                    (scene_ids,),
                )
                for layer in cursor.fetchall():
                    layers_by_scene.setdefault(layer["scene_id"], []).append({
                        "id": layer["layer_key"],
                        "tipo": layer["layer_type"],
                        "x": _optional_number(layer["x"]),
                        "y": _optional_number(layer["y"]),
                        "w": _optional_number(layer["w"]),
                        "h": _optional_number(layer["h"]),
                        "z": layer["z"],
                        "text": layer["text_value"],
                        "css": layer["css_value"],
                    })
            cursor.execute(
                """
                SELECT id, job_id, pass_kind, position, status, model,
                       estimated_cost_usd, actual_cost_usd, metadata
                  FROM cx_concept_passes
                 WHERE session_id = %s
                 ORDER BY position, id
                """,
                (session_id,),
            )
            passes = [
                {
                    "id": item["pass_kind"],
                    "job_id": item["job_id"],
                    "position": item["position"],
                    "status": item["status"],
                    "model": item["model"],
                    "estimated_cost_usd": float(item["estimated_cost_usd"] or 0),
                    "actual_cost_usd": (
                        float(item["actual_cost_usd"])
                        if item["actual_cost_usd"] is not None
                        else None
                    ),
                    "metadata": item["metadata"] or {},
                }
                for item in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT role, asset_url, position
                  FROM cx_concept_references
                 WHERE session_id = %s
                 ORDER BY position, id
                """,
                (session_id,),
            )
            references = [dict(item) for item in cursor.fetchall()]
        payload = _json_object(row["payload"])
        brand = _json_object(row["brand_snapshot"])
        scenes = []
        for item in scene_rows:
            layers = layers_by_scene.get(item["id"]) or _json_list(item.get("layers"))
            scenes.append({
                "id": item["scene_key"],
                "scene_key": item["scene_key"],
                "position": item["position"],
                "purpose": item["purpose"],
                "role": item["role"],
                "headline": item["headline"],
                "support": item["support"],
                "cta": item["cta"],
                "tip": item["tip"],
                "set_note": item["set_note"],
                "action_note": item["action_note"],
                "timecode": item["timecode"],
                "duration": float(item["duration_seconds"] or 0),
                "image_prompt": item["image_prompt"],
                "html": item["html"],
                "render_url": item["render_url"],
                "layers": layers,
                "status": item["status"],
            })
        data = dict(payload)
        data.update({
            "id": row["id"],
            "campaign_id": row["campaign_id"],
            "client_id": row["client_id"],
            "format": row["format_key"],
            "format_key": row["format_key"],
            "variant": row["variant"],
            "intent": row["intent"],
            "status": row["status"],
            "campaign_slug": row["campaign_slug"],
            "duration": row["duration_seconds"],
            "duration_seconds": row["duration_seconds"],
            "scene_count": row["scene_count"],
            "adapter": row["adapter"],
            "platform_label": row["platform_label"],
            "objective": row["objective"],
            "knobs": row["knobs"] or {},
            "spec": row["spec"] or {},
            "qa": row["qa"] or {},
            "quote": row["quote"] or {},
            "brand": brand,
            "brand_dna": brand.get("brand_dna"),
            "brand_name": brand.get("brand_name") or brand.get("name"),
            "spent_usd": float(row["spent_usd"] or 0),
            "scenes": scenes,
            "storyboard": [
                {
                    "id": item["id"],
                    "position": item["position"],
                    "purpose": item["purpose"],
                    "role": item["role"],
                    "headline": item["headline"],
                    "support": item["support"],
                    "cta": item["cta"],
                    "set_note": item["set_note"],
                    "action_note": item["action_note"],
                    "duration": item["duration"],
                    "timecode": item["timecode"],
                    "image_prompt": item["image_prompt"],
                }
                for item in scenes
            ],
            "layers": scenes[0]["layers"] if scenes else [],
            "passes": passes or payload.get("passes") or [],
            "references": [item["asset_url"] for item in references],
            "created_by": row["created_by"],
            "handed_off_at": row["handed_off_at"],
        })
        if not data.get("cards") and scenes:
            data["cards"] = [
                {
                    "id": item["id"],
                    "label": item.get("headline") or item["id"],
                    "duration": item["duration"],
                    "role": item.get("role") or "unico",
                    "layers": item.get("layers") or [],
                }
                for item in scenes
            ]
        return data

    def find_open_concept_session(self, client_id, format_key=None, campaign_slug=None):
        items = self.list_concept_sessions(client_id, format_key, campaign_slug, limit=1)
        return items[0] if items else None

    def list_concept_sessions(self, client_id, format_key=None, campaign_slug=None, limit=12):
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            return []
        format_key = _concept_format_key(format_key) if format_key else None
        slug = str(campaign_slug or "").strip() or None
        try:
            cap = max(1, min(int(limit or 12), 24))
        except (TypeError, ValueError):
            cap = 12
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                      FROM cx_concept_sessions
                     WHERE client_id = %s
                       AND status <> 'handed_off'
                       AND (%s IS NULL OR format_key = %s)
                       AND (%s IS NULL OR campaign_slug IS NULL OR campaign_slug = %s)
                     ORDER BY updated_at DESC NULLS LAST, created_at DESC
                     LIMIT %s
                    """,
                    (client_id, format_key, format_key, slug, slug, cap),
                )
                rows = [item["id"] for item in cursor.fetchall()]
        except Exception:
            return []
        found = []
        for session_id in rows:
            if not session_id:
                continue
            try:
                item = self.get_concept_session(session_id)
            except Exception:
                continue
            if item:
                found.append(item)
        return found

    def record_concept_pass(
        self,
        session_id,
        pass_kind,
        position,
        status="done",
        job_id=None,
        model="openai/gpt-5.4",
        estimated_cost_usd=0,
        actual_cost_usd=None,
        metadata=None,
    ):
        session_id = str(session_id or "").strip()
        if not session_id:
            raise CreativeConflictError("Sessão de conceito sem id.")
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_concept_passes (
                    session_id, job_id, pass_kind, position, status, model,
                    estimated_cost_usd, actual_cost_usd, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session_id,
                    job_id,
                    _concept_pass_kind(pass_kind),
                    int(position or 1),
                    status if status in {"queued", "running", "done", "review", "failed"} else "done",
                    model or "openai/gpt-5.4",
                    estimated_cost_usd or 0,
                    actual_cost_usd,
                    Json(metadata or {}),
                ),
            )
            return cursor.fetchone()["id"]

    def _replace_concept_scenes(self, cursor, session_id, session):
        cursor.execute(
            "DELETE FROM cx_concept_scenes WHERE session_id = %s",
            (session_id,),
        )
        status_fallback = _concept_scene_status(session.get("status"), "draft")
        for index, item in enumerate(_concept_scene_items(session), start=1):
            position = int(item.get("position") or index)
            if position < 1 or position > 5:
                continue
            layers = [
                layer for layer in _json_list(item.get("layers"))
                if isinstance(layer, dict)
            ]
            cursor.execute(
                """
                INSERT INTO cx_concept_scenes (
                    session_id, scene_key, position, purpose, role, headline,
                    support, cta, tip, set_note, action_note, timecode,
                    duration_seconds, image_prompt, html, render_url, layers,
                    status
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    session_id,
                    _concept_scene_key(item.get("id") or item.get("scene_key"), position),
                    position,
                    item.get("purpose"),
                    item.get("role"),
                    item.get("headline"),
                    item.get("support"),
                    item.get("cta"),
                    item.get("tip"),
                    item.get("set_note"),
                    item.get("action_note"),
                    item.get("timecode"),
                    item.get("duration") or item.get("duration_seconds") or 3,
                    item.get("image_prompt"),
                    item.get("html"),
                    item.get("render_url"),
                    Json(layers),
                    _concept_scene_status(item.get("status"), status_fallback),
                ),
            )
            scene_id = cursor.fetchone()["id"]
            self._replace_concept_layers(cursor, scene_id, layers)

    def _replace_concept_layers(self, cursor, scene_id, layers):
        seen = set()
        for index, layer in enumerate(layers, start=1):
            key = str(layer.get("id") or layer.get("layer_key") or f"layer-{index}")
            if key in seen:
                continue
            seen.add(key)
            content = layer.get("content") if isinstance(layer.get("content"), dict) else {}
            cursor.execute(
                """
                INSERT INTO cx_concept_layers (
                    scene_id, layer_key, layer_type, x, y, w, h, z,
                    text_value, css_value
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    scene_id,
                    key[:80],
                    layer.get("tipo") or layer.get("layer_type") or layer.get("type"),
                    _optional_number(layer.get("x")),
                    _optional_number(layer.get("y")),
                    _optional_number(layer.get("w")),
                    _optional_number(layer.get("h")),
                    layer.get("z"),
                    layer.get("text") or content.get("text"),
                    layer.get("css") or layer.get("css_value"),
                ),
            )

    def _replace_concept_passes(self, cursor, session_id, session):
        cursor.execute(
            """
            SELECT job_id, pass_kind, position
              FROM cx_concept_passes
             WHERE session_id = %s
            """,
            (session_id,),
        )
        existing = {
            (row["pass_kind"], row["position"]): row["job_id"]
            for row in cursor.fetchall()
        }
        cursor.execute(
            "DELETE FROM cx_concept_passes WHERE session_id = %s",
            (session_id,),
        )
        items = [
            item for item in _json_list(session.get("passes"))
            if isinstance(item, dict)
        ]
        for index, item in enumerate(items, start=1):
            kind = _concept_pass_kind(item.get("id") or item.get("pass_kind"))
            position = int(item.get("position") or index)
            if position < 1 or position > 8:
                continue
            cursor.execute(
                """
                INSERT INTO cx_concept_passes (
                    session_id, job_id, pass_kind, position, status, model,
                    estimated_cost_usd, actual_cost_usd, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    item.get("job_id") or existing.get((kind, position)),
                    kind,
                    position,
                    item.get("status") or "done",
                    item.get("model") or "openai/gpt-5.4",
                    item.get("estimated_cost_usd") or 0,
                    item.get("actual_cost_usd"),
                    Json(_json_object(item.get("metadata"))),
                ),
            )

    def _replace_concept_references(self, cursor, session_id, session):
        cursor.execute(
            "DELETE FROM cx_concept_references WHERE session_id = %s",
            (session_id,),
        )
        for item in _concept_reference_items(session):
            cursor.execute(
                """
                INSERT INTO cx_concept_references (
                    session_id, role, asset_url, position
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    session_id,
                    item["role"],
                    item["asset_url"],
                    item["position"],
                ),
            )

    def create_plate_kit(self, data, created_by=None):
        payload = data if isinstance(data, dict) else {}
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_plate_kits (
                    client_id, name, product, copy, product_assets,
                    plates, bindings, passes, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, client_id, name, product, copy, product_assets,
                          plates, bindings, passes, created_by, created_at, updated_at
                """,
                (
                    payload.get("client_id"),
                    payload.get("name") or "IAB base",
                    payload.get("product") or "",
                    Json(payload.get("campaign") or payload.get("copy") or {}),
                    Json(payload.get("product_assets") or {}),
                    Json(payload.get("plates") or []),
                    Json(payload.get("bindings") or {}),
                    Json(payload.get("passes") or []),
                    created_by or payload.get("created_by"),
                ),
            )
            return dict(cursor.fetchone())

    def list_plate_kits(self, client_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, client_id, name, product, copy, created_at, updated_at,
                       jsonb_array_length(COALESCE(passes, '[]'::jsonb)) AS pass_count
                  FROM cx_plate_kits
                 WHERE client_id = %s
                 ORDER BY created_at DESC, id DESC
                """,
                (client_id,),
            )
            rows = []
            for row in cursor.fetchall():
                item = dict(row)
                copy = item.get("copy") if isinstance(item.get("copy"), dict) else {}
                item["headline"] = copy.get("headline") or ""
                item["pass_count"] = int(item.get("pass_count") or 0)
                rows.append(item)
            return rows

    def get_plate_kit(self, kit_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, client_id, name, product, copy, product_assets,
                       plates, bindings, passes, created_by, created_at, updated_at
                  FROM cx_plate_kits
                 WHERE id = %s
                """,
                (kit_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Geração de placas não encontrada.")
        return self._plate_kit_row(row)

    def update_plate_kit(self, kit_id, data):
        payload = data if isinstance(data, dict) else {}
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_plate_kits
                   SET name = COALESCE(%s, name),
                       product = COALESCE(%s, product),
                       copy = COALESCE(%s, copy),
                       product_assets = COALESCE(%s, product_assets),
                       plates = COALESCE(%s, plates),
                       bindings = COALESCE(%s, bindings),
                       passes = COALESCE(%s, passes),
                       updated_at = NOW()
                 WHERE id = %s
                RETURNING id, client_id, name, product, copy, product_assets,
                          plates, bindings, passes, created_by, created_at, updated_at
                """,
                (
                    payload.get("name"),
                    payload.get("product"),
                    Json(payload["campaign"]) if "campaign" in payload or "copy" in payload else None,
                    Json(payload["product_assets"]) if "product_assets" in payload else None,
                    Json(payload["plates"]) if "plates" in payload else None,
                    Json(payload["bindings"]) if "bindings" in payload else None,
                    Json(payload["passes"]) if "passes" in payload else None,
                    kit_id,
                ),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Geração de placas não encontrada.")
        return self._plate_kit_row(row)

    def _plate_kit_row(self, row):
        item = dict(row)
        item["campaign"] = item.get("copy") if isinstance(item.get("copy"), dict) else {}
        item["pass_count"] = len(item.get("passes") or [])
        bindings = item.get("bindings") if isinstance(item.get("bindings"), dict) else {}
        for plate in item.get("plates") or []:
            if not isinstance(plate, dict):
                continue
            selected = bindings.get(plate.get("key"))
            if isinstance(selected, list):
                plate["selected_channels"] = selected
                plate["checked"] = bool(selected)
        return item
